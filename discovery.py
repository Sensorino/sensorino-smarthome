# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# The Discovery Agent -- listens for events and if it sees any
# hint of a new sensor node or new services in a node, it will
# query their descriptions and possibly also current states.  It'll
# then mark the node, or the service, as discovered and ignore it
# from then on.
#
import sensorino

class agent():
	def __init__(self, sensorino_state):
		self.state = sensorino_state

		self.req_handlers = []

		self.state.subscribe_changes(self.handle_sensorino_state_change)

	def subscribe_reqs(self, handler):
		self.req_handlers.append(handler)

	def unsubscribe_reqs(self, handler):
		self.req_handlers.remove(handler)

	def get_undiscovered(self, change_set):
		nodes = {}
		# TODO: ignore deletions
		for path in change_set:
			node_addr = path[0]
			if node_addr not in nodes:
				nodes[node_addr] = {}

			if len(path) < 2 or not isinstance(path[1], int):
				continue
			svc_addr = path[1]
			nodes[node_addr][svc_addr] = None

		tree = self.state.get_state_tree()
		for node_addr in nodes:
			svcs = nodes[node_addr]
			node_state = tree[node_addr]

			if '_discovered' not in tree[node_addr]:
				yield ( node_addr, )

			# Add the list of services known to the service manager
			# to the list of services in the change set.
			if 0 in node_state and 'serviceId' in node_state[0]:
				for svc_addr in node_state[0]['serviceId']:
					svcs[svc_addr] = None

			for svc_addr in svcs:
				if svc_addr in [ 0, 1 ]: # Special services
					continue

				if svc_addr not in node_state or \
						'_discovered' not in \
						node_state[svc_addr]:
					yield ( node_addr, svc_addr )

	def query_path(self, path):
		if len(path) == 1:
			msg = {
				'to': path[0],
				'type': 'request',
				'serviceId': 0,
			}
		else:
			msg = {
				'to': path[0],
				'type': 'request',
				'serviceId': path[1],
				'dataType': 'dataType',
			}

		for handler in self.req_handlers:
			handler(msg)

	def handle_sensorino_state_change(self, change_set, error=False):
		# TODO: once we have timer support, add delays between
		# consecutive requests and between a publish and a request

		# TODO: in sensorino_state, or maybe in the base, must add
		# a busy bit to remember if we have any request pending.

		for path in self.get_undiscovered(change_set):
			self.query_path(path)

			# Only one query at a time
			break
