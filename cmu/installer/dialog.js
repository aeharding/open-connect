/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* An installer session owns the disk operation. This view only reports a choice. */
var OpenConnectInstaller = (function () {
    "use strict";
    var active = null;

    function show(fw, title, message, buttons, onChoice) {
        if (typeof onChoice !== "function") { throw new TypeError("Expected a choice handler"); }
        var home = fw._currTmpltInstance;
        var common = fw.common;
        if (active || !home || !common || fw._frameworkState !== fw._FWK_STATE_IDLE ||
                fw.getCurrentApp() !== "system" || fw.getCurrCtxtId() !== "HomeScreen" ||
                common._vuiHelpDialog) {
            return false;
        }

        var own = Object.prototype.hasOwnProperty;
        var ownedInput = own.call(common, "handleControllerEvent");
        var ownedTransition = own.call(common, "getCommonTransitionData");
        var previousInput = common.handleControllerEvent;
        var previousTransition = common.getCommonTransitionData;
        function stillHome() {
            return fw._currTmpltInstance === home && fw._frameworkState === fw._FWK_STATE_IDLE &&
                fw.getCurrentApp() === "system" && fw.getCurrCtxtId() === "HomeScreen";
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
            if (!stillHome() || common._vuiHelpDialog) {
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
                if (!stillHome() || common._vuiHelpDialog) { finish("cancel"); return; }
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

    function choose(fw, installed, onChoice, version) {
        if (typeof installed !== "boolean") { throw new TypeError("Expected verified install state"); }
        var buttons = {
            button1: {label: "Cancel", appData: "cancel"},
            button2: {label: installed ? "Install/update" : "Install", appData: "install"}
        };
        if (installed) { buttons.button3 = {label: "Uninstall", appData: "uninstall"}; }
        return show(fw, installed ? "Open Connect" : "Install " + name(version) + "?",
            installed ? "Open Connect is installed." : "Mazda Connect will restart once.", buttons, onChoice);
    }

    // The installation owner calls this only after verifying the installed build.
    function complete(fw, version, onChoice) {
        return show(fw, name(version) + " installed", "Installation complete.", {
            button1: {label: "Done", appData: "done"},
            button2: {label: "Open settings", appData: "settings"}
        }, onChoice);
    }
    return {choose: choose, complete: complete};
}());
