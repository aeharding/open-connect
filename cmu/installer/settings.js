/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Firmware 74.00.324A. Present our pages inside the current Mazda Settings tab. */
var OpenConnectSettings = (function () {
    "use strict";
    var active = false, waiting = null, session = null;
    var entries = [
        {key: "touch", title: "Touchscreen While Driving", choices: ["Factory Default", "Allow"]},
        {key: "warning", title: "Startup disclaimer", choices: ["Show", "Skip"]}
    ];
    var own = Object.prototype.hasOwnProperty;

    function valid(values) {
        return values && (values.touch === 0 || values.touch === 1) &&
            (values.warning === 0 || values.warning === 1);
    }

    function replace(obj, key, fn) {
        var previous = obj[key], local = own.call(obj, key);
        obj[key] = fn;
        return function () {
            if (obj[key] !== fn) { return; }
            if (local) { obj[key] = previous; } else { delete obj[key]; }
        };
    }

    function settingsApp(id) {
        return id === "syssettings" || id === "vehsettings" || id === "audiosettings";
    }

    function inTab(fw) {
        return settingsApp(fw.getCurrentApp()) && /Tab$/.test(fw.getCurrCtxtId()) &&
            fw._frameworkState === fw._FWK_STATE_IDLE && !fw.common._vuiHelpDialog;
    }

    // One preference session outlives its pages. The last tap wins, even
    // when the driver backs out while a prior write is still completing.
    function preferences(store) {
        if (session && session.owner === store) { return session; }
        function read() {
            try { return store.read(); } catch (error) { return null; }
        }
        var saved = read();
        if (!valid(saved)) { return null; }
        var wanted = {}, busy = false, timer = null;
        var prefs = {owner: store, failure: null, changed: null};
        prefs.values = function () {
            if (!busy && !Object.keys(wanted).length) {
                var current = read();
                if (!valid(current)) { return null; }
                saved = current;
            }
            var values = {developer: saved.developer, key: saved.key, fingerprint: saved.fingerprint,
                uartCurrent: saved.uartCurrent, sshCurrent: saved.sshCurrent,
                restart: saved.restart}, keys = ["touch", "warning", "uart", "ssh"];
            keys.forEach(function (key) { values[key] = own.call(wanted, key) ? wanted[key] : saved[key]; });
            return values;
        };
        function flush() {
            var keys = Object.keys(wanted);
            if (busy || !keys.length) { return; }
            var key = keys[0], requested = wanted[key];
            if (saved[key] === requested) {
                delete wanted[key]; flush();
                if (prefs.changed) { prefs.changed(false); }
                return;
            }
            busy = true;
            var answered = false;
            function finish(actual) {
                if (answered) { return; }
                answered = true;
                busy = false;
                // A lost acknowledgement need not mean a failed write. Read
                // once before reporting it. Never resend the same request.
                if (!valid(actual)) { actual = read(); }
                if (valid(actual)) { saved = actual; }
                var failed = !valid(actual) || (actual[key] !== requested && wanted[key] === requested);
                if (failed) {
                    delete wanted[key];
                    prefs.failure = key;
                    if (prefs.changed) { prefs.changed(true); }
                } else if (wanted[key] === requested) { delete wanted[key]; }
                flush();
                if (!failed && prefs.changed) { prefs.changed(false); }
            }
            try { store.write(key, saved[key], requested, finish); }
            catch (error) { finish(null); }
        }
        prefs.pending = function () { return busy || Object.keys(wanted).length > 0; };
        prefs.select = function (key, value) {
            prefs.failure = null;
            wanted[key] = value;
            clearTimeout(timer);
            timer = setTimeout(flush, 250);
        };
        prefs.importKey = function (done) {
            if (prefs.pending() || typeof store.importKey !== "function") { return; }
            busy = true;
            var answered = false;
            function finish(actual, failed) {
                if (answered) { return; }
                answered = true; busy = false;
                if (valid(actual)) { saved = actual; }
                done(valid(actual) && !failed ? actual : null);
                flush();
            }
            try { store.importKey(finish); } catch (error) { finish(null); }
        };
        session = prefs;
        return prefs;
    }

    // read() returns verified values (zero = factory default). write(key, from, to,
    // reply) compares against 'from', commits, and returns fresh values to reply.
    function open(fw, store) {
        var host = fw._currTmpltInstance;
        if (active || !inTab(fw) || !host || !host.list2Ctrl) { return false; }
        var prefs = preferences(store);
        if (!prefs) { return false; }
        var page, choice, dismiss = null, closed = false, restorers = [];
        var oldDisplay = host.divElt.style.display;
        var tab = fw.getCurrCtxtId();
        function current() {
            return !closed && fw._currTmpltInstance === host && inTab(fw) && fw.getCurrCtxtId() === tab;
        }
        function discard(p) {
            if (p) {
                p.cleanUp();
                if (p.divElt.parentNode) { p.divElt.parentNode.removeChild(p.divElt); }
            }
        }
        function close() {
            if (closed) { return; }
            closed = true;
            if (dismiss) { dismiss(); }
            prefs.changed = null;
            while (restorers.length) { restorers.pop()(); }
            discard(page);
            host.divElt.style.display = oldDisplay;
            active = false;
        }
        function render(index, focus) {
            var values = prefs.failure ? null : prefs.values();
            if (!values) { index = "unknown"; focus = 0; }
            var rows = [], title = "Open Connect", i, row;
            if (index === null) {
                for (i = 0; i < entries.length; i++) {
                    row = entries[i];
                    rows.push({text1: row.title, label1: row.key === "touch" ? ["Default", "Allow"][values.touch] : row.choices[values[row.key]],
                        itemStyle: "style06", hasCaret: true, appData: i});
                }
                if (values.developer) {
                    rows.push({text1: "Developer options", itemStyle: "style01", hasCaret: true, appData: "developer"});
                }
                rows.push({text1: "Uninstall", itemStyle: "style01", appData: "uninstall",
                    disabled: typeof store.uninstall !== "function"});
                rows.push({text1: "About", itemStyle: "style01", appData: "about"});
            } else if (index === "unknown") {
                title = "Change could not be confirmed";
                rows.push({text1: "Return to Mazda Settings", itemStyle: "style01", hasCaret: false, appData: 0});
            } else if (index === "developer") {
                title = "Developer options";
                rows.push({text1: "UART root console", itemStyle: "styleOnOff", value: values.uart ? 1 : 2,
                    hasCaret: false, appData: "uart"});
                rows.push({text1: "Owner SSH access", itemStyle: "styleOnOff", value: values.ssh ? 1 : 2,
                    hasCaret: false, appData: "ssh", disabled: values.key === "-"});
                rows.push({text1: "Import public key", itemStyle: "style01", appData: "import",
                    disabled: prefs.pending() || typeof store.importKey !== "function"});
                rows.push({text1: "At startup: UART " + (values.uartCurrent ? "on" : "off") +
                    ", owner SSH " + (values.sshCurrent ? "on" : "off"), itemStyle: "style01", hasCaret: false, disabled: true});
                if (values.restart) {
                    rows.push({text1: "Restart required to apply changes", itemStyle: "style01", hasCaret: false, disabled: true});
                } else { rows.push({text1: "Changes apply after restart", itemStyle: "style01", hasCaret: false, disabled: true}); }
            } else {
                row = entries[index];
                title = row.title;
                for (i = 0; i < row.choices.length; i++) {
                    rows.push({text1: row.choices[i], image1: "radio", checked: i === values[row.key],
                        itemStyle: "style03", hasCaret: false, appData: i});
                }
            }
            var listProps = {dataList: {itemCountKnown: true, itemCount: rows.length, items: rows},
                titleConfiguration: "listTitle", title: {text1: title, titleStyle: "style02"},
                smallItemText: true, focussedItem: focus, selectCallback: select};
            if (index === 0 || index === 1) { listProps.checkMinChangeInterval = 0; }
            if (index === "developer") { listProps.toggleMinChangeInterval = 0; }
            var next = fw.instantiateTemplate("syssettings", host.divElt.parentNode, "List2Tmplt",
                {List2Ctrl: listProps});
            if (!next) { return false; }
            var old = page;
            page = next;
            choice = index;
            host.divElt.style.display = "none";
            discard(old);
            next.handleControllerEvent(fw.multicontroller.getMode());
            next.handleControllerEvent("acceptFocusInit");
            return true;
        }
        function select(control, item, params) {
            if (!current() || dismiss || !page || control !== page.list2Ctrl) { return; }
            if (choice === null && item === "developer") { render("developer", 0); return; }
            if (choice === "developer") {
                if ((item === "uart" || item === "ssh") && params &&
                        (params.additionalData === 1 || params.additionalData === 2)) {
                    var currentValues = prefs.values();
                    if (item === "ssh" && currentValues.key === "-") { return; }
                    if (item === "uart" && params.additionalData === 1 && currentValues.uart === 0) {
                        dismiss = OpenConnectInstaller.message(fw, "Enable UART root console?",
                            "Passwordless root access over UART. Restart to apply.",
                            {button1: {label: "Cancel", appData: "cancel"}, button2: {label: "Enable", appData: "enable"}},
                            function (action) {
                                dismiss = null;
                                if (action === "enable" && current()) { prefs.select("uart", 1); }
                                if (current() && choice === "developer") { render("developer", 0); }
                            });
                        return;
                    }
                    prefs.select(item, params.additionalData === 1 ? 1 : 0);
                } else if (item === "import" && !prefs.pending() && typeof store.importKey === "function") {
                    dismiss = OpenConnectInstaller.message(fw, "Import public key?",
                        "Put open-connect.pub on the USB drive. RSA and ECDSA public keys are supported. The imported key will be replaced.",
                        {button1: {label: "Cancel", appData: "cancel"}, button2: {label: "Import", appData: "import"}},
                        function (action) {
                            dismiss = null;
                            if (action !== "import" || !current()) { return; }
                            prefs.importKey(function (actual) {
                                if (!current() || choice !== "developer") { return; }
                                render("developer", 2);
                                dismiss = OpenConnectInstaller.message(fw, actual ? "Public key imported" : "Key could not be imported",
                                    actual ? "Fingerprint (MD5):\n" + actual.fingerprint.slice(0, 23) + "\n" +
                                        actual.fingerprint.slice(24) + "\nEnable Owner SSH access when ready." :
                                        "Use one USB drive with open-connect.pub: an RSA key of at least 2048 bits or an ECDSA public key. Private keys and Ed25519 are not supported.",
                                    {button1: {label: "OK", appData: "done"}}, function () { dismiss = null; });
                            });
                        });
                }
                return;
            }
            if (choice === null && item === "about") {
                dismiss = OpenConnectInstaller.about(fw, store.version, function () { dismiss = null; });
                return;
            }
            if (choice === null && item === "uninstall" && typeof store.uninstall === "function") {
                dismiss = OpenConnectInstaller.confirmUninstall(fw, prefs.pending(), function (action) {
                    dismiss = null;
                    if (action === "uninstall" && current() && !prefs.pending()) {
                        close();
                        store.uninstall();
                    }
                });
                return;
            }
            if (item !== 0 && item !== 1) { return; }
            if (choice === "unknown") { prefs.failure = null; close(); return; }
            if (choice === null) {
                var values = prefs.values();
                render(item, values ? values[entries[item].key] : 0);
                return;
            }
            // List2 has already moved the radio dot. Saving does not change
            // focus, push a page or interfere with the Back button.
            prefs.select(entries[choice].key, item);
        }
        if (!render(null, 0)) { return false; }
        active = true;
        prefs.changed = function (failed) {
            if (!failed) {
                if (current() && choice === "developer" && !dismiss) {
                    var values = prefs.values(), ctrl = page.list2Ctrl;
                    if (!values) { return; }
                    ctrl.dataList.items[2].disabled = prefs.pending() || typeof store.importKey !== "function";
                    ctrl.dataList.items[3].text1 = "At startup: UART " + (values.uartCurrent ? "on" : "off") +
                        ", owner SSH " + (values.sshCurrent ? "on" : "off");
                    ctrl.dataList.items[4].text1 = values.restart ? "Restart required to apply changes" : "Changes apply after restart";
                    ctrl.updateItems(2, 4);
                }
                return;
            }
            if (dismiss) { dismiss(); }
            if (current()) { render("unknown", 0); } else { close(); }
        };
        var transition = fw.common.getCommonTransitionData;
        restorers.push(replace(fw.common, "getCommonTransitionData", function () {
            close();
            return transition.apply(this, arguments);
        }));
        var input = host.handleControllerEvent;
        restorers.push(replace(host, "handleControllerEvent", function () {
            if (!current()) { close(); return input.apply(this, arguments); }
            return page.handleControllerEvent.apply(page, arguments);
        }));
        // Both the Back hard key and Mazda's on-screen back affordance go through MMUI.
        var send = fw.sendEventToMmui;
        restorers.push(replace(fw, "sendEventToMmui", function (app, event) {
            if (current() && app === "common" && (event === "Global.GoBack" || event === "Global.MenuUp")) {
                if (dismiss) { dismiss(); }
                else if (choice !== null && choice !== "unknown") { render(null, choice === "developer" ? 2 : choice); }
                else { if (choice === "unknown") { prefs.failure = null; } close(); }
                return;
            }
            return send.apply(this, arguments);
        }));
        return close;
    }

    // Install this on the System tab's Mazda app instance. All other rows
    // retain their original callbacks and indices.
    function attach(fw, app, store) {
        var entry = app._contextTable.SystemTab;
        var original = entry.readyFunction;
        var list = null, release = null, closePage = null;
        var id = "open-connect-settings";
        function bind() {
            var host = app._currentContextTemplate;
            if (!host || !host.list2Ctrl || host.list2Ctrl === list) { return; }
            if (release) { release(false); }
            list = host.list2Ctrl;
            var ctrl = list, set = ctrl.setDataList, select = ctrl.properties.selectCallback;
            var undoSelect = replace(ctrl.properties, "selectCallback", function (control, value) {
                if (control === ctrl && value === id) {
                    var opened = open(fw, store);
                    if (opened) { closePage = opened; }
                    return;
                }
                return select.apply(this, arguments);
            });
            function withEntry(data) {
                var count = data && data.itemCount, items = data && data.items;
                if (!items || !count || items.length < count || items[count - 1].appData !== "SelectAbout" ||
                        items.some(function (r) { return r && r.appData === id; })) {
                    return set.apply(this, arguments);
                }
                // Mazda addresses About as itemCount - 1 when updating its restrictions.
                // Keep About last and all preceding OEM indices stable on every refresh.
                var copy = {}, key;
                for (key in data) { if (own.call(data, key)) { copy[key] = data[key]; } }
                copy.items = items.slice(0, count);
                copy.items.splice(count - 1, 0, {text1: "Open Connect", itemStyle: "style01",
                    hasCaret: true, appData: id});
                copy.itemCount = count + 1;
                return set.call(ctrl, copy);
            }
            var undoSet = replace(ctrl, "setDataList", withEntry);
            release = function (visible) {
                if (closePage) { closePage(); closePage = null; }
                undoSelect();
                undoSet();
                if (!visible) { return; }
                var data = ctrl.dataList, rows = data.items.filter(function (r) { return r.appData !== id; });
                if (rows.length !== data.itemCount) {
                    set.call(ctrl, {itemCountKnown: true, itemCount: rows.length, items: rows,
                        vuiSupport: data.vuiSupport});
                    if (rows.length) { ctrl.updateItems(0, rows.length - 1); }
                }
            };
        }
        function repaint() {
            if (list && list.dataList.itemCount) { list.updateItems(0, list.dataList.itemCount - 1); }
        }
        if (inTab(fw) && fw.getCurrCtxtId() === "SystemTab") {
            bind();
            if (list) { list.setDataList(list.dataList); repaint(); }
        }
        var undoReady = replace(entry, "readyFunction", function () {
            bind();
            var result = original.apply(this, arguments);
            repaint();
            return result;
        });
        return function detach() {
            undoReady();
            if (release) { release(app._currentContextTemplate && app._currentContextTemplate.list2Ctrl === list); }
            list = release = null;
        };
    }
    // The stock Home action enters Settings and chooses the initial tab. Wait
    // for that transition before drawing on its template; never force a tab.
    function fromHome(fw, store, result) {
        if (active || waiting || fw._frameworkState !== fw._FWK_STATE_IDLE || fw.common._vuiHelpDialog ||
                fw.getCurrentApp() !== "system" || fw.getCurrCtxtId() !== "HomeScreen") { return false; }
        var attempts = 0;
        var timer = setInterval(function () {
            var app = fw.getCurrentApp();
            if (inTab(fw) && open(fw, store)) {
                cancel();
                result(true);
            } else if (++attempts >= 40 || (app !== "system" && !settingsApp(app)) ||
                    (app === "system" && fw.getCurrCtxtId() !== "HomeScreen") ||
                    (settingsApp(app) && fw._frameworkState === fw._FWK_STATE_IDLE && !inTab(fw))) {
                cancel();
                result(false);
            }
        }, 200);
        function cancel() {
            clearInterval(timer);
            if (waiting === cancel) { waiting = null; }
        }
        waiting = cancel;
        try { fw.sendEventToMmui("system", "SelectSettings"); }
        catch (error) { cancel(); throw error; }
        return cancel;
    }

    return {open: open, fromHome: fromHome, attach: attach};
}());
