# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# SQLite-based persistent storage for the sensorino state, console
# logs and floorplan data, all indexed by time.
#
import sqlite3
import os.path
import sensorino

datatype_by_num = {}
for t, num, py_t in sensorino.known_datatypes:
	datatype_by_num[num] = t

def datatype_to_sqlite(datatype):
	if datatype not in sensorino.known_datatypes_dict:
		return datatype
	return sensorino.known_datatypes_dict[datatype][0]

def sqlite_to_datatype(val):
	if isinstance(val, int):
		return datatype_by_num[val]
	return val

def tree_insert_value(state, path, value):
	# Create a dict for the node if first sighting
	if path[0] not in state:
		state[path[0]] = {}
	state = state[path[0]]

	# Create a dict for the service if first sighting
	if len(path) >= 3:
		if path[1] not in state:
			state[path[1]] = {}
		state = state[path[1]]

	# Create an array for the data type if first sighting
	if len(path) >= 4:
		if path[2] not in state:
			state[path[2]] = []
		state = state[path[2]]

		# Fill array with channel value placeholders if needed
		while path[3] >= len(state):
			state.append(None)

	state[path[-1]] = value

class connection():
	def __init__(self, name='sensorino.db'):
		exists = os.path.exists(name)
		self.conn = sqlite3.connect(name)
		self.cur = self.conn.cursor()

		if not exists:
			self.setup()

		# TODO: should we ANALYZE here, or maybe ANALYZE
		# periodically?

	def close(self):
		self.conn.close()

	def setup(self):
		# Create the table and indexes related to the sensorino state
		self.cur.execute('CREATE TABLE sensorino (' +
				'timestamp INT, ' + # millisec resolution
				'node_addr BLOB, ' + # NONE affinity
				'svc_id INT, ' +
				'datatype INT, ' + # int ID if type is known
				'chan_id INT, ' +
				'value BLOB, ' + # NONE affinity
				'success BOOL)') # INT affinity

		# To be used in all the queries and subqueries in get_value*
		# or get_timestamp*
		self.cur.execute('CREATE INDEX sensorino_addr ON sensorino ' +
				'(node_addr, svc_id, datatype, chan_id)')
		self.cur.execute('CREATE INDEX sensorino_time_addr ' +
				'ON sensorino (timestamp DESC, ' +
				'node_addr, svc_id, datatype, chan_id)')

		# For some reason the following don't get used...
		#self.cur.execute('CREATE INDEX sensorino_addr_p ON sensorino' +
		#		' (node_addr, svc_id, datatype, chan_id) ' +
		#		'WHERE success')
		#self.cur.execute('CREATE INDEX sensorino_time_addr_p ' +
		#		'ON sensorino (timestamp DESC, ' +
		#		'node_addr, svc_id, datatype, chan_id) ' +
		#		'WHERE success')

		# Create the table and indexes related to the console state
		self.cur.execute('CREATE TABLE console (' +
				'timestamp INT, ' + # millisec resolution
				'line TEXT)')
		self.cur.execute('CREATE INDEX console_time ON console ' +
				'(timestamp DESC)')

		# Create the table and indexes related to the floorplan state
		self.cur.execute('CREATE TABLE floorplan (' +
				'timestamp INT, ' + # millisec resolution
				'version TEXT)')
		self.cur.execute('CREATE INDEX floorplan_time ON floorplan ' +
				'(timestamp DESC)')

		self.conn.commit()

	def get_value_at_timestamp(self, path, timestamp):
		# Add the path elements to query parameters
		params = [ path[0], path[1], None, None ]
		if len(path) >= 3:
			params[2] = datatype_to_sqlite(path[2])
		if len(path) >= 4:
			params[3] = path[3]

		# Get the value of last change preceding the timestamp
		if timestamp is not None:
			time_cond = ' AND timestamp <= ?'
			params += [ int(timestamp * 1000) ]
		else:
			time_cond = ''

		# Note: IS is a = that treats two NULLs equal
		query = 'SELECT value FROM sensorino WHERE ' + \
			'node_addr IS ? AND ' + \
			'svc_id IS ? AND ' + \
			'datatype IS ? AND ' + \
			'chan_id IS ? AND ' + \
			'success' + time_cond + \
			' ORDER BY timestamp DESC LIMIT 1'

		result = self.cur.execute(query, tuple(params))

		val = self.cur.fetchone()
		if val is None:
			return None
		# TODO: bool conversion?
		return val[0]

	def get_tree_at_timestamp(self, timestamp):
		params = ()

		# Get the value of last change preceding the timestamp
		if timestamp is not None:
			time_cond = ' AND timestamp <= ?'
			timestamp = int(timestamp * 1000)
			params += ( timestamp, timestamp )
		else:
			time_cond = ''

		# Note: IS is a = that treats two NULLs equal
		query = 'SELECT path.*, (SELECT value FROM sensorino WHERE ' + \
				'node_addr IS path.node_addr AND ' + \
				'svc_id IS path.svc_id AND ' + \
				'datatype IS path.datatype AND ' + \
				'chan_id IS path.chan_id AND ' + \
				'success' + time_cond + \
				' ORDER BY timestamp DESC LIMIT 1) ' + \
			'FROM (SELECT DISTINCT node_addr, svc_id, ' + \
				'datatype, chan_id FROM sensorino WHERE ' + \
				'success' + time_cond + ') AS path'

		results = self.cur.execute(query, params)

		tree = {}
		for node_addr, svc_id, datatype, chan_id, value in results:
			state = tree
			path = ( node_addr, svc_id )
			if datatype is not None:
				path += ( sqlite_to_datatype(datatype), )
				if chan_id is not None:
					path += ( chan_id, )

			# TODO: bool conversion?

			tree_insert_value(tree, path, value)

		return tree

	def get_value_current(self, path):
		return self.get_value_at_timestamp(path, None)

	def get_tree_current(self):
		return self.get_tree_at_timestamp(None)

	def get_values_within_period(self, path, t0, t1):
		# Note: IS is a = that treats two NULLs equal
		query = 'SELECT timestamp, value FROM sensorino WHERE ' + \
			'timestamp >= ? AND timestamp < ? AND ' + \
			'node_addr IS ? AND ' + \
			'svc_id IS ? AND ' + \
			'datatype IS ? AND ' + \
			'chan_id IS ? AND ' + \
			'success ORDER BY timestamp DESC LIMIT 1024'

		params = [
			int(t0 * 1000), int(t1 * 1000),
			path[0], path[1], None, None ]

		if len(path) >= 3:
			params[4] = datatype_to_sqlite(path[2])
		if len(path) >= 4:
			params[5] = path[3]

		# TODO: bool conversion?
		return [ ( 0.001 * timestamp, value ) for timestamp, value in
			self.cur.execute(query, tuple(params)) ][::-1]

	def save_value(self, timestamp, path, value):
		query = 'INSERT INTO sensorino VALUES ( ?, ?, ?, ?, ?, ?, 1 )'
		params = [ int(timestamp * 1000),
			path[0], path[1], None, None,
			value ]

		if len(path) >= 3:
			params[3] = datatype_to_sqlite(path[2])
		if len(path) >= 4:
			params[4] = path[3]

		params = tuple(params)
		self.cur.execute(query, params)

		# The return value to be used as parameter to a potential
		# mark_saved_value_failure call
		return params[0:5]

	def mark_saved_value_failure(self, change):
		# In the typical case a rollback would do, too

		query = 'UPDATE sensorino SET success = 0 WHERE ' + \
			'timestamp IS ? AND node_addr IS ? AND ' + \
			'svc_id IS ? AND datatype IS ? AND chan_id IS ?'
		params = change

		self.cur.execute(query, params)

	def get_console_at_timestamp(self, timestamp):
		params = ()

		# Get the last 64 lines preceding the timestamp
		if timestamp is not None:
			time_cond = 'WHERE timestamp <= ? '
			params += ( int(timestamp * 1000), )
		else:
			time_cond = ''

		query = 'SELECT timestamp, line FROM console ' + time_cond + \
			'ORDER BY timestamp DESC LIMIT 64'

		return [ ( 0.001 * timestamp, line ) for timestamp, line in
			self.cur.execute(query, params) ][::-1]

	def get_console_current(self):
		return self.get_console_at_timestamp(None)

	def save_console_line(self, timestamp, line):
		query = 'INSERT INTO console VALUES ( ?, ? )'
		params = ( int(timestamp * 1000), line )

		self.cur.execute(query, params)

	def get_floorplan_at_timestamp(self, timestamp):
		params = ()

		# Get the last floorplan version preceding the timestamp
		if timestamp is not None:
			time_cond = 'WHERE timestamp <= ? '
			params += ( int(timestamp * 1000), )
		else:
			time_cond = ''

		query = 'SELECT version FROM floorplan ' + time_cond + \
			'ORDER BY timestamp DESC LIMIT 1'

		result = self.cur.execute(query, params)

		val = self.cur.fetchone()
		if val is None:
			return None
		return val[0]

	def get_floorplan_current(self):
		return self.get_floorplan_at_timestamp(None)

	def save_floorplan_version(self, timestamp, data):
		query = 'INSERT INTO floorplan VALUES ( ?, ? )'
		params = ( int(timestamp * 1000), data )

		self.cur.execute(query, params)

	def commit(self):
		self.conn.commit()
