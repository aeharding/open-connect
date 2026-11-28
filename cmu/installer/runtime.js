/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Boot-selected Settings. */
var OpenConnect=(function(){
"use strict";
function meta(n){return document.querySelector('meta[name="open-connect-'+n+'"]');}
function attr(n,k){var el=meta(n);return el&&el.getAttribute(k||"content");}
var TOK=/^[a-f0-9]{32}$/,VER=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/,
VUI=/^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/;
function ctrl(body,done,ms){
var xhr=new XMLHttpRequest(),answered=false;
var deadline=setTimeout(function(){finish(null,0);xhr.abort();},ms||185000);
function finish(a,code){
if(answered)return;
answered=true;clearTimeout(deadline);
done(a,code);
}
xhr.onreadystatechange=function(){
if(xhr.readyState!==4)return;
var a=null,code=0;
try{code=xhr.status;if(code===200){a=JSON.parse(xhr.responseText);}}catch(ignore){}
finish(a,code);
};
try{
xhr.open("POST","http://127.0.0.1:15555/control",true);
xhr.setRequestHeader("Content-Type","text/plain");
xhr.send(body);
}catch(error){finish(null,0);}
return function(){finish(null,0);xhr.abort();};
}

var api=(function(){
if(window.OpenConnect)return window.OpenConnect;
var token=attr("token"),version=attr("version");
if(!TOK.test(token)||!VER.test(version))return null;
var base="file:///tmp/open-connect/feature/";
var s=null,known=false,busy=false,saving=false,pending=false,epoch=0;
var timer,dialog,view,app,detach,ui,menus,job,queued=null,refresh=null;
var openIntent=null,openTimer;
function valid(a){return menus&&menus.validStatus(a);}
function receive(a){known=!!valid(a);if(known)s=a;}
function advance(){refresh=null;epoch++;}
function values(){return known&&s.installed&&!s.pending&&!s.conflict?s:null;}
function held(){return!!job||pending||!!refresh||!!(menus&&menus.blocked());}
function claim(){return !(job&&(!saving||job.phase==="unresolved"))&&ui.claim(framework);}
function release(){if(!job&&!pending&&ui)ui.release(framework);}
function autoshow(){return openIntent||held()||dialog||view?2:!menus||s&&!known?1:0;}
function post(op,args,done,ms,intent){
intent=intent===undefined?epoch:intent;
ctrl([token,op==="status"||!s?"-":s.revision,op].concat(args||["-","-","-"]).join("|"),function(a,code){
if(intent!==epoch)return;
if(op!=="restart")receive(a);
done(a,code);
},ms);
}
function read(done,until,intent,fast){
intent=intent===undefined?epoch:intent;
if(intent!==epoch)return;
var left=until-Date.now();
if(left<=0){done(null);return;}
post("status",fast?["settings","-","-"]:null,function(a,code){
if(fast&&code===400){read(done,until,intent,false);return;}
if(a&&a.error==="busy"||!a){
setTimeout(function(){read(done,until,intent,fast);},Math.min(500,Math.max(0,until-Date.now())));
}else{done(a);}
},left,intent);
}
function closeUI(){var close=dialog;dialog=null;if(close){close();}}
function endView(){var old=view;view=null;if(old){old.close();}}
function message(title,text){
queued=function(){
return ui.message(framework,title,text,{button1:{label:"OK",appData:"done"}},function(){dialog=null;});
};wake();
}
function paint(){
var action=job.phase==="restart"||job.op==="restart"?"Restarting Mazda Connect":job.phase==="checking"?
"Checking Open Connect":"Removing Open Connect";
var warning="Do not turn off the car.";
if(view&&!view.update(action,warning)){view=null;}
if(!view){view=ui.progress(framework,action,warning,function(){view=null;});}
return!!view;
}
function end(actual,unacked){
var reply=job.reply;
job=null;busy=saving=false;endView();release();
if(reply){reply(actual,unacked);}
}
function refuse(lost,restartRequired){
if(lost){known=false;}
var reply=job.reply;
endView();
if(lost){job.phase="unresolved";job.reply=null;}
else{job=null;busy=saving=false;release();}
if(reply){reply(null,lost||restartRequired?"restart":true);return;}
message(lost?"Unable to confirm the change":"Unable to finish",(lost?
"Restart Mazda Connect before making more changes.":
"Check your settings before trying again."));
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
if(job.op==="set"){
var key=job.args[0],wanted=Number(job.args[2]),value=a[key.replace(/-([a-z])/g,function(_,c){return c.toUpperCase();})];
(a.services||[]).forEach(function(row){if(row.id===key){value=row.saved;}});
return a.installed&&a.revision!==old.revision&&value===wanted;
}
if(job.op==="import")return job.args?a.installed&&a.revision!==old.revision:/^[a-f0-9]{64}$/.test(a.key)&&a.key!==old.key&&a.revision!==old.revision;
return false;
}
function reconcile(a){
job.phase="checking";if(!saving){paint();}
read(function(fresh){
if(a&&a.ok===false){refuse(!valid(fresh)||fresh.pending,a.error==="restart_required");}
else if(a===null&&!job.restartSent&&changed(fresh)){
if(saving){end(values(),"reconciled");}else{restart();}
}else{refuse(true);}
},budget());
}
function drive(){
if(!job||job.phase!=="waiting")return;
if(s.revision!==job.before.revision||s.version!==job.target){end(null);return;}
if(!saving&&!paint())return;
if(job.op==="restart"){restart();return;}
job.phase="writing";
post(job.op,job.args,function(a){
if(!valid(a)){reconcile(a);return;}
if(saving){end(values());}
else if(job.op==="uninstall"||a.restart){restart();}
else{end(null);}
});
}
function run(op,args,reply,leave){
if(busy||!s||!claim()){if(reply){reply(null);}return false;}
busy=true;saving=!!reply;openIntent=null;clearTimeout(openTimer);advance();
job={op:op,args:args,before:s,target:s.version,reply:reply,phase:"waiting",restartSent:false};
queued=null;closeUI();if(leave)leave();drive();wake();return true;
}
var store={version:version,read:values,
pending:function(value){
if(value&&!claim())return false;
pending=value;release();return true;
},
refresh:function(reply,until){
if(busy||pending){reply(saving&&!!values());return;}
if(refresh){refresh.push(reply);return;}
advance();var waits=refresh=[reply],intent=epoch;
read(function(a){
if(intent!==epoch)return;
refresh=null;waits.forEach(function(fn){if(intent===epoch)fn(!!values());});
},until||Date.now()+12000,intent,true);
},
unavailable:function(){
if(dialog||queued||menus.blocked())return;
dialog=ui.message(framework,"Settings unavailable",job&&job.phase==="unresolved"?
"Restart Mazda Connect before making more changes.":"Open Connect could not be reached. Try again.",
{button1:{label:"OK",appData:"done"}},function(){dialog=null;});
},
write:function(key,from,to,reply){run("set",[key,String(from),String(to)],reply);},importKey:function(reply){run("import",null,reply);},exportPrefs:function(reply){run("export",["prefs","-","-"],reply);},importPrefs:function(reply){run("import",["prefs","-","-"],reply);},uninstall:function(leave){return run("uninstall",null,null,leave);},busy:function(){return busy||pending;},restart:function(leave){return values()&&s.restart&&!pending&&run("restart",null,null,leave);}};
function openSettings(){
if(openIntent)return true;
if(!homeAvailable()||held())return false;
var host=framework._currTmpltInstance;
var intent=openIntent={host:host,seq:host.contextInfo&&host.contextInfo.contextSeq,until:Date.now()+12000};
openTimer=setTimeout(function(){if(openIntent===intent)openIntent=null;},12000);
openWhenReady();return true;
}
function homeAvailable(){
var c=framework.common;
return framework._browserShown&&framework._frameworkState===framework._FWK_STATE_IDLE&&
framework._currTmpltInstance&&framework.getCurrentApp()==="system"&&framework.getCurrCtxtId()==="HomeScreen"&&
c&&!c._openConnectDialog&&!c._openConnectPage&&!c._openConnectOperation&&
!c._vuiHelpDialog&&!c._vuiExamplesDialog&&!VUI.test(c._cachedVuiState)&&
!document.querySelector(".Dialog3Ctrl_Style19_NoTemplateInstance");
}
function openWhenReady(){
var intent=openIntent;
if(!intent||!menus)return;
function current(){
return openIntent===intent&&Date.now()<=intent.until&&homeAvailable()&&
framework._currTmpltInstance===intent.host&&
(!intent.host.contextInfo||intent.host.contextInfo.contextSeq===intent.seq);
}
if(!current()||held()){openIntent=null;clearTimeout(openTimer);return;}
function open(ok){
var active=current();
if(openIntent===intent){openIntent=null;clearTimeout(openTimer);}
if(!active)return;
if(ok)menus.fromHome(framework,store,function(){});else store.unavailable();
}
if(values())open(true);else{
clearTimeout(openTimer);
openTimer=setTimeout(function(){if(openIntent===intent)openIntent=null;},Math.max(1,intent.until-Date.now())+1);
store.refresh(open,intent.until);
}
}
function bind(){
var current=framework.getAppInstance("syssettings");
if(current&&current._contextTable&&current._contextTable.SystemTab&&current!==app){
if(detach)detach();app=current;detach=menus.attach(framework,app,store);
}
}
function wake(){
clearTimeout(timer);
if(!window.framework||!framework._browserShown){timer=setTimeout(wake,250);return;}
if(job){
if(job.phase==="waiting")drive();else if(job.phase==="restart"&&!job.restartSent)restart();else if(!saving&&job.phase!=="unresolved")paint();
}
if(queued&&!dialog){var opened=queued();if(opened){queued=null;dialog=opened;}}
clearTimeout(timer);if(queued||job&&job.phase!=="unresolved")timer=setTimeout(wake,250);
}
function load(name,next){utility.loadScript(base+name+".js",null,next);}
load("dialog",function(){
ui=OpenConnectInstaller;
load("settings",function(){
menus=OpenConnectSettings;
var initialize=framework._initApp;
if(initialize)framework._initApp=function(id){var result=initialize.apply(this,arguments);if(id==="syssettings")bind();return result;};
bind();if(window.ocCarPlay)ocCarPlay.pump();
openWhenReady();
});
});
return {protected:held,autoshowState:autoshow,openSettings:openSettings};
}());

/* OC_USB_OFFER_V1: USB entry observes Mazda's existing connection callback.
* This bootstrap never inspects or changes the installed Settings client. */
(function(){
var token=attr("token"),f=window.framework;
if(!f||!TOK.test(token)||window.__ocUSBReceiver)return;
window.__ocUSBReceiver=true;
var generation=0,until=0,retry=500,timer,abort,bound,last,loading;
function stop(){clearTimeout(timer);if(abort){var old=abort;abort=null;old();}}
function start(wait){
stop();generation++;retry=500;until=wait?Date.now()+65000:0;read(generation);
}
function launch(media){
if(media.token===last)return false;
last=media.token;
var L="oc-maintenance-loader",rm=function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);};
rm(loading);rm(document.getElementById(L));
var node,done=false;
var deadline=setTimeout(function(){done=true;rm(node);},65000);
utility.loadScript("file:///tmp/open-connect/sessions/"+media.session+"/loader.js",
{id:L,ocToken:media.token,ocPort:15557},function(){
clearTimeout(deadline);
if(!done&&loading===node&&node===document.getElementById(L)&&
typeof window.OpenConnectUSBStart==="function")OpenConnectUSBStart(node);
else rm(node);
});
node=document.getElementById(L);loading=node;return true;
}
function read(intent){
var left=until?until-Date.now():3000;if(left<=0)return;
var cancel;
cancel=abort=ctrl(token+"|-|status|media|-|-",function(answer){
if(intent!==generation||abort!==cancel)return;
abort=null;
var media=answer&&answer.ok===true&&answer.media;
if(media&&typeof media.session==="string"&&typeof media.token==="string"&&
/^session-[a-zA-Z0-9]{6}$/.test(media.session)&&TOK.test(media.token)){
if(launch(media)){until=0;return;}
}
if(Date.now()<until){
timer=setTimeout(function(){read(intent);},Math.min(retry,until-Date.now()));
retry=Math.min(retry*2,2000);
}
},Math.min(3000,left));
}
function bind(){
var app=f.getAppInstance("usbaudio"),table=app&&app._messageTable;
if(!table||app===bound||typeof table.TimedSbn_ConnectionStatus!=="function")return;
bound=app;var original=table.TimedSbn_ConnectionStatus;
table.TimedSbn_ConnectionStatus=function(message){
var result=original.apply(this,arguments),p=message&&message.params&&message.params.payload;
if(p&&p.status==="Connected"&&p.type==="UMASS"&&/^[AB]$/.test(p.usb))start(true);
return result;
};
var devices=app._connectedDevs;
if(devices&&[devices.A,devices.B].some(function(d){return d&&d.deviceId&&d.type==="UMASS";}))start(true);
}
var initialize=f._initApp;
f._initApp=function(id){var result=initialize.apply(this,arguments);if(id==="usbaudio")bind();return result;};
bind();if(!generation)start(false);
}());

