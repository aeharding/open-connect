/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* The launch URL supplies data only; authored application files stay separate. */
(function () {
    "use strict";
    var entry = document.getElementById("oc-usb-loader");
    if (!entry || window.__ocUSBLoading) { return; }
    var token = entry.ocToken;
    var base = entry.src.slice(0, entry.src.lastIndexOf("/") + 1);
    var stopped = false, nodes = [entry];
    var state = {token: token, cancel: finish};
    window.__ocUSBLoading = state;
    function finish() {
        stopped = true;
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i] && nodes[i].parentNode) { nodes[i].parentNode.removeChild(nodes[i]); }
        }
        if (window.__ocUSBLoading === state) { delete window.__ocUSBLoading; }
    }
    function load(file, id, next) {
        if (stopped) { return; }
        utility.loadScript(base + file, {id: id, ocToken: token}, function () {
            if (!stopped) { next(); }
        });
        nodes.push(document.getElementById(id));
    }
    if (window.OpenConnect && OpenConnect.reopenUSB && OpenConnect.reopenUSB(token)) { finish(); return; }
    load("runtime.js", "oc-usb-ui", function () {
        OpenConnect.start(token, true);
        finish();
    });
}());
