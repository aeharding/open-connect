/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnectInstaller=(function () {
"use strict";
var active=null, own=Object.prototype.hasOwnProperty, owner={};
function foreign(fw){return!!(fw.common._openConnectOperation&&fw.common._openConnectOperation!==owner);}
function claim(fw){
 var c=fw.common;
 if(!c||c._openConnectOperation&&c._openConnectOperation!==owner||window.__ocUSBLoading)return false;
 c._openConnectOperation=owner;return true;
}
function release(fw){if(fw.common._openConnectOperation===owner)delete fw.common._openConnectOperation;}
function show(fw, title, text, buttons, done, settings, progress) {
  var host=fw._currTmpltInstance, app=fw.getCurrentApp(), context=fw.getCurrCtxtId(), common=fw.common;
  function eligible() {
    return fw._currTmpltInstance===host&&fw._frameworkState===fw._FWK_STATE_IDLE&&
      fw.getCurrentApp()===app&&fw.getCurrCtxtId()===context&&
      !common._vuiHelpDialog&&!common._vuiExamplesDialog&&
      !/^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/.test(common._cachedVuiState);
  }
  if (active||!host||!common||!eligible()||
      common._openConnectOperation&&common._openConnectOperation!==owner||
      common._openConnectDialog||window.__ocUSBLoading||
      document.querySelector&&document.querySelector(".Dialog3Ctrl_Style19_NoTemplateInstance")||(settings ?
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
    if(common._openConnectDialog===dialog)delete common._openConnectDialog;
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
  active=dialog;common._openConnectDialog=dialog;
  dialog.divElt.classList.add("Dialog3Ctrl_Style19_NoTemplateInstance");
  dialog.divElt.classList.add("Transitions_fadeIn_0_200");
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
  return function () { finish("closed"); };
}
function versionText(version) {
  if (version===undefined||version==="-") { return "Unavailable"; }
  if (!/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(version)) {
    throw new TypeError("Expected a package version");
  }
  return version;
}

function message(fw, title, text, buttons, done) {
  return show(fw, title, text, buttons, done, /settings$/.test(fw.getCurrentApp()));
}
return {claim:claim,release:release,foreign:foreign,message: message,progress: function (fw, action, warning, suspended) {
  return show(fw, action, warning, null, suspended, /settings$/.test(fw.getCurrentApp()), true);
},about: function (fw, version, done) {
  return message(fw, "About", version===undefined ? "Installed version unavailable." : "Open Connect " + versionText(version),
    {button1: {label: "OK", appData: "done"}}, done);
},confirmUninstall: function (fw, pending, done) {
  return message(fw, "Uninstall Open Connect?", "Open Connect will be removed.\nMazda Connect will restart.",
    {button1: {label: "Cancel", appData: "cancel"}, button2: {label: "Uninstall", appData: "uninstall"}}, done);
}};
})();

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
    a.cancel(); a.dialogs++; c._oc107=1;
  }
  return c;
};
f.destroyControl=function (c) {
  var tag=c&&c._oc107, result=destroy.apply(this, arguments);
  if (tag) { delete c._oc107; a.dialogs--; setTimeout(function () { a.pump(); }, 0); }
  return result;
};
a.loaded |= 2; a.pump();
}(typeof ocCarPlay==="undefined" ? null : ocCarPlay));
