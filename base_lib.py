# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Utilities to facilities writing new Base scripts.  When a user wants
# to connect smart devices to the Sensorino server, which talk an as yet
# unsupported protocol or Radio Access Technology, they will need to
# create a gateway or adapter script that interfaces their radio stack
# to the Sensorino server.  For that they can use the python API provided
# by this library instead of having to translate each message between the
# Sensorino native format and that of the target technology.

import socket
import select
import json
import collections

import config
import base_server
import sensorino

svc_manager_id = 0

class base_node(object):
	def __init__(self, addr):
		self.addr = addr
		self.services = {}
		self.name = None
		self.add_service(base_service_manager(self))

	def get_addr(self):
		return self.addr

	def set_name(self, name):
		self.name = name

		# TODO: if comms initialised,
		# send a message with svc_id == _name to server?

	def create_service(self, *args):
		svc = base_service(*args)

		self.add_service(svc)

		return svc

	def add_service(self, svc):
		self.services[svc.get_id()] = svc
		svc.nodes.append(self)

		# TODO: if comms initialised,
		# send a "discovery" message from the node's Service Manager?

	def send_message(self, partialmsg):
		global base_addr
		msg = { 'from': self.get_addr(), 'to': base_addr }
		msg.update(partialmsg)
		# At some point we may want to append to a queue instead
		base_send_obj(msg)

class base_service(object):
	def __init__(self, svc_id):
		if not isinstance(svc_id, int):
			raise Exception('ServiceId must be an int, sorry')
		self.svc_id = svc_id
		self.channels = {}
		self.name = None
		self.nodes = []

	def get_id(self):
		return self.svc_id

	def set_name(self, name):
		self.name = name

		# TODO: if comms initialised,
		# send a message with datatype == _name to server?

	def create_channel(self, *args):
		chan = base_channel(*args)

		self.add_channel(chan)

		return chan

	def add_channel(self, channel):
		if channel.get_type() not in self.channels:
			self.channels[channel.get_type()] = ( [], [] )

		idx = 0
		if channel.is_actuator():
			idx = 1
		self.channels[channel.get_type()][idx].append(channel)
		channel.services.append(self)

	def get_chan_values(self, types):
		ret = {}
		for type in types:
			ret[type] = [ \
				chan.get_value() for chan in \
				self.channels[type][0] + \
				self.channels[type][1] \
			]
		return ret

	def get_values(self, types):
		chan_types = [ type for type in types if type != 'dataType' ]
		ret = self.get_chan_values(chan_types)

		if 'dataType' in types:
			publish_types = []
			accept_types = []
			for type in self.channels:
				p_chans, a_chans = self.channels[type]
				publish_types += [ type for ch in p_chans ]
				accept_types += [ type for ch in a_chans ]
			ret['dataType'] = publish_types + accept_types
			ret['count'] = [ len(publish_types) ]
			if len(accept_types):
				ret['count'].append(len(accept_types))

		return ret

	def set_values(self, value_map):
		# Or should we use a channel object to value map?
		for type, num in value_map:
			val = value_map[( type, num )]
			chans = self.channels[type]
			# Might want to check if new != old here.
			(chans[0] + chans[1])[num].set_value(val)

	def publish_values(self, value_map):
		self.set_values(value_map)

		msg = {
			'type': 'publish',
			'serviceId': self.get_id(),
		}
		for type, num in value_map:
			chans = self.channels[type]
			if type not in msg:
				msg[type] = []
			while len(msg[type]) <= num:
				msg[type].append((chans[0] + chans[1]) \
						[len(msg[type])].get_value())
		for node in self.nodes:
			node.send_message(msg)

class base_channel(object):
	def __init__(self, type, writable, init_val=None):
		type = sensorino.datatype_to_name(type)
		self.type = type
		self.writable = writable
		self.name = None
		self.value = init_val
		self.services = []

	def get_type(self):
		return self.type

	def is_actuator(self):
		return self.writable

	def set_name(self, name):
		self.name = name

		# TODO: if comms initialised,
		# send a message with datatype == _chan_names to server?

	def set_value(self, new_value):
		# This method should not be called directly by client code,
		# .publish_value() or the service's publish_values() should
		# be used instead, they will do the same thing plus they'll
		# notify the server of the new value.  If the channel is
		# writable (actuator), it is generally assumed to not change
		# its value spontaneously, only on server's request.
		#
		# Overload this function to add a new value handler for a
		# single channel, or overload the service's set_values method
		# to handle all the new values at once.

		self.value = new_value

	def publish_value(self, new_value):
		for svc in self.services:
			chans = svc.channels[self.type]
			chan_num = (chans[0] + chans[1]).index(self)

			svc.publish_values({
					( self.type, chan_num ): new_value
				})

	def get_value(self):
		return self.value

class base_service_manager(base_service):
	def __init__(self, node):
		super(base_service_manager, self).__init__(svc_manager_id)
		self.create_channel('serviceId', False)
		self.node = node

	def get_chan_values(self, types):
		svcs = self.node.services.keys()
		svcs.remove(self.get_id())
		return { 'serviceId': svcs }

def base_create_node(*args):
	node = base_node(*args)

	base_add_node(node)

	return node

# All simulated nodes
nodes = {}

def base_add_node(node):
	global nodes
	nodes[node.get_addr()] = node

base_addr = 0

def base_send_obj(obj):
	global s
	for field in obj:
		if isinstance(obj[field], basestring) or not \
				isinstance(obj[field], collections.Sequence):
			continue
		if len(obj[field]) == 1:
			obj[field] = obj[field][0]
	s.send(json.dumps(obj).encode('utf8'))

