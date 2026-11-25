/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnect=(function(prev){
"use strict";
if(prev&&prev.protected&&prev.protected()){return prev;}
var entry=document.getElementById("oc-usb-loader"),meta=document.querySelector('meta[name="open-connect-token"]');
var vm=document.querySelector('meta[name="open-connect-version"]'),nm=document.querySelector('meta[name="open-connect-notice"]');
var versionRE=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
var boot=meta&&vm&&nm&&{token:meta.getAttribute("content"),version:vm.getAttribute("content"),notice:nm.getAttribute("content")};
if(!boot||!/^[a-f0-9]{32}$/.test(boot.token)||!versionRE.test(boot.version)||
  !/^(?:-|installed|removed|undone|restart)$/.test(boot.notice)){boot=null;}
var base=entry&&entry.src?entry.src.slice(0,entry.src.lastIndexOf("/")+1):"file:///tmp/open-connect/feature/";
var port=entry&&entry.ocPort===35555?35555:15555;
var stopped=false,started=false,token=entry&&entry.ocToken,state=null,known=false,busy=false,saving=false;
var timer,loading,dialog,view,detach,app,ui,menus,job,marker,pending=false,feedback=false;
var nodes=[],queued=null,ready=false,usb=false,epoch=0,shown=false,proofRead=false,refresh=null,dismissing=false;
var proofEnd=0,proved=false,proofNeeded=boot&&boot.notice==="installed";
function autoshowState(){
 var cp=window.ocCarPlay;
 if(proofNeeded&&!shown&&!proved){
  if(window.framework&&framework._browserShown&&!proofEnd){proofEnd=Date.now()+35000;}
  if(proofEnd&&Date.now()>=proofEnd){proved=true;if(cp){cp.cancel();}}
 }
 if(isHeld()||busy||usb||queued||dialog||view||state&&(state.pending||state.carplayAutoshow===0)||!shown&&completion()){return 2;}
 return!ready||state&&!known||proofNeeded&&!shown&&!proved?1:0;
}
function valid(s){return menus&&menus.validStatus(s);}
function advance(){refresh=null;epoch++;}
function values(){return known&&state.installed&&!state.pending&&!state.conflict?state:null;}
function isHeld(){return!!job||pending||feedback||dismissing;}
function claim(){
 if(stopped||feedback||dismissing||window.OpenConnect!==client||job&&(!saving||job.phase==="unresolved")){return false;}
 if(window.__ocUSBLoading&&window.__ocUSBLoading!==marker){return false;}
 if(!marker){marker={token:token,cancel:function(){cancelUSB(token);}};}
 window.__ocUSBLoading=marker;
 return true;
}
function release(){
 if(!isHeld()&&window.__ocUSBLoading===marker){delete window.__ocUSBLoading;}
}
function request(op,args,done,ms,intent){
 if(stopped){return;}
 intent=intent===undefined?epoch:intent;
 var xhr=new XMLHttpRequest(),answered=false;
 var deadline=setTimeout(function(){finish(null);xhr.abort();},ms||185000);
 function finish(answer){
  if(answered){return;}
  answered=true;clearTimeout(deadline);
  if(stopped||intent!==epoch){return;}
  if(op!=="dismiss"){known=!!valid(answer);}
  if(op!=="dismiss"&&known){
   state=answer;
   store.version=answer.installedVersion===undefined?answer.version:
    (answer.installedVersion==="-"?undefined:answer.installedVersion);
  }
  done(answer,xhr.status);
 }
 xhr.onreadystatechange=function(){
  if(xhr.readyState!==4){return;}
  var answer=null;
  try{if(xhr.status===200){answer=JSON.parse(xhr.responseText);}}catch(ignore){}
  finish(answer);
 };
 try{
  xhr.open("POST","http://127.0.0.1:"+port+"/control",true);
  xhr.setRequestHeader("Content-Type","text/plain");
  xhr.send([token,op==="status"||!state?"-":state.revision,op].concat(args||["-","-","-"]).join("|"));
 }catch(error){finish(null);}
}
function readStatus(done,until,attempts,intent,fast){
 intent=intent===undefined?epoch:intent;
 if(intent!==epoch||stopped){return;}
 var left=until?until-Date.now():185000;
 if(left<=0){done(null);return;}
 var end=until||Date.now()+left;
 request("status",fast?["settings","-","-"]:null,function(answer,code){
  if(fast&&code===400){readStatus(done,end,attempts,intent,false);return;}
  if((answer&&answer.error==="busy"||(!answer&&until))&&(until||(attempts||0)<8)){
   setTimeout(function(){readStatus(done,until,(attempts||0)+1,intent,fast);},
    until?Math.min(500,Math.max(0,until-Date.now())):500);
  }else{done(answer);}
 },left,intent);
}
function closeDialog(){var close=dialog;dialog=null;if(close){close();}}
function closeView(){var old=view;view=null;if(old){old.close();}}
function message(title,text,hold){
 if(hold)feedback=true;
 queued=function(){
  return ui.message(framework,title,text,{button1:{label:"OK",appData:"done"}},function(action){
   dialog=null;if(hold){if(action==="done"){feedback=false;release();}else message(title,text,hold);}
  });
 };
}
function dismiss(done){
 if(dismissing)return;
 if(!claim()){shown=false;return;}
 dismissing=true;
 var intent=epoch,until=Date.now()+12000,revision=state.revision;
 function finish(ok){
  dismissing=false;
  if(ok)state.notice="-";
  else{shown=false;if(!completion())message("Unable to confirm","Open Mazda Settings again.",true);}
  release();
  if(ok&&done)done();
 }
 function send(){
  if(stopped||intent!==epoch)return;
  var left=until-Date.now()-6000;
  if(left<=0){finish(false);return;}
  request("dismiss",null,function(a){
   if(a&&a.ok===true){finish(true);}
   else if(a&&a.error==="busy"){setTimeout(send,Math.min(500,until-Date.now()));}
   else{readStatus(function(s){known=!!valid(s);finish(!!(s&&values()&&s.notice==="-"&&s.revision===revision));},until,0,intent);}
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
 var callback=job.reply;
 job=null;busy=saving=false;closeView();release();
 if(callback){callback(actual);}
}
function refuse(uncertain){
 if(uncertain){known=false;}
 var callback=job.reply,origin=job.origin;
 closeView();
 if(uncertain){job.phase="unresolved";job.reply=null;}
 else{job=null;busy=saving=false;release();}
 if(callback){callback(null,true);}
 message(uncertain?"Unable to confirm the change":"Unable to finish",(uncertain?
  "Restart Mazda Connect before making more changes.":
  "Check your settings before trying again.")+
  (uncertain&&origin==="usb"?"\nKeep the USB drive connected until restart.":""));
}
function budget(){if(!job.until){job.until=Date.now()+12000;}return job.until;}
function restart(){
 if(job.restartSent){return;}
 job.restartSent=true;job.phase="restart";paint();
 var current=job,until=budget();
 request("restart",null,function(answer){
  if(!valid(answer)){reconcile(answer);}
 },Math.max(1,until-Date.now()));
 setTimeout(function(){if(job===current&&job.phase!=="unresolved"){refuse(true);}},Math.max(0,until-Date.now()));
}
function changed(answer){
 if(!valid(answer)||answer.pending||answer.conflict){return false;}
 var old=job.before;
 if(job.op==="uninstall"){return!answer.installed&&!answer.retained&&answer.revision==="-";}
 if(job.op==="install"){
  return answer.installed&&answer.installedVersion===job.target&&answer.notice==="installed"&&
   answer.revision!==old.revision&&(!old.installed||old.installedVersion&&old.installedVersion!=="-"&&old.installedVersion!==job.target);
 }
 if(job.op==="set"){
  var key=job.args[0],wanted=Number(job.args[2]),value=answer[key==="carplay-autoshow"?"carplayAutoshow":key];
  (answer.services||[]).forEach(function(row){if(row.id===key){value=row.saved;}});
  return answer.installed&&answer.revision!==old.revision&&value===wanted;
 }
 return job.op==="import"&&/^[a-f0-9]{64}$/.test(answer.key)&&answer.key!==old.key&&answer.revision!==old.revision;
}
function reconcile(answer){
 job.phase="checking";if(!saving){paint();}
 readStatus(function(fresh){
  if(answer&&answer.ok===false){refuse(!valid(fresh)||fresh.pending);}
  else if(answer===null&&changed(fresh)){
   if(saving){end(values());}else if(!job.restartSent){restart();}
  }else{refuse(true);}
 },budget());
}
function drive(){
 if(!job||job.phase!=="waiting"){return;}
 if(job.op!=="recover"&&(state.revision!==job.before.revision||state.version!==job.target)){end(null);return;}
 if(!saving&&!paint()&&job.op!=="recover"){return;}
 if(job.op==="restart"){job.sent=true;restart();return;}
 job.sent=true;job.phase="writing";
 request(job.op,job.args,function(answer){
  if(!valid(answer)){reconcile(answer);return;}
  if(saving){end(values());}
  else if(job.op==="install"||job.op==="uninstall"||answer.restart){restart();}
  else{end(null);}
 });
}
function run(op,args,origin,reply,leave){
 if(busy||!state||!claim()){if(reply){reply(null);}return false;}
 busy=true;saving=!!reply;advance();
 job={op:op,args:args,origin:origin,before:state,target:state.version,
  reply:reply,phase:"waiting",sent:false,restartSent:false,
  action:op==="uninstall"?"Removing Open Connect":op==="recover"?"Applying changes":
   op==="install"?(state.installed&&state.installedVersion&&state.installedVersion!=="-"?
    (state.installedVersion===state.version?"Reinstalling":"Updating"):"Installing")+" Open Connect":"Applying changes"};
 queued=null;closeDialog();if(leave)leave();drive();return true;
}
var store={read:values,pending:function(value){
 if(value&&!claim()){return false;}
 pending=value;release();return true;
},refresh:function(reply){
 if(busy||pending){reply(saving&&!!values());return;}
 if(refresh){refresh.push(reply);return;}
 if(!dismissing)advance();var waits=refresh=[reply],intent=epoch;
 readStatus(function(){
  refresh=null;
  waits.forEach(function(fn){if(intent===epoch)fn(!!values());});
 },boot&&!entry?Date.now()+12000:null,0,intent,true);
},write:function(key,from,to,reply){run("set",[key,String(from),String(to)],"settings",reply);},
importKey:function(reply){run("import",null,"settings",reply);},
uninstall:function(leave){return run("uninstall",null,"settings",null,leave);},
busy:function(){return busy||pending;},
restart:function(leave){return values()&&state.restart&&!pending&&run("restart",null,"settings",null,leave);},
opened:function(){if(completion()){shown=true;if(queued&&queued.complete){queued=null;}}}};
function choose(){
 usb=false;
 var revision=state.revision,target=state.version;
 queued=function(){
  return ui.choose(framework,state.installed,function(action){
   dialog=null;
   if(state.revision!==revision||state.version!==target){return;}
   if(action==="install"||action==="uninstall"){run(action,null,"usb");}
   else if(action==="cancel"){dismiss();}
  },state.version,state.retained,state.installedVersion);
 };
}
function completion(){
 return known&&boot&&boot.token===token&&boot.notice==="installed"&&valid(state)&&state.installed&&
  !state.pending&&!state.conflict&&!state.restart&&state.notice==="installed"&&
  state.completionReady===true&&state.installedVersion===boot.version;
}
function tick(){
 autoshowState();
 if(stopped||!window.framework||!framework._browserShown){return;}
 if(state?state.installed:boot){
  var current=framework.getAppInstance("syssettings");
  if(current&&current!==app){
   if(detach){detach();}
   app=current;detach=menus.attach(framework,app,store);
  }
 }
 if(job){
  if(job.phase==="waiting"){drive();}
  else if(!saving&&job.phase!=="unresolved"){paint();}
 }else if(!busy&&state&&state.pending){run("recover",null,entry?"usb":"settings");}
 else if(!shown&&!proofRead&&proofNeeded&&!state){
  proofRead=true;
  readStatus(function(answer){
   if(!valid(answer)||!completion()){proved=true;}
   if(window.ocCarPlay){if(!valid(answer)){ocCarPlay.cancel();}ocCarPlay.pump();}
  },proofEnd,0,epoch,true);
 }
 if(!job&&completion()&&!shown&&!queued&&!dialog){
  queued=function(){
   if(!completion()){queued=null;return false;}
   var opened=ui.complete(framework,state.installedVersion,function(action){
    dialog=null;
    if(completion()&&(action==="done"||action==="settings")){
     dismiss(action==="settings"?function(){menus.fromHome(framework,store,function(){});}:null);
    }
   });
   if(opened){usb=false;}
   return opened;
  };
  queued.complete=true;shown=true;
 }
 if(usb&&!busy&&state&&!dialog&&!queued){choose();}
 if(queued&&!dialog){
  var opened=queued();
  if(opened){queued=null;dialog=opened;}
 }
}
function load(name,next){
 var node=document.createElement("script");
 node.type="text/javascript";node.src=base+name+".js";
 node.onload=function(){if(!stopped){next();}};
 nodes.push(node);
 document.querySelector("head").appendChild(node);
}
function start(value,fromUSB){
 if(started||stopped||!/^[a-f0-9]{32}$/.test(value)){return;}
 started=true;token=value;usb=fromUSB;
 clearTimeout(loading);loading=setTimeout(abandon,65000);
 load("dialog",function(){
  ui=OpenConnectInstaller;
  load("settings",function(){
   menus=OpenConnectSettings;
   function accept(answer){
    clearTimeout(loading);
    if(prev&&prev.protected&&prev.protected()){abandon();return;}
    if(!valid(answer)&&!(boot&&!fromUSB)){
     if(prev){abandon();return;}
     message("Unable to finish","Open Connect could not be reached. Check the connection before trying again.");
    }else{
     ready=true;
     if(prev&&prev.dispose){prev.dispose();}
     prev=null;
     if(window.ocCarPlay){ocCarPlay.pump();}
    }
    timer=setInterval(tick,500);
   }
   if(!fromUSB&&boot){store.version=boot.version;accept(null);}
   else{readStatus(accept);}
  });
 });
}
function cancelUSB(value){
 if(value!==token)return;
 var node=document.getElementById("oc-usb-loader");
 if(node&&node.ocToken===token&&node.parentNode){node.parentNode.removeChild(node);}
 usb=false;if(isHeld())return;
 advance();
 if(!ready&&prev){abandon();return;}
 queued=null;closeDialog();
 release();
}
function reopenUSB(value){
 if(stopped||!ready||value!==token){return false;}
 if(isHeld()){return true;}
 advance();usb=false;queued=null;closeDialog();
 readStatus(function(answer){
  if(!valid(answer)){message("Unable to finish","Open Connect could not be reached.");return;}
  shown=false;usb=true;
 });
 return true;
}
function abandon(){
 if(ready||stopped){return;}
 dispose();if(window.OpenConnect===client){window.OpenConnect=prev;}
}
function dispose(){
 if(isHeld()){return false;}
 stopped=true;advance();clearTimeout(loading);clearInterval(timer);
 queued=null;closeDialog();closeView();
 if(detach){detach();}
 for(var i=0;i<nodes.length;i++){
  if(nodes[i]&&nodes[i].parentNode){nodes[i].parentNode.removeChild(nodes[i]);}
 }
 release();return true;
}
var client={start:start,reopenUSB:reopenUSB,cancelUSB:cancelUSB,dispose:dispose,protected:isHeld,
 autoshowState:autoshowState};
if(entry){loading=setTimeout(abandon,65000);}
if(boot&&!entry){start(boot.token,false);}
return client;
}(window.OpenConnect));

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
