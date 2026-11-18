/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Appended inside a function(token, port) alongside dialog.js by the USB builder. */
if (window.__ocUSB) { return; }
var cancelDialog = null, ticks = 0, finished = false;
var state = {token: token, cancel: function () { finish("cancel"); }};
window.__ocUSB = state;
function mark(event) {
    log.jciLogger.JCILog("framework ERROR ocusb.js[1] OCUSB|" + token + "|" + event);
}
function finish(reason) {
    if (finished) { return; }
    finished = true;
    clearInterval(timer);
    clearTimeout(deadline);
    if (cancelDialog) { cancelDialog(); }
    if (window.__ocUSB === state) { delete window.__ocUSB; }
    mark(reason);
    // The existing bounded loopback receiver acknowledges only this session.
    state.ack = new Image();
    state.ack.src = "http://127.0.0.1:" + port + "/" + token;
}
var deadline = setTimeout(function () { finish("expired"); }, 60000);
var timer = setInterval(function () {
    try {
        if (++ticks > 80) { finish("busy"); return; }
        var fw = window.framework;
        if (!fw || !fw._browserShown) { return; }
        cancelDialog = OpenConnectInstaller.preview(fw, function () { finish("cancel"); });
        if (cancelDialog) { clearInterval(timer); mark("visible"); }
    } catch (error) {
        finish("error");
    }
}, 250);
