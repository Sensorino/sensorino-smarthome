function sensorino_state() {
	this.nodes = {};
	this.listeners = {};
	this.update_listeners = [];
	this.inited = 0;

	var status_obj = document.getElementById('conn-status');
	var this_obj = this;

	this.special_services = { "0": "Service Manager", "1": "Rule Engine" };

	function notify(path, oldval, newval) {
		var cbs = this_obj.listeners[path] || [];

		cbs.forEach(function(cb) { cb(path, oldval, newval); });
	}

	function update_all(path, state, parent, update) {
		var path_elem = path[path.length - 1];

		/* Check if we need to recurse */
		var old_recurse = state instanceof Object || state instanceof Array;
		var new_recurse = update instanceof Object || update instanceof Array;

		var visited = {};
		if (old_recurse) {
			function check_old(val, key) {
				update_all(path.concat([ key ]), val, state,
						(new_recurse && key in update) ? update[key] : null);
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

			if (oldval !== newval) /* Do we want to use != here? */
				notify(path, oldval, newval);

			if (update === null)
				delete parent[path_elem];
			else {
				state = new_recurse ? {} : update;
				parent[path_elem] = state;
			}
		}

		if (new_recurse) {
			function check_new(val, key) {
				if (!(key in visited))
					update_all(path.concat([ key ]), null, state, val);
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

		update_all([], this.nodes, null, state);
	}

	function handle_event(obj) {
		/* Check whether this is a whole new state object or a list of updates */
		if (!Array.isArray(obj)) {
			reset_state(obj);

			this_obj.update_listeners.forEach(function(cb) { cb(); });
			return;
		}

		/* Now we know this is an event -- a list of state elements that changed */
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

				if (!(path_elem in state_elem))
					state_elem[path_elem] = {};
				state_elem = state_elem[path_elem];
			}

			var path_elem = path[path.length - 1];
			update_all(path, path_elem in state_elem ? state_elem[path_elem] : null,
					state_elem, update);
		}

		this_obj.update_listeners.forEach(function(cb) { cb(); });
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

sensorino_state.prototype.subscribe_updates = function(handler) {
	this.update_listeners.push(handler);
}

sensorino_state.prototype.unsubscribe_updates = function(handler) {
	var idx = this.update_listeners.indexOf(handler);
	this.update_listeners.splice(idx, 1);
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

sensorino_state.prototype.get_channel_list = function() {
	var channels = [];

	for (var node_addr in this.nodes) {
		var nd = this.nodes[node_addr];
		for (var svc_id in nd) {
			if (svc_id in this.special_services || svc_id[0] == '_')
				continue;
			var svc = nd[svc_id];
			for (var type in svc) {
				if (type[0] == '_')
					continue;
				for (var chan_id in svc[type])
					channels.push([ node_addr, svc_id, type, chan_id ]);
			}
		}
	}

	return channels;
}

sensorino_state.prototype.get_channel_lists = function() {
	var ac_channels = [], se_channels = [];

	for (var node_addr in this.nodes) {
		var nd = this.nodes[node_addr];
		for (var svc_id in nd) {
			if (svc_id in this.special_services || svc_id[0] == '_')
				continue;

			var svc = nd[svc_id];
			for (var type in svc) {
				if (type[0] == '_')
					continue;

				var publish_cnt = Object.keys(svc[type]).length; /* TODO: use max idx */
				if ('_publish_count_' + type in svc)
					publish_cnt = svc['_publish_count_' + type]

				for (var chan_id in svc[type]) {
					var chan = [ node_addr, svc_id, type, chan_id ];
					if (chan_id < publish_cnt)
						se_channels.push(chan);
					else
						ac_channels.push(chan);
				}
			}
		}
	}

	return [ se_channels, ac_channels ];
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
