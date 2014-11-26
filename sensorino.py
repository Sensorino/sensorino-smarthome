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
import asyncore

def log_err(msg):
	sys.stderr.write(str(msg) + '\n')

def log_warn(msg):
	sys.stderr.write(str(msg) + '\n')

def addr_from_msg(msg, addrtype):
	return int(msg[addrtype])

def valuelist_from_msg(msg, datatype):
	val = msg[datatype]

	# If basic type provided, return a single-element list
	if isinstance(val, basestring) or \
			not isinstance(val, collections.Sequence):
		return [ val ]

	return val

known_datatypes = {
	# It's unlikely that we ever need to use the numerical IDs but no
	# harm in keeping them.

	# Metatypes
	'dataType': ( 0, str ),
	'serviceId': ( 1, int ),
	'message': ( 2, str ),
	'expression': ( 3, str ),
	# ISO-defined physical dimensions
	'acceleration': ( 20, float ),
	'amount': ( 21, float ),
	'angle': ( 22, float ),
	'angularVelocity': ( 23, float ),
	'area': ( 24, float ),
	'radioactivity': ( 25, float ),
	'electricalCapacitance': ( 26, float ),
	'electricalResistance': ( 27, float ),
	'electricCurrent': ( 28, float ),
	'energy': ( 29, float ),
	'force': ( 30, float ),
	'frequency': ( 31, float ),
	'illuminance': ( 32, float ),
	'inductance': ( 33, float ),
	'length': ( 34, float ),
	'luminousFlux': ( 35, float ),
	'luminousIntensity': ( 36, float ),
	'magneticFieldStrength': ( 37, float ),
	'mass': ( 38, float ),
	'power': ( 39, float ),
	'pressure': ( 40, float ),
	'relativeHumidity': ( 41, float ),
	'speed': ( 42, float ),
	'temperature': ( 43, float ),
	'time': ( 44, float ),
	'voltage': ( 45, float ),
	'volume': ( 46, float ),
	# Other common types
	'count': ( 50, int ),
	'presence': ( 51, bool ),
	'switch': ( 52, bool ),
}

def datatype_to_basic_type(datatype):
	return known_datatypes[datatype][1]

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
	# TODO: might also want to allow ints for bools if 0 or 1

	if any([ type(val) not in allowed_types for val in vallist ]):
		raise Exception('Some values don\'t match the \'' + datatype + \
				'\' type')

	if datatype == 'count':
		if any([ val < 0 for val in vallist ]):
			raise Exception('\'' + datatype + \
					'\' can\' be negative')
	if datatype == 'serviceId':
		if any([ val < 0 or val > 255 for val in vallist ]):
			raise Exception('\'' + datatype + \
					'\' must be between 0 and 255')

def validate_incoming_publish(msg):
	# Validate the source address
	if 'from' not in msg:
		raise Exception('Messsage is missing a \'from\' field')
	try:
		addr = addr_from_msg(msg, 'from')
	except:
		raise Exception('\'' + str(msg['from']) + \
				'\' can\' be parsed as an address')
	if addr < 1 or addr > 255:
		raise Exception('\'' + str(msg['from']) + \
				'\' is not a valid node address')

	# Validate the destination address if present (is optional)
	if 'to' in msg:
		try:
			addr = addr_from_msg(msg, 'to')
		except:
			raise Exception('\'' + str(msg['to']) + \
					'\' can\' be parsed as an address')
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

		if not len(vallist):
			raise Exception('\'' + field + '\' value list is empty')

		if field not in known_datatypes:
			log_warn('Unknown type \'' + field + '\'')
			continue

		valuelist_validate_types(vallist, field)

		if field in [ 'serviceId' ]:
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
		raise Exception('Messsage is missing a \'from\' field')
	try:
		addr = addr_from_msg(msg, 'from')
	except:
		raise Exception('\'' + str(msg['from']) + \
				'\' can\' be parsed as an address')
	if addr < 1 or addr > 255:
		raise Exception('\'' + str(msg['from']) + \
				'\' is not a valid node address')

def validate_outgoing_request(msg):
	# Validate the destination address
	if 'to' not in msg:
		raise Exception('Messsage is missing a \'to\' field')
	try:
		addr = addr_from_msg(msg, 'to')
	except:
		raise Exception('\'' + str(msg['to']) + \
				'\' can\' be parsed as an address')
	if addr < 1 or addr > 255:
		raise Exception('\'' + str(msg['to']) + \
				'\' is not a valid node address')

	# Validate the source address if present (is optional)
	if 'from' in msg:
		try:
			addr = addr_from_msg(msg, 'from')
		except:
			raise Exception('\'' + str(msg['from']) + \
					'\' can\' be parsed as an address')
		# Base address == 0 assumption is made here, may need to
		# be fixed at one point.
		if addr != 0:
			raise Exception('\'' + str(msg['from']) + \
					'\' is not a valid Base address')

	if 'serviceId' not in msg:
		raise Exception('Messsage is missing a \'serviceId\' field')

	# For everything else look up type by dataType and confirm
	for field in msg:
		if field in [ 'from', 'to', 'type' ]:
			continue

		if field not in [ 'serviceId', 'dataType', 'count' ]:
			log_warn('Type \'' + field +
					'\' not allowed in Requests')
			continue

		vallist = valuelist_from_msg(msg, field)

		if not len(vallist):
			raise Exception('\'' + field + '\' value list is empty')
		if len(vallist) > 1 and field == 'serviceId':
			raise Exception('Too many Service IDs')

		valuelist_validate_types(vallist, field)

