/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Firmware 74.00.324A. Present our pages inside the current Mazda Settings tab. */
var OpenConnectSettings=(function () {
"use strict";
var active=false, waiting=null, session=null;
var entries=[
  {key: "touch", title: "Touchscreen While Driving", choices: ["Factory Default", "Allow"]},
  {key: "warning", title: "Startup disclaimer", choices: ["Show", "Skip"]},
  {key: "carplayAutoshow", title: "Show CarPlay on connection", choices: ["Factory behavior", "Automatically show"]}
];
var own=Object.prototype.hasOwnProperty;
function bit(v) { return v===0||v===1; }
function optional(v) { return v===undefined||bit(v); }

function validServices(rows) {
  if (rows===undefined) { return true; }
  if (!Array.isArray(rows)||rows.length < 1||rows.length > 16) { return false; }
  var previous="";
  return rows.every(function (row) {
    if (!row||!/^[a-z][a-z0-9-]{0,31}$/.test(row.id)||row.id<=previous||
        /^(touch|warning|base|wireless|uart|ssh|carplay-autoshow)$/.test(row.id)||
        (row.saved!==0&&row.saved!==1)||
        (row.current!==null&&row.current!==0&&row.current!==1)) { return false; }
    previous=row.id;
    return ["label", "enable", "disable"].every(function (key) {
      return typeof row[key]==="string"&&row[key].length > 0&&
        row[key].length<=(key==="label" ? 64 : 256)&&!/[\x00-\x1f\x7f]/.test(row[key]);
    });
  });
}
var versionRE=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
function validStatus(s) {
  return s&&s.ok===true&&valid(s)&&/^(?:-|[a-f0-9]{32}|[a-f0-9]{64})$/.test(s.revision)&&
    ["installed", "retained", "conflict", "restart", "pending"].every(function (key) { return typeof s[key]==="boolean"; })&&
    (s.wireless===undefined||bit(s.wirelessCurrent))&&
    (s.developer===undefined||(typeof s.developer==="boolean"&&
      bit(s.uart)&&bit(s.ssh)&&
      bit(s.uartCurrent)&&bit(s.sshCurrent)&&
      /^(?:-|[a-f0-9]{64})$/.test(s.key)&&/^(?:-|[a-f0-9:]{47})$/.test(s.fingerprint)))&&
    versionRE.test(s.version)&&(s.installedVersion===undefined||s.installedVersion==="-"||versionRE.test(s.installedVersion));
}
function service(values, key) {
  var rows=values&&values.services, i;
  for (i=0; rows&&i < rows.length; i++) { if (rows[i].id===key) { return rows[i]; } }
  return null;
}
function preference(values, key) {
  var row=service(values, key);
  return row ? row.saved : values[key];
}
function valid(values) {
  return values&&validServices(values.services)&&bit(values.touch)&&
    bit(values.warning)&&
    optional(values.pandora)&&
    optional(values.base)&&autoshow(values)&&
    optional(values.wireless)&&
    (values.wirelessFactory===undefined||typeof values.wirelessFactory==="boolean");
}
function autoshow(s) {
  return s.carplayAutoshow===undefined||(bit(s.carplayAutoshow)&&
    bit(s.carplayAutoshowCurrent));
}
function toggle(title, on, key) { return {text1: title, itemStyle: "styleOnOff", value: on ? 1 : 2, hasCaret: false, appData: key}; }
function featureCount(v) { return 2 + (v&&v.carplayAutoshow!==undefined ? 1 : 0); }

function replace(obj, key, fn) {
  var previous=obj[key], local=own.call(obj, key);
  obj[key]=fn;
  return function () {
    if (obj[key]!==fn) { return; }
    if (local) { obj[key]=previous; } else { delete obj[key]; }
  };
}

function settingsApp(id) {
  return id==="syssettings"||id==="vehsettings"||id==="audiosettings";
}

function inTab(fw) {
  return settingsApp(fw.getCurrentApp())&&/Tab$/.test(fw.getCurrCtxtId())&&
    fw._frameworkState===fw._FWK_STATE_IDLE&&!fw.common._vuiHelpDialog;
}

// Keep the last choice across pages and in-flight writes.
function preferences(store) {
  if (session&&session.owner===store) { return session; }
  function read() {
    try { return store.read(); } catch (error) { return null; }
  }
  var saved=read();
  if (!valid(saved)) { return null; }
  var wanted={}, busy=false, timer=null;
  var prefs={owner: store, failure: null, changed: null};
  function pending(value) { return !store.pending||store.pending(value); }
  prefs.values=function () {
    if (!busy&&!Object.keys(wanted).length) {
      var current=read();
      if (!valid(current)) { return null; }
      saved=current;
    }
    var values={}, keys=["developer", "key", "fingerprint", "uartCurrent", "sshCurrent", "wirelessCurrent",
      "wirelessFactory", "restart", "carplayAutoshowCurrent", "touch", "warning", "uart", "ssh",
      "pandora", "base", "wireless", "carplayAutoshow"];
    keys.forEach(function (key) { values[key]=own.call(wanted, key) ? wanted[key] : saved[key]; });
    if (saved.services) {
      values.services=saved.services.map(function (row) {
        return {id: row.id, label: row.label, saved: own.call(wanted, row.id) ? wanted[row.id] : row.saved,
          current: row.current, enable: row.enable, disable: row.disable};
      });
    }
    return values;
  };
  function flush() {
    var keys=Object.keys(wanted);
    if (busy) { return; }
    if (!keys.length) { pending(false); return; }
    var key=keys[0], requested=wanted[key];
    if (preference(saved, key)===requested) {
      delete wanted[key]; flush();
      if (prefs.changed) { prefs.changed(false); }
      return;
    }
    busy=true;
    var answered=false;
    function finish(actual) {
      if (answered) { return; }
      answered=true;
      busy=false;
      // Reconcile a lost acknowledgement once; never resend.
      if (!valid(actual)) { actual=read(); }
      if (valid(actual)) { saved=actual; }
      var failed=!valid(actual)||(preference(actual, key)!==requested&&wanted[key]===requested);
      if (failed) {
        delete wanted[key];
        prefs.failure=key;
        if (prefs.changed) { prefs.changed(true); }
      } else if (wanted[key]===requested) { delete wanted[key]; }
      flush();
      if (!failed&&prefs.changed) { prefs.changed(false); }
    }
    try { store.write(key==="carplayAutoshow" ? "carplay-autoshow" : key, preference(saved, key), requested, finish); }
    catch (error) { finish(null); }
  }
  prefs.pending=function () { return busy||Object.keys(wanted).length > 0; };
  prefs.select=function (key, value) {
    if (!pending(true)) { if (prefs.revert) { prefs.revert(); } return; }
    prefs.failure=null;
    wanted[key]=value;
    clearTimeout(timer);
    timer=setTimeout(flush, 250);
  };
  prefs.importKey=function (done) {
    if (prefs.pending()||typeof store.importKey!=="function"||!pending(true)) { return; }
    busy=true;
    var answered=false;
    function finish(actual, failed) {
      if (answered) { return; }
      answered=true; busy=false;
      if (valid(actual)) { saved=actual; }
      done(valid(actual)&&!failed ? actual : null);
      flush();
    }
    try { store.importKey(finish); } catch (error) { finish(null); }
  };
  session=prefs;
  return prefs;
}

// Read verified policy; writes compare the previous value before committing.
function open(fw, store) {
  var dialogs=OpenConnectInstaller, host=fw._currTmpltInstance;
  if (active||!inTab(fw)||!host||!host.list2Ctrl) { return false; }
  var prefs=preferences(store);
  if (!prefs) { return false; }
  var page, choice, dismiss=null, closed=false, restorers=[];
  var oldDisplay=host.divElt.style.display;
  var tab=fw.getCurrCtxtId();
  function current() {
    return !closed&&fw._currTmpltInstance===host&&inTab(fw)&&fw.getCurrCtxtId()===tab;
  }
  function discard(p) {
    if (p) {
      p.cleanUp();
      if (p.divElt.parentNode) { p.divElt.parentNode.removeChild(p.divElt); }
    }
  }
  function close() {
    if (closed) { return; }
    closed=true;
    if (dismiss) { dismiss(); }
    prefs.changed=null;
    prefs.revert=null;
    while (restorers.length) { restorers.pop()(); }
    discard(page);
    host.divElt.style.display=oldDisplay;
    active=false;
  }
  function ask(title, text, label, action, done) {
    return dialogs.message(fw, title, text, {button1: {label: "Cancel", appData: "cancel"},
      button2: {label: label, appData: action}}, done);
  }
  function render(index, focus) {
    var values=prefs.failure ? null : prefs.values();
    if (!values) { index="unknown"; focus=0; }
    var rows=[], title="Open Connect", i, row;
    if (index===null) {
      for (i=0; i < entries.length; i++) {
        row=entries[i];
        if (values[row.key]===undefined) { continue; }
        rows.push({text1: row.title, label1: row.key==="touch" ? ["Default", "Allow"][values.touch] : row.choices[values[row.key]],
          itemStyle: "style06", hasCaret: true, appData: i});
      }
      if (values.wireless!==undefined) {
        rows.push({text1: "Wireless CarPlay" + (values.wirelessFactory ? " (factory enabled)" : ""),
          itemStyle: "styleOnOff", value: values.wirelessFactory||values.wireless ? 1 : 2,
          disabled: values.wirelessFactory===true, hasCaret: false, appData: "wireless"});
      }
      if (values.services||values.pandora!==undefined||values.base!==undefined) {
        rows.push({text1: "Services", itemStyle: "style01", hasCaret: true, appData: "services"});
      }
      if (values.developer) {
        rows.push({text1: "Developer options", itemStyle: "style01", hasCaret: true, appData: "developer"});
      }
      rows.push({text1: "Uninstall", itemStyle: "style01", hasCaret: false, appData: "uninstall",
        disabled: typeof store.uninstall!=="function"});
      rows.push({text1: "About", itemStyle: "style01", hasCaret: false, appData: "about"});
    } else if (index==="unknown") {
      title="Change could not be confirmed";
      rows.push({text1: "Return to Mazda Settings", itemStyle: "style01", hasCaret: false, appData: 0});
    } else if (index==="services") {
      title="Services";
      if (values.base!==undefined) {
        rows.push(toggle("Base optimizations", values.base, "base"));
      }
      if (values.services) {
        values.services.forEach(function (serviceRow) {
          rows.push(toggle(serviceRow.label + (serviceRow.current===null ? " (startup unknown)" :
            serviceRow.current!==serviceRow.saved ? " (restart needed)" : ""), serviceRow.saved, serviceRow.id));
        });
      } else if (values.pandora!==undefined) {
        rows.push(toggle("Pandora", values.pandora, "pandora"));
      }
    } else if (index==="developer") {
      title="Developer options";
      rows.push(toggle("UART", values.uart, "uart"));
      row=toggle("SSH", values.ssh, "ssh"); row.disabled=values.key==="-"; rows.push(row);
      rows.push({text1: "Import public key", itemStyle: "style01", hasCaret: false, appData: "import",
        disabled: prefs.pending()||typeof store.importKey!=="function"});
    } else {
      row=entries[index];
      title=row.title;
      for (i=0; i < row.choices.length; i++) {
        rows.push({text1: row.choices[i], image1: "radio", checked: i===values[row.key],
          itemStyle: "style03", hasCaret: false, appData: i});
      }
    }
    var listProps={dataList: {itemCountKnown: true, itemCount: rows.length, items: rows},
      titleConfiguration: "listTitle", title: {text1: title, titleStyle: "style02"},
      smallItemText: true, focussedItem: focus, selectCallback: select};
    if (typeof index==="number") { listProps.checkMinChangeInterval=0; }
    if (index==="developer"||index==="services") { listProps.toggleMinChangeInterval=0; }
    var next=fw.instantiateTemplate("syssettings", host.divElt.parentNode, "List2Tmplt",
      {List2Ctrl: listProps});
    if (!next) { return false; }
    var old=page;
    page=next;
    choice=index;
    host.divElt.style.display="none";
    discard(old);
    next.handleControllerEvent(fw.multicontroller.getMode());
    next.handleControllerEvent("acceptFocusInit");
    return true;
  }
  function select(control, item, params) {
    if (!current()||dismiss||!page||control!==page.list2Ctrl) { return; }
    if (choice===null&&item==="developer") { render("developer", 0); return; }
    if (choice===null&&item==="services") { render("services", 0); return; }
    if (choice===null&&item==="wireless") {
      if (!params||(params.additionalData!==1&&params.additionalData!==2)) { return; }
      var values=prefs.values(), enabled=params.additionalData===1;
      if (!values||values.wirelessFactory===true||values.wireless===undefined||
          values.wireless===(enabled ? 1 : 0)) { return; }
      dismiss=ask((enabled ? "Enable" : "Disable") + " Wireless CarPlay?", enabled ? "Changes apply after restarting Mazda Connect. Then select Apple CarPlay in Mazda's Wi-Fi settings and pair your iPhone over Bluetooth." :
          "Restores the original CarPlay behavior after restarting Mazda Connect.", enabled ? "Enable" : "Disable", "apply", function (action) {
          dismiss=null;
          if (action==="apply"&&current()) { prefs.select("wireless", enabled ? 1 : 0); }
          if (current()&&choice===null) { render(null, featureCount(values)); }
        });
      return;
    }
    if (choice==="services") {
      if (!params||(params.additionalData!==1&&params.additionalData!==2)) { return; }
      var enabled=params.additionalData===1, desired=enabled ? 1 : 0;
      var values=prefs.values();
      if (!values) { render("unknown", 0); return; }
      var serviceRow=service(values, item);
      if (item!=="base"&&!serviceRow&&!(item==="pandora"&&!values.services)) { return; }
      if (preference(values, item)===undefined||preference(values, item)===desired) { return; }
      var serviceLabel=item==="base" ? "Base optimizations" : serviceRow ? serviceRow.label : "Pandora";
      var serviceText=item==="base" ? (enabled ?
        (values.services ? "Reduces logging and startup work. Stops unused integrations. Applies after restart." :
          "Reduces native diagnostic logging. Applies after restart.") :
        (values.services ? "Restores original logging and startup behavior after restarting Mazda Connect." :
          "Restores original native logging after restarting Mazda Connect.")) :
        serviceRow ? (enabled ? serviceRow.enable : serviceRow.disable) :
        "Changes apply after restarting Mazda Connect.";
      if (item==="base"&&enabled&&/^0\.3\.0-dev\.(16|17|18)$/.test(store.version)&&values.wireless) {
        serviceText += " With wireless CarPlay, Mazda Navigation starts about 20 seconds later.";
      }
      var serviceFocus=item==="base"||values.base===undefined ? 0 : 1;
      if (serviceRow) {
        values.services.some(function (row, index) {
          if (row.id!==item) { return false; }
          serviceFocus += index; return true;
        });
      }
      dismiss=ask((enabled ? "Enable " : "Disable ") + serviceLabel + "?", serviceText, enabled ? "Enable" : "Disable", "apply", function (action) {
          dismiss=null;
          if (action==="apply"&&current()) { prefs.select(item, desired); }
          if (current()&&choice==="services") { render("services", serviceFocus); }
        });
      return;
    }
    if (choice==="developer") {
      if ((item==="uart"||item==="ssh")&&params&&
          (params.additionalData===1||params.additionalData===2)) {
        var values=prefs.values();
        if (item==="ssh"&&values.key==="-") { return; }
        if (params.additionalData===1&&values[item]===0) {
          dismiss=ask(item==="uart" ? "Enable UART?" : "Enable SSH?", item==="uart" ? "Passwordless root access over UART. Changes apply after restart." :
              "Changes apply after restarting Mazda Connect.", "Enable", "enable", function (action) {
              dismiss=null;
              if (action==="enable"&&current()) { prefs.select(item, 1); }
              if (current()&&choice==="developer") { render("developer", item==="uart" ? 0 : 1); }
            });
          return;
        }
        prefs.select(item, params.additionalData===1 ? 1 : 0);
      } else if (item==="import"&&!prefs.pending()&&typeof store.importKey==="function") {
        dismiss=ask("Import public key?", "Put open-connect.pub on the USB drive. RSA and ECDSA public keys are supported. The imported key will be replaced.", "Import", "import", function (action) {
            dismiss=null;
            if (action!=="import"||!current()) { return; }
            prefs.importKey(function (actual) {
              if (!current()||choice!=="developer") { return; }
              render("developer", 2);
              dismiss=dialogs.message(fw, actual ? "Public key imported" : "Key could not be imported",
                actual ? "Fingerprint (MD5):\n" + actual.fingerprint.slice(0, 23) + "\n" +
                  actual.fingerprint.slice(24) + "\nEnable SSH when ready." :
                  "Use one USB drive with open-connect.pub: an RSA key of at least 2048 bits or an ECDSA public key. Private keys and Ed25519 are not supported.",
                {button1: {label: "OK", appData: "done"}}, function () { dismiss=null; });
            });
          });
      }
      return;
    }
    if (choice===null&&item==="about") {
      dismiss=dialogs.about(fw, store.version, function () { dismiss=null; });
      return;
    }
    if (choice===null&&item==="uninstall"&&typeof store.uninstall==="function") {
      dismiss=dialogs.confirmUninstall(fw, prefs.pending(), function (action) {
        dismiss=null;
        if (action==="uninstall"&&current()&&!prefs.pending()) {
          close();
          store.uninstall();
        }
      });
      return;
    }
    if (typeof item!=="number"||item < 0||item>=(choice===null ? entries.length : 2)) { return; }
    if (choice==="unknown") { prefs.failure=null; close(); return; }
    if (choice===null) {
      var values=prefs.values();
      if (values&&values[entries[item].key]!==undefined) { render(item, values[entries[item].key]); }
      return;
    }
    // Save without moving List2 focus or its radio dot.
    if (choice===2&&item===1&&preference(prefs.values(), "carplayAutoshow")===0) {
      dismiss=ask("Automatically show CarPlay?", "Opens CarPlay when your phone connects. Applies after restarting Mazda Connect.", "Enable", "apply", function (action) {
        dismiss=null;
        if (current()) { if (action==="apply") prefs.select("carplayAutoshow", 1); else render(choice,0); }
      });
      return;
    }
    prefs.select(entries[choice].key, item);
  }
  if (!render(null, 0)) { return false; }
  active=true;
  if (typeof ocCarPlay!=="undefined"&&ocCarPlay) { ocCarPlay.cancel(); }
  prefs.revert=function () { if (current()) { render(choice, 0); } };
  prefs.changed=function (failed) {
    if (!failed) {
      if (current()&&choice==="developer"&&!dismiss) {
        var values=prefs.values(), ctrl=page.list2Ctrl;
        if (!values) { return; }
        ctrl.dataList.items[2].disabled=prefs.pending()||typeof store.importKey!=="function";
        ctrl.updateItems(2, 2);
      }
      return;
    }
    if (dismiss) { dismiss(); }
    if (current()) { render("unknown", 0); } else { close(); }
  };
  var transition=fw.common.getCommonTransitionData;
  restorers.push(replace(fw.common, "getCommonTransitionData", function () {
    close();
    return transition.apply(this, arguments);
  }));
  var input=host.handleControllerEvent;
  restorers.push(replace(host, "handleControllerEvent", function () {
    if (!current()) { close(); return input.apply(this, arguments); }
    return page.handleControllerEvent.apply(page, arguments);
  }));
  // Both Back affordances use MMUI.
  var send=fw.sendEventToMmui;
  restorers.push(replace(fw, "sendEventToMmui", function (app, event) {
    if (current()&&app==="common"&&(event==="Global.GoBack"||event==="Global.MenuUp")) {
      if (dismiss) { dismiss(); }
      else if (choice!==null&&choice!=="unknown") {
        var focus=choice;
        if (choice==="services") {
          var serviceValues=prefs.values();
          focus=featureCount(serviceValues) + (serviceValues&&serviceValues.wireless!==undefined ? 1 : 0);
        }
        if (choice==="developer") {
          var values=prefs.values();
          focus=featureCount(values) + (values&&values.wireless!==undefined ? 1 : 0) +
            (values&&(values.pandora!==undefined||values.base!==undefined) ? 1 : 0);
        }
        render(null, focus);
      }
      else { if (choice==="unknown") { prefs.failure=null; } close(); }
      return;
    }
    return send.apply(this, arguments);
  }));
  return close;
}

// Preserve every other System-tab row and callback.
function attach(fw, app, store) {
  function template() { return app._currentContextTemplate; }
  var entry=app._contextTable.SystemTab;
  var original=entry.readyFunction;
  var list=null, release=null, closePage=null;
  var id="open-connect-settings";
  function bind() {
    var host=template();
    if (!host||!host.list2Ctrl||host.list2Ctrl===list) { return; }
    if (release) { release(false); }
    list=host.list2Ctrl;
    var ctrl=list, set=ctrl.setDataList, select=ctrl.properties.selectCallback;
    var undoSelect=replace(ctrl.properties, "selectCallback", function (control, value) {
      if (control===ctrl&&value===id) {
        var selectedHost=template();
        var show=function (fresh) {
          if (!fresh||list!==ctrl||fw._currTmpltInstance!==selectedHost||
              template()!==selectedHost) { return; }
          var opened=open(fw, store);
          if (opened) { closePage=opened; }
        };
        if (store.refresh) { store.refresh(show); } else { show(true); }
        return;
      }
      return select.apply(this, arguments);
    });
    function withEntry(data) {
      var count=data&&data.itemCount, items=data&&data.items;
      if (!items||!count||items.length < count||items[count - 1].appData!=="SelectAbout"||
          items.some(function (r) { return r&&r.appData===id; })) {
        return set.apply(this, arguments);
      }
      // Mazda updates About by its last index; preserve preceding indices.
      var copy={}, key;
      for (key in data) { if (own.call(data, key)) { copy[key]=data[key]; } }
      copy.items=items.slice(0, count);
      copy.items.splice(count - 1, 0, {text1: "Open Connect", itemStyle: "style01",
        hasCaret: true, appData: id});
      copy.itemCount=count + 1;
      return set.call(ctrl, copy);
    }
    var undoSet=replace(ctrl, "setDataList", withEntry);
    release=function (visible) {
      if (closePage) { closePage(); closePage=null; }
      undoSelect();
      undoSet();
      if (!visible) { return; }
      var data=ctrl.dataList, rows=data.items.filter(function (r) { return r.appData!==id; });
      if (rows.length!==data.itemCount) {
        set.call(ctrl, {itemCountKnown: true, itemCount: rows.length, items: rows,
          vuiSupport: data.vuiSupport});
        if (rows.length) { ctrl.updateItems(0, rows.length - 1); }
      }
    };
  }
  function repaint() {
    if (list&&list.dataList.itemCount) { list.updateItems(0, list.dataList.itemCount - 1); }
  }
  if (inTab(fw)&&fw.getCurrCtxtId()==="SystemTab") {
    bind();
    if (list) { list.setDataList(list.dataList); repaint(); }
  }
  var undoReady=replace(entry, "readyFunction", function () {
    bind();
    var result=original.apply(this, arguments);
    repaint();
    return result;
  });
  return function detach() {
    undoReady();
    if (release) { release(template()&&template().list2Ctrl===list); }
    list=release=null;
  };
}
// Wait for the stock Settings tab; do not force a tab transition.
function fromHome(fw, store, result) {
  if (active||waiting||fw._frameworkState!==fw._FWK_STATE_IDLE||fw.common._vuiHelpDialog||
      fw.getCurrentApp()!=="system"||fw.getCurrCtxtId()!=="HomeScreen") { return false; }
  var attempts=0;
  var timer=setInterval(function () {
    var app=fw.getCurrentApp();
    if (inTab(fw)&&open(fw, store)) {
      cancel();
      result(true);
    } else if (++attempts>=40||(app!=="system"&&!settingsApp(app))||
        (app==="system"&&fw.getCurrCtxtId()!=="HomeScreen")||
        (settingsApp(app)&&fw._frameworkState===fw._FWK_STATE_IDLE&&!inTab(fw))) {
      cancel();
      result(false);
    }
  }, 200);
  function cancel() {
    clearInterval(timer);
    if (waiting===cancel) { waiting=null; }
  }
  waiting=cancel;
  try { fw.sendEventToMmui("system", "SelectSettings"); }
  catch (error) { cancel(); throw error; }
  return cancel;
}

return {open: open, fromHome: fromHome, attach: attach, validStatus: validStatus,
  blocked: function () { return active||waiting||session&&session.pending(); }};
}());

