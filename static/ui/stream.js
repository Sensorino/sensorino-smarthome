/* Use Oboe to stream a resource.  The stream will transparently
 * reconnect to keep the connection alive and provide the caller
 * a reliable never-ending streaming.  The reconnection and timeout
 * rules used are based on Twitter's streaming API's reconnection
 * guidelines.
 */
function stream(url, handler, status) {
	var online = false;
	var conn = null;
	var to = null;
	var retry = 0;

	function start() {
		if (to !== null)
			clearInterval(to);

		if (status !== undefined && !online)
			status('connecting');

		if (retry < 5)
			retry++;

		conn = oboe(url).
			start(start_handler).
			node('![*]', node_handler).
			fail(fail_handler).
			done(function() { fail_handler('done'); });
		/* TODO: Accept: application/json */

		/* Abort attempt after 30 seconds if not progressing */
		to = setTimeout(function() {
				to = null;
				fail_handler('too-slow');
			}, 30000);
	}

	function start_handler(code, headers) {
		if (code < 200) {
			fail_handler('cant-connect');
			return;
		}

		clearTimeout(to);

		if (status !== undefined && !online)
			status('online');
		online = true;
		retry = 0;

		/* Close the connection after 3 minutes to avoid stalling */
		to = setTimeout(function() {
				to = null;
				fail_handler('reconnect');
			}, 180000);
	}

	function node_handler(node) {
		handler(node);
		return oboe.drop;
	}

	fail_handler = function(err) {
		if (conn === null)
			return;

		if (to !== null) {
			clearTimeout(to);
			to = null;
		}

		if (err !== 'reconnect')
			console.log(url + ' stream error:' , err);

		if (err === 'done')
			conn = null;
		else {
			var tmp = conn;
			conn = null;
			tmp.abort();
		}

		var secs_wait = 3 << retry;
		setTimeout(start, secs_wait * 1000);

		if (err !== 'reconnect' && status !== undefined) {
			status('offline', secs_wait);
			to = setInterval(function() {
					secs_wait -= 5;
					status('offline', secs_wait);
				}, 5000);
		}
		if (err !== 'reconnect')
			online = false;
	}

	start();
}

/* TODO: a class wrapping stream() that eliminates possible backlog dupes
 * when reconnecting, and takes the backlog part at the beginning of the
 * stream into account.
 */

/* Possibly also a similar class for older browsers, using a long-polling
 * solution (could also use Oboe, if we know it only returns the final
 * downloaded JSON document on a given browser).
 */

/* vim: ts=2:
*/