def base_handle_set(node, svc, msg):
	channels = {}
	for prop in msg:
		type = prop.lower()
		if type in sensorino.known_datatypes_dict:
			type = sensorino.datatype_to_name(prop)

		vallist = sensorino.valuelist_from_msg(msg, type)
		svc_channels = []
		if type in svc.channels:
			svc_channels = svc.channels[type][1]

		# TODO: 'count'-typed properties in a SET may be used as an
		# argument to the write operation if accompanied by other
		# properties.  Not an error.

		# Note: on a Sensorino node unrecognized or excess values in
		# a SET message will normally not generate any error and will
		# simply be ignored.

		if len(vallist) > len(svc_channels):
			base_send_obj({
					'from': node.get_addr(),
					'to': base_addr,
					'type': 'err',
					'serviceId': svc.get_id(),
					'dataType': prop,
				})
			return

		offset = len(svc.channels[type][0])
		for chan_num, val in enumerate(vallist):
			channels[( type, chan_num + offset )] = val

	# Special case: if a SET message contains no values and is
	# addressed at a service with one actuator channel of a boolean type,
	# flip that channel's value.
	if not len(channels) and 'switch' in svc.channels and \
			len(svc.channels['switch'][1]):
		offset = len(svc.channels['switch'][0])
		channels[( 'switch', 0 + offset )] = \
			not svc.channels['switch'][1][0].get_value()
	elif not len(channels):
		base_send_obj({
				'from': node.get_addr(),
				'to': base_addr,
				'type': 'err',
				'serviceId': svc.get_id(),
			})
		return

	svc.set_values(channels)

def base_handle_request(node, svc, msg):
	if 'dataType' in msg:
		channels = sensorino.valuelist_from_msg(msg, 'dataType')
		del msg['dataType']
	else:
		channels = svc.channels.keys()

	if len(msg):
		# TODO: 'count'-typed properties in a SET may be used as an
		# argument to the read operation if accompanied by other
		# properties.  Not an error.

		# Note: on a Sensorino node unrecognized or excess values in
		# a REQUEST message will normally not generate any error and
		# will simply be ignored.

		base_send_obj({
				'from': node.get_addr(),
				'to': base_addr,
				'type': 'err',
				'serviceId': svc.get_id(),
				'dataType': msg.keys()[0],
				})
		return

	ret = svc.get_values(channels)
	ret['from'] = node.get_addr()
	ret['to'] = base_addr
	ret['type'] = 'publish'
	ret['serviceId'] = [ svc.get_id() ] + ret.get('serviceId', [])
	if len(ret['serviceId']) == 1:
		ret['serviceId'] = ret['serviceId'][0]
	base_send_obj(ret)

def base_handle_input(msg):
	global nodes, svc_manager_svcs

	# Check message parses as JSON
	try:
		obj = sensorino.message_dict(json.loads(msg))
	except:
		base_send_obj({ 'error': 'syntaxError' })
		return

	# Check if type is present
	if 'type' not in obj:
		base_send_obj({ 'error': 'noType' })
		return
	msg_type = obj['type']

	# General message structure check
	ok = 1
	for prop in [ 'from' ]:
		if prop in obj and not isinstance(obj[prop], int):
			ok = 0
	for prop in obj:
		if prop not in sensorino.known_datatypes_dict:
			continue
		type = sensorino.datatype_to_name(prop)
		try:
			vallist = sensorino.valuelist_from_msg(obj, prop)
			sensorino.valuelist_validate_types(vallist, type)
		except:
			ok = 0

	if 'to' not in obj or msg_type not in \
			[ 'publish', 'set', 'request', 'err' ] or not ok:
		base_send_obj({ 'error': 'structError' })
		return

	# Check if addressed node exists
	if obj['to'] not in nodes:
		base_send_obj({ 'error': 'xmitError' })
		return

	# Check if service exists
	node = nodes[obj['to']]

	main_svc_id = None
	if 'serviceId' in obj:
		svc_ids = sensorino.valuelist_from_msg(obj, 'serviceId')
		main_svc_id = svc_ids.pop(0)

	if main_svc_id not in node.services:
		base_send_obj({
				'from': node.get_addr(),
				'to': base_addr,
				'type': 'err',
				'dataType': 'ServiceId',
			})
		return

	svc = node.services[main_svc_id]

	# Message type check
	if msg_type not in [ 'request', 'set' ]:
		base_send_obj({
				'from': node.get_addr(),
				'to': base_addr,
				'type': 'err',
				'serviceId': main_svc_id,
			})
		return

	# Pass the message down without the fields already handled
	for prop in [ 'to', 'from', 'serviceId', 'type' ]:
		obj.pop(prop, None)
	if len(svc_ids):
		obj['serviceId'] = svc_ids

	if msg_type == 'set':
		base_handle_set(node, svc, obj)
	else:
		base_handle_request(node, svc, obj)

# Objectify?

s = None
parse_state = None

def base_init(base_name):
	global s, parse_state
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect(config.base_server_address)

	# Introduce ourselves
	base_send_obj({ 'base-name': base_name })

	parse_state = base_server.obj_parser()

class BaseDisconnect(Exception):
	pass

def base_run(timeout):
	global s, parse_state

	r, w, e = select.select([ s ], [], [ s ], timeout)
	if len(e):
		raise BaseDisconnect()
	if not len(r):
		return

	for chr in s.recv(8192).decode('utf-8'):
		obj = parse_state.handle_char(chr)
		if obj is not None:
			base_handle_input(obj)

def base_done():
	global s
	s.close()
