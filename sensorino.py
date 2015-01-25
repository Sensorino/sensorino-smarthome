# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Sensorino-specific classes and utilities, mainly the sensorino_state
# class that keeps track of the whole sensor network state.
#
import sys
import collections
import copy

import timers

def log_err(msg):
	sys.stderr.write(str(msg) + '\n')

def log_warn(msg):
	sys.stderr.write(str(msg) + '\n')

class message_dict(dict):
	# Case-insensitive dict
	def __init__(self, data):
		if not isinstance(data, dict):
			raise Exception('Not a dict')

		super(message_dict, self).__init__()
		for k in data:
			self.__setitem__(k, data[k])

	def __setitem__(self, key, value):
		super(message_dict, self).__setitem__(key.lower(), value)

	def __getitem__(self, key):
		return super(message_dict, self).__getitem__(key.lower())

	def __delitem__(self, key):
		return super(message_dict, self).__delitem__(key.lower())

	def __contains__(self, key):
		return super(message_dict, self).__contains__(key.lower())

	def pop(self, key, *args):
		return super(message_dict, self).pop(key.lower(), *args)

def addr_from_msg(msg, addrtype):
	return msg[addrtype]

def valuelist_from_msg(msg, datatype):
	val = msg[datatype]

	# If basic type provided, return a single-element list
	if isinstance(val, basestring) or \
			not isinstance(val, collections.Sequence):
		return [ val ]

	return val

known_datatypes = [
	# It's unlikely that we ever need to use the numerical IDs but no
	# harm in keeping them.

	# Metatypes
	( 'dataType', 0, str ),
	( 'serviceId', 1, int ),
	( 'message', 2, str ),
	( 'expression', 3, str ),
	# ISO-defined physical dimensions
	( 'acceleration', 20, float ),
	( 'amount', 21, float ),
	( 'angle', 22, float ),
	( 'angularVelocity', 23, float ),
	( 'area', 24, float ),
	( 'radioactivity', 25, float ),
	( 'electricalCapacitance', 26, float ),
	( 'electricalResistance', 27, float ),
	( 'electricCurrent', 28, float ),
	( 'energy', 29, float ),
	( 'force', 30, float ),
	( 'frequency', 31, float ),
	( 'illuminance', 32, float ),
	( 'inductance', 33, float ),
	( 'length', 34, float ),
	( 'luminousFlux', 35, float ),
	( 'luminousIntensity', 36, float ),
	( 'magneticFieldStrength', 37, float ),
	( 'mass', 38, float ),
	( 'power', 39, float ),
	( 'pressure', 40, float ),
	( 'relativeHumidity', 41, float ),
	( 'speed', 42, float ),
	( 'temperature', 43, float ),
	( 'time', 44, float ),
	( 'voltage', 45, float ),
	( 'volume', 46, float ),
	# Other common types
	( 'count', 50, int ),
	( 'presence', 51, bool ),
	( 'switch', 52, bool ),
	( 'colorComponent', 53, float ),
]
known_datatypes_dict = message_dict({})
for t, num, py_t in known_datatypes:
	known_datatypes_dict[t] = ( num, py_t, t )

def datatype_to_basic_type(datatype):
	return known_datatypes_dict[datatype][1]

def datatype_to_name(datatype):
	return known_datatypes_dict[datatype][2]

def valuelist_validate_unique(vallist, name='Value'):
	if len(vallist) > len(set(vallist)):
		raise Exception(name + ' list contains duplicates')

def valuelist_validate_types(vallist, datatype):
	basic_type = datatype_to_basic_type(datatype)

	# Make a list of valid JSON types for given Sensorino dataType
	allowed_types = [ basic_type ]
	if basic_type == float:
		allowed_types.append(int)
	if basic_type == str:
		allowed_types.append(unicode)
	# Also allow "null"s for anything except Service IDs, DataTypes, Counts
	if datatype not in [ 'count', 'serviceId', 'dataType' ]:
		allowed_types.append(type(None))
	# TODO: might also want to allow ints for bools if 0 or 1

	if any([ type(val) not in allowed_types for val in vallist ]):
		raise Exception('Some values don\'t match the \'' + datatype + \
				'\' type')

	if datatype == 'count':
		if any([ val < 0 for val in vallist ]):
			raise Exception('\'' + datatype + \
					'\' can\'t be negative')
	if datatype == 'serviceId':
		if any([ val < 0 for val in vallist ]):
			raise Exception('\'' + datatype + \
					'\' must be a non-negative integer')
	if datatype == 'dataType':
		for val in vallist:
			if val in known_datatypes_dict:
				continue
			log_warn('Unknown data type \'' + val + '\'')

