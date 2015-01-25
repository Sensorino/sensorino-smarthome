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
import timers
import random

class agent():
	def __init__(self, sensorino_state):
		self.state = sensorino_state

		self.req_handlers = []

		self.to_query = set()
		self.timeout = None

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

			# For now, look for all iffy services within the node
			for svc_addr in node_state:
				if not isinstance(svc_addr, int):
					continue
				if svc_addr in [ 0, 1 ]: # Special services
					continue

				if '_outdated' in node_state[svc_addr]:
					yield ( node_addr, svc_addr, None )

	def query_path(self, path):
		if len(path) == 1:
			msg = {
				'to': path[0],
				'type': 'request',
				'serviceId': 0,
			}
		elif len(path) == 2:
			msg = {
				'to': path[0],
				'type': 'request',
				'serviceId': path[1],
				'dataType': 'dataType',
			}
		else:
			msg = {
				'to': path[0],
				'type': 'request',
				'serviceId': path[1],
			}

		for handler in self.req_handlers:
			handler(msg)

	def update(self, run_queue):
		work_pending = False
		new_queue = set()

		for path in self.get_undiscovered(self.to_query):
			# Check if we have no ongoing requests with this node
			if run_queue and self.state.queue_empty(path[0]):
				# Send the query
				self.query_path(path)

				run_queue = False

				# Don't re-add this path to the queue
				# TODO: also add it to some sort of cache of
				# last executed queries so we don't re-send
				# them endlessly on permanent errors.  But we
				# do want to re-try them every now and then,
				# say every could of minutes in case a device
				# happens to come back online.
				continue

			new_queue.add(path)
			if not run_queue and not work_pending and \
					self.state.queue_empty(path[0]):
				work_pending = True

		self.to_query = new_queue
		if work_pending:
			self.schedule()

	def schedule(self):
		if self.timeout is not None:
			timers.cancel(self.timeout)

		# Make the delay between an incoming publish and any requests
		# resulting from it (and consecuently also between consecutive
		# agent requests) slightly random to avoid consistently
		# stepping on somebody else's toes.  This is similar to the
		# discovery mechanism in Bluetooth with random back-off times.
		# Make the perdiod something between 500ms and 5s
		delay = random.random() * (5 - 0.5) + 0.5
		self.timeout = timers.call_later(self.run_queue, delay)

	def handle_sensorino_state_change(self, change_set, error=False):
		self.to_query |= change_set

		self.update(False)

	def run_queue(self):
		self.timeout = None

		self.update(True)
