Sensorino Smart-Home Server
===========================

See further down for general information about the Sensorino project.  This subproject forms the central piece of a smart-home network, being the main control point in an architecture with any number of remote nodes and one server.  The nodes control actual sensor and actuators directly connected to them while the server tracks their state at any moment, maintains a database of past activity and provides the User Interface.  It communicates with nodes using the _Sensorino protocol_ but also integrates with other technologies, currently Bluetooth Low-Energy.  Your network may be comprised completely of consumer Bluetooth devices, DIY _Sensorino nodes_ or any combination thereof.

The user interface is web-based and is built around an editable 2D floor-plan.  When a new remote node is detected, it's queried for its services (discovered) and the user is alerted that they can now switch to the edit mode to locate the device on the 2D map and decide the widget type that will visualise incoming data or send commands to the service when clicked.  Updates from the nodes are immediately reflected in the floorplan view.  The history of each data channel's activity can be browsed as raw values and charts of various types.

The user interface for the Sensorino Rule Engine is still work-in-progress.

Usage, requirements
-------------------

The server has no hard dependencies beyond Python 2.7+.  It makes use of packages that ship with python such as _SQLite3_ and _asyncore_, except for the Bluetooth support (see below).  Installation boils down to cloning the repository and launching the server (`./server.py`) and one or more base scripts as appropriate.  The server will create a file-backed database in the local directory and use it for persistency and retrieving historical data.

The base script connects the server to a specific radio adapter connected to the system.  The following base scripts are available:

* `base-connect.py` opens a local serial port or a USB-to-Serial adapter to talk to the Sensorino network through a local Sensorino base node (gateway).

* `base-test.py` simulates a Sensorino base and one Sensorino remote node with two basic services.  This can be used for testing during development or demoing / getting a feel of the Sensorino user experience without any hardware investment.

* `base-ble-dbus.py` connects to the bluez daemon over D-Bus and searches for compatible Bluetooth devices, services and characteristics.

The server is pretty light-weight and can be successfully used both on a laptop and on tiny Linux machines such as the 5cm x 5cm TP-Link TL-WR703N cheap network router.  The web-interface is immediately available and by default visible from network on port 8000 of the machine.  The interface and port to listen on can be changed in the file _config.py_.  There's currently no authentication mechanism so care must be taken for the selected port not to be visible publicly (except where desired) and only to the intended Local Area Network or remotely through something like a VPN.

The web interface currently requires a quite modern browser because of its use of HTML5 features and has only been tested with Firefox 2x and Chromium 3x versions.

Bluetooth Low-Energy support
----------------------------

This is currently more a proof of concept than a usable solution.  Since many Bluetooth adapters can only be connected to one remote device at a time without some form of time-division multiplexing you can currently only use one device at any time.  Multiplexing is relatively easy to add though.  Tested devices include TI _SensorTag_ and the _Yeelight Blue_ smart-lightbulb.

The _dbus-python_ library is required for this to work including its dependencies (_D-Bus_, _pygobject_) and a 5.2x or later version of _bluez_ compiled without disabling the experimental features.  Some distributions already include such recent bluez but need the `-E` switch added to the bluetoothd invocation in their init scripts, for other distributions an external repository is needed such as the [relevant Ubuntu PPA](https://launchpad.net/~vidplace7/+archive/ubuntu/bluez5).

The Sensorino Project
=====================

Sensorino is a set of opensource software and open hardware designs that form a base for cheap, small-scale sensor networks / home-automation / remote-control setups.  The project is based around Arduino-compatible boards and other cheap technologies, aiming at great experience at less than $5 for a basic network node.  It integrates with some other technologies and the software side is intentionally flexible to allow integrating newly emerging technologies.

Documentation of the system is work-in-progress and is located in the github wikis corresponding to the subprojects.

Contact
-------

sensorino@googlegroups.com is the open mailing list for the project.  You
can also submit specific feedback through the github Issues for each
specific subproject.

Components
----------

* Hardware -- any Atmega328-based board can be used for a base or remote Sensorino node.  This includes Arduino Pro Mini, Arduino Uno, Arduino Duemilanove, and compatible boards, including cheap clones.  For a remote node, a 5V power supply, an nRF24L01+ radio module and a choice of sensors or actuators are needed.  https://github.com/Sensorino/SensorinoHardware contains specialised, minimal board designs that can be used instead of piecing a node together from individual off-the-shelf boards.
* Sensorino firmware to be used on the remote- and base-nodes, which relays data between the sensors/actuators and the central node, and executes automation rules.  https://github.com/Sensorino/Sensorino contains the firmware's source code.
* The modified optiboot bootloader at https://github.com/balrog-kun/optiboot can be used together with the Sensorino firmware to provide over-the-air flashing support for remote nodes.
* Sensorino Server -- software that runs on a Linux-capable machine to provide an HTTP API to the whole Sensorino network and a web User Interface to give the user full control of the network.  The Arduino-based Base-node may be connected to the same machine or to a different computer and connect through TCP/IP.  The Server can also control devices that use some other radio technologies and protocols, such as some consumer Bluetooth Low-Energy (BLE) devices, to provide a unified interface to all installed devices.  https://github.com/Sensorino/sensorino-smarthome contains the server implementation.
