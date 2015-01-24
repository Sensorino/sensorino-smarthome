# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# Basic and quite generic timeout support for asyncore.
#
import sched
import asyncore
import time

timefunc = time.time

def delayfunc(timeout):
	asyncore.loop(timeout=timeout, count=1)

scheduler = sched.scheduler(timefunc, delayfunc)

def loop():
	global scheduler
	while True:
		if scheduler.empty():
			asyncore.loop(count=1)
		else:
			scheduler.run()

def call_later(fun, delay, args=None):
	global scheduler
	return scheduler.enter(delay, 0, fun, [] if args is None else args)
cancel = scheduler.cancel
