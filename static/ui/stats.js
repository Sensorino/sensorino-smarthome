function stats_view(obj, sensorino_state, navaid, floorplan) {
	this.obj = obj;
	this.state = sensorino_state;
	this.navaid = navaid;
	this.floorplan = floorplan;

	this.channel = null;
}

/*
 * Result count limit enforced by the "/api/<path>/value.json" API call.
 * If we get exactly this many results we assume the data is incomplete and
 * represents only the period starting at the timestamp of the first
 * event returned, and ending at the requested period end.  This is because
 * the server retrieves results from the database starting from the most
 * recent and going back, and stops when it reaches the count limit if
 * there are too many results.
 */
stats_view.prototype.API_MAX_VALUES = 1024;

stats_view.prototype.load_channel = function(new_channel) {
	if (this.channel == new_channel)
		return;

	this.obj.innerHTML = '';
	delete this.hist_info;

	if (this.channel !== null) {
		/* TODO: unsubscribe */
	}

	this.channel = new_channel;

	if (this.channel === null) {
		bc.set_path([]);
		return;
	}

	/* TODO: subscribe, in handler update current value and graphs */

	var node_addr = this.channel[0];
	var svc_id = this.channel[1];
	var datatype = this.channel[2];
	var chan_id = this.channel[3];

	var chan_name = datatype.substr(0, 1).toUpperCase() + datatype.substr(1) +
		' ' + chan_id;
	this.navaid.set_path([ 'Smart home', 'Node ' + node_addr,
			'Service ' + svc_id, chan_name ]);

	/* Data type */
	this.append_info('Channel\'s data type / physical dimension',
			datatype, 'datatype');
	this.append_info('Measurement unit', 'TODO', 'unit');

	/* Current value */
	var val = this.state.get_channel(this.channel);
	this.append_info('Current value', val === null ?
			'not received yet' : val, 'cur-val');

	/* Channel type */
	var svc_data = this.state.nodes[node_addr][svc_id];
	var chan_cnt = this.state.get_svc_channel_counts(svc_data);
	var ch_type = (datatype in chan_cnt && chan_id < chan_cnt[datatype][0]) ?
		(chan_id < chan_cnt[datatype][1] ?
			[ 'read-only (Sensor)', 'Sensor channels are read-only and represent ' +
				'a single dimension (component) of a value measured by a sensor.  ' +
				'New values are automatically published by a node when a change is ' +
				'detected, but they can also be queried at any time the node is ' +
				'listening for requests and not in sleep mode.' ] :
			[ 'read-write (Actuator)', 'Actuator channels represent a single ' +
				'dimension (component) of a value that drives a remote actuator.  ' +
				'They can be queried or set to a new value on request.  The value ' +
				'read is typically the last value written.' ]) :
		[ 'assumed read-only (Sensor)', 'The node\'s capabilities have not been ' +
			'received yet so the channel is assumed by the server to not be ' +
			'writable.  It will still be updated when new values are received.' ];
	this.append_info('Channel type', ch_type[0] +
			'<p class="stats-explain">' + ch_type[1] + '</p>', 'chan-type');

	this.append_info('Associated floorplan widgets', 'TODO', 'fp');
	this.append_info('Associated remote rule engine entries', 'TODO', 're');
	this.append_info('Associated server-side rule engine entries', 'TODO', 're');

	/* Load channel history data */

	this.hist_info = document.createElement('div');
	this.hist_info.textContent = 'Loading channel data for the last ' +
		'365 day period...';
	this.obj.appendChild(this.hist_info);

	var this_obj = this;
	/* Request data since 365 days ago up to now */
	var ts_start = Date.now() * 0.001 - 365 * 24 * 60 * 60;
	var ts_end = undefined;
	this.state.request_values_over_period(this.channel, ts_start, ts_end,
			function(data, err) {
				if (data === null) {
					this_obj.hist_info.innerHTML = 'The following error occured ' +
						'while loading activity data for this channel:<br />' + err;
					this_obj.hist_info.classList.add('stats-error');
					return;
				}

				this_obj.hist_info.innerHTML = '';

				var init_val = data.shift();
				var events = data;
				var period = 365 * 24 * 60 * 60;
				var explain = '';
				if (events.length === this_obj.API_MAX_VALUES) {
					period -= events[0][0] - ts_start;
					explain += '<p class="stats-explain">There were over ' +
						this_obj.API_MAX_VALUES + ' events registered for this channel ' +
						'in the last 365 days and they could not be loaded in one ' +
						'request.</p>';
				}

				/* TODO: graph in time */

				/* TODO: hysteresis graph */

				this_obj.append_info('Period loaded', 'last ' +
						timeline.prototype.rel_time_str(period) + explain, 'period');

				this_obj.append_info('Number of events registered in this period',
						events.length, 'events');

				this_obj.append_info('Average interval between events',
						'approx. 1 in every ' +
						timeline.prototype.rel_time_str(period / events.length) + ' or ' +
						('' + (events.length * 24 * 60 * 60 / period)).substr(0, 6) +
						' a day', 'events');

				this_obj.append_info('Number of errors reported in relation to channel',
						'TODO', 'errors');
			});
}

stats_view.prototype.append_info = function(param, value, cls) {
	var par = document.createElement('p');
	var param_nd = document.createElement('span');
	var value_nd = document.createElement('span');

	param_nd.textContent = param + ': ';
	value_nd.innerHTML = value;

	par.classList.add('stats-' + cls);
	param_nd.classList.add('stats-param');
	value_nd.classList.add('stats-value');
	par.appendChild(param_nd);
	par.appendChild(value_nd);
	if (this.hist_info)
		this.hist_info.appendChild(par);
	else
		this.obj.appendChild(par);
}

function breadcrumbs(obj) {
	this.obj = obj;
	this.path = [];

	obj.classList.add('breadcrumbs');
}

breadcrumbs.prototype.set_path = function(path) {
	/* Clean out old breadcrumbs */
	var i;
	for (i = 0; i < this.path.length && i < path.length; i++)
		if (this.path[i].path_elem != path[i])
			break;
	while (this.path.length > i)
		this.obj.removeChild(this.path.pop());

	/* Spread new ones */
	for (var i = this.path.length; i < path.length; i++) {
		var elem = document.createElement('span');
		elem.classList.add('breadcrumbs-elem');
		elem.path_elem = path[i];
		elem.textContent = path[i];

		this.path.push(elem);
		this.obj.appendChild(elem);
	}
}

/* vim: ts=2:
*/