def validate_incoming_publish(msg):
	# Validate the source address
	if 'from' not in msg:
		raise Exception('Messsage is missing a \'from\' field')
	try:
		addr = addr_from_msg(msg, 'from')
	except:
		raise Exception('\'' + str(msg['from']) + \
				'\' can\'t be parsed as an address')
	if addr == 0:
		raise Exception('\'' + str(msg['from']) + \
				'\' is not a valid node address')

	# Validate the destination address if present (is optional)
	if 'to' in msg:
		try:
			addr = addr_from_msg(msg, 'to')
		except:
			raise Exception('\'' + str(msg['to']) + \
					'\' can\'t be parsed as an address')
		# Base address == 0 assumption is made here, may need to
		# be fixed at one point.
		if addr != 0:
			raise Exception('\'' + str(msg['to']) + \
					'\' is not a valid Base address')

	if 'serviceId' not in msg:
		raise Exception('Messsage is missing a \'serviceId\' field')

	# For everything else look up type by dataType and confirm
	for field in msg:
		if field in [ 'from', 'to', 'type' ]:
			continue

		vallist = valuelist_from_msg(msg, field)

		if field not in known_datatypes_dict:
			log_warn('Unknown type \'' + field + '\'')
			continue
		name = datatype_to_name(field)

		if not len(vallist):
			raise Exception('\'' + name + '\' value list is empty')

		valuelist_validate_types(vallist, name)

		if name in [ 'serviceId' ]:
			valuelist_validate_unique(vallist, 'Service ID')

	if 'dataType' in msg and 'count' in msg:
		types = valuelist_from_msg(msg, 'dataType')
		counts = valuelist_from_msg(msg, 'count')

		if len(counts) > 2:
			raise Exception('Too many \'count\' elements: ' +
					str(len(counts)))

		if counts[0] < 0 or counts[0] > len(types):
			raise Exception('Invalid number of published types: ' +
					str(counts[0]))

		if len(counts) > 1 and counts[0] + counts[1] != len(types):
			raise Exception('Invalid total number of types: ' +
					str(counts[0] + counts[1]))

def validate_incoming_error(msg):
	# Validate the source address
	if 'from' not in msg:
		if 'error' in msg:
			return

		raise Exception('Messsage is missing a \'from\' field')
	try:
		addr = addr_from_msg(msg, 'from')
	except:
		raise Exception('\'' + str(msg['from']) + \
				'\' can\'t be parsed as an address')
	if addr == 0:
		raise Exception('\'' + str(msg['from']) + \
				'\' is not a valid node address')

	# TODO: reject if we have nothing enqueued / have not sent anything
	# in the last couple of seconds?

def validate_request(msg):
	# Validate the destination address
	if 'to' not in msg:
		raise Exception('Messsage is missing a \'to\' field')
	try:
		addr = addr_from_msg(msg, 'to')
	except:
		raise Exception('\'' + str(msg['to']) + \
				'\' can\'t be parsed as an address')
	if addr == 0:
		raise Exception('\'' + str(msg['to']) + \
				'\' is not a valid node address')

	# Validate the source address if present (is optional)
	if 'from' in msg:
		try:
			addr = addr_from_msg(msg, 'from')
		except:
			raise Exception('\'' + str(msg['from']) + \
					'\' can\'t be parsed as an address')

	if 'serviceId' not in msg:
		raise Exception('Messsage is missing a \'serviceId\' field')

	# For everything else look up type by dataType and confirm
	for field in msg:
		if field in [ 'from', 'to', 'type' ]:
			continue

		if field not in known_datatypes_dict:
			log_warn('Unknown type \'' + field + '\'')
			continue
		name = datatype_to_name(field)

		if name not in [ 'serviceId', 'dataType', 'count' ]:
			log_warn('Type \'' + field +
					'\' not allowed in Requests')
			continue

		vallist = valuelist_from_msg(msg, field)

		if not len(vallist):
			raise Exception('\'' + name + '\' value list is empty')
		if len(vallist) > 1 and name == 'serviceId':
			raise Exception('Too many Service IDs')

		valuelist_validate_types(vallist, name)

