/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* The launch URL supplies data only; authored application files stay separate. */
(function () {
    "use strict";
    var entry = document.getElementById("oc-usb-loader");
    if (!entry) { return; }
    var owner = window.OpenConnect, held = owner && owner.protected && owner.protected();
    if (window.__ocUSBLoading || held) {
        if (held && entry.ocToken && (!window.__ocUSBLoading || entry.ocToken === window.__ocUSBLoading.token) && entry.parentNode) {
            entry.parentNode.removeChild(entry);
        }
        return;
    }
    var token = entry.ocToken;
    var base = entry.src.slice(0, entry.src.lastIndexOf("/") + 1);
    var stopped = false, nodes = [entry];
    var state = {token: token, owner: owner, valid: function () {
        return window.__ocUSBLoading === state && window.OpenConnect === (owner || state.client);
    }, done: finish, resolve: resolve, cancel: function () {
        if (state.client) { state.client.cancelUSB(token); }
        finish();
    }};
    window.__ocUSBLoading = state;
    function resolve(answer) {
        var waits = state.wait || []; delete state.wait;
        waits.forEach(function (fn) { fn(answer); });
    }
    function finish() {
        resolve();
        stopped = true; owner = null; state.owner = state.client = null;
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
    // Use this verified package's client, including its operation deadline.
    // Runtime retains the installed client until the replacement is ready.
    load("runtime.js", "oc-usb-ui", function () {
        if (!state.client) { finish(); return; }
        state.client.start(token, true);
    });
}());