def validate_outgoing_set(msg):
	# Validate the destination address
	if 'to' not in msg:
		raise Exception('Messsage is missing a \'to\' field')
	try:
		addr = addr_from_msg(msg, 'to')
	except:
		raise Exception('\'' + str(msg['to']) + \
				'\' can\' be parsed as an address')
	if addr < 1 or addr > 255:
		raise Exception('\'' + str(msg['to']) + \
				'\' is not a valid node address')

	# Validate the source address if present (is optional)
	if 'from' in msg:
		try:
			addr = addr_from_msg(msg, 'from')
		except:
			raise Exception('\'' + str(msg['from']) + \
					'\' can\' be parsed as an address')
		# Base address == 0 assumption is made here, may need to
		# be fixed at one point.
		if addr != 0:
			raise Exception('\'' + str(msg['from']) + \
					'\' is not a valid Base address')

	if 'serviceId' not in msg:
		raise Exception('Messsage is missing a \'serviceId\' field')

	# For everything else look up type by dataType and confirm
	for field in msg:
		if field in [ 'from', 'to', 'type' ]:
			continue

		vallist = valuelist_from_msg(msg, field)

		if not len(vallist):
			raise Exception('\'' + field + '\' value list is empty')

		if field not in known_datatypes:
			log_warn('Unknown type \'' + field + '\'')
			continue

		valuelist_validate_types(vallist, field)