(function(a){
if(!a||a.loaded&1){return;}
var f=framework;
a.voice=function(s,c){return c&&(c._vuiHelpDialog||c._vuiExamplesDialog)||VUI.test(s);};
var gesture,confirmed;
function button(){
var h=f._currTmpltInstance;
return h&&h.contextInfo&&h.contextInfo.uiaId==="system"&&h.contextInfo.ctxtId==="Disclaimer"&&
h.dialog3Ctrl&&h.dialog3Ctrl.buttonCtrl_0;
}
function releaseAgree(){
setTimeout(function(){
a.holding=false;gesture=null;if(!confirmed){a.user("cancelAgree");}else{a.pump();}
},0);
}
a.agree=function(event){
var b=button(),type=typeof event==="string"?event:event.type;
if(!b||!b._isEnabled){a.holding=false;gesture=null;return false;}
if(type==="mousedown"&&b.divElt&&b.divElt.contains(event.target)||type==="selectStart"&&b._hasFocus){
gesture=b;confirmed=false;a.holding=true;return true;
}
if(type==="keydown"&&event.keyCode===13&&b._hasFocus){
gesture=b;confirmed=false;a.holding=true;releaseAgree();return true;
}
if(gesture===b&&(type==="mouseup"||type==="select")){
releaseAgree();return true;
}
return false;
};
function bind(id){
if(id!=="system"){return;}
var inst=f.getAppInstance(id),disc=inst&&inst._contextTable&&inst._contextTable.Disclaimer;
var props=disc&&disc.controlProperties&&disc.controlProperties.Dialog3Ctrl;
if(!props){return;}
function agree(control,action){
if(action==="Global.Yes"&&f._currTmpltInstance&&f._currTmpltInstance.dialog3Ctrl===control&&gesture===button()){confirmed=true;}
}
a.wrap(props,"defaultSelectCallback",agree);
var h=f._currTmpltInstance,live=button()&&h.dialog3Ctrl.properties;
if(live&&live!==props)a.wrap(live,"defaultSelectCallback",agree);
}
a.wrap(f,"_initApp",null,bind);
if(f.getAppInstance("system")){bind("system");}
a.loaded|=1;a.pump();
}(window.ocCarPlay));

