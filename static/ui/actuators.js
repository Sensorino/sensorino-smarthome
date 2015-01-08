/* Actuator widget classes */

function actuator_switch(canvas, elem) {
	var channel = elem.channels[0];
	var value = 'dummy';
	var state = null;
	var echo_id = null;

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
		fill: '#e4e',
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

	function update(new_val, err) {
		var old_val = value;
		value = new_val;

		var y = value ? -10 : 10;
		var o = value === null ? 0.5 : 1;

		circle.set({ top: y, opacity: o });
		canvas.renderAll();

		if (old_val !== 'dummy' && !err)
			echo_id = start_echo(canvas.getElement(), elem.obj.getBoundingRect());
		else if (echo_id !== null) {
			if (err)
				stop_echo(echo_id)
			echo_id = null;
		}

		if (err)
			/*
			 * Work around an issue that seems to be a combination of Firefox 28,
			 * Oboe streaming of multiple simultaneous streams and the use of
			 * alert().
			 */
			setTimeout(function() {
					alert('Remote end reported an error after your last Switch ' +
						'operation.  Please see the Console View panel to inspect the ' +
						'error message contents.');
				}, 200);
		/* Might wanna make sure we only show one alert() per unit of time or
		 * something similar to Linux printk_ratelimit().  */
	}
	this.update = update;

	elem.obj.viewmode_onclick = function(o) {
		set_tip('Sending new value…');

		state.set_channel(channel, !value, function(result) {
			if (result === true)
				set_tip('Action executed.');
			else {
				set_tip('Action failed.');
				alert('Sending new value failed: ' + result);
			}
		});
	};

	/* TODO: move everything below (and more) to base class */

	elem.obj.viewmode_onover = function(o) {
		set_tip('Actuator channel ' + state.format_channel(channel) +
			', current value: ' + (value === null ? 'Unknown' :
			(value ? 'On' : 'Off')) + '.  Click to switch ' +
			(!value ? 'on.' : 'off.'), 'actuator');

		circle.set({ radius: 9 });
		/*path0.set({ strokeWidth: 17 });*/
		canvas.renderAll();
	};
	elem.obj.viewmode_onout = function(o) {
		clear_tip('actuator');

		circle.set({ radius: 8 });
		/*path0.set({ strokeWidth: 20 });*/
		canvas.renderAll();
	};

	elem.obj.histmode_onover = function(o) {
		set_tip('Actuator channel ' + state.format_channel(channel) +
			', value at timestamp: ' + (value === null ? 'Unknown' :
			(value ? 'On' : 'Off')) + '.', 'actuator');
	};
	elem.obj.histmode_onout = function(o) {
		clear_tip('actuator');
	};

	var handler = function(path, oldval, newval, err) { update(newval, err); };
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

	update(null, false);
}

/* The creator must call this when widget is deleted or we'll leak references */
actuator_switch.prototype.cleanup = function() {
	this.set_state(null);
}

/* TODO: slider actuator */
/* TODO: xy "slider" actuator */
/* TODO: rgb chooser -- is there anything in Fabric.js? */

actuator_switch.prototype.channel_reqs = [ 'bool' ];
floorplan.prototype.register_actuator(actuator_switch, 'switch', 'Uses 1 ' +
		'channel, ideally of a binary Data Type such as "switch" or "presence".  ' +
		'The value is displayed graphically.  If a non-boolean-typed channel is ' +
		'selected, any non-zero/non-null/non-empty value is treated as True.  ' +
		'Click anywhere on it to toggle.');

/* vim: ts=2:
*/
