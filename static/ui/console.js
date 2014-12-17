function sensorino_console() {
	/* TODO: we will later accept a sensorino_state parameter that
	 * is going to track both the sensor network state and the console
	 * as a combined stream.
	 */

	/* Message display */

	var output_obj = document.getElementById('console-view');
	var status_obj = document.getElementById('conn-status');

	var lines = [];

	function handle_new_line(obj) {
		var timestamp = obj[0];
		var line = obj[1];

		if (lines.length && timestamp <= lines[lines.length - 1][0])
			return;
		/* TODO: also display the timestamp in some format, e.g. an onmouseover
		 * hint or group messages with headers something like "over 5 minutes ago",
		 * "over 30 minutes ago", "yesterday", "last week", etc.
		 */

		var code = document.createElement('code');
		code.textContent = line;

		code.classList.add('language-json');
		if (line.substr(0, 3).indexOf('!') >= 0)
			code.classList.add('error');

		var br = document.createElement('br');

		hljs.highlightBlock(code);
		output_obj.appendChild(code);
		output_obj.appendChild(br);
		lines.push([ timestamp, code, br ]);

		/* Remove very old lines */
		while (lines.length > 100) {
			var line_rec = lines.unshift();
			for (var i = 1; i < line_rec.length; i++)
				output_obj.removeChild(line_rec[i]);
		}

		/* Scroll to the bottom if there's a y-overflow */
		/* TODO: Perhaps only scroll if we were at the bottom before this
		 * line was added.  Or possibly add an "autoscroll" checkbox.
		 * TODO: animate */
		code.scrollIntoView(false);
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
}
/* vim: ts=2:
*/
