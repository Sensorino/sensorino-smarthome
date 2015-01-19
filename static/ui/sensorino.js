function sensorino_state() {
	this.nodes = {};
	this.listeners = {};
	this.update_listeners = [];
	this.inited = 0;

	var status_obj = document.getElementById('conn-status');
	var this_obj = this;

	this.special_services = { "0": "Service Manager", "1": "Rule Engine" };

	function notify(path, oldval, newval, err) {
		var cbs = this_obj.listeners[path] || [];

		cbs.forEach(function(cb) { cb(path, oldval, newval, err); });
	}

	var chan_only_update;
	function update_all(path, state, parent, update, err) {
		var path_elem = path[path.length - 1];

		/* Check if we need to recurse */
		var old_recurse = state instanceof Object || state instanceof Array;
		var new_recurse = update instanceof Object || update instanceof Array;

		var visited = {};
		if (old_recurse) {
			function check_old(val, key) {
				update_all(path.concat([ key ]), val, state,
						(new_recurse && key in update) ? update[key] : null, err);
				visited[key] = null;
			}

			if (state instanceof Object)
				for (var key in state)
					check_old(state[key], key);
			else
				state.forEach(check_old);
		}

		if (!old_recurse || !new_recurse) {
			var oldval = old_recurse ? null : state;
			var newval = new_recurse ? null : update;

			if (update === null)
				delete parent[path_elem];
			else {
				state = new_recurse ? {} : update;
				parent[path_elem] = state;
			}

			if (oldval !== newval) { /* Do we want to use != here? */
				notify(path, oldval, newval, err);

				if (path.length != 4 || oldval === null || newval === null)
					chan_only_update = 0;
			}
		}

		if (new_recurse) {
			function check_new(val, key) {
				if (!(key in visited))
					update_all(path.concat([ key ]), null, state, val, err);
			}

			if (update instanceof Object)
				for (var key in update)
					check_new(update[key], key);
			else
				update.forEach(check_new);

			/*
			 * TODO: this should be done server-side, but we should also check
			 * just in-case:
			 * If state is now an empty list or object, delete it.
			 */
		}
	}

	function reset_state(state) {
		if (!this_obj.inited) {
			this_obj.nodes = state;
			this_obj.inited = 1;
			return;
		}

		update_all([], this_obj.nodes, null, state, false);
	}

	function handle_event(obj) {
		/* Check whether this is a whole new state object or a list of updates */
		if (!Array.isArray(obj)) {
			reset_state(obj);

			this_obj.update_listeners.forEach(function(cb) { cb[0]([[[]]]); });
			return;
		}

		/*
		 * Special case: first element equal to "error" means all events are
		 * result of an asynchronous error.
		 */
		var err = false;
		if (obj.length && obj[0] === "error") {
			err = true;
			obj = obj.slice(1);
		}

		/* Now we know this is an event -- a list of state elements that changed */
		chan_only_update = 1;
		for (var i = 0; i < obj.length; i++) {
			if (obj[i].length != 2) {
				console.log('Invalid change JSON', obj[i]);
				continue;
			}
			var path = obj[i][0];
			var update = obj[i][1];

			var state_elem = this_obj.nodes;
			for (var j = 0; j < path.length - 1; j++) {
				var path_elem = path[j];

				if (!(path_elem in state_elem)) {
					state_elem[path_elem] = {};
					chan_only_update = 0;
				}
				state_elem = state_elem[path_elem];
			}

			var path_elem = path[path.length - 1];
			update_all(path, path_elem in state_elem ? state_elem[path_elem] : null,
					state_elem, update, err);
		}

		this_obj.update_listeners.forEach(function(cb) {
					if (cb[1] || !chan_only_update)
						cb[0](obj);
				});
	}

	function update_status(stat, next) {
		status_obj.style.visibility = (stat === 'online') ? 'hidden' : 'visible';

		if (stat === 'connecting')
			status_obj.textContent = 'Connecting…';
		else if (stat === 'offline')
			status_obj.textContent = 'Not connected.  ' + 'Retrying in ' + next +
				(next > 1 ? ' seconds.' : ' second.');
	}

	stream('/api/stream/sensorino.json', handle_event, update_status);
}

/*
 * FIXME: in this configuration all handlers probably need to be
 * inline functions for unsubscription to work.
 */
sensorino_state.prototype.subscribe = function(addr, handler) {
	if (!(addr in this.listeners))
		this.listeners[addr] = [];
	this.listeners[addr].push(handler);
}

sensorino_state.prototype.unsubscribe = function(addr, handler) {
	var idx = this.listeners[addr].indexOf(handler);
	this.listeners[addr].splice(idx, 1);

	if (!this.listeners[addr].length)
		delete this.listeners[addr];
}

sensorino_state.prototype.subscribe_updates = function(handler, all) {
	this.update_listeners.push([ handler, !!all ]);
}

