/* SPDX-License-Identifier: AGPL-3.0-or-later */
(function (fw, applied) {
    "use strict";
    var initialize = fw._initApp, hidden = "," + applied[1] + ",";
    function invisible() { return false; }
    function keepHidden() {}
    /* OPEN_CONNECT_AA_BEGIN */
    function disableAndroidAuto(app) {
        var rows = app._masterEntertainmentDataList.items, stale = false, wiredCarPlay = false, i;
        function guard(method, event) {
            var original = app[method];
            if (typeof original !== "function") { return; }
            function appliedAndroidAuto(msg) {
                var payload = msg && msg.params && msg.params.payload;
                if (payload && (payload.appName === "androidauto" ||
                        (payload.statusMenu && payload.statusMenu.appName === "androidauto"))) { return; }
                return original.apply(this, arguments);
            }
            app[method] = appliedAndroidAuto;
            app._messageTable[event] = appliedAndroidAuto.bind(app);
        }
        if (hidden.indexOf(",androidauto,") === -1) { return; }
        for (i = 0; i < rows.length; i++) {
            if (rows[i].appData.appName === "androidauto") {
                stale = rows[i].appData.isVisible; rows[i].disabled = true;
            }
            if (rows[i].text1Id === "USB1CarPlay") { wiredCarPlay = rows[i].appData.isVisible; }
        }
        if (stale && !wiredCarPlay && rows[app._USB1EntIndex]) { rows[app._USB1EntIndex].appData.isVisible = true; }
        guard("_StatusMenuVisibleAndroidAutoMsgHandler", "StatusMenuVisibleAndroidAuto");
        guard("_StatusMenuVisibleMsgHandler", "StatusMenuVisible");
        guard("_StatusMenuMsgHandler", "StatusMenu");
    }
    /* OPEN_CONNECT_AA_END */
    function conceal(rows) {
        var i, data;
        for (i = 0; i < rows.length; i++) {
            data = rows[i].appData;
            if (hidden.indexOf("," + data.appName + ",") !== -1) {
                Object.defineProperty(data, "isVisible", {
                    enumerable: true, get: invisible, set: keepHidden
                });
            }
        }
    }
    function introEntry() {
        var app = this;
        if (app._openConnectIntroCleanup) { app._openConnectIntroCleanup(); }
        var original = fw._templateTransitionCompleteCallback, active = true;
        var local = Object.prototype.hasOwnProperty.call(fw, "_templateTransitionCompleteCallback");
        function stop() {
            active = false;
            if (fw._templateTransitionCompleteCallback === complete) {
                if (local) { fw._templateTransitionCompleteCallback = original; }
                else { delete fw._templateTransitionCompleteCallback; }
            }
            if (app._openConnectIntroCleanup === stop) { delete app._openConnectIntroCleanup; }
        }
        function complete() {
            var incoming = fw._currTmpltInstance;
            var changing = fw._frameworkState === fw._FWK_STATE_TMPLT_CHANGE;
            var result = original.apply(this, arguments);
            if (!active || !changing || !incoming || !incoming.contextInfo) { return result; }
            var info = incoming.contextInfo;
            if (info.uiaId === "system" &&
                    (info.ctxtId === "IntroAnimation" || info.ctxtId === "QuickStartLoop")) { return result; }
            stop();
            if (info.uiaId !== "system" || info.ctxtId !== "Disclaimer") {
                fw.sendEventToMmui("system", "DisposeIntroVideo");
                fw.sendEventToMmui("system", "NotifyDisclaimerEnd");
            }
            return result;
        }
        app._openConnectIntroCleanup = stop;
        fw._templateTransitionCompleteCallback = complete;
    }
    fw._initApp = function (id) {
        var result = initialize.apply(this, arguments), app;
        if (id === "system") {
            app = this._appInstances[id];
            disableAndroidAuto(app); /* OPEN_CONNECT_AA_CALL */
            conceal(app._masterEntertainmentDataList.items);
            conceal(app._masterApplicationDataList.items);
            if (applied[0]) { app._contextTable.IntroAnimation.contextInFunction = introEntry.bind(app); }
        }
        return result;
    };
}(framework, [/*OPEN_CONNECT_APPLIED*/]));
