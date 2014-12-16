function menu(mclass, param, canvas, pos, opts, onclose, dontclose) {
	if (!(mclass in menu.prototype.all_menus))
		menu.prototype.all_menus[mclass] = []
	menu.prototype.all_menus[mclass].push(this);

	this.opts = []; /* TODO: use the dict directly */
	for (var entry in opts)
		this.opts.push(opts[entry]);
	this.mclass = mclass;
	this.dontclose = dontclose;
	this.onclose = onclose;
	this.param = param;
	this.canvas = canvas;
	this.position_src = pos;
	this.create(pos.x, pos.y);
}

menu.prototype.all_menus = {};

menu.prototype.create = function(x, y) {
	/* Based on
	 * https://github.com/openstreetmap/iD/blob/master/js/id/ui/radial_menu.js */
	var r = 60; /* TODO: style */
	var a = Math.PI / 4;
	var a0 = -Math.PI / 4;
	var a1 = a0 + (this.opts.length - 1) * a;
	var path_str = 'M' + (x + r * Math.sin(a0)) + ',' + (y + r * Math.cos(a0)) +
		' A' + r + ',' + r + ' 0 ' + (this.opts.length > 5 ? '1' : '0') + ',0 ' +
		(x + r * Math.sin(a1) + 1e-3) + ',' +
		(y + r * Math.cos(a1) + 1e-3); /* positive-length path (iD issue #1305) */
	this.path = new fabric.Path(path_str, {
		strokeWidth: 50, /* TODO: style */
		strokeLineCap: 'round',
		stroke: '#abf', /* TODO: style */
		opacity: 0.5, /* TODO: style */
		fill: null,
		originX: 'center',
		originY: 'center',
		selectable: false
	});

	this.canvas.add(this.path);

	var the_menu = this;
	for (var i = 0; i < this.opts.length; i++) {
		var opt = this.opts[i];

		if (!('obj' in opt))
			continue;

		opt.obj.setLeft(x + r * Math.sin(a0 + i * a) - opt.obj.getWidth() / 2);
		opt.obj.setTop(y + r * Math.cos(a0 + i * a) - opt.obj.getHeight() / 2);
		opt.obj.selectable = false;
		opt.obj.option = opt;
		opt.obj.onclick = function(o) {
			if (the_menu.dontclose != true)
				the_menu.close();
			o.option.fun(the_menu.param, o.option);
		};
		opt.obj.onover = function(o) {
			var tip = document.getElementById('tip');
			tip.textContent = o.option.tip;
		};
		opt.obj.onout = function(o) {
			tip.textContent = '';
		};
		this.canvas.add(opt.obj);
	}

	/* TODO: show tips/labels etc. */
}

menu.prototype.close = function() {
	this.canvas.remove(this.path);

	for (var i = 0; i < this.opts.length; i++) {
		var opt = this.opts[i];
		this.canvas.remove(opt.obj);
	}

	var idx = menu.prototype.all_menus[this.mclass].indexOf(this);
	menu.prototype.all_menus[this.mclass].splice(idx, 1);

	if (this.onclose !== undefined)
		this.onclose(this);
}
/* vim: ts=2:
*/
