#! /usr/bin/python
#
# Sensorino smarthome server
#
# Author: Andrew Zaborowski <andrew.zaborowski@intel.com>
#
# This software is provided under the 3-clause BSD license.
#
# This is a gateway script for the Sensorino Server to be able to
# discover and use some Bluetooth Low-Energy devices.  When run, it'll
# connect to the server and create a Sensorino node for each supported
# Bluetooth device, with a Sensorino data channel for each supported
# characteristic, grouped into Sensorino services by their membership
# within GATT services.

import dbus
import dbus.mainloop.glib
import gobject
import bluezutils
import math

import base_lib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

device_queue = []

class bt_device(object):
	devices = {}

	def __init__(self, path):
		self.path = path
		self.discovered = False
		self.known_characteristic_paths = {}
		self.characteristics = {}

		self.sensorino_node = None
		self.sensorino_services = {}

		obj = bus.get_object(bluezutils.SERVICE_NAME, self.path)
		props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
		self.addr = props.Get(bluezutils.DEVICE_INTERFACE, 'Address')

		# State values:
		#  queued:  connection attempt scheduled when the time comes
		#  busy:    currently connected to or being connected to
		#  unknown: not queued, may be out-of-range.  In this case
		#		self.known_characteristic_paths
		#		being non-empty indicates that we want to
		#		connect to this device when there's an
		#		indication that it may be online
		self.state = 'unknown'

		# Auto-disconnect when this expires
		self.device_busy_timeout = None

		self.devices[path] = self

	def queue(self):
		global device_queue, run_queue
		if self.state != 'unknown':
			return
		self.state = 'queued'
		if self not in device_queue:
			empty = not device_queue
			device_queue.append(self)
			if empty:
				gobject.idle_add(run_queue)

	def dequeue(self):
		global device_queue
		if self.state == 'queued':
			self.state = 'unknown'
		if self in device_queue:
			device_queue.remove(self)

	def connect(self):
		global device_queue, run_queue
		if self.state == 'busy':
			return
		self.state = 'busy'
		if self in device_queue:
			device_queue.remove(self)

		obj = bus.get_object(bluezutils.SERVICE_NAME, self.path)
		dev = dbus.Interface(obj, bluezutils.DEVICE_INTERFACE)
		props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')

		paired = props.Get(bluezutils.DEVICE_INTERFACE, 'Paired')

		name = str(self.addr)

		# Tell bluez to connect to this device for 10s, assume it'll
		# manage to complete all the basic discovery in that time and
		# call relevant listeners, then .Disconnect if it doesn't do
		# that earlier automatically.  When we're pairing it seems the
		# basic discovery is finished at the moment .Pair() returns
		# but we can't rely on that, .Pair() will fail if .Paired is
		# True so we must use .Connect() meaning that the discovery
		# is asynchronous.
		try:
			if self.discovered or paired:
				print('Connecting to ' + name)
				dev.Connect()
			else:
				print('Pairing with ' + name + ' for scanning')
				dev.Pair()
		except Exception as e:
			print('Could not connect to ' + name + ': ' + str(e))
			self.state = 'unknown'
			#gobject.idle_add(run_queue)
			return

		self.device_busy_timeout = \
			gobject.timeout_add(10000, self.to_disconnect, dev)

	def to_disconnect(self, dev):
		self.device_busy_timeout = None
		self.disconnect(dev)
		return False

	def disconnect(self, dev):
		if self.device_busy_timeout is not None:
			gobject.source_remove(self.device_busy_timeout)
			self.device_busy_timeout = None

		dev.Disconnect()

	def connected(self):
		global device_queue
		self.state = 'busy'
		if self in device_queue:
			device_queue.remove(self)

		# If this device acutally has characteristics that we're
		# interested in, we change our mind and will not auto-
		# disconnect.
		if self.known_characteristic_paths and \
				self.device_busy_timeout is not None:
			gobject.source_remove(self.device_busy_timeout)
			self.device_busy_timeout = None

		for path in self.known_characteristic_paths:
			if path not in self.characteristics:
				characteristic_class = \
					self.known_characteristic_paths[path]
				self.characteristics[path] = \
					characteristic_class(path, self)
			self.characteristics[path].active()

	def disconnected(self):
		global device_queue
		prev_state = self.state
		self.state = 'unknown'

		if self in device_queue:
			device_queue.remove(self)

		name = str(self.addr)

		if prev_state == 'busy':
			gobject.idle_add(run_queue)

			print('Disconnected from ' + name)

			for path in self.characteristics:
				self.characteristics[path].inactive()

	def handle_characteristic(self, path, cls):
		if path in self.known_characteristic_paths:
			return

		self.known_characteristic_paths[path] = cls
		if self.state == 'unknown':
			self.queue()
		elif self.state == 'busy':
			# Make sure we instantiate this characteristic
			self.connected()

	@staticmethod
	def busy():
		for path in bt_device.devices:
			if bt_device.devices[path].state == 'busy':
				return True
		return False

