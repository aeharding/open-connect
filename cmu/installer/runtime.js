/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnect = (function (previous) {
    "use strict";
    if (previous && previous.protected && previous.protected()) { return previous; }
    var entry = document.getElementById("oc-usb-loader"), meta = document.querySelector('meta[name="open-connect-token"]');
    var vm = document.querySelector('meta[name="open-connect-version"]'), nm = document.querySelector('meta[name="open-connect-notice"]');
    var versionRE = /^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
    var boot = meta && vm && nm && {token: meta.getAttribute("content"), version: vm.getAttribute("content"), notice: nm.getAttribute("content")};
    if (!boot || !/^[a-f0-9]{32}$/.test(boot.token) || !versionRE.test(boot.version) ||
            !/^(?:-|installed|removed|undone|restart)$/.test(boot.notice)) { boot = null; }
    var base = entry && entry.src ? entry.src.slice(0, entry.src.lastIndexOf("/") + 1) : "file:///tmp/open-connect/feature/";
    var port = entry && entry.ocPort === 35555 ? 35555 : 15555;
    var stopped = false, started = false, token = entry && entry.ocToken, state = null, busy = false, saving = false;
    var timer, loading, dialog, view, detach, app, installer, settings, job, marker, pending = false;
    var nodes = [], queued = null, ready = false, usb = false, generation = 0, completionShown = false, proofRead = false;
    function valid(s) { return settings.validStatus(s); }
    function values() { return state && state.installed ? state : null; }
    function protectedOwner() { return !!job || pending; }
    function claim() {
        if (stopped || window.OpenConnect !== client || job && (!saving || job.phase === "unresolved")) { return false; }
        if (window.__ocUSBLoading && window.__ocUSBLoading !== marker) { return false; }
        if (!marker) { marker = {token: token, cancel: function () { cancelUSB(token); }}; }
        window.__ocUSBLoading = marker;
        return true;
    }
    function release() {
        if (!protectedOwner() && window.__ocUSBLoading === marker) { delete window.__ocUSBLoading; }
    }
    function request(operation, args, done, waitMs, intent) {
        if (stopped) { return; }
        intent = intent === undefined ? generation : intent;
        var xhr = new XMLHttpRequest(), answered = false;
        var deadline = setTimeout(function () { finish(null); xhr.abort(); }, waitMs || 185000);
        function finish(answer) {
            if (answered) { return; }
            answered = true; clearTimeout(deadline);
            if (stopped || intent !== generation) { return; }
            if (operation !== "dismiss" && valid(answer)) {
                state = answer;
                store.version = answer.installedVersion === undefined ? answer.version :
                    (answer.installedVersion === "-" ? undefined : answer.installedVersion);
            }
            done(answer);
        }
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) { return; }
            var answer = null;
            try { if (xhr.status === 200) { answer = JSON.parse(xhr.responseText); } } catch (ignore) {}
            finish(answer);
        };
        try {
            xhr.open("POST", "http://127.0.0.1:" + port + "/control", true);
            xhr.setRequestHeader("Content-Type", "text/plain");
            xhr.send([token, operation === "status" || !state ? "-" : state.revision, operation].concat(args || ["-", "-", "-"]).join("|"));
        } catch (error) { finish(null); }
    }
    function readStatus(done, until, attempts, intent) {
        intent = intent === undefined ? generation : intent;
        if (intent !== generation || stopped) { return; }
        var left = until ? until - Date.now() : 185000;
        if (left <= 0) { done(null); return; }
        request("status", null, function (answer) {
            if ((answer && answer.error === "busy" || (!answer && until)) && (until || (attempts || 0) < 8)) {
                setTimeout(function () { readStatus(done, until, (attempts || 0) + 1, intent); },
                    until ? Math.min(500, Math.max(0, until - Date.now())) : 500);
            } else { done(answer); }
        }, left, intent);
    }
    function closeDialog() { var close = dialog; dialog = null; if (close) { close(); } }
    function closeView() { var old = view; view = null; if (old) { old.close(); } }
    function message(title, text) {
        queued = function () {
            return installer.message(framework, title, text, {button1: {label: "OK", appData: "done"}}, function () {
                dialog = null;
            });
        };
    }
    function dismiss() { request("dismiss", null, function () {}); }
    function paint() {
        var action = job.phase === "restart" ? "Restarting Mazda Connect" : job.phase === "checking" ?
            "Checking Open Connect" : job.action;
        var warning = job.origin === "usb" ? "Do not remove the USB drive\nor turn off the car." : "Do not turn off the car.";
        if (view && !view.update(action, warning)) { view = null; }
        if (!view) { view = installer.progress(framework, action, warning, function () { view = null; }); }
        return !!view;
    }
    function end(actual) {
        var callback = job.reply;
        job = null; busy = saving = false; closeView(); release();
        if (callback) { callback(actual); }
    }
    function refuse(uncertain) {
        var callback = job.reply, origin = job.origin;
        closeView();
        if (uncertain) { job.phase = "unresolved"; job.reply = null; }
        else { job = null; busy = saving = false; release(); }
        if (callback) { callback(null, true); }
        message(uncertain ? "Unable to confirm the change" : "Unable to finish", (uncertain ?
            "Restart Mazda Connect before making more changes." :
            "Check your settings before trying again.") +
            (uncertain && origin === "usb" ? "\nKeep the USB drive connected until restart." : ""));
    }
    function budget() { if (!job.until) { job.until = Date.now() + 12000; } return job.until; }
    function restart() {
        if (job.restartSent) { return; }
        job.restartSent = true; job.phase = "restart"; paint();
        var current = job, until = budget();
        request("restart", null, function (answer) {
            if (!valid(answer)) { reconcile(answer); }
        }, Math.max(1, until - Date.now()));
        setTimeout(function () { if (job === current && job.phase !== "unresolved") { refuse(true); } }, Math.max(0, until - Date.now()));
    }
    function changed(answer) {
        if (!valid(answer) || answer.pending || answer.conflict) { return false; }
        var old = job.before;
        if (job.operation === "uninstall") { return !answer.installed && !answer.retained && answer.revision === "-"; }
        if (job.operation === "install") {
            return answer.installed && answer.installedVersion === job.target && answer.notice === "installed" &&
                answer.revision !== old.revision && (!old.installed || old.installedVersion && old.installedVersion !== "-" && old.installedVersion !== job.target);
        }
        if (job.operation === "set") {
            var key = job.args[0], wanted = Number(job.args[2]), value = answer[key];
            (answer.services || []).forEach(function (row) { if (row.id === key) { value = row.saved; } });
            return answer.installed && answer.revision !== old.revision && value === wanted;
        }
        return job.operation === "import" && /^[a-f0-9]{64}$/.test(answer.key) && answer.key !== old.key && answer.revision !== old.revision;
    }
    function reconcile(answer) {
        job.phase = "checking"; if (!saving) { paint(); }
        readStatus(function (fresh) {
            if (answer && answer.ok === false) { refuse(state.pending); }
            else if (answer === null && changed(fresh)) {
                if (saving) { end(values()); } else if (!job.restartSent) { restart(); }
            } else { refuse(true); }
        }, budget());
    }
    function drive() {
        if (!job || job.phase !== "waiting") { return; }
        if (job.operation !== "recover" && (state.revision !== job.before.revision || state.version !== job.target)) { end(null); return; }
        if (!saving && !paint() && job.operation !== "recover") { return; }
        job.sent = true; job.phase = "writing";
        request(job.operation, job.args, function (answer) {
            if (!valid(answer)) { reconcile(answer); return; }
            if (saving) { end(values()); }
            else if (job.operation === "install" || job.operation === "uninstall" || answer.restart) { restart(); }
            else { end(null); }
        });
    }
    function run(operation, args, origin, reply) {
        if (busy || !state || !claim()) { if (reply) { reply(null); } return false; }
        busy = true; saving = !!reply; generation++;
        job = {operation: operation, args: args, origin: origin, before: state, target: state.version,
            reply: reply, phase: "waiting", sent: false, restartSent: false,
            action: operation === "uninstall" ? "Removing Open Connect" : operation === "recover" ? "Applying changes" :
                operation === "install" ? (state.installed && state.installedVersion && state.installedVersion !== "-" ?
                    (state.installedVersion === state.version ? "Reinstalling" : "Updating") : "Installing") + " Open Connect" : "Applying changes"};
        queued = null; closeDialog(); drive(); return true;
    }
    var store = {read: values, pending: function (value) {
        if (value && !claim()) { return false; }
        pending = value; release(); return true;
    }, refresh: function (reply) {
        if (busy) { reply(saving && !!values()); return; }
        generation++;
        readStatus(function (answer) { reply(valid(answer) && answer.installed); }, boot && !entry ? Date.now() + 12000 : null);
    }, write: function (key, from, to, reply) { run("set", [key, String(from), String(to)], "settings", reply); },
    importKey: function (reply) { run("import", null, "settings", reply); },
    uninstall: function () { run("uninstall", null, "settings"); }};
    function choose() {
        usb = false;
        var revision = state.revision, target = state.version;
        queued = function () {
            return installer.choose(framework, state.installed, function (action) {
                dialog = null;
                if (state.revision !== revision || state.version !== target) { return; }
                if (action === "install" || action === "uninstall") { run(action, null, "usb"); }
                else if (action === "cancel") { dismiss(); }
            }, state.version, state.retained, state.installedVersion);
        };
    }
    function completion() {
        return boot && boot.token === token && boot.notice === "installed" && valid(state) && state.installed &&
            !state.pending && !state.conflict && !state.restart && state.notice === "installed" &&
            state.completionReady === true && state.installedVersion === boot.version;
    }
    function tick() {
        if (stopped || !window.framework || !framework._browserShown) { return; }
        if (state ? state.installed : boot) {
            var current = framework.getAppInstance("syssettings");
            if (current && current !== app) {
                if (detach) { detach(); }
                app = current; detach = settings.attach(framework, app, store);
            }
        }
        if (job) {
            if (job.phase === "waiting") { drive(); }
            else if (!saving && job.phase !== "unresolved") { paint(); }
        } else if (!busy && state && state.pending) { run("recover", null, entry ? "usb" : "settings"); }
        else if (!completionShown && !proofRead && boot && boot.notice === "installed" && !state) {
            proofRead = true;
            readStatus(function () {}, Date.now() + 12000);
        }
        if (!job && completion() && !completionShown && !queued && !dialog) {
            queued = function () {
                if (!completion()) { queued = null; return false; }
                var opened = installer.complete(framework, state.installedVersion, function (action) {
                    dialog = null;
                    if (completion() && (action === "done" || action === "settings")) {
                        dismiss(); if (action === "settings") { settings.fromHome(framework, store, function () {}); }
                    }
                });
                if (opened) { usb = false; }
                return opened;
            };
            completionShown = true;
        }
        if (usb && !busy && state && !dialog && !queued) { choose(); }
        if (queued && !dialog) {
            var opened = queued();
            if (opened) { queued = null; dialog = opened; }
        }
    }
    function load(name, next) {
        var node = document.createElement("script");
        node.type = "text/javascript"; node.src = base + name + ".js";
        node.onload = function () { if (!stopped) { next(); } };
        nodes.push(node);
        document.querySelector("head").appendChild(node);
    }
    function start(value, fromUSB) {
        if (started || stopped || !/^[a-f0-9]{32}$/.test(value)) { return; }
        started = true; token = value; usb = fromUSB;
        clearTimeout(loading); loading = setTimeout(abandon, 65000);
        load("dialog", function () {
            installer = OpenConnectInstaller;
            load("settings", function () {
                settings = OpenConnectSettings;
                function accept(answer) {
                    clearTimeout(loading);
                    if (previous && previous.protected && previous.protected()) { abandon(); return; }
                    if (!valid(answer) && !(boot && !fromUSB)) {
                        if (previous) { abandon(); return; }
                        message("Unable to finish", "Open Connect could not be reached. Check the connection before trying again.");
                    } else {
                        ready = true;
                        if (previous && previous.dispose) { previous.dispose(); }
                        previous = null;
                    }
                    timer = setInterval(tick, 500);
                }
                if (!fromUSB && boot) { store.version = boot.version; accept(null); }
                else { readStatus(accept); }
            });
        });
    }
    function cancelUSB(value) {
        if (value !== token || pending || job && (job.sent || job.origin !== "usb")) { return; }
        generation++;
        if (!ready && previous) { abandon(); return; }
        if (job) { end(null); }
        usb = false; queued = null; closeDialog();
        var node = document.getElementById("oc-usb-loader");
        if (node && node.ocToken === token && node.parentNode) { node.parentNode.removeChild(node); }
        release();
    }
    function reopenUSB(value) {
        if (stopped || !ready || value !== token) { return false; }
        if (protectedOwner()) { return true; }
        generation++; usb = false; queued = null; closeDialog();
        readStatus(function (answer) {
            if (!valid(answer)) { message("Unable to finish", "Open Connect could not be reached."); return; }
            completionShown = false; usb = true;
        });
        return true;
    }
    function abandon() {
        if (ready || stopped) { return; }
        dispose(); if (window.OpenConnect === client) { window.OpenConnect = previous; }
    }
    function dispose() {
        if (protectedOwner()) { return false; }
        stopped = true; generation++; clearTimeout(loading); clearInterval(timer);
        queued = null; closeDialog(); closeView();
        if (detach) { detach(); }
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i] && nodes[i].parentNode) { nodes[i].parentNode.removeChild(nodes[i]); }
        }
        release(); return true;
    }
    var client = {start: start, reopenUSB: reopenUSB, cancelUSB: cancelUSB, dispose: dispose, protected: protectedOwner};
    if (entry) { loading = setTimeout(abandon, 65000); }
    if (boot && !entry) { start(boot.token, false); }
    return client;
}(window.OpenConnect));
