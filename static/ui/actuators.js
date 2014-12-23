/* Actuator widget classes */

function actuator_switch(state, canvas, elem) {
	var channel = elem.channels[0];
	var value = null;

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

	function update(val) {
		var y = val ? -10 : 10;
		var o = val === null ? 0.5 : 1;

		circle.set({ top: y, opacity: o });
		canvas.renderAll();

		value = val;
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

	/* TODO: move to base class */
	state.subscribe(channel, function(path, oldval, newval) { update(newval); });
	update(state.get_channel(channel));
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