(function (a, f) {
if (!a||a.loaded & 4) { return; }
var owner, held;
a.owner=function () {
  if (window.__ocUSBLoading) { return 2; }
  var current=window.OpenConnect;
  if (!current) { return 1; }
  if (current.autoshowState) { return current.autoshowState(); }
  if (current!==owner) {
    owner=current; held=true; a.cancel();
    ["start", "reopenUSB"].forEach(function (key) { if (owner[key]) { a.wrap(owner, key, function () { held=true; a.cancel(); }); } });
    ["cancelUSB", "dispose"].forEach(function (key) { if (owner[key]) { a.wrap(owner, key, null, function () { a.closed(); }); } });
  }
  return held||owner.protected() ? 2 : 0;
};
a.closed=function () { if (owner===window.OpenConnect&&!owner.protected()&&!a.dialogs) { held=false; } };
function context(id, ctx) {
  if (id==="backupparking"||/^(IntroAnimation|QuickStartLoop|Disclaimer)$/.test(ctx)) return 1;
  return id==="system" ? (/^(HomeScreen|Entertainment)$/.test(ctx) ? 0 : 2) :
    /^(fmradio|amradio|usbaudio|btaudio|auxin|satradio|xmaudio|cd|dvd|tv|stitcher|aharadio|pandora|dab)$/.test(id) ? 0 : 2;
}
a.check=function (focus, next) {
  var state=a.owner(), h=f._currTmpltInstance, id=f.getCurrentApp(), c=f.common, s=OpenConnectSettings;
  if (state) { return state; }
  if (a.dialogs||s.blocked&&s.blocked()||departure(next, a.edge())) { return 2; }
  if (!h||!c||!focus||f._focusStack!==focus||focus[0].id!==id||
      h.contextInfo.uiaId!==id||f._frameworkState!==f._FWK_STATE_IDLE||!f._browserShown) { return 1; }
  var ctx=h.contextInfo.ctxtId, app=f.getAppInstance(id);
  if (!app||!app._currentContext||app._currentContext.ctxtId!==ctx||
      next&&(next.uiaId!==id||next.contextSeq!==h.contextInfo.contextSeq)) { return 1; }
  if (c._vuiHelpDialog||c._vuiExamplesDialog||a.voice(c._cachedVuiState)) { return 2; }
  var edge=a.edge(), kind=context(id, ctx);
  if (edge&&edge.reverse) {
    if (kind||a.focus<=edge.reverse) return 1;
    edge.origin=[id,ctx,h.contextInfo.contextSeq]; edge.reverse=0;
  }
  return kind;
};
function departure(m, edge) {
  if (!edge||!m||m.msgType!=="ctxtChg"||m._cp.order<=edge.order) return false;
  if (m.uiaId==="backupparking") { edge.reverse=m._cp.order; return false; }
  var kind=context(m.uiaId,m.ctxtId), old=edge.origin;
  if (kind===2) return true;
  if (kind===1||!old||context(old[0],old[1])===1) return false;
  return old[0]!==m.uiaId||old[1]!==m.ctxtId||!edge.reverse&&old[2]!==m.contextSeq;
}
a.signal=function (m) {
  var id=m.msgId, p=m.params&&m.params.payload;
  var edge=a.edge();
  if (edge&&m._cp.order>edge.order&&m.uiaId==="system"&&p&&p.appName==="carplay"&&
      /^(StatusMenuVisibleCarPlay|StatusMenuCarPlayWifi)$/.test(id)) {
    if (id==="StatusMenuVisibleCarPlay" ? p.state==="Visible" : p.appStatus==="Available") edge.menu=m;
    else if (edge.menu&&edge.menu.msgId===id) edge.menu=null;
  }
  if (m.uiaId==="common"&&id==="vuiState"&&p) a.busy=a.busy & ~16 | (a.voice(p.state) ? 16 : 0);
  if (m.uiaId==="system") {
    if (id==="StatusPhoneCall"&&p&&/^(Connecting|ActiveCall|IncomingCall|NoCall)$/.test(p.phoneCallStatus)) { a.busy=a.busy & ~1 | (p.phoneCallStatus!=="NoCall" ? 1 : 0); }
    if (id==="ShowStateSBN_SiriActive") { a.busy |= 4; }
    if (/^(RemoveStateSBN_SiriActive|TimedSBN_SiriError|TimedSBN_VRLoading|TimedSBN_VoiceNotSupported)$/.test(id)) { a.busy &= ~4; }
  }
  if (m.uiaId==="phone") {
    if (/^(ActiveCallInfo|ConferenceCallInfo|BTMultipleCallCP)$/.test(id)) { a.busy |= 2; }
    if (id==="NoCallState") { a.busy &= ~2; }
  }
  if (departure(m, edge)||a.busy&&(!edge||m._cp.order>=edge.order)) { a.cancel(); }
};
a.early.forEach(a.signal); a.early=null;
a.run=function (pending, input, trusted, focus, next) {
  if (Date.now()>=pending.until||input!==pending.input||a.busy) { a.cancel(); return; }
  if (a.loaded!==7) return;
  var state=a.check(focus, next);
  if (state===2) a.cancel();
  if (state!==0||a.edge()!==pending||!trusted||!pending.menu||!pending.menu._cp.delivered||
      !pending.delivered||f.websockets._waitMsgArray.length||a.holding) return;
  a.cancel(); f.sendEventToMmui("system", "SelectCarPlay");
};
a.loaded |= 4; a.pump();
}(typeof ocCarPlay==="undefined" ? null : ocCarPlay, typeof framework==="undefined" ? null : framework));
