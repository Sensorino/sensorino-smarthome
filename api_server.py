# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Classes that implement the API & UI httpd
#

import json
import socket
import medusaserver
import asynchat
import SimpleHTTPServer
import urllib
import posixpath
import cgi

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

	def handle_close(self):
		asynchat.async_chat.handle_close(self)

		self.server.conns.remove(self)

		if self.subscribed_to_changes:
			self.server.state.unsubscribe_changes(
					self.handle_sensorino_state_change)
			self.subscribed_to_changes = 0

		if self.subscribed_to_console:
			self.server.console.unsubscribe_lines(
					self.handle_sensorino_console_line)
			self.subscribed_to_console = 0

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

	def post_get_json(self, limit):
		self.check_ctype([ 'application/json' ])

		if self.body.length > limit:
			raise Exception(413, 'JSON data too long')

		self.body.file.seek(0)
		return self.body.file.read(limit).decode('utf-8')

	def send_stream_chunk(self, chunk):
		chunk = chunk.encode('utf-8')
		self.wfile.write(hex(len(chunk))[2:] + '\r\n' + chunk + '\r\n')

	def handle_sensorino_state_change(self, change_set):
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

		chg_data = []
		state = self.server.state.get_state_tree()
		for pre in prefixes:
			obj = state
			path = []
			for id in pre:
				path.append(id)
				if id in obj:
					obj = obj[id]
				else:
					obj = None
					break
			chg_data.append(( path, obj ))

		content = json.dumps(chg_data) + ','
		self.send_stream_chunk(content)

	def handle_sensorino_console_line(self, line):
		json_str = json.dumps(line)

		content = json_str + ','
		self.send_stream_chunk(content)

	def handle_api_sensorino(self):
		self.check_params([])
		self.check_method([ 'GET' ])

		# TODO: in the future will need to handle a few params
		# to provide historical states.

		content = json.dumps(self.server.state.get_state_tree()). \
			encode('utf-8')

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

	def handle_api_console(self):
		self.check_params([])
		self.check_method([ 'GET', 'POST' ])

		# TODO: in the future will need to handle a GET with a few
		# params to provide historical states.

		if self.command == 'GET':
			content = json.dumps(
				self.server.console.get_recent_lines()). \
				encode('utf-8')

			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(content)))
			self.end_headers()

			self.wfile.write(content)

			return

		if self.command == 'POST':
			line = self.post_get_json(256)
			try:
				self.server.handle_user_req(line, self)
				self.send_response(200)
				self.send_header("Content-Length", '0')
				self.end_headers()

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
			','.join([ json.dumps(line) for line in
				self.server.console.get_recent_lines() ]) + ','
		self.send_stream_chunk(content)

		self.server.console.subscribe_lines(
				self.handle_sensorino_console_line)
		self.subscribed_to_console = 1
		self.streaming = 1

	def handle_api_floorplan(self):
		self.check_params([])
		self.check_method([ 'GET', 'POST' ])

		# TODO: in the future will need to handle a GET with a few
		# params to provide historical states.

		if self.command == 'GET':
			content = json.dumps(self.server.floorplan). \
				encode('utf-8')

			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(content)))
			self.end_headers()

			self.wfile.write(content)

			return

		if self.command == 'POST':
			content = self.post_get_json(128 * 1024)
			try:
				self.server.floorplan = json.loads(content)
			except Exception as e:
				raise Exception(400, 'Bad JSON: ' + e.args[0])

			self.send_response(200)
			self.send_header("Content-Length", '0')
			self.end_headers()

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
			else:
				medusaserver.RequestHandler.handle_data(self)
		except Exception as e:
			if len(e.args) == 2:
				self.send_error(*e.args)
			else:
				raise

class sensorino_httpd_server(medusaserver.Server):
	def __init__(self, addr, sensorino_state, sensorino_console):
		medusaserver.Server.__init__(self, addr[0], addr[1], \
				sensorino_httpd_request_handler)
		self.state = sensorino_state
		self.console = sensorino_console
		# TODO: use a floorplan_store object
		self.floorplan = []

		self.conns = []

		self.user_req_handlers = []

	def subscribe_user_reqs(self, handler):
		self.user_req_handlers.append(handler)

	def unsubscribe_user_reqs(self, handler):
		self.user_req_handlers.remove(handler)

	def handle_user_req(self, raw_req, conn):
		for handler in self.user_req_handlers:
			handler(raw_req, conn)
