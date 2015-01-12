function nodebrowser(obj, sensorino_state, handler) {
	this.obj = obj;
	this.state = sensorino_state;
	this.nodes = {};
	this.selection = {};
	this.hilighted = {};

	obj.classList.add('browser');

	this.click_handler = function(evt) {
		var chan = evt.target;
		while (!('chan_num' in chan))
			chan = chan.parentNode;
		handler([ chan.node_addr, chan.svc_id, chan.chan_type, chan.chan_num ]);
	}

	this.over_handler = function(evt) {
		var chan = evt.target;
		while (!('chan_num' in chan))
			chan = chan.parentNode;
		var chan_name = chan.chan_type.substr(0, 1).toUpperCase() +
			chan.chan_type.substr(1) + ' ' + chan.chan_num + ' ' +
			(chan.is_sensor ? 'sensor' : 'actuator') + ' in service ' +
			chan.svc_id + ' in Node ' + chan.node_addr;
		set_tip(chan_name, 'browser');
	}
	this.out_handler = function(evt) {
		/* Poor man's mouseleave - unreliable */
		if ((evt.relatedTarget || evt.toElement) === evt.target.parentNode)
			clear_tip('browser');
	}

	/*
	 * Need a new function so it gets a unique pointer value we can use to
	 * unsubscribe later.
	 */
	var this_obj = this;
	this.update_handler = function() { this_obj.update_nodes(); };
	this.state.subscribe_updates(this.update_handler);
	this.update_nodes();
}

/* The creator must call this when widget is deleted or we'll leak references */
nodebrowser.prototype.cleanup = function() {
	this.state.unsubscribe_updates(this.update_handler);
}

nodebrowser.prototype.update_nodes = function() {
	/* Update nodes if modified */
	for (var node_addr_str in this.state.nodes) {
		if (('' + node_addr_str).startsWith('_'))
			continue;

		this.update_node(node_addr_str);
	}

	/* Drop nodes no longer existing */
	for (var node_addr_str in this.nodes)
		if (!(node_addr_str in this.state.nodes)) {
			this.obj.removeChild(this.nodes[node_addr_str]);
			delete this.nodes[node_addr_str];
		}
}

nodebrowser.prototype.update_node = function(node_addr_str) {
	var node_data = this.state.nodes[node_addr_str];
	var node_addr = node_data._addr;

	/* Create new node box if node is new */
	if (!(node_addr_str in this.nodes)) {
		var node = document.createElement('div');
		node.classList.add('browser-node');
		node.name = document.createElement('span');
		node.name.classList.add('browser-nodename');

		node.appendChild(node.name);
		this.obj.appendChild(node);

		node.services = {};
		this.nodes[node_addr_str] = node;
	}

	/* Update contents */
	var node = this.nodes[node_addr_str];

	node.name.textContent = 'Node ' +
		('_name' in node_data ? node_data._name :
			('_addr' in node_data ? node_data._addr : node_addr_str));

	if ([ node_addr_str ] in this.hilighted)
		node.classList.add('browser-hilight');
	else
		node.classList.remove('browser-hilight');

	/* Update services in this node if modified */
	for (var svc_id_str in node_data) {
		if (('' + svc_id_str).startsWith('_') ||
				svc_id_str in this.state.special_services)
			continue;

		this.update_service(node_addr, svc_id_str);
	}

	/* Drop services no longer existing */
	for (var svc_id_str in node.services)
		if (!(svc_id_str in node_data)) {
			node.removeChild(node.services[svc_id_str]);
			delete node.services[svc_id_str];
		}
}

nodebrowser.prototype.update_service = function(node_addr, svc_id_str) {
	var svc_data = this.state.nodes[node_addr][svc_id_str];
	var svc_id = parseInt(svc_id_str);

	/* Create new service box if new service */
	if (!(svc_id_str in this.nodes[node_addr].services)) {
		var svc = document.createElement('div');
		svc.classList.add('browser-svc');
		svc.name = document.createElement('span');
		svc.name.classList.add('browser-svcname');

		svc.appendChild(svc.name);
		this.nodes[node_addr].appendChild(svc);

		svc.channels = {};
		this.nodes[node_addr].services[svc_id_str] = svc;
	}

	/* Update contents */
	var svc = this.nodes[node_addr].services[svc_id_str];

	svc.name.textContent = '_name' in svc_data ?
		svc_data._name : 'Service ' + svc_id_str;

	if ([ node_addr, svc_id ] in this.hilighted)
		svc.classList.add('browser-hilight');
	else
		svc.classList.remove('browser-hilight');

	/* Update channels in this service if modified */
	var chan_cnt = this.state.get_svc_channel_counts(svc_data);

	for (var typ in chan_cnt)
		for (var chan_num = 0; chan_num < chan_cnt[typ][0]; chan_num++)
			this.update_chan(node_addr, svc_id, typ, chan_num,
					chan_num < chan_cnt[typ][1]);

	/* Drop channels no longer existing */
	for (var chan_id in svc.channels) {
		var chan = svc.channels[chan_id];
		if (!(chan.chan_type in chan_cnt) ||
				chan.chan_num >= chan_cnt[chan.chan_type][0]) {
			svc.removeChild(chan);
			delete svc.channels[chan_id];
		}
	}
}