def run_queue():
	while device_queue and not bt_device.busy():
		device_queue[0].connect()
	return False

def device_change(path, changed):
	if path in bt_device.devices:
		dev = bt_device.devices[path]
	else:
		dev = bt_device(path)

	if 'Connected' in changed:
		obj = bus.get_object(bluezutils.SERVICE_NAME, path)
		props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')

		if props.Get(bluezutils.DEVICE_INTERFACE, 'Connected'):
			dev.connected()
		else:
			dev.disconnected()

	if not dev.discovered and ('Paired' in changed or
			'Connected' in changed):
		obj = bus.get_object(bluezutils.SERVICE_NAME, path)
		props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
		paired = props.Get(bluezutils.DEVICE_INTERFACE, 'Paired')
		connected = props.Get(bluezutils.DEVICE_INTERFACE, 'Connected')

		# Must test both Connected and Paired because bluetoothd will
		# remove all the service, characteristic, etc. data after some
		# time from last activity on a device, but will keep Paired
		# set to True.  Neither Paired nor Connected alone set to True
		# nor populated UUIDs mean that the sub-objects are present.
		if connected and paired:
			dev.discovered = True

	if dev.known_characteristic_paths or not dev.discovered:
		dev.queue()
	else:
		dev.dequeue()

# Services we know how to handle
known_characteristics = {}

# This is currently only called when the object/interface is created
def characteristic_change(path, changed):
	global known_characteristics

	obj = bus.get_object(bluezutils.SERVICE_NAME, path)
	props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')

	# TODO: call a function to first check UUID and then also go
	# through all associated descriptors and figure out based on them
	# if we could possibly support the characteristic...  If the device
	# is disconnected though, we'd need to queue it and remember to
	# re-check all the characteristics when we can read their
	# descriptors.
	uuid = props.Get(bluezutils.GATT_CHAR_INTERFACE, 'UUID')
	if uuid not in known_characteristics:
		return

	svc_path = props.Get(bluezutils.GATT_CHAR_INTERFACE, 'Service')
	svc_obj = bus.get_object(bluezutils.SERVICE_NAME, svc_path)
	svc_props = dbus.Interface(svc_obj, 'org.freedesktop.DBus.Properties')

	dev_path = svc_props.Get(bluezutils.GATT_SVC_INTERFACE, 'Device')
	# Raise an exception if device doesn't exist
	dev = bt_device.devices[dev_path]

	dev.handle_characteristic(path, known_characteristics[uuid])

class bt_base_service(base_lib.base_service):
	def __init__(self, svc_id):
		super(bt_base_service, self).__init__(svc_id)
		self.gatt_chars = []
		self.act_channels = {}

	def add_characteristic(self, char):
		pos = len(self.gatt_chars)
		self.gatt_chars.append(char)

		for chan in char.channels:
			if not chan.writable:
				continue
			chan_num = chan.get_chan_num(self)
			act_channels[chan.type, chan_num] = pos

	def set_values(self, value_map):
		super(bt_base_service, self).set_values(value_map)

		# Split the value_map by characteristic.. may be unnecessary
		chars = {}
		for chan_id in value_map:
			if chan_id not in self.act_channels:
				continue
			char_num = self.act_channels[chan_id]
			if char_num not in chars:
				chars[char_num] = {}
			chars[char_num][chan_id] = value_map[chan_id]

		for char_num in chars:
			self.gatt_chars[char_num].set_values(chars[chan_num])

