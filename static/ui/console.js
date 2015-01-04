function sensorino_console() {
	/* TODO: we will later accept a sensorino_state parameter that
	 * is going to track both the sensor network state and the console
	 * as a combined stream.
	 */

	/* Message display */

	function format_line(output, obj) {
		var timestamp = obj[0];
		var line = obj[1];

		/* TODO: also display the timestamp in some format, e.g. an onmouseover
		 * hint or group messages with headers something like "over 5 minutes ago",
		 * "over 30 minutes ago", "yesterday", "last week", etc.
		 */

		var code = document.createElement('code');
		var pref = document.createElement('span');

		pref.textContent = line.substr(0, 4);
		pref.classList.add('prefix');
		code.textContent = line.substr(4);
		code.classList.add('language-json');

		if (line[0] == '>')
			code.classList.add('out');
		else if (line[0] == '<')
			code.classList.add('in');
		if (line.substr(0, 3).indexOf('!') >= 0)
			code.classList.add('error');

		var br = document.createElement('br');

		hljs.highlightBlock(code);
		code.insertBefore(pref, code.firstChild);
		output.appendChild(code);
		output.appendChild(br);

		/* Scroll to the bottom if there's a y-overflow */
		/* TODO: Perhaps only scroll if we were at the bottom before this
		 * line was added.  Or possibly add an "autoscroll" checkbox.
		 * TODO: animate */
		code.scrollIntoView(false);

		return [ timestamp, code, br ];
	}

	/* Live console view */

	var output_obj = document.getElementById('console-view');
	var status_obj = document.getElementById('conn-status');

	var lines = [];

	function handle_new_line(obj) {
		var timestamp = obj[0];
		var line = obj[1];

		if (lines.length && timestamp <= lines[lines.length - 1][0])
			return;

		lines.push(format_line(output_obj, obj));

		/* Remove very old lines */
		while (lines.length > 100) {
			var line_rec = lines.shift();
			for (var i = 1; i < line_rec.length; i++)
				output_obj.removeChild(line_rec[i]);
		}
	}

	stream('/api/stream/console.json', handle_new_line);

	/* Message input */

	var input_obj = document.getElementById('console-input');
	input_obj.innerHTML = '<input id="console-edit" autocomplete="no" ' +
		'placeholder="{ &quot;to&quot;: …, &quot;type&quot;: ' +
		'&quot;…&quot;, &quot;serviceId&quot;: … }" ' +
		'inputmode="verbatim" maxlength="256" spellcheck="false" ' +
		'type="text" /><button id="console-send" />';
	var edit_obj = document.getElementById('console-edit');
	var send_obj = document.getElementById('console-send');

	function send_done(ret) {
		if (ret != 'err')
			edit_obj.value = '';
		send_obj.textContent = 'Send to base';
		edit_obj.disabled = false;
		send_obj.disabled = false;
	}
	send_done();

	function send_error(err) {
		if (err.statusCode === undefined)
			alert('Unable to send message: Can\'t connect');
		else if (err.body.length)
			alert('Unable to send message:\n\n' + err.body);
		else
			alert('Error ' + err.statusCode +
					' sending your message');
		send_done('err');
	}

	attach(send_obj, 'click', function(evt) {
			edit_obj.disabled = true;
			send_obj.disabled = true;
			send_obj.textContent = 'Sending';

			var options = {
				url: '/api/console.json',
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: edit_obj.value,
			};

			oboe(options).fail(send_error).done(send_done);
		}, true);

	/* Console history logs view */

	var hist_output_obj = document.getElementById('console-hist-view');

	function load_at_timestamp(new_timestamp) {
		/*
		 * Use the "ago=" parameter to the API call, instead of "at=", to
		 * reduce the dependency on server and client timezone difference and
		 * clock synchronisation.  Unfortunately network delays may be a
		 * problem for some users when passing "ago=".
		 */
		var now = Date.now() * 0.001;
		var ago = now - new_timestamp;

		function load_error(err) {
			set_tip('Error while loading console logs from server.');

			var msg;
			if (err.statusCode === undefined)
				msg = 'Can\'t connect';
			else if (err.body.length)
				msg = 'Server message: ' + err.body;
			else
				msg = 'Error ' + err.statusCode + ' loading historical state.';

			alert('The following error was reported while trying to load ' +
					'the logs from the server:\n\n' + msg);
		}

		function load_done(log) {
			set_tip('Loaded requested logs from the server.');

			hist_output_obj.innerHtml = '';
			hist_output_obj.classList.remove('msg');

			for (var i = 0; i < log.length; i++)
				format_line(hist_output_obj, log[i]);
		}

		set_tip('Loading console logs from server.');
		oboe('/api/console.json?ago=' + ago).fail(load_error).done(load_done);
	}

	hist_output_obj.classList.add('msg');
	hist_output_obj.textContent = 'No console logs are loaded.  Select a ' +
		'date & time on the timeline to load the log buffer at given timestamp.';

	this.slider = new timeline(document.getElementById('console-time-slider'),
			load_at_timestamp);
}
/* vim: ts=2:
*/
