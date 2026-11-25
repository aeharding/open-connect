/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Installed Settings: this boot's code, view and endpoint never change on USB. */
var OpenConnect=(function(){
"use strict";
if(window.OpenConnect)return window.OpenConnect;
var meta=document.querySelector('meta[name="open-connect-token"]');
var vm=document.querySelector('meta[name="open-connect-version"]');
var token=meta&&meta.getAttribute("content"),version=vm&&vm.getAttribute("content");
if(!/^[a-f0-9]{32}$/.test(token)||!/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/.test(version))return null;
var boot=true,entry=null,base="file:///tmp/open-connect/feature/",port=15555;
var dead=false,s=null,known=false,busy=false,saving=false,pending=false,feedback=false,epoch=0;
var timer,dialog,view,app,detach,ui,menus,job,queued=null,refresh=null;
function valid(a){return menus&&menus.validStatus(a);}
function receive(a){known=!!valid(a);if(known)s=a;}
function advance(){refresh=null;epoch++;}
function values(){return known&&s.installed&&!s.pending&&!s.conflict?s:null;}
function held(){return!!job||pending||feedback||!!refresh||!!(menus&&menus.blocked());}
function claim(){return !feedback&&!(job&&(!saving||job.phase==="unresolved"))&&ui.claim(framework);}
function release(){if(!job&&!pending&&!feedback&&ui)ui.release(framework);}
function autoshow(){return job||pending||feedback||dialog||view?2:!menus||s&&!known?1:0;}
function post(op,args,done,ms,intent){
 if(dead)return;
 intent=intent===undefined?epoch:intent;
 var xhr=new XMLHttpRequest(),answered=false;
 var deadline=setTimeout(function(){finish(null);xhr.abort();},ms||185000);
 function finish(a){
 if(answered)return;
 answered=true;clearTimeout(deadline);
 if(dead||intent!==epoch)return;
 receive(a);
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
};wake();
}
function paint(){
 var action=job.phase==="restart"||job.op==="restart"?"Restarting Mazda Connect":job.phase==="checking"?
 "Checking Open Connect":job.action;
 var warning="Do not turn off the car.";
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
 "");
}
function budget(){if(!job.until){job.until=Date.now()+12000;}return job.until;}
function restart(){
 if(job.restartSent)return;
 job.phase="restart";if(!paint())return;
 job.restartSent=true;
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
 if(s.revision!==job.before.revision||s.version!==job.target){end(null);return;}
 if(!saving&&!paint())return;
 if(job.op==="restart"){job.sent=true;restart();return;}
 job.sent=true;job.phase="writing";
 post(job.op,job.args,function(a){
 if(!valid(a)){reconcile(a);return;}
 if(saving){end(values());}
 else if(job.op==="uninstall"||a.restart){restart();}
 else{end(null);}
});
}
function run(op,args,origin,reply,leave){
 if(busy||!s||!claim()){if(reply){reply(null);}return false;}
 busy=true;saving=!!reply;advance();
 job={op:op,args:args,origin:origin,before:s,target:s.version,
 reply:reply,phase:"waiting",sent:false,restartSent:false,
 action:op==="uninstall"?"Removing Open Connect":"Applying changes"};
 queued=null;closeUI();if(leave)leave();drive();wake();return true;
}
var store={version:version,read:values,
pending:function(value){
 if(value&&!claim())return false;
 pending=value;release();return true;
},
refresh:function(reply){
 if(busy||pending){reply(saving&&!!values());return;}
 if(refresh){refresh.push(reply);return;}
 advance();var waits=refresh=[reply],intent=epoch;
 read(function(a){
  if(intent!==epoch)return;
  receive(a);refresh=null;waits.forEach(function(fn){if(intent===epoch)fn(!!values());});
 },Date.now()+12000,0,intent,true);
},
unavailable:function(){
 if(dialog||queued)return;
 dialog=ui.message(framework,"Settings unavailable","Open Connect could not be reached. Try again.",
  {button1:{label:"OK",appData:"done"}},function(){dialog=null;});
},
write:function(key,from,to,reply){run("set",[key,String(from),String(to)],"settings",reply);},importKey:function(reply){run("import",null,"settings",reply);},uninstall:function(leave){return run("uninstall",null,"settings",null,leave);},busy:function(){return busy||pending;},restart:function(leave){return values()&&s.restart&&!pending&&run("restart",null,"settings",null,leave);}};
function openSettings(){
 if(!menus||held()||framework.getCurrentApp()!=="system"||framework.getCurrCtxtId()!=="HomeScreen")return false;
 function open(ok){
  if(framework.getCurrentApp()!=="system"||framework.getCurrCtxtId()!=="HomeScreen")return;
  if(ok)menus.fromHome(framework,store,function(){});else store.unavailable();
 }
 if(values())open(true);else store.refresh(open);
 return true;
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
 if(queued||job&&job.phase!=="unresolved")timer=setTimeout(wake,250);
}
function load(name,next){
 var node=document.createElement("script");
 node.type="text/javascript";node.src=base+name+".js";
 node.onload=function(){if(!dead){next();}};
 document.querySelector("head").appendChild(node);
}
var client={protected:held,autoshowState:autoshow,openSettings:openSettings};
load("dialog",function(){
 ui=OpenConnectInstaller;
 load("settings",function(){
  menus=OpenConnectSettings;
  var initialize=framework._initApp;
  if(initialize)framework._initApp=function(id){var result=initialize.apply(this,arguments);if(id==="syssettings")bind();return result;};
  bind();if(window.ocCarPlay)ocCarPlay.pump();
 });
});
return client;
}());


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

/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Boot-page completion entry, independent of the installed Settings closure. */
(function(){
"use strict";
var notice=document.querySelector('meta[name="open-connect-notice"]');
if(notice&&notice.getAttribute("content")==="installed"){
 var token=document.querySelector('meta[name="open-connect-token"]').getAttribute("content");
 utility.loadScript("file:///tmp/open-connect/feature/maintenance.js",{id:"oc-completion",ocToken:token,ocPort:15555},function(){});
}
}());