/* Independent boot completion entry. */
(function(){
if(attr("notice")==="installed"){
var token=attr("token"),version=attr("version"),bootId=attr("token","data-boot");
if(!TOK.test(token)||!VER.test(version)||!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(bootId))return;
var state={},node,stopped=false;
window.__ocCompletionLoading=state;
window.__ocCompletionGeneration=state;
var finish=function(){
stopped=true;clearTimeout(timer);
if(window.__ocCompletionLoading===state)delete window.__ocCompletionLoading;
if(node&&node.parentNode)node.parentNode.removeChild(node);
};
var timer=setTimeout(function(){
if(window.__ocCompletionGeneration===state)delete window.__ocCompletionGeneration;
finish();if(window.ocCarPlay){ocCarPlay.cancel();ocCarPlay.pump();}
},35000);
utility.loadScript("file:///tmp/open-connect/feature/maintenance.js",{id:"oc-completion"},function(){
if(!stopped&&window.__ocCompletionLoading===state&&typeof window.OpenConnectMaintenanceStart==="function"){
OpenConnectMaintenanceStart({token:token,port:15555,role:"completion",boot:{notice:"installed",version:version,
id:bootId},current:function(){return window.__ocCompletionGeneration===state;}});
}
finish();
});
node=document.getElementById("oc-completion");
}
}());

return api;
}());
