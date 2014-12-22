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

import socket
import config
import select
import time
import json
import base_server
import sensorino
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(config.base_server_address)

node_addr = 10
base_addr = 0

svc_manager_svcs = [ 0 ]
relay_svcs = [ 2 ]
switch_svcs = [ 3 ]

switch = [ True for svc in switch_svcs ]
relay = [ True for svc in relay_svcs ]

def handle_20s_timeout():
	global s, switch, node_addr, base_addr, switch_svcs
	switch[0] = not switch[0]
	obj = {
		'from': node_addr,
		'to': base_addr,
		'type': 'publish',
		'serviceId': switch_svcs[0],
		'switch': switch[0],
	}
	s.send(json.dumps(obj).encode('utf8'))

def handle_input(msg):
	global s, switch, relay, node_addr, base_addr, \
		svc_manager_svcs, relay_svcs, switch_svcs

	try:
		obj = sensorino.message_dict(json.loads(msg))
	except:
		ret = {
			'error': 'syntaxError',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	if 'type' not in obj:
		ret = {
			'error': 'noType',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	ok = 1
	for prop in [ 'from', 'serviceid' ]: # TODO: fuller checks
		if prop in obj and not isinstance(obj[prop], int):
			ok = 0
	for prop in [ 'switch' ]:
		if prop in obj and not isinstance(obj[prop], bool):
			ok = 0
	if 'dataType' in obj and (not isinstance(obj['dataType'], basestring) or
			obj['dataType'] not in sensorino.known_datatypes_dict):
		ok = 0

	if 'to' not in obj or not isinstance(obj['to'], int) or \
			obj['type'] not in \
			[ 'publish', 'set', 'request', 'err' ] or not ok:
		ret = {
			'error': 'structError',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	if obj['to'] != node_addr:
		ret = {
			'error': 'xmitError',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	all_svcs = svc_manager_svcs + relay_svcs + switch_svcs
	if 'serviceId' not in obj or obj['serviceId'] not in all_svcs:
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'err',
			'dataType': 'ServiceId',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	permitted_types = [ 'request' ]
	if obj['serviceId'] in relay_svcs:
		permitted_types.append('set')

	if obj['type'] not in permitted_types:
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'err',
			'serviceId': obj['serviceId'],
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	if obj['serviceId'] in svc_manager_svcs:
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'publish',
			'serviceId': all_svcs,
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	if obj['type'] == 'request' and 'dataType' in obj and \
			obj['dataType'].lower() not in [ 'datatype', 'switch' ]:
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'err',
			'serviceId': obj['serviceId'],
			'dataType': 'DataType',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	if obj['type'] == 'request' and 'dataType' in obj and \
			obj['dataType'].lower() == 'datatype':
		if obj['serviceId'] in relay_svcs:
			# Relay service accepts one value and publishes none
			cnt = [ 0, 1 ]
		else:
			# Switch service publish one value and accepts none
			cnt = 1
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'publish',
			'serviceId': obj['serviceId'],
			'count': cnt,
			'dataType': 'Switch',
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	# Now we know the request has no DataType or DataType is Switch
	if obj['type'] == 'request':
		if obj['serviceId'] in relay_svcs:
			val = relay[relay_svcs.index(obj['serviceId'])]
		else:
			val = switch[switch_svcs.index(obj['serviceId'])]
		ret = {
			'from': node_addr,
			'to': base_addr,
			'type': 'publish',
			'serviceId': obj['serviceId'],
			'switch': val,
		}
		s.send(json.dumps(ret).encode('utf8'))
		return

	# Now we know type is "set" and ServiceId is relay's
	idx = relay_svcs.index(obj['serviceId'])
	prev_relay = relay[idx]
	if 'switch' in obj:
		relay[idx] = obj['switch']
	else:
		relay[idx] = not relay[idx]

	if relay[idx] != prev_relay:
		if relay[idx]:
			sys.stderr.write('It\'s bright again.\n')
		else:
			sys.stderr.write('It\'s dark now.\n')

parse_state = base_server.obj_parser()
last_ts = time.time()
while 1:
	now = time.time()
	timeout = 20.0 - (now - last_ts)
	if timeout < 0:
		handle_20s_timeout()
		last_ts = now
		continue

	try:
		r, w, e = select.select([ s ], [], [ s ], timeout)
	except KeyboardInterrupt:
		break
	if len(e):
		break
	if not len(r):
		continue

	for chr in s.recv(8192).decode('utf-8'):
		obj = parse_state.handle_char(chr)
		if obj is not None:
			handle_input(obj)
s.close()