# Note: not basing on asyncore.dispatcher because it doesn't have any timer
# support
class sensorino_state():
	def __init__(self):
		self.state = {}

		# One last Set or Request message sent to any node is
		# kept in the queue here so we can associate any incoming
		# error message with that outgoing message.
		self.pending = {}

		self.change_handlers = []

	def subscribe_changes(self, handler):
		self.change_handlers.append(handler)

	def unsubscribe_changes(self, handler):
		self.change_handlers.remove(handler)

	def enqueue(self, msg, callback, change_set):
		'''Save the message to the pending-op queue so we can
		track the success status of this operation.  But first
		check if another unconfirmed message is there.'''

		addr = addr_from_msg(msg, 'to')

		if addr in self.pending:
			# Another operation is pending
			prev_msg, prev_callback, prev_state, c = \
				self.pending.pop(addr)

			# Notify
			if prev_callback is not None:
				prev_callback(prev_msg, 'no-error', None)

		# Save a deep copy of the affected node's state so we can
		# restore it if the operation results in an error.
		state = None
		if addr in self.state:
			state = copy.deepcopy(self.state[addr])

		self.pending[addr] = ( msg, callback, state, change_set )
		# TODO: Set a timeout?

	# Must have gone through the static validation first
	def validate_incoming_publish(self, msg):
		addr = addr_from_msg(msg, 'from')
		if addr not in self.state:
			return

		node_state = self.state[addr]

		# Find the service in question
		service_ids = valuelist_from_msg(msg, 'serviceId')
		main_service_id = service_ids.pop(0)
		if main_service_id not in node_state:
			return

		service_state = node_state[main_service_id]

		# Validate type counts against declared counts
		for field in msg:
			if field in [ 'from', 'to', 'type' ]:
				continue

			if field == 'count' and 'dataType' in msg:
				continue

			if field == 'serviceId' and main_service_id == 0:
				continue

			prop_name = '_publish_count_' + field
			if prop_name not in service_state:
				continue

			vallist = valuelist_from_msg(msg, field)
			if len(vallist) > service_state[prop_name]:
				raise Exception('Service published ' + \
					str(len(vallist)) + ' \'' + field + \
					'\' values while only ' + \
					str(service_state[prop_name]) + \
					' had been declared')

	def validate_outgoing_set(self, msg):
		addr = addr_from_msg(msg, 'to')
		if addr not in self.state:
			raise Exception('Unkown destination address: ' + \
					str(addr))

		node_state = self.state[addr]

		# Find the service in question
		service_ids = valuelist_from_msg(msg, 'serviceId')
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

			prop_name = '_accept_count_' + field
			if prop_name not in service_state:
				raise Exception('This service\'s description ' +
						'has not been received yet or' +
						'it did not include \'' +
						field + '\'')

			vallist = valuelist_from_msg(msg, field)
			if len(vallist) > service_state[prop_name]:
				raise Exception('Setting ' + \
					str(len(vallist)) + ' \'' + field + \
					'\' values while service declared ' + \
					'it only accepts ' + \
					str(service_state[prop_name]))

	def update_service_desc(service_state, types, counts):
		changed = false

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
		for num, type in enumerate(types):
			if num >= counts[0] + counts[1]:
				break

			if type not in publish_by_type:
				publish_by_type[type] = 0
			if type not in accept_by_type:
				accept_by_type[type] = 0

			if num < counts[0]:
				publish_by_type[type] += 1
			else:
				accept_by_type[type] += 1

		for type in publish_by_type:
			prop_name = '_publish_count_' + type
			if prop_name not in service_state or \
					service_state[prop_name] != \
					publish_by_type[type]:
				service_state[prop_name] = publish_by_type[type]
				changed = True

		for type in accept_by_type:
			prop_name = '_accept_count_' + type
			if prop_name not in service_state or \
					service_state[prop_name] != \
					accept_by_type[type]:
				service_state[prop_name] = accept_by_type[type]
				changed = True

		return changed

	def update_state(self, msg, addr, is_set):
		'''Process an incoming or outgoing message such as Publish
		or Set and see what state changes it implies.  Update our
		local copy of the state and the database.'''

		changes = []

		# Find the node in question
		if addr not in self.state:
			# New node
			self.state[addr] = {}
			changes.append(( addr, ))

		node_state = self.state[addr]

		# Find the service in question
		service_ids = valuelist_from_msg(msg, 'serviceId')

		main_service_id = service_ids.pop(0)
		if main_service_id not in node_state:
			# New service
			node_state[main_service_id] = {}
			changes.append(( addr, main_service_id ))

		service_state = node_state[main_service_id]

		# Update all the individual values in the service
		def handle_field(field, vallist):
			offset = 0
			if is_set:
				prop_name = '_publish_count_' + field
				offset = service_state[prop_name]

			if field not in service_state:
				# New channels in this service
				service_state[field] = []
				changes.append(( addr, main_service_id, field ))

			for num, val in enumerate(vallist):
				pos = num + offset
				if pos < len(service_state[field]):
					if val == service_state[field][pos]:
						continue
					service_state[field][pos] = val
					changes.append(( addr, main_service_id,
							field, num ))
				else:
					while len(service_state[field]) < pos:
						service_state[field]. \
							append(None)
					service_state[field].append(val)
					changes.append(( addr, main_service_id,
							field, num ))

		skip = [ 'from', 'to', 'type', 'serviceId' ]
		if 'dataType' in msg:
			# Count used as a helper for dataType values
			skip.append('count')

			types = valuelist_from_msg(msg, 'dataType')

			counts = []
			if 'count' in msg:
				counts = valuelist_from_msg(msg, 'count')

			changed = update_service_desc(service_state,
					types, counts)
			if changed:
				changes.append(( addr, main_service_id ))

		for field in [ k for k in msg if k not in skip ]:
			handle_field(field, valuelist_from_msg(msg, field))
		if len(service_ids):
			handle_field('serviceId', service_ids)

		# Make it a set
		change_set = set(changes)

		if len(changes):
			for handler in self.change_handlers:
				handler(change_set)

		return change_set

	# None of the handle_ methods here nor the update_state() above
	# perform input validation.  All of their messages must first
	# go through the validate functions and if those raise an
	# Exception, the message must not be passed to the handle_
	# function.
	#
	# NOTE: when editing any of these, if you make any new assumptions
	# about the input message (e.g. presence of a field or value type),
	# you must include a check in the relevant validate function first.

	def handle_publish(self, msg):
		# TODO: save the full message to the database

		addr = addr_from_msg(msg, 'from')

		self.update_state(msg, addr, False)

	def handle_error(self, msg):
		# TODO: save the full message to the database

		addr = addr_from_msg(msg, 'from')

		if addr not in self.pending:
			return

		prev_msg, prev_callback, prev_state, change_set = \
			self.pending.pop(addr)

		# TODO: mark the last message's status in the database
		# as failure

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
					handler(change_set)

		if prev_callback is not None:
			prev_callback(prev_msg, 'error', msg)

		# TODO: possibly, if the last message was a Set, now
		# send a Request so we can reliably know the current
		# state.

	def handle_request(self, msg, callback = None):
		# TODO: save the full message to the database with an
		# additional 'success' field to be cleared on error

		self.enqueue(msg, callback, set())

		# There's no specific action that we need to take on
		# this.

	def handle_set(self, msg, callback = None):
		# TODO: save the full message to the database with an
		# additional 'success' field to be cleared on error

		addr = addr_from_msg(msg, 'to')

		change_set = self.update_state(msg, addr, True)

		self.enqueue(msg, callback, change_set)

	def handle_invalid_incoming(self, msg):
		# TODO: save the full message to the database
		pass

	def handle_invalid_outgoing(self, msg):
		# TODO: save the full message to the database

		try:
			addr = addr_from_msg(msg, 'to')
		except:
			return

		# We take no responsibility for the new message, don't
		# enqueue it
		if addr in self.pending:
			# Another operation is pending
			prev_msg, prev_callback, prev_state, c = \
				self.pending.pop(addr)

			# Notify
			if prev_callback is not None:
				prev_callback(prev_msg, 'no-error', None)

	def get_state_tree(self):
		return self.state
