/* SPDX-License-Identifier: AGPL-3.0-or-later */
(function (fw, applied) {
    "use strict";
    var initialize = fw._initApp, hidden = "," + applied[1] + ",";
    function invisible() { return false; }
    function keepHidden() {}
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
            conceal(app._masterEntertainmentDataList.items);
            conceal(app._masterApplicationDataList.items);
            if (applied[0]) { app._contextTable.IntroAnimation.contextInFunction = introEntry.bind(app); }
        }
        return result;
    };
}(framework, [/*OPEN_CONNECT_APPLIED*/]));