nodebrowser.prototype.update_chan = function(node_addr, svc_id, typ, chan_num,
		is_sensor_chan) {
	var data = null;
	var chan_id = typ + '_' + chan_num;
	var svc_data = this.state.nodes[node_addr][svc_id];
	if (typ in svc_data && chan_num in svc_data[typ])
		data = svc_data[typ][chan_num];

	/* Create new channel box if new channel */
	if (!(chan_id in this.nodes[node_addr].services[svc_id].channels)) {
		var chan = document.createElement('div');
		chan.classList.add('browser-chan');

		chan.name = document.createElement('span');
		chan.name.classList.add('browser-channame');

		chan.appendChild(chan.name);
		this.nodes[node_addr].services[svc_id].appendChild(chan);

		attach(chan, 'mousedown', this.click_handler, false);
		attach(chan, 'mouseover', this.over_handler, false);
		attach(chan, 'mouseout', this.out_handler, false);

		chan.node_addr = node_addr;
		chan.svc_id = svc_id;
		chan.chan_type = typ;
		chan.chan_num = chan_num;
		this.nodes[node_addr].services[svc_id].channels[chan_id] = chan;
	}

	/* Update contents */
	var chan = this.nodes[node_addr].services[svc_id].channels[chan_id];

	/* TODO: also look up name in any floorplan widgets that use this channel */
	chan.name.textContent = chan_id.substr(0, 1);

	if (data === null)
		chan.classList.add('browser-chan-unknown');
	else
		chan.classList.remove('browser-chan-unknown');

	if ([ chan.node_addr, chan.svc_id, chan.chan_type, chan.chan_num ] in
			this.selection)
		chan.classList.add('browser-chan-selected');
	else
		chan.classList.remove('browser-chan-selected');

	if ([ chan.node_addr, chan.svc_id, chan.chan_type, chan.chan_num ] in
			this.hilighted)
		chan.classList.add('browser-hilight');
	else
		chan.classList.remove('browser-hilight');

	chan.is_sensor = is_sensor_chan;
	chan.classList.add(is_sensor_chan ?
				'browser-chan-sensor' : 'browser-chan-actuator');
	chan.classList.remove(!is_sensor_chan ?
				'browser-chan-sensor' : 'browser-chan-actuator');
}

nodebrowser.prototype.select = function(addr) {
	/* Don't automatically deselect previous select, allow multiple selection
	 * (at least in theory) */
	this.selection[addr] = 1;

	if (!(addr[0] in this.nodes))
		return;
	var nd = this.nodes[addr[0]];
	if (!(addr[1] in nd.services))
		return;
	var svc = nd.services[addr[1]];
	var chan_id = addr[2] + '_' + addr[3];
	if (!(chan_id in svc.channels))
		return;
	this.update_chan(addr[0], addr[1], addr[2], addr[3],
			svc.channels[chan_id].is_sensor);
}

nodebrowser.prototype.deselect = function(addr) {
	delete this.selection[addr];

	if (!(addr[0] in this.nodes))
		return;
	var nd = this.nodes[addr[0]];
	if (!(addr[1] in nd.services))
		return;
	var svc = nd.services[addr[1]];
	var chan_id = addr[2] + '_' + addr[3];
	if (!(chan_id in svc.channels))
		return;
	this.update_chan(addr[0], addr[1], addr[2], addr[3],
			svc.channels[chan_id].is_sensor);
}

nodebrowser.prototype.hilight = function(addrs) {
	this.hilighted = {};
	var this_obj = this;
	addrs.forEach(function(addr) { this_obj.hilighted[addr] = null; });

	this.update_nodes();
}

/* vim: ts=2:
*/