sensorino_state.prototype.unsubscribe_updates = function(handler) {
	for (var idx = 0; idx < this.update_listeners.length; idx++)
		if (this.update_listeners[idx][0] == handler) {
			this.update_listeners.splice(idx, 1);
			return;
		}
}

sensorino_state.prototype.get_channel = function(addr) {
	/*
	 * A channel address is 4 elements long:
	 * node address,
	 * service ID,
	 * data type,
	 * channel number
	 */
	try {
		return this.nodes[addr[0]][addr[1]][addr[2]][addr[3]];
	} catch(e) {}
	return null;
}

sensorino_state.prototype.set_channel = function(addr, value, done) {
	try {
		/* TODO: validate type and/or convert */

		/*
		 * Note: the node addr passed to this function *must* be of the same
		 * type as should be in final JSON.
		 */
		var node_addr = addr[0];
		var svc_id = parseInt(addr[1]);
		var type_name = addr[2];
		var channel_id = parseInt(addr[3]);

		var all_values = [];
		for (var ch = 0; ch < channel_id; ch++) {
			var ch_addr = [ node_addr, svc_id, type_name, ch ];
			var new_val = this.get_channel(ch_addr);
			if (new_val === null)
				throw 'Must retrieve value for channel ' + ch_addr + ' first.';

			all_values.push(new_val);
		}

		if (all_values.length)
			all_values.push(value);
		else
			all_values = value;

		var options = {
			url: '/api/console.json',
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: { to: node_addr, type: 'set', serviceId: svc_id },
		};
		options.body[type_name] = all_values;

		function set_error(err) {
			console.log(err);
			if (err.statusCode === undefined)
				done('Can\'t connect');
			else if (err.body.length)
				done('Server message: ' + err.body);
			else
				done('Error ' + err.statusCode + ' sending the SET message.');
		}

		function set_done() {
			done(true);
		}

		oboe(options).fail(set_error).done(set_done);
	} catch(e) {
		done(e);
	}
}

sensorino_state.prototype.get_svc_channel_counts = function(svc) {
	var channels = {};

	for (var member in svc) {
		var type = member;
		if (member[0] == '_') {
			if (member.startsWith('_publish_count_'))
				type = member.substr('_publish_count_'.length);
			else if (member.startsWith('_accept_count_'))
				type = member.substr('_accept_count_'.length);
			else
				continue;
		}

		if (type in channels)
			continue;

		var chan_cnt = 0;
		if ('_publish_count_' + type in svc && '_accept_count_' + type in svc)
			var chan_cnt = svc['_publish_count_' + type] +
				svc['_accept_count_' + type];

		for (var chan_id in svc[type])
			if (parseInt(chan_id) <= chan_cnt)
				chan_cnt = parseInt(chan_id) + 1;

		var publish_cnt = chan_cnt;
		if ('_publish_count_' + type in svc)
			publish_cnt = svc['_publish_count_' + type];

		channels[type] = [ chan_cnt, publish_cnt ];
	}

	return channels;
}

sensorino_state.prototype.get_channel_list = function() {
	var channels = [];

	for (var node_addr_str in this.nodes) {
		var nd = this.nodes[node_addr_str];
		var node_addr = nd._addr;
		for (var svc_id in nd) {
			if (svc_id in this.special_services || svc_id[0] == '_')
				continue;

			var chan_cnt = this.get_svc_channel_counts(nd[svc_id]);
			for (var type in chan_cnt)
				for (var chan_id = 0; chan_id < chan_cnt[type][0]; chan_id++)
					channels.push([ node_addr, svc_id, type, chan_id ]);
		}
	}

	return channels;
}

sensorino_state.prototype.get_channel_lists = function() {
	var ac_channels = [], se_channels = [];

	for (var node_addr_str in this.nodes) {
		var nd = this.nodes[node_addr_str];
		var node_addr = nd._addr;
		for (var svc_id in nd) {
			if (svc_id in this.special_services || svc_id[0] == '_')
				continue;

			var chan_cnt = this.get_svc_channel_counts(nd[svc_id]);
			for (var type in chan_cnt)
				for (var chan_id = 0; chan_id < chan_cnt[type][0]; chan_id++) {
					var chan = [ node_addr, svc_id, type, chan_id ];
					if (chan_id < chan_cnt[type][1])
						se_channels.push(chan);
					else
						ac_channels.push(chan);
				}
		}
	}

	return [ se_channels, ac_channels ];
}

