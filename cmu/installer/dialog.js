/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* View ownership yields to Mazda; operation ownership stays in runtime.js. */
var OpenConnectInstaller=(function () {
"use strict";
var active=null, own=Object.prototype.hasOwnProperty;
function show(fw, title, text, buttons, done, settings, progress) {
  var host=fw._currTmpltInstance, app=fw.getCurrentApp(), context=fw.getCurrCtxtId(), common=fw.common;
  function eligible() {
    return fw._currTmpltInstance===host&&fw._frameworkState===fw._FWK_STATE_IDLE&&
      fw.getCurrentApp()===app&&fw.getCurrCtxtId()===context&&
      !common._vuiHelpDialog&&!common._vuiExamplesDialog;
  }
  if (active||!host||!common||!eligible()||(settings ?
      !/^(syssettings|audiosettings|vehsettings)$/.test(app)||!/Tab$/.test(context) :
      app!=="system"||context!=="HomeScreen")) { return false; }
  if (typeof ocCarPlay!=="undefined"&&ocCarPlay) { ocCarPlay.cancel(); }
  var restores=[], home=common.statusBar&&common.statusBar.homeBtn;
  function replace(object, key, fn) {
    var before=object[key], local=own.call(object, key);
    object[key]=fn;
    restores.push(function () {
      if (object[key]===fn) { if (local) { object[key]=before; } else { delete object[key]; } }
    });
    return before;
  }
  function finish(action) {
    if (active!==dialog) { return; }
    active=null;
    while (restores.length) { restores.pop()(); }
    fw.destroyControl(dialog);
    try { done(action); } catch (error) { log.error("Open Connect dialog: " + error); }
  }
  function transition() { finish("cancel"); return previousTransition.apply(this, arguments); }
  function input(event, first) {
    if (!eligible()) { finish("cancel"); return previousInput.apply(this, arguments); }
    if (progress&&/^(goBack|touchActive|controllerActive|cw|ccw|select|selectStart|left|right|up|down|lostFocus)(Start)?$/.test(event)) { return; }
    if (progress) { finish("cancel"); return previousInput.apply(this, arguments); }
    if (event==="goBack") { finish("cancel"); return; }
    if (/^(left|right|up|down)Start$/.test(event)) { return; }
    if (/^(touchActive|controllerActive|cw|ccw|select|selectStart|left|right|up|down|lostFocus)$/.test(event)) {
      if (!first) { dialog.handleControllerEvent(event); } return;
    }
    finish("cancel"); return previousInput.apply(this, arguments);
  }
  var props=progress ? {contentStyle: "style27", fullScreen: true, text1: title, text2: text,
    meter: {meterType: "indeterminate", meterPath: "common/images/IndeterminateMeter_2.png"}} : {
    contentStyle: "style02", titleStyle: "titleStyle01", title: title, text1: text,
    initialFocus: 0, buttonConfig: buttons, defaultSelectCallback: function (control, action) {
      if (control!==dialog) { return; }
      if (!eligible()) { finish("cancel"); return; }
      for (var key in buttons) {
        if (own.call(buttons, key)&&buttons[key].appData===action) { finish(action); return; }
      }
    }};
  var dialog=fw.instantiateControl("system", document.body, "Dialog3Ctrl", props);
  if (!dialog) { return false; }
  active=dialog;
  dialog.divElt.classList.add("Dialog3Ctrl_Style19_NoTemplateInstance");
  var previousInput=replace(common, "handleControllerEvent", input);
  var previousTransition=replace(common, "getCommonTransitionData", transition);
  if (progress) {
    dialog.divElt.style.top="0px";
    var capture=function (event) {
      if (!eligible()) { finish("cancel"); return; }
      event.preventDefault(); event.stopImmediatePropagation();
    };
    ["mousedown", "mouseup", "click"].forEach(function (key) {
      document.addEventListener(key, capture, true);
      restores.push(function () { document.removeEventListener(key, capture, true); });
    });
    // Release pre-armed Home holds without firing callbacks.
    if (home) {
      ["selectCallback", "holdStartCallback", "holdStopCallback"].forEach(function (key) {
        replace(home.properties, key, function () {});
      });
      clearTimeout(home._holdTimeoutId); home._holdTimeoutId=null;
      var enabled=home._isEnabled;
      try { home._isEnabled=true; home.finishPartialActivity(); }
      finally { home._isEnabled=enabled; }
    }
    ["Global.StartHelp", "Global.StartExamples"].forEach(function (key) {
      if (!common._messageTable||!common._messageTable[key]) { return; }
      var before=replace(common._messageTable, key, function () {
        finish("cancel"); return before.apply(this, arguments);
      });
    });
    return {close: function () { finish("cancel"); }, update: function (action, warning) {
      if (active!==dialog) { return false; }
      if (!eligible()) { finish("cancel"); return false; }
      if (title!==action) { dialog.setText1(title=action); }
      if (text!==warning) { dialog.setText2(text=warning); }
      return true;
    }};
  }
  dialog.handleControllerEvent(fw.multicontroller.getMode());
  return function () { finish("cancel"); };
}
function versionText(version) {
  if (version===undefined||version==="-") { return "Unavailable"; }
  if (!/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(version)) {
    throw new TypeError("Expected a package version");
  }
  return version;
}
function choose(fw, installed, done, version, retained, from) {
  if (typeof installed!=="boolean") { throw new TypeError("Expected verified install state"); }
  var label=installed&&from&&from!=="-" ? (from===version ? "Reinstall" : "Update") : "Install";
  var buttons={button1: {label: "Cancel", appData: "cancel"}, button2: {label: label, appData: "install"}};
  if (installed||retained) { buttons.button3={label: "Uninstall", appData: "uninstall"}; }
  return show(fw, label + " Open Connect?", (installed ?
    "From: " + versionText(from) + "\nTo: " + versionText(version) : "Version " + versionText(version) + ".") +
    "\nMazda Connect will restart.", buttons, done);
}
function message(fw, title, text, buttons, done) {
  return show(fw, title, text, buttons, done, /settings$/.test(fw.getCurrentApp()));
}
return {choose: choose, message: message, progress: function (fw, action, warning, suspended) {
  return show(fw, action, warning, null, suspended, /settings$/.test(fw.getCurrentApp()), true);
}, complete: function (fw, version, done) {
  return show(fw, "Open Connect installed", "Version " + versionText(version) + ".\nYou can now remove the USB drive.", {
    button1: {label: "Done", appData: "done"}, button2: {label: "Open settings", appData: "settings"}}, done);
}, about: function (fw, version, done) {
  return message(fw, "About", version===undefined ? "Installed version unavailable." : "Open Connect " + versionText(version),
    {button1: {label: "OK", appData: "done"}}, done);
}, confirmUninstall: function (fw, pending, done) {
  return message(fw, "Uninstall Open Connect?", pending ? "Finishing your settings change. Try again in a moment." :
    "Open Connect will be removed.\nMazda Connect will restart.", pending ?
    {button1: {label: "OK", appData: "cancel"}} :
    {button1: {label: "Cancel", appData: "cancel"}, button2: {label: "Uninstall", appData: "uninstall"}}, done);
}};
}());
(function (a) {
if (!a||a.loaded & 2) { return; }
var f=framework, create=f.instantiateControl, destroy=f.destroyControl;
a.wrap(f, "sendEventToMmui", function (id, event) {
  if (/^Global\.(Intent|GoBack|MenuUp)/.test(event)||/^Select/.test(event)&&event!=="SelectCarPlay") { a.user(event); }
});
a.dialogs=0;
f.instantiateControl=function (id, parent, kind, props) {
  var c=create.apply(this, arguments);
  if (c&&id==="system"&&parent===document.body&&kind==="Dialog3Ctrl") {
    if (a.owner) a.owner(); a.cancel(); a.dialogs++;
    var b=props.buttonConfig||{}, ids=Object.keys(b).map(function (k) { return b[k].appData; }).join();
    c._oc107=/^(cancel,install(,uninstall)?|done(,settings)?)$/.test(ids) ? 2 : 1;
  }
  return c;
};
f.destroyControl=function (c) {
  var tag=c&&c._oc107, result=destroy.apply(this, arguments);
  if (tag) { delete c._oc107; a.dialogs--; setTimeout(function () { if (tag===2&&a.closed) a.closed(); a.pump(); }, 0); }
  return result;
};
a.loaded |= 2; a.pump();
}(typeof ocCarPlay==="undefined" ? null : ocCarPlay));