class bt_characteristic(object):
	def __init__(self, path, dev):
		self.path = path
		self.dev = dev

		# Derive the Sensorino service ID from GATT parent service
		# for this characteristic
		self.obj = bus.get_object(bluezutils.SERVICE_NAME, self.path)
		self.props = dbus.Interface(self.obj,
				'org.freedesktop.DBus.Properties')
		self.char = dbus.Interface(self.obj,
				bluezutils.GATT_CHAR_INTERFACE)

		svc_path = self.props.Get(bluezutils.GATT_CHAR_INTERFACE,
				'Service')
		short_id = str(svc_path)[-4:]
		# Use the service handle but reserve the IDs 0..9
		service_id = int(short_id, 16) + 10

		if dev.sensorino_node is None:
			dev.sensorino_node = base_lib.base_create_node(dev.addr)

		if service_id not in dev.sensorino_services:
			svc = bt_base_service(service_id)
			dev.sensorino_services[service_id] = svc
			dev.sensorino_node.add_service(svc)

		self.service = dev.sensorino_services[service_id]

		# TODO: figure out how to make the channel order in the
		# Sensorino service independent of the characteristic
		# discovery order

		# TODO: also make sure we're flexible enough to allow a
		# subclass to create just one Sensorino channel from
		# multiple characteristics

		self.channels = []
		self.is_active = False

		self.props.connect_to_signal('PropertiesChanged',
				self.properties_changed)
		self.poll_id = None
		self.poll_interval = None

	def save_channels(self):
		self.service.add_characteristic(self)

	def active(self):
		if self.is_active:
			return
		self.is_active = True

		# TODO: check if we have any read-only channels registered
		if self.poll_interval is None:
			return

		try:
			self.char.StartNotify()
		except Exception as e:
			print('Characteristic StartNotify() failed: ' + str(e))
			self.poll_id = gobject.timeout_add(self.poll_interval,
					self.poll)
		try:
			self.val = self.char.ReadValue()
		except Exception as e:
			print('Characteristic ReadValue() failed: ' + str(e))
			return

		self.handler(self.val)

	def inactive(self):
		if not self.is_active:
			return
		self.is_active = False

		# TODO: check if we have any read-only channels registered

		try:
			self.char.StopNotify()
		except Exception as e:
			print('Characteristic StopNotify() failed: ' + str(e))

		if self.poll_id is not None:
			gobject.source_remove(self.poll_id)
			self.poll_id = None

		self.publish_values(*[ None for chan in self.channels \
				if not chan.writable ])

	def properties_changed(self, interface, changed, invalidated):
		if self.poll_id is not None:
			return
		if interface == bluezutils.GATT_CHAR_INTERFACE and \
				'Value' in changed:
			self.val = changed['Value']
			self.handler(self.val)

	def poll(self):
		try:
			new_val = self.char.ReadValue()
		except Exception as e:
			print('Characteristic ReadValue() failed: ' + str(e))
			return
		if self.val != new_val:
			self.val = new_val
			self.handler(self.val)

		return True

	def publish_values(self, *args):
		value_map = {}
		for i, chan in enumerate(self.channels):
			if chan.writable:
				continue
			chan_num = chan.get_chan_num(self.service)
			value_map[chan.type, chan_num] = args[i]
		if value_map:
			self.service.publish_values(value_map)

# Sensor Tag characteristics

