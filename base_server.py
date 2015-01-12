# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Classes that manage communication with Base nodes.
#

import sensorino
import sys
import socket
import asyncore
import json

class obj_parser():
	def __init__(self):
		self.obj_buffer = ''
		self.nest_depth = 0
		self.quote = 0
		self.escape = 0

	def handle_char(self, ch):
		self.obj_buffer += ch

		if self.quote and not self.escape and ch == '\\':
			self.escape = 1
		elif not self.escape and ch == '"':
			self.quote = not self.quote
		elif not self.quote:
			if ch in '{[(':
				self.nest_depth += 1
			elif ch in '}])':
				self.nest_depth -= 1

				if self.nest_depth <= 0:
					# End of a JSON object

					# Don't try to parse the object here..
					# For now submit it to all handlers
					# regardless of what Base we are, i.e.
					# messages from all the Bases will
					# reach the server all mixed-up.
					ret = self.obj_buffer

					self.obj_buffer = ''
					self.nest_depth = 0

					return ret
		return None

class sensorino_base_handler(asyncore.dispatcher_with_send):
	def __init__(self, sock, addr, server):
		asyncore.dispatcher_with_send.__init__(self, sock)

		self.client_address = addr
		self.server = server
		self.name = None

		self.parser = obj_parser()

	def handshake(self, obj):
		try:
			hs = json.loads(obj)
			self.name = hs['base-name']

			if self.name in self.server.bases:
				raise Exception('Base "' + self.name +
						'" already exists')
		except Exception as e:
			sensorino.log_warn(str(e.args))
			self.close()
			return

		self.server.bases[self.name] = self

		sensorino.log_warn('New Base connected')

	def handle_close(self):
		asyncore.dispatcher.handle_close(self)

		del self.server.bases[self.name]

		sensorino.log_warn('Base disconnected')

	def handle_read(self):
		for chr in self.recv(8192).decode('utf-8'):
			obj = self.parser.handle_char(chr)
			if obj is not None:
				if self.name is None:
					# This is the handshake message
					self.handshake(obj)
					continue

				self.server.handle_obj(obj, self)

	def send_json(self, buffer):
		self.send(buffer.encode('utf-8'))

class sensorino_base_server(asyncore.dispatcher):
	# All boilerplate here
	def __init__(self, addr):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind(addr)
		self.listen(5)

		self.bases = {}
		self.obj_handlers = []

	def handle_accept(self):
		pair = self.accept()
		if pair is None:
			return
		sock, addr = pair
		handler = sensorino_base_handler(sock, addr, self)

	def subscribe_objs(self, handler):
		self.obj_handlers.append(handler)

	def unsubscribe_objs(self, handler):
		self.obj_handlers.remove(handler)

	def handle_obj(self, obj, base):
		for handler in self.obj_handlers:
			handler(obj, base)