def validate_incoming_request(msg):
	validate_request(msg)

def validate_outgoing_request(msg):
	validate_request(msg)

	# Validate the source address if present
	if 'from' in msg:
		addr = addr_from_msg(msg, 'from')

		# Base address == 0 assumption is made here, may need to
		# be fixed at one point.
		if addr != 0:
			raise Exception('\'' + str(msg['from']) + \
					'\' is not a valid Base address')

def validate_set(msg):
	# Validate the destination address
	if 'to' not in msg:
		raise Exception('Messsage is missing a \'to\' field')
	try:
		addr = addr_from_msg(msg, 'to')
	except:
		raise Exception('\'' + str(msg['to']) + \
				'\' can\'t be parsed as an address')
	if addr == 0:
		raise Exception('\'' + str(msg['to']) + \
				'\' is not a valid node address')

	# Validate the source address if present (is optional)
	if 'from' in msg:
		try:
			addr = addr_from_msg(msg, 'from')
		except:
			raise Exception('\'' + str(msg['from']) + \
					'\' can\'t be parsed as an address')

	if 'serviceId' not in msg:
		raise Exception('Messsage is missing a \'serviceId\' field')

	# For everything else look up type by dataType and confirm
	for field in msg:
		if field in [ 'from', 'to', 'type' ]:
			continue

		vallist = valuelist_from_msg(msg, field)

		if field not in known_datatypes_dict:
			log_warn('Unknown type \'' + field + '\'')
			continue
		name = datatype_to_name(field)

		if not len(vallist):
			raise Exception('\'' + name + '\' value list is empty')

		valuelist_validate_types(vallist, name)

def validate_incoming_set(msg):
	validate_set(msg)

def validate_outgoing_set(msg):
	validate_set(msg)

	# Validate the source address if present
	if 'from' in msg:
		addr = addr_from_msg(msg, 'from')

		# Base address == 0 assumption is made here, may need to
		# be fixed at one point.
		if addr != 0:
			raise Exception('\'' + str(msg['from']) + \
					'\' is not a valid Base address')

