function popup() {
	/*
	 * Create the background div that covers the normal UI under the popup
	 * to make the popup as "modal" as easily possible.
	 */
	this.bg = document.createElement('div');
	this.bg.classList.add('popup-bg');
	/* These are independent of the graphical style, so they go in the code */
	this.bg.style.position = 'absolute';
	this.bg.style.left = '0';
	this.bg.style.top = '0';
	this.bg.style.width = '100%';
	this.bg.style.height = '100%';
	this.bg.style.zIndex = 10000;
	document.body.appendChild(this.bg);

	/*
	 * TODO: Attach a mousescroll handler to keep this and other events
	 * from bubbling up.
	 */

	/* Create the popup "window" */
	this.obj = document.createElement('div');
	this.obj.classList.add('popup');
	this.bg.appendChild(this.obj);
}

popup.prototype.close = function() {
	document.body.removeChild(this.bg);
}

/* vim: ts=2:
*/
