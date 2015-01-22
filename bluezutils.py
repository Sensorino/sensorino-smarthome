'''test/bluezutils.py, test/test-discovery.py from the bluez source tree with
a few changes'''
import dbus

SERVICE_NAME = "org.bluez"
ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
DEVICE_INTERFACE = SERVICE_NAME + ".Device1"
GATT_SVC_INTERFACE = SERVICE_NAME + ".GattService1"
GATT_CHAR_INTERFACE = SERVICE_NAME + ".GattCharacteristic1"
GATT_DESC_INTERFACE = SERVICE_NAME + ".GattDescriptor1"

def get_managed_objects(bus):
	manager = dbus.Interface(bus.get_object("org.bluez", "/"),
				"org.freedesktop.DBus.ObjectManager")
	return manager.GetManagedObjects()

def find_adapter(bus, pattern=None):
	return find_adapter_in_objects(bus, get_managed_objects(bus), pattern)

def find_adapter_in_objects(bus, objects, pattern=None):
	for path, ifaces in objects.iteritems():
		adapter = ifaces.get(ADAPTER_INTERFACE)
		if adapter is None:
			continue
		if not pattern or pattern == adapter["Address"] or \
							path.endswith(pattern):
			obj = bus.get_object(SERVICE_NAME, path)
			return dbus.Interface(obj, ADAPTER_INTERFACE)
	raise Exception("Bluetooth adapter not found")

def find_device(bus, device_address, adapter_pattern=None):
	return find_device_in_objects(bus, get_managed_objects(bus),
			device_address, adapter_pattern)

def find_device_in_objects(bus, objects, device_address, adapter_pattern=None):
	path_prefix = ""
	if adapter_pattern:
		adapter = find_adapter_in_objects(bus, objects, adapter_pattern)
		path_prefix = adapter.object_path
	for path, ifaces in objects.iteritems():
		device = ifaces.get(DEVICE_INTERFACE)
		if device is None:
			continue
		if (device["Address"] == device_address and
						path.startswith(path_prefix)):
			obj = bus.get_object(SERVICE_NAME, path)
			return dbus.Interface(obj, DEVICE_INTERFACE)

	raise Exception("Bluetooth device not found")

device_listeners = []
service_listeners = []
characteristic_listeners = []

def init_listeners(bus):
	bus.add_signal_receiver(interfaces_added,
			dbus_interface = "org.freedesktop.DBus.ObjectManager",
			signal_name = "InterfacesAdded")

	bus.add_signal_receiver(interfaces_removed,
			dbus_interface = "org.freedesktop.DBus.ObjectManager",
			signal_name = "InterfacesRemoved")

	# TODO: also listen for property changes on the other interfaces
	bus.add_signal_receiver(properties_changed,
			dbus_interface = "org.freedesktop.DBus.Properties",
			signal_name = "PropertiesChanged",
			arg0 = DEVICE_INTERFACE,
			path_keyword = "path")

def device_notify(path, changed):
	for listener in device_listeners:
		listener(path, changed)

def service_notify(path, changed):
	for listener in service_listeners:
		listener(path, changed)

def characteristic_notify(path, changed):
	for listener in characteristic_listeners:
		listener(path, changed)

def interfaces_added(path, interfaces):
	# TODO: seems like we need to cache all the objects' interfaces
	# and see if the sum of the already notified interfaces and the new
	# ones contains the two interfaces that we want, since sometimes
	# they will not be created at the same times.
	if DEVICE_INTERFACE in interfaces and \
			'org.freedesktop.DBus.Properties' in interfaces:
		device_notify(path, interfaces[DEVICE_INTERFACE])
	if GATT_SVC_INTERFACE in interfaces and \
			'org.freedesktop.DBus.Properties' in interfaces:
		service_notify(path, interfaces[GATT_SVC_INTERFACE])
	if GATT_CHAR_INTERFACE in interfaces and \
			'org.freedesktop.DBus.Properties' in interfaces:
		characteristic_notify(path, interfaces[GATT_CHAR_INTERFACE])

def interfaces_removed(path, interfaces):
	if DEVICE_INTERFACE in interfaces:
		device_notify(path, None)
	if GATT_SVC_INTERFACE in interfaces:
		service_notify(path, None)
	if GATT_CHAR_INTERFACE in interfaces:
		characteristic_notify(path, None)

def properties_changed(interface, changed, invalidated, path):
	if interface != DEVICE_INTERFACE:
		return

	device_notify(path, changed)
