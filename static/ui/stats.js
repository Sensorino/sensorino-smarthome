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
		this.navaid.set_path([]);
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
	var is_sensor = !(datatype in chan_cnt && chan_id < chan_cnt[datatype][0]) ||
		chan_id < chan_cnt[datatype][1];
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
					ts_start = events[0][0];
					explain += '<p class="stats-explain">There were over ' +
						this_obj.API_MAX_VALUES + ' events registered for this channel ' +
						'in the last 365 days and they could not be loaded in one ' +
						'request.</p>';
				}

				var datatype = this_obj.channel[2];
				var basic_type = 'float';
				if (datatype === 'switch' || datatype === 'presence')
					basic_type = 'bool';
				else if (datatype === 'count' || datatype === 'serviceId')
					basic_type = 'int';

				/* Basic value in time graph */

				/* TODO: replace Google with something opensource, e.g. this looks
				 * good but canvas-only: http://canvasjs.com/docs/charts/basics-of-creating-html5-chart/zooming-panning/, there are some zoomable D3.js examples too */
				/* TODO: type tricks so that values show as "On" / "Off" for switches,
				 * etc.  Support for RGB values, etc.  */

				var chart0_div = document.createElement('div');
				var chart0 = new google.visualization.LineChart(chart0_div);

				var chart0_data = new google.visualization.DataTable();
				chart0_data.addColumn({ type: 'datetime', id: 'Timestamp' });
				/* Only 'number' supported, we'll "simulate" booleans below */
				chart0_data.addColumn({ type: 'number', id: 'value',
						label: chan_name });
				/*
				 * Really should use google.visualization.Timeline() for booleans
				 * and similar but that doesn't support the "explorer" mode and
				 * other parameters.
				 */

				var last_val = null;
				function add_point(ts, val) {
					/*
					 * For boolean, integer, string, etc. values we need to emit
					 * two rows for each data point so that there's a clear jump
					 * from one value to the other at the time of the data point,
					 * no diagonal line suggesting interpolation from one value
					 * to another.  The interpolation might only work for channels
					 * of continuous types (float) that are sensors, never for
					 * acutators.
					 */
					var interp = is_sensor && basic_type === 'float';

					/* Adapt types if needed */
					if (basic_type === 'bool' && val !== null)
						val = val ? 1 : 0;

					if (!interp && last_val !== null)
						chart0_data.addRow([ new Date(ts * 1000 - 10), last_val ]);
					chart0_data.addRow([ new Date(ts * 1000), val ]);

					last_val = val;
				}

				if (events.length !== this_obj.API_MAX_VALUES)
					if (events.length && events[0][0] > ts_start)
						add_point(ts_start, init_val);
				for (var i = 0; i < events.length; i++)
					add_point(events[i][0], events[i][1]);

				var chart0_opts = {
					title: 'Basic channel value in time plot',
					explorer: {
						axis: 'horizontal',
						keepInBounds: true,
						maxZoomIn: 0.00001,
						maxZoomOut: 1.01,
					},
					animation: 300,
					lineWidth: 3,
					hAxis: {
						minValue: new Date(ts_start * 1000),
						maxValue: new Date(),
					},
					vAxis: {
					},
				};

				if (basic_type === 'bool') {
					chart0_opts.vAxis.minValue = -0.05;
					chart0_opts.vAxis.maxValue = 1.05;
					if (datatype === 'switch') {
						chart0_opts.vAxis.ticks = [
							{ v: 0, f: 'Off' },
							{ v: 1, f: 'On' }
						];
					} else {
						chart0_opts.vAxis.ticks = [
							{ v: 0, f: 'False' },
							{ v: 1, f: 'True' }
						];
					}
					/* TODO: also show these custom values in tooltips -- looks like we
					 * need to attach a tooltip role to each data point though.  */
				}

				chart0_div.classList.add('stats-val-in-time');
				this_obj.hist_info.appendChild(chart0_div);
				chart0.draw(chart0_data, chart0_opts);

				/* Github-style days of activity chart */

				var chart1_div = document.createElement('div');
				var chart1 = new google.visualization.Calendar(chart1_div);

				var chart1_data = new google.visualization.DataTable();
				chart1_data.addColumn({ type: 'date', id: 'Timestamp' });
				chart1_data.addColumn({ type: 'number', id: 'Count' });
				var day = null;
				var day_count;
				for (var i = 0; i < events.length; i++) {
					var full_date = new Date(events[i][0] * 1000);
					var date = new Date(full_date.getFullYear(),
							full_date.getMonth(), full_date.getDay());

					if (day === null || day.toDateString() != date.toDateString()) {
						if (day !== null)
							chart1_data.addRow([ day, day_count ]);
						day = date;
						day_count = 0;
					}
					day_count++;
				}
				if (day !== null)
					chart1_data.addRow([ day, day_count ]);

				var chart1_opts = {
					title: 'Channel activity by calendar day',
				};
				chart1_div.classList.add('stats-by-day');
				this_obj.hist_info.appendChild(chart1_div);
				chart1.draw(chart1_data, chart1_opts);

				/* TODO: hysteresis graphs, also customized for types (e.g. pie for
				 * all types with finite number of values?) */
				/* TODO: activity by hour */

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
/*
 * Google's jsapi uses document.write() which only work for pages served as
 * HTML content-type, not XHTML for example.  The "callback:" below is a
 * workaround that makes jsapi mysteriously use doucemnt.createElement()
 * instead.  Source:
 * https://groups.google.com/forum/#!topic/google-ajax-search-api/ZIfUgB4iSLU
 */
google.load("visualization", "1", {
			packages: [ "corechart", "calendar" ],
			callback: function() {},
		});

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
