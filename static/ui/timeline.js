function timeline(obj, handler) {
	this.obj = obj;
	this.handler = handler;
	var this_obj = this;

	/* TODO: 12/24 display settings */
	/* TODO: scale the number of labels with window width */

	/* Value of -1 means current time */
	this.value = -1;

	this.value_div = document.createElement('div');
	this.value_div.classList.add('timeline-value');
	this.line_div = document.createElement('div');
	this.line_div.classList.add('timeline-line');
	this.axis_div = document.createElement('div');
	this.axis_div.classList.add('timeline-axis');
	this.timestamp_marker = document.createElement('div');
	this.timestamp_marker.classList.add('timeline-marker');
	this.timestamp_marker.classList.add('timeline-ts-marker');
	this.current_marker = document.createElement('div');
	this.current_marker.classList.add('timeline-marker');
	this.current_marker.classList.add('timeline-cur-marker');
	this.hover_marker = document.createElement('div');
	this.hover_marker.classList.add('timeline-marker');
	this.hover_marker.classList.add('timeline-hover-marker');

	this.obj.appendChild(this.value_div);
	this.obj.appendChild(this.line_div);
	this.line_div.appendChild(this.axis_div);
	this.line_div.appendChild(this.timestamp_marker);
	this.line_div.appendChild(this.current_marker);
	this.line_div.appendChild(this.hover_marker);

	this.labels = [];

	this.update();
	attach(this.line_div, 'mousemove', function(evt) {
			this_obj.hover_update(evt);
		}, false);
	attach(this.line_div, 'mouseover', function(evt) {
			this_obj.hover_marker.style.visibility = 'visible';
			this_obj.line_rect = this_obj.line_div.getBoundingClientRect();
			this_obj.hover_update(evt);
		}, true);
	attach(this.line_div, 'mouseout', function(evt) {
			this_obj.hover_marker.style.visibility = 'hidden';
			clear_tip('time');
		}, true);
	attach(this.line_div, 'mousedown', function(evt) {
			this_obj.line_rect = this_obj.line_div.getBoundingClientRect();
			this_obj.move_timestamp(evt);
		}, false);
}

timeline.prototype.get_timestamp = function() {
	if (this.value === -1)
		return Date.now() * 0.001;
	else
		return this.value;
}

timeline.prototype.update = function() {
	this.timestamp = this.get_timestamp();
	this.upper_limit = Date.now() * 0.001;
	this.lower_limit = this.timestamp - 2 * 365 * 24 * 60 * 60; /* 2 years back */
	this.update_steps();

	this.timestamp_marker.style.left =
		this.timestamp_to_pos(this.timestamp) + '%';
	this.current_marker.style.left =
		this.timestamp_to_pos(this.upper_limit) + '%';
	this.axis_div.style.left =
		this.timestamp_to_pos(this.lower_limit) + '%';
	this.axis_div.style.width =
		(this.timestamp_to_pos(this.upper_limit) -
			this.timestamp_to_pos(this.lower_limit)) + '%';

	var date = new Date(this.timestamp * 1000);
	this.value_div.textContent =
		date.toDateString() + ' ' +
		date.toTimeString().substr(0, 5) + '+' +
		date.getSeconds() + '.' +
		Math.floor(date.getMilliseconds() * 0.01) + 's (' +
		this.rel_time_str(this.timestamp - this.upper_limit - 0.0001, 'ago') + ')';

	/* Update labels */
	while (this.labels.length)
		this.obj.removeChild(this.labels.shift());

	date.setMinutes(0, 0, 0);
	var hour_timestamp = date.getTime() * 0.001;
	date.setHours(12);
	var day_timestamp = date.getTime() * 0.001;
	date.setDate(15);
	var month_timestamp = date.getTime() * 0.001;

	this.min_ts = this.timestamp;
	this.max_ts = this.timestamp;
	this.min_x = this.obj.clientWidth;
	this.max_x = 0;

	for (var i = 0; i <= 5; i++) {
		this.add_label(hour_timestamp + i * 60 * 60, 1);
		this.add_label(hour_timestamp - i * 60 * 60, 1);
	}
	for (var i = 0; i <= 5; i++) {
		this.add_label(day_timestamp + i * 24 * 60 * 60, 2);
		this.add_label(day_timestamp - i * 24 * 60 * 60, 2);
	}
	for (var i = 0; i <= 5; i++) {
		this.add_label(month_timestamp + i * 30 * 24 * 60 * 60, 3); /* FIXME */
		this.add_label(month_timestamp - i * 30 * 24 * 60 * 60, 3); /* FIXME */
	}
	this.add_label(this.upper_limit, 0);
}