sensorino_state.prototype.format_channel = function(addr) {
	var node_addr = addr[0];
	var svc_id = parseInt(addr[1]);
	var data_type = addr[2];
	var channel_id = parseInt(addr[3]);

	var str = node_addr + ',' + svc_id;
	var type_str = ' (type: ' + data_type + ')';

	var svc = this.nodes[node_addr][svc_id];
	var chan_cnt = this.get_svc_channel_counts(svc);

	if (chan_cnt[data_type][0] == 1 && Object.keys(chan_cnt).length == 1)
		return str + type_str;

	str += ',' + data_type;

	if (chan_cnt[data_type][0] == 1)
		return str + type_str;

	str += ',' + channel_id;

	return str + type_str;
}

sensorino_state.prototype.parse_channel = function(str) {
	var elems = str.replace(/ /g, '').split(',', 4);

	if (elems.length < 2)
		return null;

	var node_addr_str = elems[0];
	var svc_id = parseInt(elems[1]);
	var data_type = null;
	var channel_id = 0;

	if (elems.length <= 2) {
		if (!(node_addr_str in this.nodes))
			return null;
		if (!(svc_id in this.nodes[node_addr_str]))
			return null;

		var svc = this.nodes[node_addr_str][svc_id];
		var chan_cnt = this.get_svc_channel_counts(svc);
		if (Object.keys(chan_cnt).length != 1)
			return null;	/* If type not given, the service can have only one */
		for (var type in chan_cnt)
			data_type = type;
	} else
		data_type = elems[2];

	/* TODO: eventually only check that type name is valid, for now we
	 * check if given type was already discovered in this service.  */

	if (!(node_addr_str in this.nodes))
		return null;
	if (!(svc_id in this.nodes[node_addr_str]))
		return null;

	var node_addr = this.nodes[node_addr_str]._addr;
	var svc = this.nodes[node_addr_str][svc_id];
	if (!(data_type in svc) && !('_publish_count_' + data_type in svc))
		return null;

	if (elems.length >= 4)
		channel_id = parseInt(elems[3]);

	return [ node_addr, svc_id, data_type, channel_id ];
}

sensorino_state.prototype.request_state_at_timestamp =
	function(timestamp, handler) {
	/*
	 * Use the "ago=" parameter to the API call, instead of "at=", to
	 * reduce the dependency on server and client timezone difference and
	 * clock synchronisation.  Unfortunately network delays may be a
	 * problem for some users when passing "ago=".
	 */
	var now = Date.now() * 0.001;
	var ago = now - timestamp;

	function load_error(err) {
		console.log(err);
		if (err.statusCode === undefined)
			handler(null, 'Can\'t connect');
		else if (err.body.length)
			handler(null, 'Server message: ' + err.body);
		else
			handler(null, 'Error ' + err.statusCode + ' loading historical state.');
	}

	function load_done(tree) {
		handler(new temporary_state(timestamp, tree));
	}

	oboe('/api/sensorino.json?ago=' + ago).fail(load_error).done(load_done);
}

function temporary_state(timestamp, tree) {
	this.timestamp = timestamp;
	this.nodes = tree;
}

/* These only access .nodes so re-use them */
temporary_state.prototype.get_channel =
	sensorino_state.prototype.get_channel;
temporary_state.prototype.get_svc_channel_counts =
	sensorino_state.prototype.get_svc_channel_counts;
temporary_state.prototype.format_channel =
	sensorino_state.prototype.format_channel;

temporary_state.prototype.subscribe = function(addr, handler) {}
temporary_state.prototype.unsubscribe = function(addr, handler) {}
temporary_state.prototype.subscribe_updates = function(handler, all) {}
temporary_state.prototype.unsubscribe_updates = function(handler) {}

sensorino_state.prototype.request_values_over_period =
	function(path, timestamp0, timestamp1, handler) {
	/*
	 * Use the "ago=" parameter to the API call, instead of "at=", to
	 * reduce the dependency on server and client timezone difference and
	 * clock synchronisation.  Unfortunately network delays may be a
	 * problem for some users when passing "ago=".
	 */
	var now = Date.now() * 0.001;
	var ago0 = now - timestamp0;
	var ago1;
	if (timestamp1 !== undefined)
		ago1 = now - timestamp1;

	function load_error(err) {
		console.log(err);
		if (err.statusCode === undefined)
			handler(null, 'Can\'t connect');
		else if (err.body.length)
			handler(null, 'Server message: ' + err.body);
		else
			handler(null, 'Error ' + err.statusCode + ' loading historical state.');
	}

	function load_done(list) {
		handler(list);
	}

	var url = '/api/' + path.join('/') + '/value.json?ago0=' + ago0
	if (timestamp1 !== undefined)
		url += '&ago1=' + ago1
	oboe(url).fail(load_error).done(load_done);
}

/* From MDN */
if (!String.prototype.startsWith) {
	Object.defineProperty(String.prototype, 'startsWith', {
		enumerable: false,
		configurable: false,
		writable: false,
		value: function(searchString, position) {
			position = position || 0;
			return this.lastIndexOf(searchString, position) === position;
		}
	});
}
/* vim: ts=2:
*/
