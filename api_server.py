# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Classes that implement the API & UI httpd
#

import sensorino

import json
import socket
import medusaserver
import asynchat
import SimpleHTTPServer
import urllib
import posixpath
import cgi
import collections
import os
import time
import sys

class sensorino_httpd_request_handler(medusaserver.RequestHandler):
	protocol_version = 'HTTP/1.1' # Enable keep-alive
	server_version = 'SensorinoServer/0.1'

	SimpleHTTPServer.SimpleHTTPRequestHandler.extensions_map['.xhtml'] = \
		'application/xhtml+xml'

	def __init__(self, conn, addr, server):
		medusaserver.RequestHandler.__init__(self, conn, addr, server)
		self.subscribed_to_changes = 0
		self.subscribed_to_console = 0
		self.server.conns.append(self)

	def done(self):
		self.server.conns.remove(self)

		if self.subscribed_to_changes:
			self.server.state.unsubscribe_changes(
					self.handle_sensorino_state_change)
			self.subscribed_to_changes = 0

		if self.subscribed_to_console:
			self.server.console.unsubscribe_lines(
					self.handle_sensorino_console_line)
			self.subscribed_to_console = 0

	def handle_close(self):
		self.done()

		asynchat.async_chat.handle_close(self)

	def handle_error(self):
		t, v = sys.exc_info()[:2]
		sensorino.log_err(str(self.client_address) +
				': Dropping client: ' + str(t) + ': ' +
				str(v))
		self.done()

		try:
			self.close()
		except:
			pass

	def check_params(self, params):
		unknown = []
		for param in self.params:
			if param not in params:
				unknown.append(param)

		if unknown:
			raise Exception(400, 'Unknown parameters: ' +
					', '.join(unknown))

	def check_method(self, methods):
		if self.command not in methods:
			raise Exception(405, 'Method not allowed')

	def check_ctype(self, ctypes):
		# For non-POST need to use this:
        	#ctype, pdict = cgi.parse_header(
		#		self.headers.getheader('content-type'))
		ctype = self.body.type
		if ctype not in ctypes:
			raise Exception(415, 'Unsupported content type')

	time_params = [ 'at', 'ago' ]

	def parse_time_params(self, at='at', ago='ago'):
		if at in self.params and ago in self.params:
			raise Exception(400, 'Either ' + at + '= or ' + ago +
					'= parameter may be given but ' +
					'not both.')

		try:
			if at in self.params:
				t = float(self.params[at])
				int(t * 1000.0) # Raise exception if NaN, etc.
				return t

			if ago in self.params:
				t = time.time() - float(self.params[ago])
				int(t * 1000.0) # Raise exception if NaN, etc.
				return t

			return None
		except:
			raise Exception(400, e.args[0])

	def post_get_json(self, limit):
		self.check_ctype([ 'application/json' ])

		if self.body.length > limit:
			raise Exception(413, 'JSON data too long')

		self.body.file.seek(0)
		return self.body.file.read(limit).decode('utf-8')

	def send_stream_chunk(self, chunk):
		chunk = chunk.encode('utf-8')
		self.wfile.write(hex(len(chunk))[2:] + '\r\n' + chunk + '\r\n')

	def stream_chromium_workaround(self):
		ua = self.headers.getheader('user-agent', None)
		if ua is None or 'WebKit' not in ua:
			return

		# Chrome/chromium workaround - nothing else seems to work
		# http://code.google.com/p/chromium/issues/detail?id=2016
		self.send_stream_chunk('\n' * 32768)

	def handle_sensorino_state_change(self, change_set, error=False):
		# Find out the minimum set of changes covering events
		# in all the set.  Go through the list of events from
		# shortest (most general) to longest, only add the event
		# to the list if none of its prefixes is there yet.
		sorted_changes = sorted(change_set,
				cmp = lambda x, y: len(x) - len(y))
		prefixes = []
		for chg in sorted_changes:
			found = 0
			for i in xrange(1, len(chg)):
				if chg[:i] in prefixes:
					found = 1
					break
			if not found:
				prefixes.append(chg)

		def check_idx(idx, obj):
			if isinstance(obj, collections.Mapping):
				return idx in obj
			if isinstance(obj, collections.Sequence):
				return isinstance(idx, int) and idx >= 0 and \
					idx < len(obj)
			return False

		chg_data = []
		if error:
			chg_data.append('error')

		state = self.server.state.get_state_tree()
		for pre in prefixes:
			obj = state
			path = []
			for id in pre:
				path.append(id)
				if check_idx(id, obj):
					obj = obj[id]
				else:
					obj = None
					break
			chg_data.append(( path, obj ))

		content = json.dumps(chg_data) + ','
		try:
			self.send_stream_chunk(content)
		except:
			self.handle_error()

	def handle_sensorino_console_line(self, line):
		json_str = json.dumps(line)

		content = json_str + ','
		try:
			self.send_stream_chunk(content)
		except:
			self.handle_error()

	def handle_api_sensorino(self):
		self.check_params(self.time_params)
		self.check_method([ 'GET' ])

		timestamp = self.parse_time_params()

		if timestamp is None:
			ret = self.server.state.get_state_tree()
		else:
			ret = self.server.state. \
				get_state_at_timestamp(timestamp)

		content = json.dumps(ret).encode('utf-8')

		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(content)))
		self.end_headers()

		self.wfile.write(content)

	def handle_api_sensorino_stream(self):
		self.check_params([])
		self.check_method([ 'GET' ])

		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Transfer-Encoding", "chunked")
		self.end_headers()

		# Send the initial state as the first chunk of the stream.
		# All further chunks only contain changes, not the entire
		# state.  For the whole thing to look like a valid JSON
		# objects, we start an array first ("[")
		content = '[' + \
			json.dumps(self.server.state.get_state_tree()) + ','
		self.send_stream_chunk(content)

		self.server.state.subscribe_changes(
				self.handle_sensorino_state_change)
		self.subscribed_to_changes = 1
		self.streaming = 1

		self.stream_chromium_workaround()

	def handle_api_console(self):
		self.check_method([ 'GET', 'POST' ])

		if self.command == 'GET':
			self.check_params(self.time_params)
			timestamp = self.parse_time_params()

			if timestamp is None:
				ret = self.server.console.get_recent_lines()
			else:
				ret = self.server.console. \
					get_lines_at_timestamp(timestamp)

			content = json.dumps(ret).encode('utf-8')

			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(content)))
			self.end_headers()

			self.wfile.write(content)

			return

		if self.command == 'POST':
			self.check_params([])

			line = self.post_get_json(256)
			try:
				self.server.handle_user_req(line, self)
				self.send_response(200)
				self.send_header("Content-Type",
						"application/json")
				self.send_header("Content-Length", '2')
				self.end_headers()

				self.wfile.write('{}')

				return
			except Exception as e:
				if len(e.args) == 2:
					raise
				raise Exception(500, e.args[0])

	def handle_api_console_stream(self):
		self.check_params([])
		self.check_method([ 'GET' ])

		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Transfer-Encoding", "chunked")
		self.end_headers()

		# Send the last few lines of console log as the inital
		# chunk of the stream.  Further chunks only contain
		# new lines in the log.  For the whole thing to look like
		# a valid JSON objects, we start an array first ("[")
		content = '[' + \
			''.join([ json.dumps(line) + ',' for line in
				self.server.console.get_recent_lines() ])
		self.send_stream_chunk(content)

		self.server.console.subscribe_lines(
				self.handle_sensorino_console_line)
		self.subscribed_to_console = 1
		self.streaming = 1

		self.stream_chromium_workaround()

	def handle_api_floorplan(self):
		self.check_method([ 'GET', 'POST' ])

		if self.command == 'GET':
			self.check_params(self.time_params)
			timestamp = self.parse_time_params()

			if timestamp is None:
				ret = self.server.floorplan
			else:
				ret = self.server.storage. \
					get_floorplan_at_timestamp(timestamp)
				if ret is None:
					ret = []

			content = json.dumps(ret).encode('utf-8')

			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(content)))
			self.end_headers()

			self.wfile.write(content)

			return

		if self.command == 'POST':
			self.check_params([])

			content = self.post_get_json(128 * 1024)
			obj = None
			timestamp = time.time()

			# Try to ensure nothing is saved when either
			# parsing or the database return an error
			try:
				obj = json.loads(content)
			except Exception as e:
				raise Exception(400, 'Bad JSON: ' + e.args[0])
			try:
				self.server.storage.save_floorplan_version(
						timestamp, content)
				self.server.storage.commit()
				self.server.floorplan = obj
			except Exception as e:
				raise Exception(400, 'DB error: ' + e.args[0])

			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", '2')
			self.end_headers()

			self.wfile.write('{}')

			return

	def handle_api_value(self, path):
		self.check_method([ 'GET' ]) # TODO: POST

		self.check_params([ 'at', 'ago', 'at0', 'ago0', 'at1', 'ago1' ])
		timestamp = self.parse_time_params()
		timestamp0 = self.parse_time_params('at0', 'ago0')
		timestamp1 = self.parse_time_params('at1', 'ago1')

		try:
			node_addr, svc_id, typ, chan_id = path
			svc_id = int(svc_id)
			chan_id = int(chan_id)
			if typ in sensorino.known_datatypes_dict:
				typ = sensorino.datatype_to_name(typ)
		except:
			raise Exception(404, 'Bad channel address')
		try:
			node_addr = int(node_addr)
		except:
			pass

		if timestamp is None and timestamp0 is None:
			tree = self.server.state.get_state_tree()
			try:
				ret = tree[node_addr][svc_id][typ][chan_id]
			except:
				raise Exception(404, 'No such channel')
		elif timestamp is not None:
			path = [ node_addr, svc_id, typ, chan_id ]
			ret = self.server.storage.get_value_at_timestamp( \
					path, timestamp)
			if ret is None:
				raise Exception(404, 'No such channel')
		else:
			path = [ node_addr, svc_id, typ, chan_id ]
			if timestamp1 is None:
				timestamp1 = time.time()

			# First load the value at the start of the period
			val0 = self.server.storage.get_value_at_timestamp( \
					path, timestamp0)
			vals = self.server.storage.get_values_within_period( \
					path, timestamp0, timestamp1)
			if val0 is None and not vals:
				raise Exception(404, 'No such channel')

			ret = [ val0 ] + vals

		content = json.dumps(ret).encode('utf-8')

		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(content)))
		self.end_headers()

		self.wfile.write(content)

		return

	def handle_data(self):
		# Translate path
		path = self.path.split('#', 1)[0]
		elems = path.split('?', 1)
		path = elems[0]
		path = posixpath.normpath(urllib.unquote(path))

		self.params = {}
		if len(elems) == 2:
			for var in elems[1].split('&'):
				kv = var.split('=', 1)
				if len(kv) == 1:
					kv.append('')
				self.params[kv[0]] = urllib.unquote(kv[1])

		try:
			# TODO: use bottle/flask-like routing

			# TODO: also add a combined stream of all events.

			splitpath = path[1:].split('/')
			if path == '/api/sensorino.json':
				self.handle_api_sensorino()
			elif path == '/api/stream/sensorino.json':
				self.handle_api_sensorino_stream()
			elif path == '/api/console.json':
				self.handle_api_console()
			elif path == '/api/stream/console.json':
				self.handle_api_console_stream()
			elif path == '/api/floorplan.json':
				self.handle_api_floorplan()
			elif len(splitpath) == 6 and splitpath[0] == 'api' and \
					splitpath[5] == 'value.json':
				self.handle_api_value(splitpath[1:5])
			else:
				medusaserver.RequestHandler.handle_data(self)
		except Exception as e:
			if len(e.args) == 2:
				self.send_error(*e.args)
			else:
				raise

class sensorino_httpd_server(medusaserver.Server):
	def __init__(self, addr, sensorino_state, sensorino_console, storage):
		medusaserver.Server.__init__(self, addr[0], addr[1], \
				sensorino_httpd_request_handler)
		self.state = sensorino_state
		self.console = sensorino_console
		self.storage = storage

		self.floorplan = []

		self.conns = []

		self.user_req_handlers = []

		self.static_root = os.getcwd() + '/static'

	def subscribe_user_reqs(self, handler):
		self.user_req_handlers.append(handler)

	def unsubscribe_user_reqs(self, handler):
		self.user_req_handlers.remove(handler)

	def handle_user_req(self, raw_req, conn):
		for handler in self.user_req_handlers:
			handler(raw_req, conn)

	def load_floorplan(self):
		latest = self.storage.get_floorplan_current()
		if latest is None:
			self.floorplan = []
		else:
			self.floorplan = json.loads(latest)
