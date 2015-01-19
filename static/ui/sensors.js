/* Sensor widget classes */

function sensor_text(canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';
	var state = null;

	elem.obj = new fabric.Text('', {
		fontFamily: 'Times', /* TODO: style */
		stroke: '#558', /* TODO: style */
		originX: 'center',
		originY: 'center',
	});

	function update(new_val) {
		var old_val = value;
		value = new_val;

		var content = '' +
			(value !== null && value !== undefined ? value : channel);

		/* Up to 3 fractional digits depending on the magnitude */
		if (typeof value == "number") {
			var str = '' + value;
			var idx = str.indexOf('.');
			if (idx > -1)
				content = str.substr(0, idx >= 3 ? idx + 2 : 5);
		}

		elem.obj.setText(content);
		canvas.renderAll();

		if (old_val !== 'dummy')
			start_echo(canvas.getElement(), elem.obj.getBoundingRect());
	}
	this.update = update;

	/* TODO: move everything below (and more) to base class */

	elem.obj.viewmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', current value: ' + value, 'sensor');
	};
	elem.obj.viewmode_onout = function(o) {
		clear_tip('sensor');
	};

	elem.obj.histmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', value at timestamp: ' + value, 'sensor');
	};
	elem.obj.histmode_onout = function(o) {
		clear_tip('sensor');
	};

	var handler = function(path, oldval, newval) { update(newval); };
	this.set_state = function(new_state) {
		if (state === new_state)
			return;

		if (state !== null)
			state.unsubscribe(channel, handler);

		state = new_state;
		value = 'dummy';

		if (state !== null) {
			state.subscribe(channel, handler);
			update(state.get_channel(channel));
		}
	}

	update(null);
}

/* The creator must call this when widget is deleted or we'll leak references */
sensor_text.prototype.cleanup = function() {
	this.set_state(null);
}

function sensor_switch(canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';
	var state = null;

	var path0 = new fabric.Path('M0,-10V10', {
		strokeWidth: 20,
		strokeLineCap: 'round',
		stroke: '#aaa',
		fill: null,
		originX: 'center',
		originY: 'center',
		selectable: false
	});

	var path1 = new fabric.Path('M0,-10V10', {
		strokeWidth: 2,
		strokeLineCap: 'round',
		stroke: '#fff',
		fill: null,
		originX: 'center',
		originY: 'center',
		selectable: false
	});

	var circle = new fabric.Circle({
		stroke: null,
		fill: '#abf', /* TODO: style */
		radius: 8,
		left: 0,
		originX: 'center',
		originY: 'center',
		selectable: false
	});

	elem.obj = new fabric.Group([ path0, path1, circle ], {
		originX: 'center',
		originY: 'center',
	});

	function update(new_val) {
		var old_val = value;
		value = new_val;

		var y = value ? -10 : 10;
		var o = value === null ? 0.5 : 1;

		circle.set({ top: y, opacity: o });
		canvas.renderAll();

		if (old_val !== 'dummy')
			start_echo(canvas.getElement(), elem.obj.getBoundingRect());
	}
	this.update = update;

	/* TODO: move everything below (and more) to base class */

	elem.obj.viewmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', current value: ' + (value === null ? 'Unknown' :
			(value ? 'On' : 'Off')), 'sensor');
	};
	elem.obj.viewmode_onout = function(o) {
		clear_tip('sensor');
	};

	elem.obj.histmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', value at timestamp: ' + (value === null ? 'Unknown' :
			(value ? 'On' : 'Off')), 'sensor');
	};
	elem.obj.histmode_onout = function(o) {
		clear_tip('sensor');
	};

	var handler = function(path, oldval, newval) { update(newval); };
	this.set_state = function(new_state) {
		if (state === new_state)
			return;

		if (state !== null)
			state.unsubscribe(channel, handler);

		state = new_state;
		value = 'dummy';

		if (state !== null) {
			state.subscribe(channel, handler);
			update(state.get_channel(channel));
		}
	}

	update(null);
}

/* The creator must call this when widget is deleted or we'll leak references */
sensor_switch.prototype.cleanup = function() {
	this.set_state(null);
}