class sensor_tag_ir_temperature_char(bt_characteristic):
	uuid = 'f000aa01-0451-4000-b000-000000000000'
	config_uuid = 'f000aa02-0451-4000-b000-000000000000'

	def __init__(self, path, dev):
		super(sensor_tag_ir_temperature_char, self). \
			__init__(path, dev)

		self.channels = [
			self.service.create_channel('temperature', False),
			self.service.create_channel('temperature', False),
		]
		self.save_channels()
		self.channels[0].set_name('Ambient temperature')
		self.channels[1].set_name('Object temperature')

		self.enabled = False
		self.poll_interval = 5000
		gobject.timeout_add(1000, self.enable_sensor)

	def enable_sensor(self):
		svc_path = self.props.Get(bluezutils.GATT_CHAR_INTERFACE,
				'Service')
		cfg_path = None

		objs = bluezutils.get_managed_objects(bus)
		for path, interfaces in objs.iteritems():
			if bluezutils.GATT_CHAR_INTERFACE not in interfaces or \
					not path.startswith(svc_path):
				continue
			char = interfaces[bluezutils.GATT_CHAR_INTERFACE]
			if char['UUID'] == self.config_uuid:
				cfg_path = path

		cfg_obj = bus.get_object(bluezutils.SERVICE_NAME, cfg_path)
		cfg_char = dbus.Interface(cfg_obj,
				bluezutils.GATT_CHAR_INTERFACE)

		cfg_char.WriteValue([ 0x01 ])

		self.enabled = True
		return False

	def handler(self, val):
		if not self.is_active or not self.enabled:
			return

		# Ambient / Die temperature
		temp0 = ((val[3] << 8) | val[2]) / 128.0

		# Target / Object temperature
		raw1 = (val[1] << 8) | val[0]
		if raw1 > 32767:
			raw1 -= 65536
		vobj = raw1 * 0.00000015625
		tdie = temp0 + 273.15
		s0 = 5.593E-14
		a1 = 1.75E-3
		a2 = -1.678E-5
		b0 = -2.94E-5
		b1 = -5.7E-7
		b2 = 4.63E-9
		c2 = 13.4
		tref = 298.15
		s = s0 * (1 + a1 * (tdie - tref) + a2 * \
			math.pow(tdie - tref, 2))
		vos = b0 + b1 * (tdie - tref) + b2 * \
			math.pow(tdie - tref, 2)
		fobj = (vobj - vos) + c2 * math.pow(vobj - vos, 2)
		temp1 = math.pow(math.pow(tdie, 4) + fobj / s, 0.25) - 273.15

		self.publish_values(temp0, temp1)

class sensor_tag_simple_key_service_char(bt_characteristic):
	uuid = '0000ffe1-0000-1000-8000-00805f9b34fb'

	def __init__(self, path, dev):
		super(sensor_tag_simple_key_service_char, self). \
			__init__(path, dev)

		self.channels = [
			self.service.create_channel('switch', False),
			self.service.create_channel('switch', False),
		]
		self.save_channels()
		self.channels[0].set_name('Left button')
		self.channels[1].set_name('Right button')

	def handler(self, val):
		if not self.is_active:
			return

		self.publish_values((val[0] >> 0) & 1, (val[0] >> 1) & 1)

char_classes = [
	sensor_tag_ir_temperature_char,
	#sensor_tag_simple_key_service_char,
]
for char_class in char_classes:
	known_characteristics[char_class.uuid] = char_class

adapter = bluezutils.find_adapter(bus)

# Connect the D-Bus main loop with the base_lib main loop
base_lib.base_init(adapter.object_path)
def base_run(s, *args):
	base_lib.base_run(0)
	return True
gobject.io_add_watch(base_lib.s,
		gobject.IO_IN | gobject.IO_ERR | gobject.IO_HUP, base_run)

# Make sure adapter is powered on (UP in hciconfig)
adapter_props = dbus.Interface(adapter, 'org.freedesktop.DBus.Properties')
adapter_props.Set(bluezutils.ADAPTER_INTERFACE, 'Powered', dbus.Boolean(True))

# Subscribe to all signals that could indicate a device was just detected
bluezutils.device_listeners.append(device_change)

bluezutils.characteristic_listeners.append(characteristic_change)

bluezutils.init_listeners(bus)

# Also process devices that have been discovered earlier
# TODO: cmdline option to skip this
for path, interfaces in bluezutils.get_managed_objects(bus).iteritems():
	if bluezutils.DEVICE_INTERFACE in interfaces:
		device_change(path, interfaces[bluezutils.DEVICE_INTERFACE])

for path, interfaces in bluezutils.get_managed_objects(bus).iteritems():
	if bluezutils.GATT_CHAR_INTERFACE in interfaces:
		characteristic_change(path,
				interfaces[bluezutils.GATT_CHAR_INTERFACE])

try:
	adapter.StopDiscovery()
except:
	pass
adapter.StartDiscovery()

mainloop = gobject.MainLoop()
try:
	mainloop.run()
except KeyboardInterrupt as e:
	pass
except base_lib.BaseDisconnect as e:
	pass
finally:
	base_lib.base_done()
