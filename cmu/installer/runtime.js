/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* One local POST/JSON contract for USB maintenance and installed Settings. */
var OpenConnect = (function (previous) {
    "use strict";
    var entry = document.getElementById("oc-usb-loader");
    var base = entry && entry.src ? entry.src.slice(0, entry.src.lastIndexOf("/") + 1) :
        "file:///tmp/open-connect/feature/";
    var versionMeta = document.querySelector('meta[name="open-connect-version"]');
    var noticeMeta = document.querySelector('meta[name="open-connect-notice"]');
    var boot = !entry && versionMeta && noticeMeta && {
        version: versionMeta.getAttribute("content"), notice: noticeMeta.getAttribute("content")};
    if (!boot || !/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(boot.version) ||
            !/^(?:-|installed|removed|undone|restart)$/.test(boot.notice)) { boot = null; }
    var stopped = false, started = false, token = entry && entry.ocToken, state = null, busy = false, saving = false;
    var timer = null, dialog = null, detach = null, app = null, usb = false;
    var nodes = [], queued = null, completionShown = false, ready = false, usbRequest = 0;
    var installer, settings, loading = null;
    function validServices(rows) {
        if (rows === undefined) { return true; }
        if (!Array.isArray(rows) || rows.length < 1 || rows.length > 16) { return false; }
        var previous = "";
        return rows.every(function (row) {
            if (!row || !/^[a-z][a-z0-9-]{0,31}$/.test(row.id) || row.id <= previous ||
                    /^(touch|warning|base|wireless|uart|ssh)$/.test(row.id) ||
                    (row.saved !== 0 && row.saved !== 1) ||
                    (row.current !== null && row.current !== 0 && row.current !== 1)) { return false; }
            previous = row.id;
            return ["label", "enable", "disable"].every(function (key) {
                return typeof row[key] === "string" && row[key].length > 0 &&
                    row[key].length <= (key === "label" ? 64 : 256) && !/[\x00-\x1f\x7f]/.test(row[key]);
            });
        });
    }
    function values() {
        return state && state.installed ? {services: state.services, touch: state.touch, warning: state.warning, pandora: state.pandora,
            base: state.base, wireless: state.wireless, wirelessCurrent: state.wirelessCurrent,
            wirelessFactory: state.wirelessFactory === true,
            developer: state.developer === true, uart: state.uart || 0, ssh: state.ssh || 0,
            key: state.key || "-", fingerprint: state.fingerprint || "-", restart: state.restart,
            uartCurrent: state.uartCurrent || 0, sshCurrent: state.sshCurrent || 0} : null;
    }
    function valid(s) {
        return s && s.ok === true && validServices(s.services) && /^(?:-|[a-f0-9]{32}|[a-f0-9]{64})$/.test(s.revision) &&
            typeof s.installed === "boolean" && typeof s.retained === "boolean" &&
            typeof s.restart === "boolean" && typeof s.conflict === "boolean" && typeof s.pending === "boolean" &&
            (s.touch === 0 || s.touch === 1) && (s.warning === 0 || s.warning === 1) &&
            (s.pandora === undefined || s.pandora === 0 || s.pandora === 1) &&
            (s.base === undefined || s.base === 0 || s.base === 1) &&
            (s.wirelessFactory === undefined || typeof s.wirelessFactory === "boolean") &&
            (s.wireless === undefined || ((s.wireless === 0 || s.wireless === 1) &&
                (s.wirelessCurrent === 0 || s.wirelessCurrent === 1))) &&
            (s.developer === undefined || (typeof s.developer === "boolean" &&
                (s.uart === 0 || s.uart === 1) && (s.ssh === 0 || s.ssh === 1) &&
                (s.uartCurrent === 0 || s.uartCurrent === 1) && (s.sshCurrent === 0 || s.sshCurrent === 1) &&
                /^(?:-|[a-f0-9]{64})$/.test(s.key) && /^(?:-|[a-f0-9:]{47})$/.test(s.fingerprint))) &&
            /^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(s.version) &&
            (s.installedVersion === undefined || s.installedVersion === "-" ||
                /^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(s.installedVersion));
    }
    function request(operation, args, done, waitMs) {
        if (stopped) { return; }
        var xhr = new XMLHttpRequest(), answered = false;
        // Leave the server's bounded transaction time plus response headroom.
        var deadline = setTimeout(function () { finish(null); xhr.abort(); }, waitMs || 185000);
        function finish(answer) {
            if (answered) { return; }
            answered = true;
            clearTimeout(deadline);
            if (stopped) { return; }
            if (valid(answer)) {
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
            xhr.open("POST", "http://127.0.0.1:35555/control", true);
            xhr.setRequestHeader("Content-Type", "text/plain");
            xhr.send([token, operation === "status" || !state ? "-" : state.revision, operation].concat(args || ["-", "-", "-"]).join("|"));
        } catch (error) { finish(null); }
    }
    function closeDialog() {
        var cancel = dialog;
        dialog = null;
        if (cancel) { cancel(); }
    }
    function readStatus(done, attempts, began) {
        began = began === undefined ? Date.now() : began;
        var remaining = boot ? 12000 - (Date.now() - began) : 185000;
        if (remaining <= 0) { done(null); return; }
        request("status", null, function (answer) {
            if ((answer && answer.error === "busy" || (!answer && boot)) &&
                    (boot || (attempts || 0) < 8) && (!boot || Date.now() - began < 12000)) {
                setTimeout(function () { if (!stopped) { readStatus(done, (attempts || 0) + 1, began); } }, 500);
            } else { done(answer); }
        }, remaining);
    }
    function message(title, text, buttons, chosen) {
        queued = function () {
            return installer.message(framework, title, text, buttons, function (action) {
                dialog = null;
                chosen(action);
            });
        };
    }
    function dismiss() {
        request("dismiss", null, function () {});
    }
    function error(answer) {
        var text = "The change could not be confirmed. Check again before retrying.";
        if (answer && answer.error === "state_changed") { text = "Files or settings have changed. Nothing was overwritten."; }
        if (answer && answer.error === "stale_state") { text = "The state has changed. Please try again."; }
        message("Open Connect", text, {button1: {label: "OK", appData: "done"}}, function () {});
        // A status read reconciles an unknown acknowledgement; never resend a write.
        readStatus(function () {});
    }
    function run(operation, args) {
        if (busy) { return; }
        busy = true;
        queued = null;
        closeDialog();
        message("Open Connect", "Applying changes. Do not remove the USB drive or turn off the car.",
            {button1: {label: "Close", appData: "close"}}, function () {});
        request(operation, args, function (answer) {
            busy = false;
            queued = null;
            closeDialog();
            if (!valid(answer)) { error(answer); return; }
            if (answer.restart || operation === "uninstall") {
                message("Open Connect", "Restarting. Do not remove the USB drive or turn off the car.",
                    {button1: {label: "Close", appData: "close"}}, function () {});
                request("restart", null, function (reply) {
                    if (!valid(reply)) { queued = null; closeDialog(); error(reply); }
                });
            }
        });
    }
    var store = {
        read: values,
        refresh: function (reply) {
            if (busy) { reply(saving && !!state && state.installed); return; }
            readStatus(function (answer) { reply(valid(answer) && answer.installed); });
        },
        write: function (key, from, to, reply) {
            if (busy || !state) { reply(null); return; }
            busy = saving = true;
            request("set", [key, String(from), String(to)], function (answer) {
                busy = saving = false;
                if (valid(answer)) { reply(values()); }
                else {
                    state = null;
                    readStatus(function (fresh) { reply(valid(fresh) ? values() : null); });
                }
            });
        },
        importKey: function (reply) {
            if (busy || !state) { reply(null); return; }
            busy = saving = true;
            request("import", null, function (answer) {
                busy = saving = false;
                if (valid(answer)) { reply(values()); }
                else {
                    readStatus(function (fresh) { reply(valid(fresh) ? values() : null, true); });
                }
            });
        },
        uninstall: function () { run("uninstall"); }
    };
    function choose() {
        usb = false;
        queued = function () {
            return installer.choose(framework, state.installed, function (action) {
                dialog = null;
                if (action === "install" || action === "uninstall") { run(action); }
                else { dismiss(); }
            }, state.version, state.retained, state.installedVersion);
        };
    }
    function tick() {
        if (stopped || !window.framework || !framework._browserShown) { return; }
        if (!state && !boot) {
            if (queued && !dialog) {
                dialog = queued();
                if (dialog) { queued = null; }
            }
            return;
        }
        if (state ? state.installed : boot) {
            var current = framework.getAppInstance("syssettings");
            if (current && current !== app) {
                if (detach) { detach(); }
                app = current;
                detach = settings.attach(framework, app, store);
            }
        }
        var installed = state ? state.installed : !!boot;
        var restart = state ? state.restart : false;
        var notice = state ? state.notice : boot.notice;
        if (installed && !restart && notice === "installed") { usb = false; }
        if (usb && !busy && !dialog && !queued) { choose(); }
        if (!usb && !completionShown && !queued && !dialog && installed && !restart && notice === "installed") {
            queued = function () {
                return installer.complete(framework, state ? state.version : boot.version, function (action) {
                    dialog = null;
                    if (action !== "done" && action !== "settings") { return; }
                    function complete() {
                        dismiss();
                        if (action === "settings") { settings.fromHome(framework, store, function () {}); }
                    }
                    if (state) { complete(); }
                    else { readStatus(function (answer) { if (valid(answer)) { complete(); } else { error(answer); } }); }
                });
            };
            completionShown = true;
        }
        if (queued && !dialog) {
            var show = queued;
            var opened = show();
            if (opened) { queued = null; dialog = opened; }
        }
    }
    function load(name, next) {
        var id = "oc-runtime-" + name;
        utility.loadScript(base + name + ".js", {id: id}, function () {
            if (!stopped) { next(); }
        });
        nodes.push(document.getElementById(id));
    }
    function start(value, fromUSB) {
        if (started || stopped || !/^[a-f0-9]{32}$/.test(value)) { return; }
        started = true; token = value; usb = fromUSB;
        clearTimeout(loading);
        loading = setTimeout(abandon, 65000);
        load("dialog", function () {
            installer = OpenConnectInstaller;
            load("settings", function () {
                settings = OpenConnectSettings;
                if (!fromUSB && boot) {
                    clearTimeout(loading);
                    ready = true;
                    store.version = boot.version;
                    if (previous && previous.dispose) { previous.dispose(); }
                    previous = null;
                    timer = setInterval(tick, 500);
                    return;
                }
                readStatus(function (answer) {
                    clearTimeout(loading);
                    if (!valid(answer)) {
                        if (previous) { abandon(); return; }
                        message("Open Connect", "The installer could not be reached. Reinsert the USB to try again.",
                            {button1: {label: "OK", appData: "done"}}, function () {});
                    }
                    else {
                        ready = true;
                        if (previous && previous.dispose) { previous.dispose(); }
                        previous = null;
                        if (answer.pending) { usb = false; run("recover"); }
                    }
                    timer = setInterval(tick, 500);
                });
            });
        });
    }
    function cancelUSB(value) {
        if (value !== token || busy) { return; }
        usbRequest++;
        if (!ready && previous) { abandon(); return; }
        usb = false; queued = null; closeDialog();
    }
    function reopenUSB(value) {
        if (stopped || !ready || value !== token) { return false; }
        if (busy) { usb = true; return true; }
        var current = ++usbRequest;
        usb = false;
        queued = null; closeDialog();
        readStatus(function (answer) {
            if (current !== usbRequest) { return; }
            if (!valid(answer)) { error(answer); return; }
            completionShown = false;
            if (answer.pending) { run("recover"); }
            else { usb = true; }
        });
        return true;
    }
    function abandon() {
        if (ready || stopped) { return; }
        dispose();
        if (window.OpenConnect === client) { window.OpenConnect = previous; }
    }
    function dispose() {
        stopped = true;
        clearTimeout(loading);
        clearInterval(timer);
        queued = null;
        closeDialog();
        if (detach) { detach(); }
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i] && nodes[i].parentNode) { nodes[i].parentNode.removeChild(nodes[i]); }
        }
    }
    var client = {start: start, reopenUSB: reopenUSB, cancelUSB: cancelUSB, dispose: dispose};
    if (entry) { loading = setTimeout(abandon, 65000); }
    var meta = document.querySelector('meta[name="open-connect-token"]');
    if (meta && !document.getElementById("oc-usb-loader")) { start(meta.getAttribute("content"), false); }
    return client;
}(window.OpenConnect));