function sensor_slider(canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';
	var state = null;

	if (!('min_value' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the minimum value to display'));
		/* NaN != NaN && NaN !== NaN */
		elem.min_value = isNaN(resp) ? 0 : resp;
	}

	if (!('max_value' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the maximum value to display'));
		/* NaN != NaN && NaN !== NaN */
		elem.max_value = isNaN(resp) ? 0 : resp;
		if (elem.max_value <= elem.min_value)
			elem.max_value = elem.min_value + 100.0;
	}

	if (!('ticks' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the ticks interval to ' +
				'display on the axis, leave empty for none'));
		/* NaN != NaN && NaN !== NaN */
		elem.ticks = isNaN(resp) ? 0 : resp;
	}

	var len = 100;

	var subelems = [
		new fabric.Path('M0,-' + (len / 2) + 'V' + (len / 2), {
				strokeWidth: 20,
				strokeLineCap: 'round',
				stroke: '#aaa',
				fill: null,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
		new fabric.Path('M0,-' + (len / 2) + 'V' + (len / 2), {
				strokeWidth: 2,
				strokeLineCap: 'round',
				stroke: '#fff',
				fill: null,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
	];

	if (elem.ticks > 0)
		for (var n = Math.ceil(elem.min_value / elem.ticks);
				n <= Math.floor(elem.max_value / elem.ticks); n++)
			subelems.push(new fabric.Rect({
					stroke: null,
					fill: '#fff',
					top: len / 2 - (n * elem.ticks - elem.min_value) * len /
						(elem.max_value - elem.min_value),
					width: 14,
					height: 2,
					originX: 'center',
					originY: 'center',
					selectable: false
				}));

	var rect = new fabric.Rect({
			stroke: null,
			fill: '#adf', /* TODO: style */
			top: 0,
			width: 16,
			height: 4,
			originX: 'center',
			originY: 'center',
			selectable: false
		});
	subelems.push(rect);

	elem.obj = new fabric.Group(subelems, {
			originX: 'center',
			originY: 'center',
		});

	function update(new_val) {
		var old_val = value;
		value = new_val;

		var o = value === null ? 0.5 : 1;
		var y = value;
		if (y < elem.min_value) {
			y = elem.min_value;
			o = 0.5;
		} else if (y > elem.max_value) {
			y = elem.max_value;
			o = 0.5;
		}
		y = len / 2 - (y - elem.min_value) * len /
			(elem.max_value - elem.min_value);

		rect.set({ top: y, opacity: o });
		canvas.renderAll();

		if (old_val !== 'dummy')
			start_echo(canvas.getElement(), elem.obj.getBoundingRect());
	}
	this.update = update;

	/* TODO: move everything below (and more) to base class */

	elem.obj.viewmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', current value: ' + (value === null ? 'Unknown' : value), 'sensor');
	};
	elem.obj.viewmode_onout = function(o) {
		clear_tip('sensor');
	};

	elem.obj.histmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', value at timestamp: ' + (value === null ? 'Unknown' : value),
			'sensor');
	};
	elem.obj.histmode_onout = function(o) {
		clear_tip('sensor');
	};

	var handler = function(path, oldval, newval) { update(newval); };
	this.set_state = function(new_state) {
		if (state === new_state)
			return;

		if (state !== null)
			state.unsubscribe(channel, handler);

		state = new_state;
		value = 'dummy';

		if (state !== null) {
			state.subscribe(channel, handler);
			update(state.get_channel(channel));
		}
	}

	update(null);
}

/* The creator must call this when widget is deleted or we'll leak references */
sensor_slider.prototype.cleanup = function() {
	this.set_state(null);
}

function sensor_temp(canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';
	var state = null;

	if (!('min_value' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the minimum value to display'));
		/* NaN != NaN && NaN !== NaN */
		elem.min_value = isNaN(resp) ? 0 : resp;
	}

	if (!('max_value' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the maximum value to display'));
		/* NaN != NaN && NaN !== NaN */
		elem.max_value = isNaN(resp) ? 0 : resp;
		if (elem.max_value <= elem.min_value)
			elem.max_value = elem.min_value + 100.0;
	}

	if (!('ticks' in elem)) {
		/* TODO */
		var resp = parseFloat(prompt('Please give the ticks interval to ' +
				'display on the axis, leave empty for none'));
		/* NaN != NaN && NaN !== NaN */
		elem.ticks = isNaN(resp) ? 0 : resp;
	}

	var len = 100;

	var subelems = [
		new fabric.Path('M0,-' + (len / 2) + 'V' + (len / 2), {
				strokeWidth: 20,
				strokeLineCap: 'round',
				stroke: '#aaa',
				fill: null,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
		new fabric.Circle({
				stroke: null,
				fill: '#aaa',
					top: len / 2,
				radius: 15,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
		new fabric.Path('M0,-' + (len / 2) + 'V' + (len / 2), {
				strokeWidth: 12,
				strokeLineCap: 'round',
				stroke: '#fff',
				fill: null,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
		new fabric.Circle({
				stroke: null,
				fill: '#abf',
				top: len / 2,
				radius: 11,
				originX: 'center',
				originY: 'center',
				selectable: false
			}),
	];

	var temp = new fabric.Path('M0,-' + (len / 2) + 'V' + (len / 2), {
			strokeWidth: 12,
			stroke: '#abf',
			fill: null,
			originX: 'center',
			originY: 'center',
			selectable: false
		});
	subelems.push(temp);

	if (elem.ticks > 0)
		for (var n = Math.ceil(elem.min_value / elem.ticks);
				n <= Math.floor(elem.max_value / elem.ticks); n++)
			subelems.push(new fabric.Rect({
					stroke: null,
					fill: '#aaa',
					top: len / 2 - (n * elem.ticks - elem.min_value) * len /
						(elem.max_value - elem.min_value),
					width: 14,
					height: 1,
					originX: 'center',
					originY: 'center',
					selectable: false
				}));

	elem.obj = new fabric.Group(subelems, {
			originX: 'center',
			originY: 'center',
		});

	function update(new_val) {
		var old_val = value;
		value = new_val;

		var o = value === null ? 0.5 : 1;
		var y = value;
		var linecap = 'butt';
		if (y < elem.min_value) {
			y = elem.min_value;
		} else if (y > elem.max_value) {
			y = elem.max_value;
			linecap = 'round';
		}
		y = len / 2 - (y - elem.min_value) * len /
			(elem.max_value - elem.min_value);

		temp.path[0][2] = y;
		temp.set({ opacity: o, strokeLineCap: linecap });
		canvas.renderAll();

		if (old_val !== 'dummy')
			start_echo(canvas.getElement(), elem.obj.getBoundingRect());
	}
	this.update = update;

	/* TODO: move everything below (and more) to base class */

	elem.obj.viewmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', current value: ' + (value === null ? 'Unknown' : value), 'sensor');
	};
	elem.obj.viewmode_onout = function(o) {
		clear_tip('sensor');
	};

	elem.obj.histmode_onover = function(o) {
		set_tip('Sensor channel ' + state.format_channel(channel) +
			', value at timestamp: ' + (value === null ? 'Unknown' : value),
			'sensor');
	};
	elem.obj.histmode_onout = function(o) {
		clear_tip('sensor');
	};

	var handler = function(path, oldval, newval) { update(newval); };
	this.set_state = function(new_state) {
		if (state === new_state)
			return;

		if (state !== null)
			state.unsubscribe(channel, handler);

		state = new_state;
		value = 'dummy';

		if (state !== null) {
			state.subscribe(channel, handler);
			update(state.get_channel(channel));
		}
	}

	update(null);
}

/* The creator must call this when widget is deleted or we'll leak references */
sensor_temp.prototype.cleanup = function() {
	this.set_state(null);
}

/* TODO: xy "slider" sensor */
/* TODO: rgb sensor */

sensor_text.prototype.channel_reqs = [ 'any' ];
floorplan.prototype.register_sensor(sensor_text, 'text', 'Uses 1 channel, ' +
		'displays its value as-is in raw text.');

sensor_switch.prototype.channel_reqs = [ 'bool' ];
floorplan.prototype.register_sensor(sensor_switch, 'switch', 'Uses 1 ' +
		'channel, ideally of a binary Data Type such as "switch" or "presence".  ' +
		'The value is displayed graphically.  If a non-boolean-typed channel is ' +
		'selected, any non-zero/non-null/non-empty value is treated as True.');

sensor_slider.prototype.channel_reqs = [ 'number' ];
floorplan.prototype.register_sensor(sensor_slider, 'slider', 'Uses 1 ' +
		'channel, ideally of a numeric Data Type (integer, float).  ' +
		'The value is displayed graphically.');

sensor_temp.prototype.channel_reqs = [ 'number' ];
floorplan.prototype.register_sensor(sensor_temp, 'thermometer', 'Uses 1 ' +
		'channel, ideally of a numeric Data Type (integer, float).  ' +
		'The value is displayed graphically.  Subtype of the "slider" widget');

/* vim: ts=2:
*/
