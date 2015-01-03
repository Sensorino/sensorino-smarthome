#! /usr/bin/python
#
# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Sensorino server -- talks to and manages the Sensorino nodes, keeps
# a database of current state and all historical states, provides
# users a command & control UI over httpd.  All communication with
# the Sensorino nodes happens through a Base, which connects to us
# through a socket.  We accept connections from Base(s) on one port,
# and server the UI over httpd on another port.
#

import sensorino
import config
import base_server
import api_server
import discovery
import db

import json
import socket
import time

# For now use asyncore.  It has its downsides, but overall it works,
# user code is not overly ugly, doesn't force us to reimplement httpd
# from scratch, and creates no dependencies.
# Some other python web serving possibilities that look decent, and
# may be explored if asyncore starts being a blocker:
#
# * twisted
#   ("Deferreds" don't look as nice as "dispatchers", but twisted has
#    full-featured web support.  Would be quite a big dependency though,
#    may be unsuitable for runnning on tiny routers?)
# * cogen
#   (comes quite far behind twisted in benchmarks, and doesn't come
#    with any of the web/HTTP niceties included)
# * bluelets
#   (same as cogen, but nicely small and contained)
#
import asyncore

class console_log():
	# Keep this many lines of most recent log data to be present
	# in memory and served without querying the database.
	n = 30

	def __init__(self, storage):
		self.storage = storage

		self.last_n = []

		self.line_handlers = []

	def subscribe_lines(self, handler):
		self.line_handlers.append(handler)

	def unsubscribe_lines(self, handler):
		self.line_handlers.remove(handler)

	def handle_line(self, incoming, valid, line, timestamp):
		prefix = '>>>'
		if incoming:
			prefix = '<<<'

		# Lines that couldn't be understood by the state tracker
		# have a >>! or <<! prefix so that they can be clearly
		# identified.  Invalid messages submitted by the user are
		# passed to the Base nevertheless, but the user will see
		# there's something wrong with them even if there's no
		# error returned by the node, perhaps highlighed in red.
		if not valid:
			prefix = prefix[:2] + '!'

		line = ( timestamp, prefix + ' ' + line.strip() )

		# Append to the log and trim to n lines if longer
		self.last_n.append(line)
		self.last_n = self.last_n[-self.n:]

		# Save to persistent storage
		self.storage.save_console_line(*line)
		self.storage.commit()

		# Notify our subscribers
		for handler in self.line_handlers:
			handler(line)

	def load(self):
		self.last_n = self.storage.get_console_current()[-self.n:]

	def get_recent_lines(self):
		return self.last_n

	def get_lines_at_timestamp(self, timestamp):
		return self.storage.get_console_at_timestamp(timestamp)

def base_message_handler(raw_msg, base):
	global state, console

	timestamp = time.time()

	# We received a new message from a Sensorino node, try parsing it
	# as far as possible.  If there's any error, still submit it to
	# our state keeping object as an invalid message, and to the
	# console log object.

	try:
		msg = sensorino.message_dict(json.loads(raw_msg))

		# Basic validation
		if 'type' not in msg and 'error' not in msg:
			raise Exception('No type')
		type = msg.get('type', 'err')

		if type not in [ 'publish', 'request', 'set', 'err' ]:
			raise Exception('Unknown type')

		if type == 'publish':
			sensorino.validate_incoming_publish(msg)
			state.validate_incoming_publish(msg)
		elif type == 'request':
			sensorino.validate_incoming_request(msg)
		elif type == 'set':
			sensorino.validate_incoming_set(msg)
			state.validate_incoming_set(msg)
		else:
			sensorino.validate_incoming_error(msg)

		valid = True
	except Exception as e:
		sensorino.log_warn(str(e.args))

		valid = False

	console.handle_line(True, valid, raw_msg, timestamp)

	try:
		if valid:
			type = msg.get('type', 'err')

			if type == 'publish':
				state.handle_publish(timestamp, msg)
			elif type == 'request':
				state.handle_request(timestamp, msg)
			elif type == 'set':
				state.handle_set(timestamp, msg)
			else:
				state.handle_error(timestamp, msg)
		else:
			# If it parses, submit it to the state handler anyway
			msg = sensorino.message_dict(json.loads(raw_msg))
			state.handle_invalid_incoming(timestamp, msg)
	except Exception as e:
		if valid:
			sensorino.log_warn(str(e.args))

