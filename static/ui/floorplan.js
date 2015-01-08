function floorplan(canvas, sensorino_state) {
	var this_obj = this;
	this.elems = [];
	this.canvas = canvas;
	this.sensorino_state = sensorino_state;

	function add_elem(x, y, elemtype) {
		var elem = { 'type': elemtype, 'x': x, 'y': y, adj: [] };
		this_obj.elems.push(elem);

		modified = true;

		return elem;
	}

	function add_pt(x, y) {
		return add_elem(x, y, 'pt');
	}

	function remove_elem(elem) {
		var idx = this_obj.elems.indexOf(elem);
		this_obj.elems.splice(idx, 1);

		/* If this is a line, update the endpoint's adjacency lists */
		if (elem.type == 'ln') {
			var idx = elem.from.adj.indexOf(elem);
			elem.from.adj.splice(idx, 1);
			if (elem.from.adj.length == 0)
				remove_elem(elem.from);
			var idx = elem.to.adj.indexOf(elem);
			elem.to.adj.splice(idx, 1);
			if (elem.to.adj.length == 0)
				remove_elem(elem.to);
		}

		modified = true;
	}

	/* Menus */
	/* TODO: extract image paths from the stylesheet */

	var create_menu = {
		'thick': {
			'tip': 'Draw a thick line (wall)',
			'fun': function(o) { start_line(o, 0); },
			'url': 'img/thick.png'
		},
		'thin': {
			'tip': 'Draw a thin line (door, window, etc.)',
			'fun': function(o) { start_line(o, 1); },
			'url': 'img/thin.png'
		},
		'label': {
			'tip': 'Place a label',
			'fun': function(o) {
				var content = prompt('Please enter the label text.', 'Kitchen');
				if (!content)
					return;
				var elem = add_elem(o.x, o.y, 'tx');
				elem.obj = new fabric.Text(content, {
					fontFamily: 'Times', /* TODO: style */
					stroke: '#555', /* TODO: style */
					originX: 'center',
					originY: 'center',
					selectable: true,
					left: o.x,
					top: o.y,
				});
				elem.obj.elem = elem; /* For move/rotate callbacks' use */
				canvas.add(elem.obj);
				edit_mode_modified({ 'target': elem.obj });
			},
			'url': 'img/text.png'
		},
		'sensor': {
			'tip': 'Add a sensor',
			'fun': function(o) { add_sensor_actuator(o, 'se'); },
			'url': 'img/sensor.png'
		},
		'actuator': {
			'tip': 'Add an actuator',
			'fun': function(o) { add_sensor_actuator(o, 'ac'); },
			'url': 'img/actuator.png'
		},
	};

	/* Line menu */
	var line_menu = {
		'delete': {
			'tip': 'Delete line',
			'fun': function(o) { canvas.remove(o.obj); remove_elem(o); },
			'url': 'img/trashcan.png'
		},
		'thick': {
			'tip': 'Make line thick (wall)',
			'fun': function(o) {
				o.ltype = 0; o.obj.set({ 'strokeWidth': 4 }); modified = true;
			},
			'url': 'img/thick.png'
		},
		'thin': {
			'tip': 'Make line thin (door, window, etc.)',
			'fun': function(o) {
				o.ltype = 1; o.obj.set({ 'strokeWidth': 1 }); modified = true;
			},
			'url': 'img/thin.png'
		},
	};

	/* Text menu */
	var text_menu = {
		'delete': {
			'tip': 'Delete label',
			'fun': function(o) { canvas.remove(o.obj); remove_elem(o); },
			'url': 'img/trashcan.png'
		},
		'edit': {
			'tip': 'Change the label\'s text',
			'fun': function(o) {
				var content = prompt('Please enter new text content.', o.obj.getText());
				if (content === null)
					return;
				if (!content)
					return; /* TODO: delete */
				o.text = content;
				o.obj.setText(content);
				canvas.renderAll();
				modified = true;
			},
			'url': 'img/text.png'
		},
	};

	/* Sensor menu */
	var sensor_menu = {
		'delete': {
			'tip': 'Delete sensor object',
			'fun': function(o) {
				canvas.remove(o.obj);
				o.widget.cleanup();
				remove_elem(o);
				this_obj.update_unused_services();
			},
			'url': 'img/trashcan.png'
		},
	};

	/* Actuator menu */
	var actuator_menu = {
		'delete': {
			'tip': 'Delete actuator control',
			'fun': sensor_menu.delete.fun,
			'url': 'img/trashcan.png'
		},
	};

	var menus = [ create_menu, line_menu, text_menu, sensor_menu, actuator_menu ];
	var loaders = {};
	for (var i = 0; i < menus.length; i++)
		for (j in menus[i]) {
			var entry = menus[i][j];
			if (!('url' in entry))
				continue;
			if (!(entry.url in loaders))
				loaders[entry.url] = [];
			loaders[entry.url].push(entry);
		}
	for (var url in loaders)
		fabric.Image.fromURL(url, function(o) {
				for (var i = 0; i < loaders[o.url].length; i++)
					loaders[o.url][i].obj = o;
			}, { url: url });

	/* Canvas functionality */
	canvas.selection = false;

	var inited = 0;

	/* Edit mode */
	var is_down = false;
	var selected = null;
	var ctx_menu = null;
	var line = null;
	var skip_mouse_down = false;
	var modified = false;

	this.reset_edit_state = function() {
		/* Reset editor state */
		if (ctx_menu !== null)
			ctx_menu.close();
		deselect();
		canvas.deactivateAll();
		is_down = false;
		skip_mouse_down = false;
		if (line !== null) {
			canvas.remove(line);
			line = null;
		} else
			canvas.renderAll();
	}

	function find_nearest(x, y, type) {
		var dist = 1e6;
		var obj = null;
		for (var i = 0; i < this_obj.elems.length; i++) {
			var pt = this_obj.elems[i];
			if (type && pt.type != type)
				continue;
			var ndist = Math.abs(pt.x - x) + Math.abs(pt.y - y);
			if (ndist < dist) {
				dist = ndist;
				obj = pt;
			}
		}
		return [ obj, dist ];
	}

	var sel_symbol = new fabric.Circle({
		'radius': 10, /* TODO: style */
		'fill': '#abf', /* TODO: style */
		'selectable': false
	});
	function select(obj) {
		if (obj === null)
			return;

		/* TODO: Must also mark all Fabric.js objects as non-selectable, if we
		 * can't do it en-masse, which it seems we can't (?).  Must also do this
		 * whever a line is being drawn.
		 * Must also register on-select to close any menus, etc.
		 */
		canvas.deactivateAll();

		selected = obj;
		sel_symbol.setLeft(obj.x - sel_symbol.getWidth() / 2);
		sel_symbol.setTop(obj.y - sel_symbol.getHeight() / 2);
		canvas.add(sel_symbol);
		sel_symbol.sendToBack();

		set_tip({
			'pt': 'Point',
			'ln': 'Line',
			'tx': 'Text',
			'se': 'Sensor',
			'ac': 'Actuator',
		}[selected.type], 'edit-obj');
		if ('obj' in selected) {
			selected.obj.prev_selectable = selected.obj.selectable;
			selected.obj.selectable = false;
		}
	}

	function deselect() {
		if (selected === null)
			return;

		if ('obj' in selected)
			selected.obj.selectable = selected.obj.prev_selectable;
		canvas.remove(sel_symbol);
		selected = null;

		clear_tip('edit-obj');
	}

	function start_line(pos, ltype) {
		var points = [ pos.x, pos.y, pos.x, pos.y ];
		line = new fabric.Line(points, {
			strokeWidth: ltype == 0 ? 4 : 1, /* TODO: style */
			stroke: '#555', /* TODO: style */
			originX: 'center',
			originY: 'center',
			strokeLineCap: 'round', /* TODO: style */
			selectable: false
		});
		line.props = {
			'from': null,
			'to': null,
			'len': 0,
			'atan2': 0,
			'ltype': ltype,
		};
		line.max_len = 0;
		canvas.add(line);
	}

	function add_sensor_actuator(o, elem_type) {
		var msg;
		if (elem_type == 'se')
			msg = 'TODO: proper UI needed.\n\n' +
				'Please select the way for the sensor value to be displayed.  The ' +
				'following types are available:\n';
		else
			msg = 'TODO: proper UI needed.\n\n' +
				'Please select the type of actuator controller widget.  The ' +
				'following types are available:\n';

		var map = {};
		var class_list = elem_type == 'se' ? this_obj.sensors : this_obj.actuators;
		for (var i = 0; i < class_list.length; i++) {
			msg += '\n' + class_list[i].name;
			map[class_list[i].name] = class_list[i].cls;
		}

		var type = prompt(msg);
		if (!(type in map)) {
			alert('Unknown type.');
			return;
		}

		var cls = map[type];
		/* TODO: this part will be async */
		var channels = this_obj.query_channels(
				cls.prototype.channel_reqs, elem_type == 'ac');
		if (channels === null)
			return;

		var elem = add_elem(o.x, o.y, elem_type);
		elem.dsp_type = type;
		elem.channels = channels;

		elem.widget = new cls(canvas, elem);
		elem.widget.set_state(sensorino_state);
		elem.obj.elem = elem; /* For move/rotate callbacks' use */
		elem.obj.selectable = true;
		elem.obj.set({ left: elem.x, top: elem.y });
		canvas.add(elem.obj);

		edit_mode_modified({ 'target': elem.obj });

		this_obj.update_unused_services();
	}

	function view_mode_mouse_down(o) {
		/* Is something interactive being clicked on? */
		if (o.target !== undefined && 'viewmode_onclick' in o.target) {
			o.target.viewmode_onclick(o.target);
			return;
		}
	}

	var over = null;
	function view_mode_mouse_over(o) {
		if (o.target !== undefined && 'viewmode_onover' in o.target) {
			o.target.viewmode_onover(o.target);
			over = o;
		}
	}

	function view_mode_mouse_out(o) {
		if (o.target !== undefined && 'viewmode_onout' in o.target)
			o.target.viewmode_onout(o.target);
		over = null;
	}

	function hist_mode_mouse_over(o) {
		if (o.target !== undefined && 'histmode_onover' in o.target) {
			o.target.histmode_onover(o.target);
			over = o;
		}
	}

	function hist_mode_mouse_out(o) {
		if (o.target !== undefined && 'histmode_onout' in o.target)
			o.target.histmode_onout(o.target);
		over = null;
	}

	function edit_mode_mouse_over(o) {
		if (o.target !== undefined && 'onover' in o.target) {
			o.target.onover(o.target);
			over = o;
		}
	}

	function edit_mode_mouse_out(o) {
		if (o.target !== undefined && 'onout' in o.target)
			o.target.onout(o.target);
		over = null;
	}

	function edit_mode_mouse_down(o) {
		/* Is an object being edited through Fabric.js controls? */
		if (canvas.getActiveObject() !== null || !inited || skip_mouse_down) {
			skip_mouse_down = false;
			return;
		}

		/* Is something interactive being clicked on? */
		if (o.target !== undefined && 'onclick' in o.target) {
			o.target.onclick(o.target);
			return;
		}

		if (ctx_menu !== null) {
			ctx_menu.close();
			if (selected !== null && 'obj' in selected &&
					selected.obj.prev_selectable) {
				selected.obj.selectable = true;
				canvas.setActiveObject(selected.obj);
				deselect();
				return;
			}
			deselect();
		}

		is_down = new Date().getTime(); /* Will need the timestamp on mouse:up */

		if (line !== null)
			return;

		if (selected !== null) {
			if (selected.type === 'ln') {
				var lmenu = { 'delete': line_menu.delete };
				if (selected.ltype != 0)
					lmenu.thick = line_menu.thick;
				if (selected.ltype != 1)
					lmenu.thin = line_menu.thin;

				ctx_menu = new menu('line', selected, canvas, selected,
						lmenu, function() { ctx_menu = null; });
			} else if (selected.type in { tx: 0, se: 0, ac: 0 }) {
				var obj_menu =
					(selected.type === 'tx' ? text_menu :
					(selected.type === 'se' ? sensor_menu :
					actuator_menu));

				ctx_menu = new menu(selected.type, selected, canvas, selected,
						obj_menu, function() { ctx_menu = null; });

				set_tip('Click on this object again to select.');
			}

			/* TODO: possibly a pt menu on mouse:up:
			 * start line vs. move node vs. join? */
			if (selected.type != 'pt')
				return;

			var start = selected;
			var from = selected;
			deselect();
		} else {
			/* If nothing selected, start line at cursor position */
			var start = canvas.getPointer(o.e);
			var from = null;
		}

		start_line(start, 0);
		line.props.from = from;
	}

	function edit_mode_mouse_move(o) {
		var pos = canvas.getPointer(o.e);

		if (line === null && is_down === false) {
			if (ctx_menu !== null) {
				var dist = Math.abs(ctx_menu.position_src.x - pos.x) +
					Math.abs(ctx_menu.position_src.y - pos.y);
				if (dist > 120)
					ctx_menu.close();
				return;
			}

			var pt = find_nearest(pos.x, pos.y);
			if (pt[1] > 30) {
				deselect();
				return;
			}

			if (selected === pt[0])
				return;

			if ('obj' in pt[0] && pt[0].obj === canvas.getActiveObject())
				return;

			/* Change the selection/highlight */

			if (ctx_menu !== null && pt[0] !== ctx_menu.position_src) /* Unused now */
				ctx_menu.close();

			deselect();
			select(pt[0]);
			return;
		}

		if (line === null)
			return;

		var pt = find_nearest(pos.x, pos.y, 'pt');
		if (pt[1] > 20) {
			line.props.to = null;
		} else {
			pos = pt[0];
			line.props.to = pt[0];
		}

		var p0 = { x: line.x1, y: line.y1 };
		var dx = pos.x - p0.x;
		var dy = pos.y - p0.y;
		var len = Math.hypot(dx, dy);
		var atan2 = Math.atan2(dx, dy);

		/* TODO: don't allow lines in any directions where another line
		 * starting or ending in p0 exists already.
		 */
		/* Snap to one of the 8 or more directions depending on the distance */
		if (len && line.props.to === null) {
			var num_dirs = 8 << Math.floor(len / 150);
			var dir = atan2 * num_dirs / Math.PI / 2;
			atan2 = Math.PI * 2 * Math.round(dir) / num_dirs;
			dx = len * Math.sin(atan2);
			dy = len * Math.cos(atan2);
		}
		line.props.atan2 = atan2;
		line.props.len = len;
		if (len > line.max_len)
			line.max_len = len;

		line.set({ x2: p0.x + dx, y2: p0.y + dy });
		canvas.renderAll();
	}

	function edit_mode_mouse_up(o) {
		if (is_down === false)
			return;

		var time_down = new Date().getTime() - is_down;
		is_down = false;

		if (line !== null) {
			if (line.max_len < 10) {
				var pos = { x: line.x1, y: line.y1 };

				canvas.remove(line);
				line = null;

				if (time_down > 500)
					return;
				/* If no line was drawn and the button has been down for less than
				 * half a sec, treat this as a click, open the context menu.  */
				ctx_menu = new menu('create', pos, canvas, pos,
						create_menu, function() { ctx_menu = null; });

				return;
			}

			/* Otherwise add a new line */

			if (line.props.from === null)
				line.props.from = add_pt(line.x1, line.y1);
			if (line.props.to === null)
				line.props.to = add_pt(line.x2, line.y2);

			var cx = (line.x1 + line.x2) / 2;
			var cy = (line.y1 + line.y2) / 2;

			ln = add_elem(cx, cy, 'ln');

			ln.obj = line;
			for (var prop in line.props)
				ln[prop] = line.props[prop];
			delete line.props;
			line = null;

			ln.from.adj.push(ln);
			ln.to.adj.push(ln);
		}
	}

	function edit_mode_modified(o) {
		o = o.target;
		if (!('elem' in o))
			return;

		var cp = o.getCenterPoint();
		o.elem.angle = o.getAngle();
		o.elem.x = cp.x;
		o.elem.y = cp.y;
		o.elem.width = o.getWidth();
		o.elem.height = o.getHeight();
		if (o.elem.type === 'tx')
			o.elem.text = o.getText(); /* May possibly use IText */

		modified = true;
	}

	function edit_mode_deselected(o) {
		/* Don't open menu when user tries to clear selection */
		skip_mouse_down = true;
	}

	/* TODO: rewrite all of this so that we keep track of the server status
	 * and only (re-) send when we know we're online, similar to gmail, etc.
	 */
	function save_done(ret) {
		clear_tip('fp-save');
		set_tip('Floorplan saved Ok.');

		modifed = false;
	}

	function save_error(err) {
		clear_tip('fp-save');
		set_tip('Floorplan not saved.');

		if (err.statusCode === undefined)
			alert('Unable to save floorplan: Can\'t connect');
		else if (err.body.length)
			alert('Unable to save floorplan:\n\n' + err.body);
		else
			alert('Error ' + err.statusCode + ' saving the floorplan to server.');
	}

	/* History mode support */

	var temp_state = null;

	function load_temp_state(state, err) {
		if (state === null) {
			set_tip('Request for historical state failed');
			alert('The following error occured when trying to load the ' +
					'state at requested date & time:\n\n' + err);
			return;
		}

		temp_state = state;

		this.update_mode();
		set_tip('Requested historical state loaded.');
	}

	this.slider = new timeline(document.getElementById('fp-time-slider'),
			function(new_timestamp) {
				set_tip('Loading historical state from server.');
				sensorino_state.request_state_at_timestamp(new_timestamp,
						load_temp_state);
			});

	/* Mode switch support and general initialisation */

	var mode = 'none';

	this.update_mode = function() {
		/* Objects are selectable only in edit mode */
		var selectable = (mode === 'edit');

		/*
		 * If we're switching away from history mode, may need to tell all our
		 * widgets to show the current state again.
		 */
		var state = (mode === 'hist' && temp_state !== null) ? temp_state :
			sensorino_state;

		for (var i = 0; i < this.elems.length; i++) {
			var elem = this.elems[i];

			if (elem.type === 'tx' || elem.type === 'se' || elem.type === 'ac')
				elem.obj.selectable = selectable;

			if (elem.type === 'se' || elem.type === 'ac')
				elem.widget.set_state(state);
		}
	}

	this.switch = function(to) {
		this.reset_edit_state();

		canvas.off('mouse:down')
		canvas.off('mouse:move')
		canvas.off('mouse:up')
		canvas.off('mouse:over')
		canvas.off('mouse:out')
		canvas.off('object:modified')
		canvas.off('selection:cleared');

		if (over !== null) {
			if (mode === 'view')
				view_mode_mouse_out(over);
			else if (mode === 'hist')
				hist_mode_mouse_out(over);
			else if (mode === 'edit')
				edit_mode_mouse_out(over);
		}

		if (to === 'view') {
			canvas.on('mouse:down', view_mode_mouse_down);
			canvas.on('mouse:over', view_mode_mouse_over);
			canvas.on('mouse:out', view_mode_mouse_out);
		} else if (to === 'hist') {
			canvas.on('mouse:over', hist_mode_mouse_over);
			canvas.on('mouse:out', hist_mode_mouse_out);
		} else if (to === 'edit') {
			canvas.on('mouse:down', edit_mode_mouse_down);
			canvas.on('mouse:move', edit_mode_mouse_move);
			canvas.on('mouse:up', edit_mode_mouse_up);
			canvas.on('mouse:over', edit_mode_mouse_over);
			canvas.on('mouse:out', edit_mode_mouse_out);
			canvas.on('object:modified', edit_mode_modified);
			canvas.on('selection:cleared', edit_mode_deselected);
		}

		/* If we're exiting the edit mode, submit new state to server */
		if (mode === 'edit' && to !== 'edit' && inited && modified) {
			set_tip('Saving changes…', 'fp-save');

			var options = {
				url: '/api/floorplan.json',
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: this.get_state(),
			};

			oboe(options).fail(save_error).done(save_done);
		}

		mode = to;

		this.update_mode();
	}

	/* Everything is now initialised, load the floorplan data from server */
	this.load_state = function(state) {
		this.reset_edit_state()
		this.clear_state();

		var node_map = {};
		for (var i = 0; i < state.length; i++) {
			var state_elem = state[i];
			var elem = add_elem(state_elem.x, state_elem.y, state_elem.type);

			for (var key in state_elem)
				if (key == 'x' || key == 'y' || key == 'type')
					continue;
				else if (key == 'from' || key == 'to') {
					var pt;

					if (state_elem[key] in node_map)
						pt = node_map[state_elem[key]];
					else {
						var coords = state_elem[key].split(',', 2);
						pt = add_pt(parseFloat(coords[0]), parseFloat(coords[1]));
						node_map[state_elem[key]] = pt;
					}

					elem[key] = pt;
					pt.adj.push(elem);
				} else
					elem[key] = state_elem[key];

			if (elem.type == 'ln') {
				start_line(elem, elem.ltype);
				elem.obj = line, line = null;

				elem.obj.set({ x1: elem.from.x, y1: elem.from.y,
						x2: elem.to.x, y2: elem.to.y });
				delete elem.obj.props;
			} else if (elem.type == 'tx') {
				elem.obj = new fabric.Text(elem.text, {
					fontFamily: 'Times', /* TODO: style */
					stroke: '#555', /* TODO: style */
					originX: 'center',
					originY: 'center',
					left: elem.x,
					top: elem.y,
					angle: elem.angle,
				});
				/* Setting .width or .height has no effect */
				elem.obj.setScaleX(elem.width / elem.obj.width);
				elem.obj.setScaleY(elem.height / elem.obj.height);
				elem.obj.elem = elem; /* For move/rotate callbacks' use */
				canvas.add(elem.obj);
			} else if (elem.type == 'se' || elem.type == 'ac') {
				/* First find the constructor of this Sensor/Actuator widget type */
				var class_list = elem.type == 'se' ? this.sensors : this.actuators;
				var cls = undefined;
				for (var j = 0; j < class_list.length; j++)
					if (elem.dsp_type == class_list[j].name) {
						cls = class_list[j].cls;
						break;
					}

				/* Now we can instantiate it */
				elem.widget = new cls(canvas, elem);
				elem.widget.set_state(sensorino_state);
				elem.obj.elem = elem; /* For move/rotate callbacks' use */
				elem.obj.set({
					left: elem.x,
					top: elem.y,
					angle: elem.angle,
				});
				/* Setting .width or .height has no effect */
				elem.obj.setScaleX(elem.width / elem.obj.width);
				elem.obj.setScaleY(elem.height / elem.obj.height);
				canvas.add(elem.obj);
			}
		}

		modified = false;

		this.update_mode();
		canvas.renderAll(); /* TODO: May also disable auto-rerender temporarily */
		this.update_unused_services();
	};

	/* Launch the floorplan request once the sensorino state is initialised */
	function load_done(obj) {
		inited = 1;

		/* TODO: try/catch */
		this_obj.load_state(obj);
	}

	function load_error(err) {
		var msg = 'Problem loading the floorplan state from the server.  ' +
			'Something must be wrong with the server or the connection.  You\'ll ' +
			'need to refresh this page to retry.';

		if (err.statusCode === undefined)
			alert('Can\'t connect\n\n' + msg);
		else if (err.body.length)
			alert(msg + '\n\nServer returned this: ' + err.body);
		else
			alert('Error ' + err.statusCode + '.\n\n' + msg);
	}

	var req = null;
	function state_update() {
		if (inited)
			this_obj.update_unused_services();
		else if (req === null)
			req = oboe('/api/floorplan.json').fail(load_error).done(load_done);
	}

	sensorino_state.subscribe_updates(state_update);
	if (sensorino_state.inited)
		state_update();
}

