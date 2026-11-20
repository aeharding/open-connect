/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* An installer session owns the disk operation. This view only reports a choice. */
var OpenConnectInstaller = (function () {
    "use strict";
    var active = null;

    function show(fw, title, message, buttons, onChoice, settings) {
        if (typeof onChoice !== "function") { throw new TypeError("Expected a choice handler"); }
        var host = fw._currTmpltInstance, app = fw.getCurrentApp(), context = fw.getCurrCtxtId();
        var common = fw.common;
        if (active || !host || !common || fw._frameworkState !== fw._FWK_STATE_IDLE ||
                (settings ? !/^(syssettings|audiosettings|vehsettings)$/.test(app) || !/Tab$/.test(context) :
                    app !== "system" || context !== "HomeScreen") ||
                common._vuiHelpDialog) {
            return false;
        }

        var own = Object.prototype.hasOwnProperty;
        var ownedInput = own.call(common, "handleControllerEvent");
        var ownedTransition = own.call(common, "getCommonTransitionData");
        var previousInput = common.handleControllerEvent;
        var previousTransition = common.getCommonTransitionData;
        function sameContext() {
            return fw._currTmpltInstance === host && fw._frameworkState === fw._FWK_STATE_IDLE &&
                fw.getCurrentApp() === app && fw.getCurrCtxtId() === context;
        }

        function finish(action) {
            if (!dialog || active !== dialog) { return; }
            active = null;
            if (common.handleControllerEvent === input) {
                if (ownedInput) { common.handleControllerEvent = previousInput; }
                else { delete common.handleControllerEvent; }
            }
            if (common.getCommonTransitionData === transition) {
                if (ownedTransition) { common.getCommonTransitionData = previousTransition; }
                else { delete common.getCommonTransitionData; }
            }
            fw.destroyControl(dialog);
            try {
                onChoice(action);
            } catch (error) {
                log.error("Open Connect installer choice handler failed: " + error);
            }
        }

        function input(event, first) {
            if (!sameContext() || common._vuiHelpDialog) {
                finish("cancel");
                return previousInput.apply(this, arguments);
            }
            if (event === "goBack") {
                finish("cancel");
                return;
            }
            switch (event) {
            case "leftStart": case "rightStart": case "upStart": case "downStart":
                // The Mazda dialog moves focus on release.
                return;
            case "touchActive": case "controllerActive":
            case "cw": case "ccw": case "select": case "selectStart":
            case "left": case "right": case "up": case "down": case "lostFocus":
                if (!first) { dialog.handleControllerEvent(event); }
                return;
            default:
                finish("cancel");
                return previousInput.apply(this, arguments);
            }
        }

        function transition() {
            finish("cancel");
            return previousTransition.apply(this, arguments);
        }

        var dialog = fw.instantiateControl("system", document.body, "Dialog3Ctrl", {
            titleStyle: "titleStyle01",
            title: title,
            contentStyle: "style02",
            text1: message,
            initialFocus: 0,
            buttonConfig: buttons,
            defaultSelectCallback: function (control, action) {
                if (control !== dialog) { return; }
                if (!sameContext() || common._vuiHelpDialog) { finish("cancel"); return; }
                for (var key in buttons) {
                    if (own.call(buttons, key) && buttons[key].appData === action) { finish(action); return; }
                }
            }
        });
        if (!dialog) { return false; }
        dialog.divElt.classList.add("Dialog3Ctrl_Style19_NoTemplateInstance");
        active = dialog;
        common.handleControllerEvent = input;
        common.getCommonTransitionData = transition;
        dialog.handleControllerEvent(fw.multicontroller.getMode());
        return function cancel() { finish("cancel"); };
    }

    function name(version) {
        if (version === undefined) { return "Open Connect"; }
        if (typeof version !== "string" || !/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(version)) {
            throw new TypeError("Expected a package version");
        }
        return "Open Connect " + version;
    }

    function choose(fw, installed, onChoice, version, retained) {
        if (typeof installed !== "boolean") { throw new TypeError("Expected verified install state"); }
        var buttons = {
            button1: {label: "Cancel", appData: "cancel"},
            button2: {label: installed ? "Install/update" : "Install", appData: "install"}
        };
        if (installed || retained) { buttons.button3 = {label: "Uninstall", appData: "uninstall"}; }
        return show(fw, installed || retained ? "Open Connect" : "Install " + name(version) + "?",
            "Do not remove the USB drive or turn off the car during installation.", buttons, onChoice);
    }

    // The installation owner calls this only after verifying the installed build.
    function complete(fw, version, onChoice) {
        return show(fw, name(version) + " installed", "Installation complete. You can now remove the USB drive.", {
            button1: {label: "Done", appData: "done"},
            button2: {label: "Open settings", appData: "settings"}
        }, onChoice);
    }
    function about(fw, version, done) {
        var text = version === undefined ? "Installed version unavailable." : name(version);
        return show(fw, "About", text, {button1: {label: "OK", appData: "done"}}, done, true);
    }

    function confirmUninstall(fw, pending, done) {
        if (pending) {
            return show(fw, "Uninstall", "Finishing your settings change. Try again in a moment.",
                {button1: {label: "OK", appData: "cancel"}}, done, true);
        }
        return show(fw, "Uninstall?", "Open Connect will be removed. Mazda Connect will restart.", {
            button1: {label: "Cancel", appData: "cancel"},
            button2: {label: "Uninstall", appData: "uninstall"}
        }, done, true);
    }

    function message(fw, title, text, buttons, done) {
        return show(fw, title, text, buttons, done, /settings$/.test(fw.getCurrentApp()));
    }

    return {choose: choose, complete: complete, about: about, confirmUninstall: confirmUninstall,
        message: message};
}());
