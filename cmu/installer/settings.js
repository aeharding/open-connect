/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Firmware 55.00.750B. Present our pages inside the current Mazda Settings tab. */
var OpenConnectSettings = (function () {
    "use strict";
    var active = false, waiting = null;
    var entries = [
        {key: "touch", title: "Touchscreen", choices: ["Mazda default", "Always enabled"]},
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

    // read() returns verified values (zero = Mazda default). write(key, from, to,
    // reply) compares against 'from', commits, and returns fresh values to reply.
    function open(fw, store) {
        var host = fw._currTmpltInstance;
        if (active || !inTab(fw) || !host || !host.list2Ctrl) { return false; }
        var values = store.read();
        if (!valid(values)) { return false; }
        var page, choice, pending = false, closed = false, restorers = [];
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
            while (restorers.length) { restorers.pop()(); }
            discard(page);
            host.divElt.style.display = oldDisplay;
            active = false;
        }
        function render(index, focus, message) {
            var rows = [], title = "Open Connect", i, row;
            if (index === null) {
                for (i = 0; i < entries.length; i++) {
                    row = entries[i];
                    rows.push({text1: row.title, label1: row.key === "touch" ? ["Default", "Always"][values.touch] : row.choices[values[row.key]],
                        itemStyle: "style06", hasCaret: true, appData: i});
                }
            } else if (index === "saving") {
                title = "Open Connect";
                rows.push({text1: "Saving setting…", itemStyle: "style01", disabled: true, hasCaret: false});
            } else if (index === "unknown") {
                title = "Change could not be confirmed";
                rows.push({text1: "Return to Mazda Settings", itemStyle: "style01", hasCaret: false, appData: 0});
            } else {
                row = entries[index];
                title = row.title;
                for (i = 0; i < row.choices.length; i++) {
                    rows.push({text1: row.choices[i], image1: "radio", checked: i === values[row.key],
                        itemStyle: "style03", hasCaret: false, appData: i});
                }
            }
            var next = fw.instantiateTemplate("syssettings", host.divElt.parentNode, "List2Tmplt", {
                List2Ctrl: {dataList: {itemCountKnown: true, itemCount: rows.length, items: rows},
                    titleConfiguration: "listTitle", title: {text1: message || title, titleStyle: "style02"},
                    smallItemText: true, focussedItem: focus, selectCallback: select}
            });
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
        function select(control, item) {
            if (!current() || !page || control !== page.list2Ctrl || pending ||
                    (item !== 0 && item !== 1)) { return; }
            if (choice === "unknown") { close(); return; }
            if (choice === null) {
                render(item, values[entries[item].key]);
                return;
            }
            var index = choice, key = entries[index].key, from = values[key];
            if (from === item) { render(null, index); return; }
            // List2 changes its own radio before invoking selectCallback.
            // Replace that list in the same turn so an unconfirmed value cannot linger.
            pending = true;
            if (!render("saving", 0)) { close(); return; }
            var replied = false;
            function reply(actual) {
                if (replied) { return; }
                replied = true;
                pending = false;
                if (!current()) { return; }
                if (!valid(actual)) { render("unknown", 0); return; }
                values = actual;
                if (actual[key] === item) { render(null, index); }
                else { render(index, actual[key], "Change could not be confirmed"); }
            }
            try { store.write(key, from, item, reply); }
            catch (error) { reply(null); }
        }
        if (!render(null, 0)) { return false; }
        active = true;
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
                if (choice !== null && choice !== "unknown" && !pending) { render(null, choice); } else { close(); }
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
        var list = null, release = null;
        var id = "open-connect-settings";
        function bind() {
            var host = app._currentContextTemplate;
            if (!host || !host.list2Ctrl || host.list2Ctrl === list) { return; }
            if (release) { release(false); }
            list = host.list2Ctrl;
            var ctrl = list, set = ctrl.setDataList, select = ctrl.properties.selectCallback;
            var undoSelect = replace(ctrl.properties, "selectCallback", function (control, value) {
                if (control === ctrl && value === id) { open(fw, store); return; }
                return select.apply(this, arguments);
            });
            function withEntry(data) {
                var count = data && data.itemCount, items = data && data.items;
                if (!items || !count || items.length < count || items[count - 1].appData !== "SelectAbout" ||
                        items.some(function (r) { return r && r.appData === id; })) {
                    return set.apply(this, arguments);
                }
                // v55 addresses About as itemCount - 1 when updating its restrictions.
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