floorplan.prototype.get_state = function() {
	var state = [];

	for (var i = 0; i < this.elems.length; i++) {
		var elem = this.elems[i];

		if (elem.type === 'pt')
			continue;

		var state_elem = {};
		state.push(state_elem);

		for (var key in elem)
			if (key === 'obj')
				continue;
			else if (key === 'from' || key === 'to')
				state_elem[key] = elem[key].x + ',' + elem[key].y;
			else if (key !== 'adj')
				state_elem[key] = elem[key];
			/* TODO: may also want to drop and recalculate stuff like len, atan2 */
	}

	return state;
};

floorplan.prototype.clear_state = function() {
	/* TODO: disable auto re-render temporarily? */
	for (var i = 0; i < this.elems.length; i++) {
		var elem = this.elems[i];

		if ('obj' in elem)
			this.canvas.remove(elem.obj);
		if ('widget' in elem)
			elem.widget.cleanup();
	}

	this.elems = [];
};

/* TODO: make graphical and async, move to a different class/file,
 * when only one channel of given type then display it as just type addr.
 * when only one type in a service then only show the service addr.
 */
floorplan.prototype.query_channels = function(reqs, is_actuator) {
	var unused = [];
	var channels = [];
	var all = this.sensorino_state.get_channel_lists()[is_actuator ? 1 : 0];

	/* .indexOf() won't work for checking if a channel is present in "all"
	 * because it uses pointer comparison.  We could use .find or .includes/
	 * .contains() and they polyfills from MDN but probably it's simplest
	 * and possibly faster to use an object.
	 */
	var all_map = {};
	all.forEach(function(chan) { all_map[chan] = chan; });

 	/* Get a list of unused channels of the type indicated by is_actuator */
	this.unused.forEach(function(chan) {
			if (chan in all_map)
				unused.push(chan);
		});

	for (var i = 0; i < reqs.length; i++) {
		var msg = 'TODO: proper UI with a nice clickable list of all ' +
			'services, with the ones yet unused highlighted in bold.\n\n' +
			'Please select ' + (is_actuator ? 'an actuator' : 'a sensor') +
			' data channel to be used as input channel ' + (i + 1) +
			' of ' + reqs.length + ' required by this widget.  The following ' +
			'type is expected: ' + reqs[i] + '\n\nThe following channels are ' +
			'currently unused:\n';
		var options = [];
		for (var j = 0; j < unused.length && j < 10; j++)
			options.push(this.sensorino_state.format_channel(unused[j]));
		for (var j = 0; j < options.length; j++)
			msg += '\n' + options[j];
		if (unused.length > 10)
			msg += '\n...';

		var def = undefined;
		if (options.length)
			def = options[0].split(' ', 1)[0];
		var resp = prompt(msg, def);
		if (resp === null)
			return null;

		/* TODO: allow any address as long as the components are valid */
		var channel = this.sensorino_state.parse_channel(resp);
		if (!(channel in all_map)) {
			alert('Invalid channel address.');
			return null;
		}

		var idx = unused.indexOf(channel);
		unused.splice(idx, 1);

		channels.push(channel);
	}

	return channels;
};

