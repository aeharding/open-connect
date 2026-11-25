/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnect=(function(prev){
"use strict";
if(prev&&prev.protected&&prev.protected())return prev;
var entry=document.getElementById("oc-usb-loader"),meta=document.querySelector('meta[name="open-connect-token"]');
var vm=document.querySelector('meta[name="open-connect-version"]'),nm=document.querySelector('meta[name="open-connect-notice"]');
var versionRE=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
var boot=meta&&vm&&nm&&{token:meta.getAttribute("content"),version:vm.getAttribute("content"),notice:nm.getAttribute("content")};
if(!boot||!/^[a-f0-9]{32}$/.test(boot.token)||!versionRE.test(boot.version)||
 !/^(?:-|installed|removed|undone|restart)$/.test(boot.notice)){boot=null;}
var base=entry&&entry.src?entry.src.slice(0,entry.src.lastIndexOf("/")+1):"file:///tmp/open-connect/feature/";
var port=entry&&entry.ocPort===35555?35555:15555;
var dead=false,begun=false,token=entry&&entry.ocToken,s=null,known=false,busy=false,saving=false;
var timer,expiry,dialog,view,detach,app,ui,menus,job,marker,pending=false,feedback=false;
var nodes=[],queued=null,ready=false,usb=false,epoch=0,shown=false,readOnce=false,refresh=null,acking=false;
var due=0,proved=false,proof=boot&&boot.notice==="installed";
var attempt=entry&&window.__ocUSBLoading;
function loaded(){if(attempt&&attempt.done)attempt.done();attempt=null;}
function held(){return isHeld()||!!refresh||!!(menus&&menus.blocked());}
function receive(a){
 known=!!valid(a);
 if(known){s=a;store.version=a.installedVersion===undefined?a.version:
 (a.installedVersion==="-"?undefined:a.installedVersion);}
}
function autoshow(){
 var cp=window.ocCarPlay;
 if(proof&&!shown&&!proved){
 if(window.framework&&framework._browserShown&&!due){due=Date.now()+35000;}
 if(due&&Date.now()>=due){proved=true;if(cp){cp.cancel();}}
}
 if(isHeld()||busy||usb||queued||dialog||view||s&&(s.pending||s.carplayAutoshow===0)||!shown&&complete())return 2;
 return!ready||s&&!known||proof&&!shown&&!proved?1:0;
}
function valid(s){return menus&&menus.validStatus(s);}
function advance(){refresh=null;epoch++;}
function values(){return known&&s.installed&&!s.pending&&!s.conflict?s:null;}
function isHeld(){return!!job||pending||feedback||acking;}
function claim(){
 if(dead||feedback||acking||OpenConnect!==client||job&&(!saving||job.phase==="unresolved"))return false;
 if(window.__ocUSBLoading&&window.__ocUSBLoading!==marker){
 if(window.__ocUSBLoading.owner!==client)return false;
 window.__ocUSBLoading.cancel();
}
 if(!marker){marker={token:token,cancel:function(){cancelUSB(token);}};}
 window.__ocUSBLoading=marker;
 return true;
}
function release(){
 if(!isHeld()&&window.__ocUSBLoading===marker){delete window.__ocUSBLoading;}
}
function post(op,args,done,ms,intent){
 if(dead)return;
 intent=intent===undefined?epoch:intent;
 var xhr=new XMLHttpRequest(),answered=false;
 var deadline=setTimeout(function(){finish(null);xhr.abort();},ms||185000);
 function finish(a){
 if(answered)return;
 answered=true;clearTimeout(deadline);
 if(dead||intent!==epoch)return;
 if(op!=="dismiss")receive(a);
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
function read(done,until,attempts,intent,fast){
 intent=intent===undefined?epoch:intent;
 if(intent!==epoch||dead)return;
 var left=until?until-Date.now():185000;
 if(left<=0){done(null);return;}
 var end=until||Date.now()+left;
 post("status",fast?["settings","-","-"]:null,function(a,code){
 if(fast&&code===400){read(done,end,attempts,intent,false);return;}
 if((a&&a.error==="busy"||(!a&&until))&&(until||(attempts||0)<8)){
  setTimeout(function(){read(done,until,(attempts||0)+1,intent,fast);},
   until?Math.min(500,Math.max(0,until-Date.now())):500);
 }else{done(a);}
 },left,intent);
}
function closeUI(){var close=dialog;dialog=null;if(close){close();}}
function endView(){var old=view;view=null;if(old){old.close();}}
function message(title,text,hold){
 if(hold)feedback=true;
 queued=function(){
 return ui.message(framework,title,text,{button1:{label:"OK",appData:"done"}},function(action){
  dialog=null;if(hold){if(action==="done"){feedback=false;release();}else message(title,text,hold);}
});
};
}
function dismiss(done){
 if(acking)return;
 if(!claim()){shown=false;return;}
 acking=true;
 var intent=epoch,until=Date.now()+12000,revision=s.revision;
 function finish(ok){
 acking=false;
 if(ok)s.notice="-";
 else{shown=false;if(!complete())message("Unable to confirm","Open Mazda Settings again.",true);}
 release();
 if(ok&&done)done();
}
 function send(){
 if(dead||intent!==epoch)return;
 var left=until-Date.now()-6000;
 if(left<=0){finish(false);return;}
 post("dismiss",null,function(a){
  if(a&&a.ok===true){finish(true);}
  else if(a&&a.error==="busy"){setTimeout(send,Math.min(500,until-Date.now()));}
  else{read(function(s){known=!!valid(s);finish(!!(s&&values()&&s.notice==="-"&&s.revision===revision));},until,0,intent);}
 },left,intent);
}
 send();
}
function paint(){
 var action=job.phase==="restart"||job.op==="restart"?"Restarting Mazda Connect":job.phase==="checking"?
 "Checking Open Connect":job.action;
 var warning=job.origin==="usb"?"Do not remove the USB drive\nor turn off the car.":"Do not turn off the car.";
 if(view&&!view.update(action,warning)){view=null;}
 if(!view){view=ui.progress(framework,action,warning,function(){view=null;});}
 return!!view;
}
function end(actual){
 var reply=job.reply;
 job=null;busy=saving=false;endView();release();
 if(reply){reply(actual);}
}
function refuse(lost){
 if(lost){known=false;}
 var reply=job.reply,origin=job.origin;
 endView();
 if(lost){job.phase="unresolved";job.reply=null;}
 else{job=null;busy=saving=false;release();}
 if(reply){reply(null,true);}
 message(lost?"Unable to confirm the change":"Unable to finish",(lost?
 "Restart Mazda Connect before making more changes.":
 "Check your settings before trying again.")+
 (lost&&origin==="usb"?"\nKeep the USB drive connected until restart.":""));
}
function budget(){if(!job.until){job.until=Date.now()+12000;}return job.until;}
function restart(){
 if(job.restartSent)return;
 job.restartSent=true;job.phase="restart";paint();
 var current=job,until=budget();
 post("restart",null,function(a){
 if(!valid(a)){reconcile(a);}
 },Math.max(1,until-Date.now()));
 setTimeout(function(){if(job===current&&job.phase!=="unresolved"){refuse(true);}},Math.max(0,until-Date.now()));
}
function changed(a){
 if(!valid(a)||a.pending||a.conflict)return false;
 var old=job.before;
 if(job.op==="uninstall")return!a.installed&&!a.retained&&a.revision==="-";
 if(job.op==="install"){
 return a.installed&&a.installedVersion===job.target&&a.notice==="installed"&&
  a.revision!==old.revision&&(!old.installed||old.installedVersion&&old.installedVersion!=="-"&&old.installedVersion!==job.target);
}
 if(job.op==="set"){
 var key=job.args[0],wanted=Number(job.args[2]),value=a[key==="carplay-autoshow"?"carplayAutoshow":key];
 (a.services||[]).forEach(function(row){if(row.id===key){value=row.saved;}});
 return a.installed&&a.revision!==old.revision&&value===wanted;
}
 return job.op==="import"&&/^[a-f0-9]{64}$/.test(a.key)&&a.key!==old.key&&a.revision!==old.revision;
}
function reconcile(a){
 job.phase="checking";if(!saving){paint();}
 read(function(fresh){
 if(a&&a.ok===false){refuse(!valid(fresh)||fresh.pending);}
 else if(a===null&&changed(fresh)){
  if(saving){end(values());}else if(!job.restartSent){restart();}
 }else{refuse(true);}
 },budget());
}
function drive(){
 if(!job||job.phase!=="waiting")return;
 if(job.op!=="recover"&&(s.revision!==job.before.revision||s.version!==job.target)){end(null);return;}
 if(!saving&&!paint()&&job.op!=="recover")return;
 if(job.op==="restart"){job.sent=true;restart();return;}
 job.sent=true;job.phase="writing";
 post(job.op,job.args,function(a){
 if(!valid(a)){reconcile(a);return;}
 if(saving){end(values());}
 else if(job.op==="install"||job.op==="uninstall"||a.restart){restart();}
 else{end(null);}
});
}
function run(op,args,origin,reply,leave){
 if(busy||!s||!claim()){if(reply){reply(null);}return false;}
 busy=true;saving=!!reply;advance();
 job={op:op,args:args,origin:origin,before:s,target:s.version,
 reply:reply,phase:"waiting",sent:false,restartSent:false,
 action:op==="uninstall"?"Removing Open Connect":op==="recover"?"Applying changes":
  op==="install"?(s.installed&&s.installedVersion&&s.installedVersion!=="-"?
   (s.installedVersion===s.version?"Reinstalling":"Updating"):"Installing")+" Open Connect":"Applying changes"};
 queued=null;closeUI();if(leave)leave();drive();return true;
}
var store={read:values,pending:function(value){
 if(value&&!claim())return false;
 pending=value;release();return true;
},refresh:function(reply){
 if(busy||pending){reply(saving&&!!values());return;}
 if(refresh){refresh.push(reply);return;}
 if(!acking)advance();var waits=refresh=[reply],intent=epoch;
 function finish(a){
 if(dead||intent!==epoch)return;
 receive(a);refresh=null;
 waits.forEach(function(fn){if(intent===epoch)fn(!!values());});
}
 function fetch(until){read(finish,until||(boot&&!entry?Date.now()+12000:null),0,intent,true);}
 var usbLoad=window.__ocUSBLoading;
 if(usbLoad&&usbLoad.owner===client&&usbLoad.wait){
 usbLoad.wait.push(function(a){if(valid(a))finish(a);else fetch(usbLoad.until);});return;
}
 fetch();
},write:function(key,from,to,reply){run("set",[key,String(from),String(to)],"settings",reply);},
importKey:function(reply){run("import",null,"settings",reply);},
uninstall:function(leave){return run("uninstall",null,"settings",null,leave);},
busy:function(){return busy||pending;},
restart:function(leave){return values()&&s.restart&&!pending&&run("restart",null,"settings",null,leave);},
opened:function(){if(complete()){shown=true;if(queued&&queued.complete){queued=null;}}}};
function choose(){
 usb=false;
 var revision=s.revision,target=s.version;
 queued=function(){
 return ui.choose(framework,s.installed,function(action){
  dialog=null;
  if(s.revision!==revision||s.version!==target)return;
  if(action==="install"||action==="uninstall"){run(action,null,"usb");}
  else if(action==="cancel"){dismiss();}
 },s.version,s.retained,s.installedVersion);
};
}
function complete(){
 return known&&boot&&boot.token===token&&boot.notice==="installed"&&valid(s)&&s.installed&&
 !s.pending&&!s.conflict&&!s.restart&&s.notice==="installed"&&
 s.completionReady===true&&s.installedVersion===boot.version;
}
function bind(){
 if(s?s.installed:boot){
 var current=framework.getAppInstance("syssettings");
 if(current&&current!==app){
  if(detach){detach();}
  app=current;detach=menus.attach(framework,app,store);
}
}
}
function tick(){
 autoshow();
 if(dead||!window.framework||!framework._browserShown)return;
 bind();
 if(job){
 if(job.phase==="waiting"){drive();}
 else if(!saving&&job.phase!=="unresolved"){paint();}
 }else if(!busy&&s&&s.pending){run("recover",null,entry?"usb":"settings");}
 else if(!shown&&!readOnce&&proof&&!s){
 readOnce=true;
 read(function(a){
  if(!valid(a)||!complete()){proved=true;}
  if(window.ocCarPlay){if(!valid(a)){ocCarPlay.cancel();}ocCarPlay.pump();}
 },due,0,epoch,true);
}
 if(!job&&complete()&&!shown&&!queued&&!dialog){
 queued=function(){
  if(!complete()){queued=null;return false;}
  var opened=ui.complete(framework,s.installedVersion,function(action){
   dialog=null;
   if(complete()&&(action==="done"||action==="settings")){
    dismiss(action==="settings"?function(){menus.fromHome(framework,store,function(){});}:null);
}
});
  if(opened){usb=false;}
  return opened;
};
 queued.complete=true;shown=true;
}
 if(usb&&!busy&&s&&!dialog&&!queued){choose();}
 if(queued&&!dialog){
 var opened=queued();
 if(opened){queued=null;dialog=opened;}
}
}
function load(name,next){
 var node=document.createElement("script");
 node.type="text/javascript";node.src=base+name+".js";
 node.onload=function(){if(!dead){next();}};
 nodes.push(node);
 document.querySelector("head").appendChild(node);
}
function start(value,fromUSB){
 if(begun||dead||!/^[a-f0-9]{32}$/.test(value)){return;}
 begun=true;token=value;usb=fromUSB;
 if(prev&&prev.protected&&prev.protected()){abandon();return;}
 clearTimeout(expiry);expiry=setTimeout(abandon,65000);
 if(attempt&&attempt.done)attempt.wait=[];
 load("dialog",function(){
 ui=OpenConnectInstaller;
 load("settings",function(){
  menus=OpenConnectSettings;
  function accept(a){
   if(fromUSB&&(attempt&&attempt.valid?!attempt.valid():OpenConnect!==client)){abandon();return;}
   var swap=prev;if(attempt&&attempt.resolve)attempt.resolve(a);
   clearTimeout(expiry);
   if(prev&&prev.protected&&prev.protected()){abandon();return;}
   if(!valid(a)&&!(boot&&!fromUSB)){
    if(prev){abandon();return;}
    message("Unable to finish","Open Connect could not be reached. Check the connection before trying again.");
   }else{
    if(prev&&prev.dispose&&prev.dispose(a&&a.installed)===false){abandon();return;}
    OpenConnect=client;prev=null;ready=true;
    if(window.ocCarPlay){ocCarPlay.pump();}
}
   if(swap)bind();timer=setInterval(tick,500);
   loaded();
}
  if(!fromUSB&&boot){store.version=boot.version;accept(null);}
  else{read(accept);}
});
});
}
function cancelUSB(value){
 if(value!==token)return;
 var node=document.getElementById("oc-usb-loader");
 if(node&&node.ocToken===token&&node.parentNode){node.parentNode.removeChild(node);}
 usb=false;if(held())return;
 advance();
 if(!ready){abandon();return;}
 queued=null;closeUI();
 release();
}
function reopenUSB(value){
 if(dead||!ready||value!==token)return false;
 if(held())return true;
 advance();usb=false;queued=null;closeUI();
 read(function(a){
 if(!valid(a)){message("Unable to finish","Open Connect could not be reached.");return;}
 shown=false;usb=true;
});
 return true;
}
function abandon(){
 if(ready||dead)return;
 dispose();if(OpenConnect===client){OpenConnect=prev;}
 loaded();
}
function dispose(transfer){
 if(held())return false;
 dead=true;advance();clearTimeout(expiry);clearInterval(timer);
 queued=null;closeUI();endView();
 if(detach){detach(transfer);}
 nodes.forEach(function(n){if(n.parentNode)n.parentNode.removeChild(n);});
 release();return true;
}
var client={start:start,reopenUSB:reopenUSB,cancelUSB:cancelUSB,dispose:dispose,protected:held,
 autoshowState:autoshow};
if(entry){
 expiry=setTimeout(abandon,65000);
 if(attempt&&attempt.done){attempt.client=client;return prev||client;}
}
if(boot&&!entry){start(boot.token,false);}
return client;
}(OpenConnect));

(function(a){
if(!a||a.loaded&1){return;}
var f=framework;
a.voice=function(s,c){return c&&(c._vuiHelpDialog||c._vuiExamplesDialog)||/^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/.test(s);};
var gesture,confirmed;
function button(){
 var h=f._currTmpltInstance;
 return h&&h.contextInfo.uiaId==="system"&&h.contextInfo.ctxtId==="Disclaimer"&&
 h.dialog3Ctrl&&h.dialog3Ctrl.buttonCtrl_0;
}
a.agree=function(event){
 var b=button(),type=typeof event==="string"?event:event.type;
 if(!b||!b._isEnabled){a.holding=false;gesture=null;return false;}
 if(type==="mousedown"&&b.divElt.contains(event.target)||type==="selectStart"&&b._hasFocus||
  type==="keydown"&&event.keyCode===13&&b._hasFocus){
 gesture=b;confirmed=false;a.holding=true;return true;
}
 if(gesture===b&&(type==="mouseup"||type==="select")){
 setTimeout(function(){
  a.holding=false;gesture=null;if(!confirmed){a.user("cancelAgree");}else{a.pump();}
 },0);
 return true;
}
 return false;
};
function bind(id){
 if(id!=="system"){return;}
 var props=f.getAppInstance(id)._contextTable.Disclaimer.controlProperties.Dialog3Ctrl;
 function agree(control,action){
 if(action==="Global.Yes"&&f._currTmpltInstance.dialog3Ctrl===control&&gesture===button()){confirmed=true;}
}
 a.wrap(props,"defaultSelectCallback",agree);
 var h=f._currTmpltInstance,live=button()&&h.dialog3Ctrl.properties;
 if(live&&live!==props)a.wrap(live,"defaultSelectCallback",agree);
}
a.wrap(f,"_initApp",null,bind);
if(f.getAppInstance("system")){bind("system");}
a.loaded|=1;a.pump();
}(window.ocCarPlay));