timeline.prototype.add_label = function(ts, precision) {
	if (ts > this.upper_limit || ts < this.lower_limit ||
			!(ts < this.min_ts || ts > this.max_ts))
		return;

	if (ts < this.min_ts)
		this.min_ts = ts;
	else
		this.max_ts = ts;

	var pos = this.timestamp_to_pos(ts);
	var x = pos * this.obj.clientWidth / 100;

	if (x > this.min_x && x < this.max_x)
		return;

	if (x < this.min_x)
		this.min_x = x - 50;
	else
		this.max_x = x + 50;

	var label = document.createElement('div');

	label.classList.add('timeline-label');
	label.style.left = (x - 100) + 'px';
	label.style.width = '200px';

	var date = new Date(ts * 1000.0);
	if (precision === 0)
		label.textContent = 'now';
	else if (precision === 1)
		label.textContent = date.getHours() + ':00';
	else if (precision === 2) {
		var days = [ 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat' ];
		label.textContent = days[date.getDay()];
	} else {
		var months = [ 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
			'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec' ];
		label.textContent = months[date.getMonth()] + ' ' + date.getFullYear();
	}

	this.labels.push(label);
	this.obj.appendChild(label);
}

/*
 * Decide where to show the selected timestamp on T axis.  Since the axis
 * has no lower limit, but has an upper limit which is the current time, if
 * the currently selected time is close to current time, it's goint to be
 * shown closer to the right edge.  If it's further back, it's going to be
 * closer to the middle.
 */
timeline.prototype.update_steps = function() {
	var right_edge = 100;
	var current = 50;

	/*
	 * Move the right end of the time line closer to 75% and the current
	 * timestamp's position closer to the right end as value approches the
	 * upper limit.
	 */
	if (this.upper_limit - this.timestamp < 2 * 24 * 60 * 60) {
		/* Fraction of two days period */
		var dist = 1.0 - (this.upper_limit - this.timestamp) / (2 * 24 * 60 * 60);

		right_edge -= 25 * Math.pow(dist, 10);
		current += 25 * Math.pow(dist, 10);
	}

	var middle = (this.upper_limit + this.timestamp) * 0.5;
	this.steps = [
		[ this.timestamp, current, this.lower_limit, 0 ],
		[ this.timestamp, current, middle, 75 ],
		[ this.upper_limit, right_edge, middle, 75 ]
	];
}

timeline.prototype.log_factor = 4; /* 4-fold increase per every 1/10th dist */
timeline.prototype.log_scale = Math.pow(timeline.prototype.log_factor, 10) - 1;

timeline.prototype.timestamp_to_pos = function(value) {
	for (var i = 0; i < this.steps.length; i++) {
		var step = this.steps[i];
		if ((value >= step[0] && value <= step[2]) ||
				(value >= step[2] && value <= step[0])) {
			var dist = (value - step[0]) / (step[2] - step[0]);
			dist = Math.log(dist * this.log_scale + 1) /
				Math.log(this.log_factor) * 0.1;

			if (value >= step[0])
				return step[1] + dist * (step[3] - step[1]);
			else
				return step[1] + dist * (step[3] - step[1]);
		}
	}

	return null;
}

timeline.prototype.pos_to_timestamp = function(pos) {
	for (var i = 0; i < this.steps.length; i++) {
		var step = this.steps[i];
		if ((pos >= step[1] && pos <= step[3]) ||
				(pos >= step[3] && pos <= step[1])) {
			var dist = (pos - step[1]) / (step[3] - step[1]);
			dist = (Math.pow(this.log_factor, dist * 10) - 1) / this.log_scale;

			if (pos >= step[1])
				return step[0] + dist * (step[2] - step[0]);
			else
				return step[0] + dist * (step[2] - step[0]);
		}
	}

	return null;
}

timeline.prototype.rel_time_str = function(secs, fmt) {
	var s = '';
	var sign = secs >= 0;
	var units = [ 365 * 24 * 60 * 60, 'year', 30 * 24 * 60 * 60, 'month',
		24 * 60 * 60, 'day', 60 * 60, 'hour', 60, 'min', 1, 'sec', 0.001, 'ms' ];
	var i;

	secs = Math.abs(secs);
	for (i = 0; i < units.length - 2; i += 2)
		if (secs >= units[i])
			break;

	if (fmt == '+')
		s += sign ? '+' : '-';

	var num = secs / units[i];
	if (num >= 3.0)
		s += Math.round(num);
	else
		s += Math.floor(num);
	var mult = num >= 2.0 && units[i + 1].substr(-1) != 's';
	s += ' ' + units[i + 1] + (mult ? 's' : '');

	if (num < 3.0 && i < units.length - 2) {
		secs -= Math.floor(num) * units[i];
		num = secs / units[i + 2];
		s += ' ' + Math.floor(num);
		var mult = (num >= 2.0 || num < 1.0) && units[i + 3].substr(-1) != 's';
		s += ' ' + units[i + 3] + (mult ? 's' : '');
	}

	if (fmt == 'ago')
		s += sign ? ' in the future' : ' ago';
	else if (fmt == 'earlier')
		s += sign ? ' later' : ' earlier';

	return s;
}

timeline.prototype.move_timestamp = function(evt) {
	var x = evt.clientX - this.line_rect.left;
	var pos = 100 * x / this.line_div.clientWidth;

	var ts = this.pos_to_timestamp(pos);
	if (ts === null)
		return;

	this.value = ts;

	this.update();
	this.hover_update(evt);

	if (this.handler !== undefined)
		this.handler(evt);
}

timeline.prototype.hover_update = function(evt) {
	var x = evt.clientX - this.line_rect.left;
	var pos = 100 * x / this.line_div.clientWidth;

	var ts = this.pos_to_timestamp(pos);
	if (ts === null)
		return;

	var msg = 'Go ' + this.rel_time_str(ts - this.timestamp, '+');
	if (Math.abs(this.timestamp - this.upper_limit) >= 60)
		msg += ' (' + this.rel_time_str(ts - this.upper_limit, 'ago') + ')';
	set_tip(msg, 'time');

	this.hover_marker.style.left = x + 'px';
}

/* vim: ts=2:
*/