class sensorino_state():
	def __init__(self, storage):
		self.storage = storage

		self.state = {}

		# One last Set or Request message sent to any node is
		# kept in the queue here so we can associate any incoming
		# error message with that outgoing message.
		self.pending = {}
		self.last_addr = None

		self.change_handlers = []

	def subscribe_changes(self, handler):
		self.change_handlers.append(handler)

	def unsubscribe_changes(self, handler):
		self.change_handlers.remove(handler)

	def load(self):
		self.state = self.storage.get_tree_current()

	def enqueue(self, msg, callback):
		'''Save the message to the pending-op queue so we can
		track the success status of this operation.  But first
		check if another unconfirmed message is there.'''

		addr = addr_from_msg(msg, 'to')

		if addr in self.pending:
			# Another operation is pending, assume success if
			# no other indication from the remote end.  Kind of
			# questionable.
			self.queued_success(addr)

		# Save a deep copy of the affected node's state so we can
		# restore it if the operation results in an error.
		state = None
		if addr in self.state:
			state = copy.deepcopy(self.state[addr])

		# Assume success after 20s if no feedback
		# Normally we could use a ~1s timeout and the callback could
		# well be used by the API to return the right HTTP status
		# code, but with some bases (BLE) with time multiplexing these
		# times may be quite long.
		to = timers.call_later(self.queued_success, 20, [ addr ])

		self.pending[addr] = ( msg, callback, state, set(), [], to )
		self.last_addr = addr

	def queue_empty(self, addr):
		return addr not in self.pending

	def queued_change_set(self, change_set, ref_list):
		'''After enqueue has been called, this function can be
		used to additionally save information about the set of
		changes occuring since the last saved state, so that it
		doesn't need to be recalculated when the state is being
		reverted.'''

		saved_set = self.pending[self.last_addr][3]
		saved_set |= change_set
		saved_refs = self.pending[self.last_addr][4]
		saved_refs += ref_list

	def queued_success(self, addr):
		'''Clear the queue of pending transaction-like requests
		if its not empty.  The transaction was successful.'''
		self.last_addr = None

		if addr not in self.pending:
			return

		# An operation was pending
		prev_msg, prev_callback, prev_state, \
			c, r, to = self.pending.pop(addr)

		try:
			timers.cancel(to)
		except:
			pass

		# Notify
		if prev_callback is not None:
			prev_callback(prev_msg, 'no-error', None)

	def queued_failure(self, addr):
		'''Clear the queue of pending transaction-like requests
		if its not empty.  The transaction failed.'''

		self.last_addr = None

		if addr not in self.pending:
			return

		prev_msg, prev_callback, prev_state, change_set, ref_list, \
			to = self.pending.pop(addr)

		timers.cancel(to)

		# If the failing message is a Set, try to restore the
		# recorded node's state to what it was prior to the
		# operation.
		if prev_msg['type'] == 'set':
			if prev_state is None and addr in self.state:
				del self.state[addr]
			elif prev_state is not None:
				self.state[addr] = prev_state

			# If we could call update_state, that would take
			# care of this for us...
			if len(change_set):
				for handler in self.change_handlers:
					handler(change_set, error=True)

			# Mark all of the database records related to
			# the failing message as unsuccessful.
			for ref in ref_list:
				self.storage.mark_saved_value_failure(ref)
			if ref_list:
				self.storage.commit()

		if prev_callback is not None:
			prev_callback(prev_msg, 'error', msg)

		# TODO: possibly, if the last message was a Set, now
		# send a Request so we can reliably know the current
		# state.

	# Must have gone through the static validation first
	def validate_incoming_publish(self, msg):
		addr = addr_from_msg(msg, 'from')
		if addr not in self.state:
			return

		node_state = self.state[addr]

		# Find the service in question
		service_ids = copy.copy(valuelist_from_msg(msg, 'serviceId'))
		main_service_id = service_ids.pop(0)
		if main_service_id not in node_state:
			return

		service_state = node_state[main_service_id]

		# Validate type counts against declared counts
		for field in msg:
			if field in [ 'from', 'to', 'type' ]:
				continue

			if field in known_datatypes_dict:
				field = datatype_to_name(field)

			if field == 'count' and 'dataType' in msg:
				continue

			vallist = valuelist_from_msg(msg, field)

			if field == 'serviceId':
				if main_service_id == 0:
					continue
				vallist = service_ids
				if not vallist:
					continue

			prop_name = '_publish_count_' + field
			if prop_name not in service_state:
				continue
			cnt = service_state[prop_name]
			prop_name = '_accept_count_' + field
			if prop_name not in service_state:
				continue
			cnt += service_state[prop_name]

			# For now we allow publishing up to the total number
			# of channels of given type.  If the number is
			# higher than the publish_count then we should
			# check that this is a response to a "request"
			# message, otherwise not reject the message.
			if len(vallist) > cnt:
				raise Exception('Service published ' + \
					str(len(vallist)) + ' \'' + field + \
					'\' values while only ' + \
					str(service_state[prop_name]) + \
					' had been declared')

	def validate_set(self, msg):
		addr = addr_from_msg(msg, 'to')
		if addr not in self.state:
			raise Exception('Unkown destination address: ' + \
					str(addr))

		node_state = self.state[addr]

		# Find the service in question
		service_ids = copy.copy(valuelist_from_msg(msg, 'serviceId'))
		main_service_id = service_ids.pop(0)
		if main_service_id not in node_state:
			raise Exception('Unkown destination Service ID: ' + \
					str(main_service_id))

		if main_service_id == 0:
			raise Exception('Service ID 0 is read-only')

		service_state = node_state[main_service_id]

		# Validate type counts against declared counts
		for field in msg:
			if field in [ 'from', 'to', 'type' ]:
				continue

			if field in known_datatypes_dict:
				field = datatype_to_name(field)

			vallist = valuelist_from_msg(msg, field)

			if field == 'serviceId':
				vallist = service_ids
				if not vallist:
					continue

			prop_name = '_accept_count_' + field
			if prop_name not in service_state:
				raise Exception('This service\'s description ' +
						'has not been received yet or' +
						' it did not include \'' +
						field + '\'')
			# Note: if the user manually sends a correct message to
			# a service that we don't yet know the description of,
			# we're gonna end up with an inconsistent state in the
			# server.  This also applies to messages generated by
			# a remote rule engine that we process.  Perhaps should
			# automatically query all affected services every time
			# we send or receive a SET message we don't understand,
			# with a delay of a few seconds.

			if len(vallist) > service_state[prop_name]:
				raise Exception('Setting ' + \
					str(len(vallist)) + ' \'' + field + \
					'\' values while service declared ' + \
					'it only accepts ' + \
					str(service_state[prop_name]))

	def validate_incoming_set(self, msg):
		self.validate_set(msg)
	def validate_outgoing_set(self, msg):
		self.validate_set(msg)

	@staticmethod
	def update_service_desc(service_state, types, counts):
		changes = []

		# The counts are optional, if not present, calculate
		# from the number of the dataType elements provided.
		if len(counts) == 0:
			counts.append(len(types))
		if len(counts) == 1:
			counts.append(len(types) - counts[0])

		# Count the number of elements being published and
		# those accepted for each data type.
		publish_by_type = {}
		accept_by_type = {}
		for num, typ in enumerate(types):
			if num >= counts[0] + counts[1]:
				break

			typ = typ.lower()
			if typ in known_datatypes_dict:
				typ = datatype_to_name(typ)

			if typ not in publish_by_type:
				publish_by_type[typ] = 0
			if typ not in accept_by_type:
				accept_by_type[typ] = 0

			if num < counts[0]:
				publish_by_type[typ] += 1
			else:
				accept_by_type[typ] += 1

		for typ in publish_by_type:
			prop_name = '_publish_count_' + typ
			if prop_name not in service_state or \
					service_state[prop_name] != \
					publish_by_type[typ]:
				service_state[prop_name] = publish_by_type[typ]

				changes.append(( ( prop_name, ),
						publish_by_type[typ] ))

		for typ in accept_by_type:
			prop_name = '_accept_count_' + typ
			if prop_name not in service_state or \
					service_state[prop_name] != \
					accept_by_type[typ]:
				service_state[prop_name] = accept_by_type[typ]

				changes.append(( ( prop_name, ),
						accept_by_type[typ] ))

		if '_discovered' not in service_state:
			service_state['_discovered'] = True
			changed = True

			changes.append(( ( '_discovered', ), True ))

		return changes

	def update_state(self, timestamp, msg, addr, base_id, is_set):
		'''Process an incoming or outgoing message such as Publish
		or Set and see what state changes it implies.  Update our
		local copy of the state and the database.'''

		changes = []
		change_refs = []

		# Find the node in question
		if addr not in self.state:
			# New node
			self.state[addr] = { '_addr': addr }

			ref = self.storage.save_value(timestamp,
					( addr, '_addr' ), addr)
			change_refs.append(ref)

			changes.append(( addr, ))

		node_state = self.state[addr]

		if '_base' not in node_state and base_id is not None:
			node_state['_base'] = base_id

			ref = self.storage.save_value(timestamp,
					( addr, '_base' ), base_id)
			change_refs.append(ref)

			changes.append(( addr, '_base' ))

		# Find the service in question
		service_ids = copy.copy(valuelist_from_msg(msg, 'serviceId'))

		main_service_id = service_ids.pop(0)
		if main_service_id not in node_state:
			# New service
			node_state[main_service_id] = {}

			changes.append(( addr, main_service_id ))

		service_state = node_state[main_service_id]

		# Update all the individual values in the service
		def handle_field(field, vallist):
			datatype = field
			if field in known_datatypes_dict:
				datatype = datatype_to_name(field)

			offset = 0
			if is_set:
				prop_name = '_publish_count_' + datatype
				offset = service_state[prop_name]

			if datatype not in service_state:
				# New channels in this service
				service_state[datatype] = []
				changes.append(( addr, main_service_id,
						datatype ))

			for num, val in enumerate(vallist):
				pos = num + offset

				if pos < len(service_state[datatype]):
					if val == service_state[datatype][pos]:
						continue
					service_state[datatype][pos] = val
				else:
					while len(service_state[datatype]) < \
							pos:
						service_state[datatype]. \
							append(None)
					service_state[datatype].append(val)

				path = ( addr, main_service_id, datatype, num )
				ref = self.storage.save_value(timestamp,
						path, val)
				change_refs.append(ref)

				changes.append(path)

		skip = [ 'from', 'to', 'type', 'serviceId'.lower() ]
		if 'dataType' in msg:
			skip.append('dataType'.lower())
			# Count used as a helper for dataType values
			skip.append('count')

			types = valuelist_from_msg(msg, 'dataType')

			counts = []
			if 'count' in msg:
				counts = valuelist_from_msg(msg, 'count')

			desc_changes = self.update_service_desc(service_state,
					types, counts)
			if len(desc_changes):
				changes.append(( addr, main_service_id ))
			for subpath, value in desc_changes:
				ref = self.storage.save_value(timestamp,
						( addr, main_service_id ) +
						subpath, value)
				change_refs.append(ref)

		fields = []
		for field in msg:
			if field in skip:
				continue
			if field in known_datatypes_dict:
				field = datatype_to_name(field)
			fields.append(field)

		# Special case: if a set message has no values and is
		# addressed at a service with one boolean channel, toggle
		# that channel's value.
		if is_set and not fields and \
				'_accept_count_switch' in service_state and \
				service_state['_accept_count_switch'] == 1 and \
				'switch' in service_state:
			msg['switch'] = not service_state['switch'][0]
			fields.append('switch')

		for field in fields:
			handle_field(field, valuelist_from_msg(msg, field))
		if len(service_ids):
			handle_field('serviceId', service_ids)

		# Special case: Service ID 0 publish messages are the node
		# description messages.  If we receive one, the node is
		# node "discovered".
		if main_service_id == 0 and not is_set and \
				'_discovered' not in node_state:
			node_state['_discovered'] = True

			ref = self.storage.save_value(timestamp,
					( addr, '_discovered' ), True)
			change_refs.append(ref)

			changes.append(( addr, '_discovered' ))

		self.storage.commit()

		# Make it a set
		change_set = set(changes)

		if len(changes):
			for handler in self.change_handlers:
				handler(change_set)

		return change_set, change_refs

	# None of the handle_ methods here nor the update_state() above
	# perform input validation.  All of their messages must first
	# go through the validate functions and if those raise an
	# Exception, the message must not be passed to the handle_
	# function.
	#
	# NOTE: when editing any of these, if you make any new assumptions
	# about the input message (e.g. presence of a field or value type),
	# you must include a check in the relevant validate function first.

	def handle_publish(self, timestamp, msg, base_id):
		addr = addr_from_msg(msg, 'from')

		self.queued_success(addr)

		self.update_state(timestamp, msg, addr, base_id, False)

	def handle_error(self, timestamp, msg, base_id):
		if 'from' in msg:
			addr = addr_from_msg(msg, 'from')
		else:
			addr = self.last_addr

		# TODO: might want to inspect serviceId, if present, and
		# match it to what we have in the queue.

		self.queued_failure(addr)

	def handle_request(self, timestamp, msg, base_id, callback = None):
		self.enqueue(msg, callback)

		# There's no specific action that we need to take on
		# this.

	def handle_set(self, timestamp, msg, base_id, callback = None):
		addr = addr_from_msg(msg, 'to')

		self.enqueue(msg, callback)

		change_set, change_refs = \
			self.update_state(timestamp, msg, addr, base_id, True)

		self.queued_change_set(change_set, change_refs)

	def handle_invalid_incoming(self, timestamp, msg, base_id):
		if 'from' in msg:
			addr = addr_from_msg(msg, 'from')
		else:
			addr = self.last_addr

		# Questionable.. but assume failure if timeout not expired
		self.queued_failure(addr)

	def handle_invalid_outgoing(self, timestamp, msg, base_id):
		try:
			addr = addr_from_msg(msg, 'to')
		except:
			addr = self.last_addr

		# We take no responsibility for the new message, don't
		# enqueue and terminate any running transactions.
		# Again questionable here but assume success if we've
		# got no other indication from the remote end.
		self.queued_success(addr)

	def get_state_tree(self):
		return self.state

	def get_state_at_timestamp(self, timestamp):
		return self.storage.get_tree_at_timestamp(timestamp)

	def get_base_for_addr(self, addr):
		if addr in self.state and '_base' in self.state[addr]:
			return self.state[addr]['_base']
		return None
