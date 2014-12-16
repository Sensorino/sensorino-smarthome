function panels(classname) {
	this.panels = [];
	this.elems = [];

	/* Find subpanels and store elements in a conventional list, initialise */
	for (var i = 0;; i++) {
		var panel_elems = document.getElementsByClassName(classname + ' c' + i);
		if (!panel_elems.length)
			break;

		var panel = undefined;
		for (var j = 0; j < panel_elems.length; j++)
			if (this.elems.indexOf(panel_elems[j]) == -1) {
				this.elems.push(panel_elems[j]);
				panel = panel || panel_elems[j];
			}

		var id = panel.id;
		var prefix = classname + '_' + id + '_';

		panel.panel_init = window[prefix + 'init'] || function() {};
		panel.panel_enter = window[prefix + 'enter'] || function() {};
		panel.panel_exit = window[prefix + 'exit'] || function() {};
		panel.panel_active = false;
		panel.name = panel.getAttribute('panel-name');
		panel.tip = panel.getAttribute('panel-tip');

		this.panels.push(panel);
		/* TODO: could also do a lazy init */
		panel.panel_init(panel);
	}

	this.active = -1;
	this.switch(0);
}

panels.prototype.switch = function(to) {
	if (this.active >= 0)
		this.panels[this.active].panel_exit();

	this.active = to;
	for (var i = 0; i < this.panels.length; i++)
		this.panels[i].panel_active = (this.active == i);

	for (var i = 0; i < this.elems.length; i++) {
		var elem = this.elems[i];
		elem.style.visibility =
			elem.classList.contains('c' + this.active) ? 'inherit' : 'hidden';
	}

	this.panels[this.active].panel_enter();
}
/* vim: ts=2:
*/