def httpd_request_handler(raw_req, conn):
	global state, base_server, console

	timestamp = time.time()

	if len(base_server.bases) == 0:
		# We have no Bases connected right now.
		# Send an error directly to the UI, don't log anything
		# anywhere as there is basically no message sent.
		raise Exception(503, 'No Base connected')

	try:
		msg = sensorino.message_dict(json.loads(raw_req))
	except Exception as e:
		# For simplicity we don't allow sending non-JSON junk
		# to the Base through the web UI.  Don't store such
		# messages anywhere, just send back an error message
		# right away.
		raise Exception(400, 'Bad JSON: ' + str(e.args))

	# The UI has made a request to the sensor network on behalf of
	# the user, validate it and try to make the state keeping object
	# consume it as far as possible, then send to the base even
	# if invalid.
	try:
		# Basic validation
		if 'type' not in msg:
			raise Exception('No type')
		type = msg['type']

		if type not in [ 'request', 'set' ]:
			raise Exception('Unknown type')

		if type == 'set':
			sensorino.validate_outgoing_set(msg)
			state.validate_outgoing_set(msg)
			state.handle_set(timestamp, msg)
		else:
			sensorino.validate_outgoing_request(msg)
			state.handle_request(timestamp, msg)

		valid = True
	except Exception as e:
		sensorino.log_warn(str(e.args))

		# If it parses, submit it to the state handler anyway
		state.handle_invalid_outgoing(timestamp, msg)

		valid = False

	# For now we send all the outgoing request through the first
	# base that is registered with us.  In the future we either want
	# to track which sensorino is talking to us through which base
	# and send through the relevant base, or allow only one base per
	# "Smarthome" object, and make the different "Smarthomes"
	# different entities inside the UI, so that we know exactly which
	# base we're talking to.
	base_server.bases[0].send_json(raw_req)

	console.handle_line(False, valid, raw_req, timestamp)

def discovery_request_handler(req):
	global state, base_server, console

	timestamp = time.time()

	if len(base_server.bases) == 0:
		# Bad luck -- the base must have *just* disconnected

		# TODO: possibly store the query somewhere and re-emit
		# as soon as a new base is connected.  Or just call
		# something like discovery_agent.run().

		return

	# Be extra careful: validate the message generated by the agent.
	# If valid, send to the state keeping object for tracking.
	try:
		sensorino.validate_outgoing_request(req)
		state.handle_request(timestamp, req)

		valid = True
	except Exception as e:
		sensorino.log_warn(str(e.args))

		state.handle_invalid_outgoing(timestamp, req)

		valid = False

	req_str = json.dumps(req)

	# For now we send all the outgoing request through the first
	# base that is registered with us.  In the future we either want
	# to track which sensorino is talking to us through which base
	# and send through the relevant base, or allow only one base per
	# "Smarthome" object, and make the different "Smarthomes"
	# different entities inside the UI, so that we know exactly which
	# base we're talking to.
	base_server.bases[0].send_json(req_str)

	console.handle_line(False, valid, req_str, timestamp)

# Create and introduce all the helpers to each other
db = db.connection()
state = sensorino.sensorino_state(db)
console = console_log(db)
discovery_agent = discovery.agent(state)

httpd = api_server.sensorino_httpd_server(config.httpd_address,
		state, console, db)
base_server = base_server.sensorino_base_server(config.base_server_address)

state.load()
console.load()
httpd.load_floorplan()
print("State loaded from the database")

base_server.subscribe_objs(base_message_handler)
httpd.subscribe_user_reqs(httpd_request_handler)
discovery_agent.subscribe_reqs(discovery_request_handler)

httpd_sn = httpd.socket.getsockname()
base_sn = base_server.socket.getsockname()
print("Serving HTTP on " + httpd_sn[0] + " port " + str(httpd_sn[1]) +
		" and Base server on " + base_sn[0] + " port " +
		str(base_sn[1]) + "...")
try:
	# TODO: timer support for sensorino error queue timeouts
	asyncore.loop()
except KeyboardInterrupt:
	pass
db.close()
