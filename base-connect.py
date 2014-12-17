#! /usr/bin/python
#
# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# This script communicates the Base node connected to the local machine's
# serial port (USB-serial, etc.) with the server process.  The script
# accepts only one argument, the path to the character device to which
# the Base is physically connected, e.g. /dev/ttyUSB0 or /dev/ttyACM0.
#
# You could probably do the same thing in one clever line of shell using
# standard shell commands such as a serial terminal and netcat.
#
# By default the server listens for Base communication on the localhost
# port 8888, but you can easily configure the server to run on a
# different machine from that which connects to the Base node, by editing
# config.py.  You can also connect multiple Bases, perhaps serving
# multiple sensor networks in different geographical locations, to one
# server, over network.

import socket
import termios
import config
import select
import sys
import os

f = open(sys.argv[1], 'r+')
attr = termios.tcgetattr(f)
# Pretty much cfmakeraw()
attr[0] = 0			# iflag
attr[1] = 0			# oflag
attr[2] = termios.CS8 | termios.CLOCAL | termios.CREAD # cflag
attr[3] = 0			# lflag
attr[4] = termios.B115200	# ispeed
attr[5] = termios.B115200	# ospeed

termios.tcsetattr(f, termios.TCSAFLUSH, attr)
sys.stderr.write('Connected to serial port\n')

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(config.base_server_address)
sys.stderr.write('Connected to server\n')

while 1:
	try:
		r, w, e = select.select([ f, s ], [], [ f, s ])
	except KeyboardInterrupt:
		break
	if len(e):
		break

	if f in r:
		d = os.read(f.fileno(), 8192)
		if not len(d):
			break
		s.sendall(d)
	if s in r:
		os.write(f.fileno(), s.recv(8192))

sys.stderr.write('Disconnecting\n')
s.close()
f.close()