floorplan.prototype.update_unused_services = function() {
	var used = {};

	this.elems.forEach(function(elem) {
			if (elem.type !== 'se' && elem.type !== 'ac')
				return;
			elem.channels.forEach(function(channel) { used[channel] = null; });
		});

	var unused = [];

	this.sensorino_state.get_channel_list().forEach(function(channel) {
			if (!(channel in used))
				unused.push(channel);
		});

	this.unused = unused;

	var elem = document.getElementById('fp-unused-warning');

	if (!unused.length) {
		elem.style.visibility = 'hidden';
		return;
	}

	/* TODO: figure out which channels are actuators and which are sensors */

	elem.style.visibility = 'inherit';

	var services = {};
	unused.forEach(function(channel) { services[channel.slice(0, 2)] = null; });
	services = Object.keys(services);

	var are = unused.length == 1 ? 'is' : 'are';
	var s = unused.length == 1 ? '' : 's';
	var ss = services.length == 1 ? '' : 's';

	elem.textContent = 'There ' + are + ' ' + unused.length + ' channel' + s +
		' in ' + services.length + ' service' + ss + ' that ' + are +
		' not assigned to any sensor or actuator widget in your floorplan.  ' +
		'Go to Edit Floorplan mode to add controls for these services.  In the ' +
		'channel selection dialog select one of the highlighted channels.';
};

floorplan.prototype.sensors = [];
floorplan.prototype.register_sensor = function(sensor_class, name, desc) {
	floorplan.prototype.sensors.push(
			{ cls: sensor_class, name: name, desc: desc });
};

floorplan.prototype.actuators = [];
floorplan.prototype.register_actuator = function(actuator_class, name, desc) {
	floorplan.prototype.actuators.push(
			{ cls: actuator_class, name: name, desc: desc });
};

/* Polyfills from MDN */

if (!Math.hypot) {
	Math.hypot = function hypot() {
		var y = 0;
		var length = arguments.length;

		for (var i = 0; i < length; i++) {
			if(arguments[i] === Infinity || arguments[i] === -Infinity) {
				return Infinity;
			}
			y += arguments[i] * arguments[i];
		}
		return Math.sqrt(y);
	};
}
/* vim: ts=2:
*/
