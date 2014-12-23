function choice(obj_id, handler) {
	this.options = handler.options;
	this.obj = document.getElementById(obj_id);
	this.obj.classList.add('choice');

	for (var i = 0; i < this.options.length; i++) {
		var option = this.options[i];

		option.choice_obj = document.createElement('button');
		option.choice_obj.textContent = option.name || option.id;
		option.choice_obj.classList.add('choice-button');
		if (i == 0)
			option.choice_obj.classList.add('choice-button-first');
		if (i == this.options.length - 1)
			option.choice_obj.classList.add('choice-button-last');
		option.choice_obj.style.left = (100 * i / this.options.length) + '%';
		/*option.choice_obj.style.width = (100 / this.options.length) + '%';*/

		var the_choice = this;
		option.choice_obj.choice_num = i;
		attach(option.choice_obj, 'click', function(evt) {
			var choice_obj = this;
			handler.switch(choice_obj.choice_num);
			active_update();
		}, true);
		if ('tip' in option) {
			option.choice_obj.tip = option.tip;
			attach(option.choice_obj, 'mouseover', function(evt) {
				var choice_obj = this;
				document.getElementById('tip').textContent = choice_obj.tip;
			});
			attach(option.choice_obj, 'mouseout', function(evt) {
				document.getElementById('tip').textContent = '';
			});
		}

		this.obj.appendChild(option.choice_obj);
	}

	function active_update() {
		for (var i = 0; i < handler.options.length; i++) {
			var option = handler.options[i];
			if (i == handler.active)
				option.choice_obj.classList.add('choice-button-active');
			else
				option.choice_obj.classList.remove('choice-button-active');
		}
	}
	handler.switch(0);
	active_update();
}

function attach(obj, evt, fn, capt) {
	if (obj.addEventListener) {
		if (navigator.appName.indexOf("Netscape") == -1)
			if (evt == "DOMMouseScroll")
				evt = "mousewheel";
		if (navigator.userAgent.indexOf("Safari") != -1) {
			if (evt == "DOMMouseScroll")
				obj.onmousewheel = fn;
			else
				obj.addEventListener(evt, fn, capt);
		} else
			obj.addEventListener(evt, fn, capt);
	} else {
		if (evt == "DOMMouseScroll")
			obj.attachEvent("onmousewheel", fn);
		else
			obj.attachEvent("on" + evt, fn);
	}
};
/* vim: ts=2:
*/
