#! /usr/bin/python
#
# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# This script simulates a trivial sensor node setup so that the server
# can be dry-run tested easily.  When the server is running, start this
# script to make it connect to localhost port 8888 and make it appear as
# if a Base node was present and able to communicate over-the-air with
# a single Sensorino node at address 10.  That remote node has two
# services:
#   * a light switch, which someone stubbornly keeps flipping
#     every 20 seconds indefinitely.
#   * a relay that controls the light in the room.

import time
import sys

import base_lib

node_addr = 10

relay_svcs = [ 2 ]
switch_svcs = [ 3 ]

class relay_channel(base_lib.base_channel):
	def set_value(self, val):
		base_lib.base_channel.set_value(self, val)
		if val:
			sys.stderr.write('It\'s bright again.\n')
		else:
			sys.stderr.write('It\'s dark now.\n')

node = base_lib.base_create_node(node_addr)

switches = [ node.create_service(svc_id).create_channel('switch', False, True) \
	for svc_id in switch_svcs ]

for svc_id in relay_svcs:
	node.create_service(svc_id).add_channel(relay_channel('switch', \
			True, True))

def handle_20s_timeout():
	switches[0].publish_value(not switches[0].get_value())

base_lib.base_init()
last_ts = time.time()
while 1:
	now = time.time()
	timeout = 20.0 - (now - last_ts)
	if timeout < 0:
		handle_20s_timeout()
		last_ts = now
		continue

	try:
		base_lib.base_run(timeout)
	except KeyboardInterrupt:
		break
	except base_lib.BaseDisconnect:
		break

base_lib.base_done()
