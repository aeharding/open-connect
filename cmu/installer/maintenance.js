/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Transient maintenance only. Never loads, binds or replaces installed Settings. */
// Delivery only defines this factory; the captured requesting loader starts it.
var OpenConnectMaintenanceStart=function(entry){
"use strict";
if(!entry||typeof entry.current!=="function"||!entry.current())return null;
var token=entry.token,port=entry.port,usb=entry.role==="usb";
if(!/^[a-f0-9]{32}$/.test(token)||(usb?port!==15557:entry.role!=="completion"||port!==15555))return null;
var boot=usb?null:entry.boot,discovery=usb&&entry.discovery;
if(!usb&&(!boot||boot.notice!=="installed"||
 !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(boot.id)||
 !/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(boot.version)))return null;
var slot=usb?"OpenConnectMaintenance":"OpenConnectCompletion",previous=window[slot];
if(previous)previous.cancel(previous.token);
// Dev.22 can cancel this temporary claim for a deliberate Settings write.
// It carries no shared read/client handoff and ends at first display or close.
function releaseDiscovery(){
 var hold=discovery;discovery=null;
 if(hold){hold.stop=null;hold.cancel();}
}
if(discovery)discovery.stop=close;
var ui=(function () {
"use strict";
var active=null, own=Object.prototype.hasOwnProperty, owner={};
function available(fw){
 var c=fw.common;
 return c&&fw._browserShown&&fw._frameworkState===fw._FWK_STATE_IDLE&&
  fw.getCurrentApp()==="system"&&fw.getCurrCtxtId()==="HomeScreen"&&
  !c._vuiHelpDialog&&!c._vuiExamplesDialog&&
  !/^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/.test(c._cachedVuiState);
}
function foreign(fw){
 return fw.common._openConnectOperation&&fw.common._openConnectOperation!==owner||
  window.__ocUSBLoading&&window.__ocUSBLoading!==owner&&window.__ocUSBLoading!==discovery;
}
function claim(fw){
 var c=fw.common;
 if(!available(fw)||foreign(fw))return false;
 c._openConnectOperation=owner;return true;
}
function release(fw){
 if(fw.common._openConnectOperation===owner)delete fw.common._openConnectOperation;
 if(window.__ocUSBLoading===owner)delete window.__ocUSBLoading;
}
function show(fw, title, text, buttons, done, progress) {
  var host=fw._currTmpltInstance, common=fw.common;
  function eligible() {
    return fw._currTmpltInstance===host&&available(fw);
  }
  if (active||!host||!eligible()||foreign(fw)||common._openConnectDialog||common._openConnectPage||
      document.querySelector&&document.querySelector(".Dialog3Ctrl_Style19_NoTemplateInstance")) { return false; }
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
  releaseDiscovery();
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
  return show(fw, title, text, buttons, done);
}
return {claim:claim,release:release,admit:function(){window.__ocUSBLoading=owner;},choose: choose,message: message,progress: function (fw, action, warning, suspended) {
  return show(fw, action, warning, null, suspended, true);
},complete: function (fw, version, done) {
  return show(fw, "Open Connect installed", "Version " + versionText(version) + ".\nYou can now remove the USB drive.", {
    button1: {label: "Done", appData: "done"}, button2: {label: "Open settings", appData: "settings"}}, done);
}};
})();
var dead=false,s=null,known=false,busy=false,feedback=false,acking=false;
var epoch=0,job,dialog,view,timer,queued=null,shown=false,probing=false,ready=false;
var originUSB=usb,requests=[];
function valid(a,metadata){
 return a&&a.ok===true&&/^(?:-|[a-f0-9]{32}|[a-f0-9]{64})$/.test(a.revision)&&
 ["installed","retained","restart","pending"].every(function(k){return typeof a[k]==="boolean";})&&
 (metadata||typeof a.conflict==="boolean")&&
 /^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(a.version)&&
 (a.installedVersion===undefined||a.installedVersion==="-"||/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(a.installedVersion));
}
function proof(a){
 return a&&a.ok===true&&/^[a-f0-9]{64}$/.test(a.revision)&&/^[a-f0-9]{64}$/.test(a.package)&&
 /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(a.boot)&&
 /^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(a.installedVersion)&&
 /^(?:-|installed)$/.test(a.notice)&&a.completionReady===(a.notice==="installed");
}
function sameProof(a,b){
 return proof(a)&&a.revision===b.revision&&a.package===b.package&&a.boot===b.boot&&a.installedVersion===b.installedVersion;
}
function receive(a,metadata,completion){known=!!(completion?proof(a):valid(a,metadata));if(known)s=a;}
function advance(){epoch++;}
function held(){return!!job||feedback||acking;}
function claim(){return !dead&&!feedback&&!acking&&!framework.common._openConnectPage&&ui.claim(framework);}
function release(){if(!held())ui.release(framework);}
function close(){
 if(dead)return;dead=true;advance();clearTimeout(timer);queued=null;
 releaseDiscovery();
 requests.slice().forEach(function(cancelRequest){cancelRequest();});
 closeUI();endView();job=null;feedback=acking=false;ui.release(framework);
 if(window[slot]===client)window[slot]=null;
 if(window.ocCarPlay)ocCarPlay.pump();
}
function cancel(value){
 if(value!==token)return;
 if(job&&job.sent&&!(job.phase==="unresolved"&&!entry.current())||feedback||acking)return;
 close();
}
function closeUSB(){
 if(held())return;
 post("dismiss",["usb","-","-"],function(){close();},3000);
}
function session(done){
 post("status",["session","-","-"],function(a){
  done(a&&a.ok===true&&typeof a.closed==="boolean"?!a.closed:null);
 },3000);
}
function post(op,args,done,ms,intent){
 if(dead)return;
 intent=intent===undefined?epoch:intent;
 var xhr=new XMLHttpRequest(),answered=false;
 function cancelRequest(){finish(null);xhr.abort();}
 requests.push(cancelRequest);
 var deadline=setTimeout(cancelRequest,ms||185000);
 function finish(a){
 if(answered)return;
 answered=true;clearTimeout(deadline);
 var index=requests.indexOf(cancelRequest);if(index!==-1)requests.splice(index,1);
 if(dead||intent!==epoch)return;
 if(op!=="restart"&&op!=="dismiss"&&!(op==="status"&&args&&args[0]==="session"))receive(a,originUSB&&op==="status"&&args&&args[0]==="settings",op==="status"&&args&&args[0]==="completion");
 done(a,xhr.status);
}
 xhr.onreadystatechange=function(){
 if(xhr.readyState!==4)return;
 var a=null;
 try{if(xhr.status===200){a=JSON.parse(xhr.responseText);}}catch(ignore){}
 finish(a);
};
 try{
 xhr.open("POST","http://127.0.0.1:"+port+"/control",true);
 xhr.setRequestHeader("Content-Type","text/plain");
 xhr.send([token,op==="status"||!s?"-":s.revision,op].concat(args||["-","-","-"]).join("|"));
 }catch(error){finish(null);}
}
function read(done,until,attempts,intent,purpose){
 intent=intent===undefined?epoch:intent;
 if(intent!==epoch||dead)return;
 var left=until?until-Date.now():185000;
 if(left<=0){done(null);return;}
 post("status",purpose?[purpose,"-","-"]:null,function(a,code){
 
 if((a&&a.error==="busy"||(!a&&until))&&(until||(attempts||0)<8)){
  setTimeout(function(){read(done,until,(attempts||0)+1,intent,purpose);},
   until?Math.min(500,Math.max(0,until-Date.now())):500);
 }else{done(a);}
 },left,intent);
}
function closeUI(){var close=dialog;dialog=null;if(close){close();}}
function endView(){var old=view;view=null;if(old){old.close();}}
function message(title,text,hold){
 if(hold)feedback=true;
 queued=function(){
 if(!job&&(framework.getCurrentApp()!=="system"||framework.getCurrCtxtId()!=="HomeScreen"))return false;
 return ui.message(framework,title,text,{button1:{label:"OK",appData:"done"}},function(action){
  dialog=null;if(hold){if(action==="done"){feedback=false;if(boot)close();else release();}else message(title,text,hold);}
  else if(action==="done"&&originUSB&&!job)closeUSB();
});
};wake();
}
function dismiss(done){
 if(acking)return;
 if(!claim()){shown=false;return;}
 acking=true;
 var intent=epoch,until=Date.now()+12000,confirmation=s;
 function finish(ok){
 acking=false;
 if(ok)s.notice="-";
 else{shown=false;if(!complete())message("Unable to confirm","Open Mazda Settings again.",true);}
 release();
 if(ok){close();if(done)done();}else wake();
}
 function send(){
 if(dead||intent!==epoch)return;
 var left=until-Date.now()-6000;
 if(left<=0){finish(false);return;}
 post("dismiss",null,function(a){
  if(a&&a.ok===true){finish(true);}
  else if(a&&a.ok===false&&a.error==="busy"){setTimeout(send,Math.min(500,until-Date.now()));}
  else if(a&&a.ok===false){known=false;finish(false);}
  else{read(function(fresh){
   var matched=sameProof(fresh,confirmation);if(!matched)known=false;
   finish(!!(matched&&fresh.notice==="-"));
  },until,0,intent,"completion");}
 },left,intent);
}
 send();
}
function paint(){
 var action=job.phase==="restart"?"Restarting Mazda Connect":job.phase==="checking"?
 "Checking Open Connect":job.action;
 var warning=originUSB?"Do not remove the USB drive\nor turn off the car.":"Do not turn off the car.";
 if(view&&!view.update(action,warning)){view=null;}
 if(!view){view=ui.progress(framework,action,warning,function(){view=null;});}
 return!!view;
}
function end(){
 job=null;busy=false;endView();release();
}
function refuse(lost){
 if(lost){known=false;}
 endView();
 if(lost){job.phase="unresolved";}
 else{job=null;busy=false;release();}
 message(lost?"Unable to confirm the change":"Unable to finish",(lost?
 "Restart Mazda Connect before making more changes.":
 "Check your settings before trying again.")+
 (lost&&originUSB?"\nKeep the USB drive connected until restart.":""));
}
function budget(){if(!job.until){job.until=Date.now()+12000;}return job.until;}
function restart(){
 if(job.restartSent)return;
 job.phase="restart";if(!paint())return;
 job.restartSent=true;
 var current=job;
 // Restart admission starts at this send, independently of prior readback.
 job.until=Date.now()+12000;
 post("restart",null,function(a){
 if(a&&a.ok===true&&a.restarting===true){
  setTimeout(function(){if(job===current){refuse(true);}},12000);
 }else{reconcile(a);}
 },12000);
}
function changed(a){
 if(!valid(a)||a.pending||a.conflict)return false;
 var old=job.before;
 if(job.op==="uninstall")return!a.installed&&!a.retained&&a.revision==="-";
 if(job.op==="install"){
 return a.installed&&a.installedVersion===job.target&&a.notice==="installed"&&
  a.revision!==old.revision&&(!old.installed||old.installedVersion&&old.installedVersion!=="-"&&old.installedVersion!==job.target);
}
 return false;
}
function reconcile(a){
 job.phase="checking";paint();
 read(function(fresh){
 if(a&&a.ok===false){refuse(!valid(fresh)||fresh.pending);}
 else if(a===null&&!job.restartSent&&changed(fresh)){
  restart();
 }else{refuse(true);}
 },budget());
}
function drive(){
 if(!job||job.phase!=="waiting")return;
 if(job.op!=="recover"&&(s.revision!==job.before.revision||s.version!==job.target)){end();return;}
 if(!paint())return;
 job.sent=true;job.phase="writing";
 // Dev.22 already honors this foreign claim before sending a Settings write.
 ui.admit();
 post(job.op,null,function(a){
 if(a&&a.error==="session_closed"){close();return;}
 if(!valid(a)){reconcile(a);return;}
 if(job.op==="install"||job.op==="uninstall"||a.restart){restart();}
 else{end();}
});
}
function run(op){
 if(busy||!s||!entry.current()||!claim())return false;
 busy=true;advance();
 job={op:op,before:s,target:s.version,phase:"waiting",sent:false,restartSent:false,
 action:op==="uninstall"?"Removing Open Connect":op==="recover"?"Applying changes":
  (s.installed&&s.installedVersion&&s.installedVersion!=="-"?
   (s.installedVersion===s.version?"Reinstalling":"Updating"):"Installing")+" Open Connect"};
 queued=null;closeUI();drive();wake();return true;
}
function choose(){
 usb=false;
 var revision=s.revision,target=s.version;
 queued=function(){
 return ui.choose(framework,s.installed,function(action){
  dialog=null;
  if(s.revision!==revision||s.version!==target)return;
  if(action==="install"||action==="uninstall"){run(action);}
  else if(action==="cancel"){closeUSB();}
 },s.version,s.retained,s.installedVersion);
};
}
function complete(){
 return known&&boot&&proof(s)&&s.boot===boot.id&&s.installedVersion===boot.version&&
 s.notice==="installed"&&s.completionReady===true;
}
function wake(){
 clearTimeout(timer);if(dead)return;
 if(!entry.current()){cancel(token);if(dead)return;}
 if(!window.framework||!framework._browserShown){timer=setTimeout(wake,250);return;}
 if(job){
  if(job.phase==="waiting")drive();else if(job.phase==="restart"&&!job.restartSent)restart();else if(job.phase!=="unresolved")paint();
 }
 if(!job&&known&&s.pending&&!completionWaiting()){run("recover");}
 if(boot&&/settings$/.test(framework.getCurrentApp())&&!held()){close();return;}
 if(!job&&boot&&!shown&&complete()&&!queued&&!dialog){
  queued=function(){
   if(!complete())return false;
   return ui.complete(framework,s.installedVersion,function(action){
    dialog=null;
    if(action==="done"||action==="settings")dismiss(action==="settings"?function(){
     var settings=window.OpenConnect;if(settings&&settings.openSettings)settings.openSettings();
    }:null);else{shown=false;wake();}
   });
  };shown=true;
 }
 if(usb&&!busy&&s&&!dialog&&!queued){choose();}
 if(queued&&!dialog&&(!originUSB||!completionWaiting())&&entry.current()){var opened=queued();if(opened){queued=null;dialog=opened;}}
 if(!probing&&originUSB){
  probing=true;session(function(live){probing=false;if(live!==true)cancel(token);});
 }
 if(!dead)timer=setTimeout(wake,1000);
}
function completionWaiting(){
 var settings=window.OpenConnect;
 return originUSB&&(window.__ocCompletionLoading||window.OpenConnectCompletion||
  settings&&settings.openSettings&&settings.autoshowState()===2);
}
var client={token:token,close:close,cancel:cancel,protected:function(){
 return!!(job&&job.sent||feedback||acking);
},autoshowState:function(){
 return held()||dialog||queued?2:!ready?1:0;
}};
function prepared(a){
 if(boot&&a&&a.error==="operation_pending"){
  // Recovery still consumes the full maintenance contract, with visible progress.
  read(function(fresh){
   if(valid(fresh)&&fresh.pending){ready=true;wake();}else close();
  },Date.now()+12000,0,epoch,"settings");return;
 }
 if(!(boot?proof(a):valid(a,originUSB))){
  if(boot){if(window.ocCarPlay)ocCarPlay.cancel();close();}
  else message("Unable to finish","Open Connect could not be reached. Check the connection before trying again.");
  return;
 }
 ready=true;
 if(boot&&!complete()){
  if(window.ocCarPlay)ocCarPlay.cancel();close();return;
 }
 wake();
}
function begin(){
 if(boot){
  if(!framework._browserShown){timer=setTimeout(begin,250);return;}
  read(prepared,Date.now()+35000,0,epoch,"completion");
 }else session(function(live){
  if(live!==true){close();return;}
  read(function(a){
   session(function(stillLive){if(stillLive===true)prepared(a);else close();});
  },Date.now()+65000,0,epoch,"settings");
 });
}
window[slot]=client;
begin();
return dead?null:client;
};
