/* Sensor widget classes */

function sensor_text(state, canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';

	elem.obj = new fabric.Text('', {
		fontFamily: 'Times', /* TODO: style */
		stroke: '#558', /* TODO: style */
		originX: 'center',
		originY: 'center',
	});

	function update(new_val) {
		var old_val = value;
		value = new_val;

		var content = '' + (value !== null ? value : channel);

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

	/* TODO: move to base class */
	state.subscribe(channel, function(path, oldval, newval) { update(newval); });
	update(state.get_channel(channel));
}

function sensor_switch(state, canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';

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
		fill: '#abf',
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

	state.subscribe(channel, function(path, oldval, newval) { update(newval); });
	update(state.get_channel(channel));
}

/* TODO: slider sensor */
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

/* vim: ts=2:
*/
