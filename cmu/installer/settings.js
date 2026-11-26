/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnectSettings=(function(){
"use strict";
var active=false,waiting=null,session=null,dialogs=OpenConnectInstaller;
var entries=[
 {key:"touch",title:"Touchscreen While Driving",choices:["Factory Default","Allow"]},
 {key:"warning",title:"Startup disclaimer",choices:["Show","Skip"]},
 {key:"carplayAutoshow",title:"Show CarPlay on connection",choices:["Factory behavior","Automatically show"]}
];
var own=Object.prototype.hasOwnProperty;
function bit(v){return v===0||v===1;}
function optional(v){return v===undefined||bit(v);}

function validServices(rows){
 if(rows===undefined){return true;}
 if(!Array.isArray(rows)||rows.length<1||rows.length>16){return false;}
 var previous="";
 return rows.every(function(row){
 if(!row||!/^[a-z][a-z0-9-]{0,31}$/.test(row.id)||row.id<=previous||
   /^(touch|warning|base|wireless|uart|ssh|carplay-autoshow)$/.test(row.id)||
   !bit(row.saved)||(row.current!==null&&!bit(row.current))){return false;}
 previous=row.id;
 return["label","enable","disable"].every(function(key){
  return typeof row[key]==="string"&&row[key].length>0&&
   row[key].length<=(key==="label"?64:256)&&!/[\x00-\x1f\x7f]/.test(row[key]);
 });
 });
}
var versionRE=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
function validStatus(s){
 return s&&s.ok===true&&valid(s)&&/^(?:-|[a-f0-9]{32}|[a-f0-9]{64})$/.test(s.revision)&&
 ["installed","retained","conflict","restart","pending"].every(function(key){return typeof s[key]==="boolean";})&&
 (s.wireless===undefined||bit(s.wirelessCurrent))&&
 (s.developer===undefined||(typeof s.developer==="boolean"&&
  bit(s.uart)&&bit(s.ssh)&&
  bit(s.uartCurrent)&&bit(s.sshCurrent)&&
  /^(?:-|[a-f0-9]{64})$/.test(s.key)&&/^(?:-|[a-f0-9:]{47})$/.test(s.fingerprint)))&&
 versionRE.test(s.version)&&(s.installedVersion===undefined||s.installedVersion==="-"||versionRE.test(s.installedVersion));
}
function service(values,key){
 var rows=values&&values.services,i;
 for(i=0;rows&&i<rows.length;i++){if(rows[i].id===key){return rows[i];}}
 return null;
}
function preference(values,key){
 var row=service(values,key);
 return row?row.saved:values[key];
}
function valid(values){
 return values&&validServices(values.services)&&bit(values.touch)&&
 bit(values.warning)&&
 optional(values.pandora)&&
 optional(values.base)&&autoshow(values)&&
 optional(values.wireless)&&
 (values.wirelessFactory===undefined||typeof values.wirelessFactory==="boolean");
}
function autoshow(s){
 return s.carplayAutoshow===undefined||(bit(s.carplayAutoshow)&&
 bit(s.carplayAutoshowCurrent));
}
function toggle(title,on,key){return{text1:title,itemStyle:"styleOnOff",value:on?1:2,hasCaret:false,appData:key};}

// Stock offscreen slide/reparent; MMUI owns context.
function slide(from,to,back,done,reveal){
 var a=from.divElt,b=to.divElt,timer,finished=false;
 var init=back?"Transitions_Init_OffscreenLeft":"Transitions_Init_OffscreenRight";
 var out="Transitions_slideOut"+(back?"Right":"Left")+"TmpltWithStatusLeftBtn_0_400";
 var into="Transitions_slideIn"+(back?"Left":"Right")+"TmpltWithStatusLeftBtn_0_400";
 function finish(event){
 if(finished||event&&event.target!==b){return;}
 finished=true;clearTimeout(timer);
 b.removeEventListener("animationend",finish,false);
 a.classList.remove(out);b.classList.remove(into);b.classList.remove(init);
 if(to.endTransitionTo)to.endTransitionTo();
 done();
 }
 b.addEventListener("animationend",finish,false);
 b.classList.add(init);b.parentNode.appendChild(b);
 if(reveal!==undefined)b.style.display=reveal;
 if(from.startTransitionFrom)from.startTransitionFrom();
 a.classList.add(out);b.classList.add(into);
 timer=setTimeout(finish,900);
 return finish;
}

function replace(obj,key,fn){
 var previous=obj[key],local=own.call(obj,key);
 obj[key]=fn;
 return function(){
 if(obj[key]!==fn){return;}
 if(local){obj[key]=previous;}else{delete obj[key];}
 };
}

function settingsApp(id){
 return /^(sys|veh|audio)settings$/.test(id);
}

function voice(fw){
 var c=fw.common;
 return c._vuiHelpDialog||c._vuiExamplesDialog||
 /^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/.test(c._cachedVuiState);
}
function inTab(fw){
 return settingsApp(fw.getCurrentApp())&&/Tab$/.test(fw.getCurrCtxtId())&&
 fw._frameworkState===fw._FWK_STATE_IDLE&&!voice(fw)&&!dialogs.foreign(fw);
}

function preferences(store){
 function read(){
 try{return store.read();}catch(error){return null;}
 }
 var saved=read();
 if(!valid(saved)||saved.pending||saved.conflict){return null;}
 if(session&&session.owner===store){return session;}
 var wanted={},busy=false,timer=null;
 var prefs={owner:store,failure:null,changed:null};
 function pending(value){return!store.pending||store.pending(value);}
 prefs.values=function(){
 if(!busy&&!Object.keys(wanted).length){
  var current=read();
  if(!valid(current)){return null;}
  saved=current;
 }
 var values={};
 Object.keys(saved).forEach(function(k){values[k]=own.call(wanted,k)?wanted[k]:saved[k];});
 if(saved.services){
  values.services=saved.services.map(function(row){
   return{id:row.id,label:row.label,saved:own.call(wanted,row.id)?wanted[row.id]:row.saved,
    current:row.current,enable:row.enable,disable:row.disable};
  });
 }
 return values;
 };
 function flush(){
 var keys=Object.keys(wanted);
 if(busy){return;}
 if(!keys.length){pending(false);return;}
 var key=keys[0],requested=wanted[key];
 if(preference(saved,key)===requested){
  delete wanted[key];flush();
  if(prefs.changed){prefs.changed(false);}
  return;
 }
 busy=true;
 var answered=false;
 function finish(actual,outcome){
  if(answered){return;}
  answered=true;
  busy=false;
  // Never resend after a lost ack.
  if(outcome==="unresolved"){wanted={};}else if(!valid(actual)){actual=read();}
  if(valid(actual)){saved=actual;}
  var failed=!valid(actual)||(preference(actual,key)!==requested&&wanted[key]===requested);
  if(failed){
   delete wanted[key];
   prefs.failure=outcome||key;
   if(prefs.changed){prefs.changed(true);}
  }else if(wanted[key]===requested){delete wanted[key];}
  flush();
  if(!failed&&prefs.changed){prefs.changed(false);}
 }
 try{store.write(key==="carplayAutoshow"?"carplay-autoshow":key,preference(saved,key),requested,finish);}
 catch(error){finish(null);}
 }
 prefs.pending=function(){return busy||Object.keys(wanted).length>0;};
 prefs.select=function(key,value){
 if(!pending(true)){if(prefs.revert){prefs.revert();}return;}
 prefs.failure=null;
 wanted[key]=value;
 clearTimeout(timer);
 timer=setTimeout(flush,250);
 };
 prefs.importKey=function(done){
 if(prefs.pending()||typeof store.importKey!=="function"||!pending(true)){return;}
 busy=true;
 var answered=false;
 function finish(actual,failed){
  if(answered){return;}
  answered=true;busy=false;
  if(valid(actual)){saved=actual;}
  done(valid(actual)&&!failed?actual:null,failed);
  flush();
 }
 try{store.importKey(finish);}catch(error){finish(null);}
 };
 session=prefs;
 return prefs;
}

function open(fw,store){
 var host=fw._currTmpltInstance;
 if(active||!inTab(fw)||!host||!host.list2Ctrl){return false;}
 var prefs=preferences(store);
 if(!prefs){return false;}
 var page,choice,dismiss=null,moving=null,closed=false,leaving=false,restorers=[];
 var oldDisplay=host.divElt.style.display;
 var tab=fw.getCurrCtxtId();
 function current(){
 return!closed&&!leaving&&fw._currTmpltInstance===host&&inTab(fw)&&fw.getCurrCtxtId()===tab;
 }
 function discard(p){
 if(p){
  p.cleanUp();
  if(p.divElt.parentNode){p.divElt.parentNode.removeChild(p.divElt);}
 }
 }
 function close(){
 if(closed){return;}
 closed=true;
 if(moving){moving();}
 if(dismiss){dismiss();}
 prefs.changed=null;
 prefs.revert=null;
 while(restorers.length){restorers.pop()();}
 discard(page);
 host.divElt.style.display=oldDisplay;
 if(fw.common._openConnectPage===close)delete fw.common._openConnectPage;
 active=false;
 }
 function ask(title,text,label,action,done){
 return dialogs.message(fw,title,text,{button1:{label:"Cancel",appData:"cancel"},
  button2:{label:label,appData:action}},done);
 }
 function render(index,focus,back){
 if(moving){moving();}
 var values=prefs.failure?null:prefs.values();
 if(!values){index="unknown";focus=0;}
 var rows=[],title="Open Connect",i,row;
 function action(text,key,caret,disabled){
  rows.push({text1:text,itemStyle:"style01",hasCaret:!!caret,appData:key,disabled:!!disabled});
 }
 function entry(i){
  var e=entries[i];
  if(values[e.key]!==undefined){rows.push({text1:e.title,
   label1:e.key==="touch"?["Factory Default","Allow"][values.touch]:
    i===2?["Factory","Auto"][values.carplayAutoshow]:e.choices[values[e.key]],
   itemStyle:"style06",labelWidth:i?"normal":"wide",hasCaret:true,appData:i});}
 }
 function integrations(phone){
  if(values.services){
   values.services.forEach(function(s){
    if((s.id==="android-auto")===phone){
     rows.push(toggle(s.label+(s.current===null?" (startup unknown)":
      s.current!==s.saved?" (restart needed)":""),s.saved,s.id));
    }
   });
  }else if(!phone&&values.pandora!==undefined){rows.push(toggle("Pandora",values.pandora,"pandora"));}
 }
 if(index===null){
  entry(0);entry(1);
  if(values.base!==undefined){rows.push(toggle("Startup optimizations",values.base,"base"));}
  if(values.wireless!==undefined||values.carplayAutoshow!==undefined||service(values,"android-auto")){
   action("CarPlay & Android Auto","phone",true);
  }
  if(values.services||values.pandora!==undefined){
   action("Audio sources","sources",true);
  }
  if(values.developer){
   action("Developer options","developer",true);
  }
  action("Apply changes","restart",false,!canRestart());
  action("Uninstall","uninstall",false,typeof store.uninstall!=="function");
  action("About","about");
 }else if(index==="phone"){
  title="CarPlay & Android Auto";
  if(values.wireless!==undefined){
   rows.push({text1:"Wireless CarPlay"+(values.wirelessFactory?" (factory enabled)":""),
    itemStyle:"styleOnOff",value:values.wirelessFactory||values.wireless?1:2,
    disabled:values.wirelessFactory===true,hasCaret:false,appData:"wireless"});
  }
  entry(2);integrations(true);
 }else if(index==="unknown"){
  title=prefs.failure==="unresolved"?"Restart Mazda Connect":"Change could not be confirmed";
  action("Return to Mazda Settings",0);
 }else if(index==="sources"){
  title="Audio sources";integrations(false);
 }else if(index==="developer"){
  title="Developer options";
  rows.push(toggle("UART",values.uart,"uart"));
  row=toggle("SSH",values.ssh,"ssh");row.disabled=values.key==="-";rows.push(row);
  action("Import public key","import",true,prefs.pending()||typeof store.importKey!=="function");
 }else{
  row=entries[index];
  title=row.title;
  for(i=0;i<row.choices.length;i++){
   rows.push({text1:row.choices[i],image1:"radio",checked:i===values[row.key],
    itemStyle:"style03",hasCaret:false,appData:i});
  }
 }
 for(i=0;i<rows.length;i++){if(rows[i].appData===focus){break;}}
 var listProps={dataList:{itemCountKnown:true,itemCount:rows.length,items:rows},
  titleConfiguration:"listTitle",title:{text1:title,titleStyle:"style02"},
  smallItemText:true,focussedItem:i<rows.length?i:0,selectCallback:select};
 if(typeof index==="number"){listProps.checkMinChangeInterval=0;}
 if(typeof index!=="number"){listProps.toggleMinChangeInterval=0;}
 var next=fw.instantiateTemplate("syssettings",host.divElt.parentNode,"List2Tmplt",
  {List2Ctrl:listProps});
 if(!next){return false;}
 var old=page||host,animate=!page||choice!==index;
 page=next;
 choice=index;
 if(animate){
  moving=slide(old,next,back,function(){
   moving=null;
   if(old===host){host.divElt.style.display="none";}else{discard(old);}
  });
 }else{discard(old);}
 next.handleControllerEvent(fw.multicontroller.getMode());
 next.handleControllerEvent("acceptFocusInit");
 return true;
 }
 function canRestart(){
 var values=prefs.values();
 return values&&values.restart===true&&!prefs.pending()&&
  typeof store.restart==="function"&&!(store.busy&&store.busy());
 }
 function maintain(action){
 dismiss=null;
 if(!current())return;
 if(action==="restart"&&canRestart()||action==="uninstall"&&!prefs.pending()){
  if(store[action](close))return;
  dismiss=dialogs.message(fw,"Try again in a moment.","Another action is finishing.",
   {button1:{label:"OK",appData:"done"}},maintain);
 }else prefs.changed(false);
 }
 function select(control,item,params){
 if(!current()||dismiss||!page||control!==page.list2Ctrl){return;}
 if(moving){moving();}
 if(choice===null&&/^(developer|phone|sources)$/.test(item)){render(item,0);return;}
 if(choice==="phone"&&item===2){var v=prefs.values();if(v){render(2,v.carplayAutoshow);}return;}
 if(choice==="phone"&&item==="wireless"){
  if(!params||(params.additionalData!==1&&params.additionalData!==2)){return;}
  var values=prefs.values(),enabled=params.additionalData===1;
  if(!values||values.wirelessFactory===true||values.wireless===undefined||
    values.wireless===(enabled?1:0)){return;}
  dismiss=ask((enabled?"Enable":"Disable")+" Wireless CarPlay?",enabled?"Changes apply after restarting Mazda Connect. Then select Apple CarPlay in Mazda's Wi-Fi settings and pair your iPhone over Bluetooth."+
    (values.base?" Delays Mazda Navigation about 20 s.":""):
    "Restores the original CarPlay behavior after restarting Mazda Connect.",enabled?"Enable":"Disable","apply",function(action){
    dismiss=null;
    if(action==="apply"&&current()){prefs.select("wireless",enabled?1:0);}
    if(current()&&choice==="phone"){render("phone","wireless");}
   });
  return;
 }
 if(choice===null&&item==="base"||choice==="phone"||choice==="sources"){
  if(!params||(params.additionalData!==1&&params.additionalData!==2)){return;}
  var enabled=params.additionalData===1,desired=enabled?1:0;
  var values=prefs.values();
  if(!values){render("unknown",0);return;}
  var row=service(values,item);
  if(item!=="base"&&!row&&!(item==="pandora"&&!values.services)){return;}
  if(preference(values,item)===undefined||preference(values,item)===desired){return;}
  var label=item==="base"?"Startup optimizations":row?row.label:"Pandora";
  var text=item==="base"?(enabled?
   (values.services?"Reduces background logging and unused services. Applies after restart.":
    "Reduces native diagnostic logging. Applies after restart."):
   (values.services?"Restores original logging and startup behavior after restarting Mazda Connect.":
    "Restores original native logging after restarting Mazda Connect.")):
   row?(enabled?row.enable:row.disable):
   "Changes apply after restarting Mazda Connect.";
  if(item==="base"&&enabled&&values.wireless){
   text+=" Wireless CarPlay delays Mazda Navigation about 20 s.";
  }
  var origin=choice;
  dismiss=ask((enabled?"Enable ":"Disable ")+label+"?",text,enabled?"Enable":"Disable","apply",function(action){
    dismiss=null;
    if(action==="apply"&&current()){prefs.select(item,desired);}
    if(current()&&choice===origin){render(origin,item);}
   });
  return;
 }
 if(choice==="developer"){
  if((item==="uart"||item==="ssh")&&params&&
    (params.additionalData===1||params.additionalData===2)){
   var values=prefs.values();
   if(item==="ssh"&&values.key==="-"){return;}
   if(params.additionalData===1&&values[item]===0){
    dismiss=ask(item==="uart"?"Enable UART?":"Enable SSH?",item==="uart"?"Passwordless root access over UART. Changes apply after restart.":
      "Changes apply after restarting Mazda Connect.","Enable","enable",function(action){
      dismiss=null;
      if(action==="enable"&&current()){prefs.select(item,1);}
      if(current()&&choice==="developer"){render("developer",item);}
     });
    return;
   }
   prefs.select(item,params.additionalData===1?1:0);
  }else if(item==="import"&&!prefs.pending()&&typeof store.importKey==="function"){
   dismiss=ask("Import public key?","Put open-connect.pub on the USB drive. RSA and ECDSA public keys are supported. The imported key will be replaced.","Import","import",function(action){
     dismiss=null;
     if(action!=="import"||!current()){return;}
     prefs.importKey(function(actual,outcome){
      if(!current()||choice!=="developer"){return;}
      if(outcome==="unresolved"){prefs.failure=outcome;render("unknown",0);return;}
      render("developer","import");
      dismiss=dialogs.message(fw,actual?"Public key imported":"Key could not be imported",
       actual?"Fingerprint (MD5):\n"+actual.fingerprint.slice(0,23)+"\n"+
        actual.fingerprint.slice(24)+"\nEnable SSH when ready.":
        "Use one USB drive with open-connect.pub: an RSA key of at least 2048 bits or an ECDSA public key. Private keys and Ed25519 are not supported.",
       {button1:{label:"OK",appData:"done"}},function(){dismiss=null;});
     });
    });
  }
  return;
 }
 if(choice===null&&item==="about"){
  dismiss=dialogs.about(fw,store.version,function(){dismiss=null;if(current())prefs.changed(false);});
  return;
 }
 if(choice===null&&item==="restart"){
  if(!canRestart()){return;}
  dismiss=ask("Apply changes?","Restart Mazda Connect to apply your saved changes.","Restart","restart",maintain);
  return;
 }
 if(choice===null&&item==="uninstall"&&typeof store.uninstall==="function"){
  dismiss=dialogs.confirmUninstall(fw,prefs.pending(),maintain);
  return;
 }
 if(typeof item!=="number"||item<0||item>=(choice===null?entries.length:2)){return;}
 if(choice==="unknown"){prefs.failure=null;close();return;}
 if(choice===null){
  var values=prefs.values();
  if(values&&values[entries[item].key]!==undefined){render(item,values[entries[item].key]);}
  return;
 }
 if(choice===2&&item===1&&preference(prefs.values(),"carplayAutoshow")===0){
  dismiss=ask("Automatically show CarPlay?","Opens CarPlay when your phone connects. Applies after restarting Mazda Connect.","Enable","apply",function(action){
   dismiss=null;
   if(current()){if(action==="apply")prefs.select("carplayAutoshow",1);else render(choice,0);}
  });
  return;
 }
 prefs.select(entries[choice].key,item);
 }
 if(!render(null,0)){return false;}
 active=true;
 fw.common._openConnectPage=close;
 if(store.opened){store.opened();}
 if(typeof ocCarPlay!=="undefined"&&ocCarPlay){ocCarPlay.cancel();}
 prefs.revert=function(){if(current()){render(choice,0);}};
 prefs.changed=function(failed){
 if(!failed){
  if(current()&&choice===null&&!dismiss){
   page.list2Ctrl.dataList.items.forEach(function(row,i){
    if(row.appData==="restart"){row.disabled=!canRestart();page.list2Ctrl.updateItems(i,i);}
   });
  }
  if(current()&&choice==="developer"&&!dismiss){
   var values=prefs.values(),ctrl=page.list2Ctrl;
   if(!values){return;}
   ctrl.dataList.items[2].disabled=prefs.pending()||typeof store.importKey!=="function";
   ctrl.updateItems(2,2);
  }
  return;
 }
 if(dismiss){dismiss();}
 if(current()){render("unknown",0);}else{close();}
 };
 var transition=fw.common.getCommonTransitionData;
 restorers.push(replace(fw.common,"getCommonTransitionData",function(){
 close();
 return transition.apply(this,arguments);
 }));
 var input=host.handleControllerEvent;
 restorers.push(replace(host,"handleControllerEvent",function(event){
 if(leaving&&event==="goBack")return;
 if(!current()){close();return input.apply(this,arguments);}
 return page.handleControllerEvent.apply(page,arguments);
 }));
 var send=fw.sendEventToMmui;
 restorers.push(replace(fw,"sendEventToMmui",function(app,event){
 if(leaving||/^(Global.Intent|SelectHome|SelectNavigation)/.test(event)){close();}
 if(current()&&app==="common"&&(event==="Global.GoBack"||event==="Global.MenuUp")){
  if(dismiss){dismiss();}
  else if(choice!==null&&choice!=="unknown"){
   render(choice===2?"phone":null,choice,true);
  }
  else{
   if(choice==="unknown"){prefs.failure=null;}
   if(moving){moving();}
   leaving=true;
   moving=slide(page,host,true,close,oldDisplay);
  }
  return;
 }
 return send.apply(this,arguments);
 }));
 return close;
}

function attach(fw,app,store){
 function template(){return app._currentContextTemplate;}
 var entry=app._contextTable.SystemTab;
 var original=entry.readyFunction;
 var list=null,release=null,closePage=null;
 var id="open-connect-settings";
 function bind(){
 var host=template();
 if(!host||!host.list2Ctrl||host.list2Ctrl===list){return;}
 if(release){release(false);}
 list=host.list2Ctrl;
 var ctrl=list,set=ctrl.setDataList,select=ctrl.properties.selectCallback;
 var undoSelect=replace(ctrl.properties,"selectCallback",function(control,value){
  if(control===ctrl&&value===id){
   var selectedHost=template();
   var show=function(fresh){
    if(list!==ctrl||fw._currTmpltInstance!==selectedHost||
      template()!==selectedHost){return;}
    if(!fresh){if(store.unavailable)store.unavailable();return;}
    var opened=open(fw,store);
    if(opened){closePage=opened;}
   };
   var cached;
   try{cached=store.read();}catch(error){}
   if(valid(cached)&&!cached.pending&&!cached.conflict){show(true);}
   else if(store.refresh){store.refresh(show);}
   return;
  }
  return select.apply(this,arguments);
 });
 function withEntry(data){
  var count=data&&data.itemCount,items=data&&data.items;
  if(!items||!count||items.length<count||items[count-1].appData!=="SelectAbout"||
    items.some(function(r){return r&&r.appData===id;})){
   return set.apply(this,arguments);
  }
  var copy={},key;
  for(key in data){if(own.call(data,key)){copy[key]=data[key];}}
  copy.items=items.slice(0,count);
  copy.items.splice(count-1,0,{text1:"Open Connect",itemStyle:"style01",
   hasCaret:true,appData:id});
  copy.itemCount=count+1;
  return set.call(ctrl,copy);
 }
 var undoSet=replace(ctrl,"setDataList",withEntry);
 release=function(visible){
  if(closePage){closePage();closePage=null;}
  undoSelect();
  undoSet();
  if(!visible){return;}
  var data=ctrl.dataList,rows=data.items.filter(function(r){return r.appData!==id;});
  if(rows.length!==data.itemCount){
   set.call(ctrl,{itemCountKnown:true,itemCount:rows.length,items:rows,
    vuiSupport:data.vuiSupport});
   if(rows.length){ctrl.updateItems(0,rows.length-1);}
  }
 };
 }
 function repaint(){
 if(list&&list.dataList.itemCount){list.updateItems(0,list.dataList.itemCount-1);}
 }
 if(fw.getCurrCtxtId()==="SystemTab"&&fw._currTmpltInstance===template()){
 bind();
 if(list){
  if(!list.dataList.items.some(function(r){return r.appData===id;}))list.setDataList(list.dataList);
  repaint();
 }
 }
 var undoReady=replace(entry,"readyFunction",function(){
 bind();
 var result=original.apply(this,arguments);
 repaint();
 return result;
 });
 return function detach(){
 undoReady();
 if(release){release(template()&&template().list2Ctrl===list);}
 list=release=null;
 };
}
function fromHome(fw,store,result){
 if(active||waiting||fw._frameworkState!==fw._FWK_STATE_IDLE||voice(fw)||
  fw.common._openConnectDialog||dialogs.foreign(fw)||
  fw.getCurrentApp()!=="system"||fw.getCurrCtxtId()!=="HomeScreen"){return false;}
 var attempts=0;
 var timer=setInterval(function(){
 var app=fw.getCurrentApp();
 if(inTab(fw)&&open(fw,store)){
  cancel();
  result(true);
 }else if(++attempts>=40||(app!=="system"&&!settingsApp(app))||
   (app==="system"&&fw.getCurrCtxtId()!=="HomeScreen")||
   (settingsApp(app)&&fw._frameworkState===fw._FWK_STATE_IDLE&&!inTab(fw))){
  cancel();
  result(false);
 }
 },200);
 function cancel(){
 clearInterval(timer);
 if(waiting===cancel){waiting=null;}
 }
 waiting=cancel;
 try{fw.sendEventToMmui("system","SelectSettings");}
 catch(error){cancel();throw error;}
 return cancel;
}

return{open:open,fromHome:fromHome,attach:attach,validStatus:validStatus,
 blocked:function(){return active||waiting||session&&session.pending();}};
}());

(function(a,f){
if(!a||a.loaded&4){return;}
var camera,cameraSeen,displayOff;
function owner(client){return client&&client.autoshowState();}
a.owner=function(){
 if(f.common._openConnectOperation||window.__ocCompletionLoading||window.__ocMaintenanceLoading||
  document.getElementById("oc-maintenance-loader"))return 2;
 return owner(window.OpenConnectCompletion)||owner(window.OpenConnectMaintenance)||
  (window.OpenConnect?owner(window.OpenConnect):1);
};
function context(id,ctx){
 if(id==="backupparking"||/^(IntroAnimation|QuickStartLoop|Disclaimer)$/.test(ctx))return 1;
 if(id==="emnavi"&&ctx==="Active")return 0;
 return id==="system"?(/^(HomeScreen|Entertainment)$/.test(ctx)?0:2):
 /^(fmradio|amradio|usbaudio|btaudio|auxin|satradio|xmaudio|cd|dvd|tv|stitcher|aharadio|pandora|dab)$/.test(id)?0:2;
}
a.check=function(focus,next){
 var gate=a.owner(),h=f._currTmpltInstance,id=f.getCurrentApp(),c=f.common,s=OpenConnectSettings,edge=a.edge();
 if(gate){return gate;}
 if(a.dialogs||s.blocked&&s.blocked()||displayOff){return 2;}
 if(camera||!h||!c||!focus||f._focusStack!==focus||focus[0].id!==id||
  h.contextInfo.uiaId!==id||f._frameworkState!==f._FWK_STATE_IDLE||!f._browserShown){return 1;}
 var ctx=h.contextInfo.ctxtId,app=f.getAppInstance(id);
 if(!app||!app._currentContext||app._currentContext.ctxtId!==ctx||
  next&&edge&&next._cp.seq>Math.max(edge.seq,a.focus||0)&&next._cp.ctx&&
  (next.uiaId!==id||next.contextSeq!==h.contextInfo.contextSeq)){return 1;}
 if(a.voice(c._cachedVuiState,c)){return 2;}
 var kind=context(id,ctx),old=edge&&edge.origin;
 if(edge&&!kind&&old&&context(old[0],old[1])!==1&&
  (old[0]!==id||old[1]!==ctx||!edge.reverse&&old[2]!==h.contextInfo.contextSeq))return 2;
 if(edge&&!kind&&(!old||context(old[0],old[1])===1))edge.origin=a.copy(h.contextInfo);
 if(edge&&edge.reverse){
 if(kind||a.focus<=edge.reverse)return 1;
 edge.origin=a.copy(h.contextInfo);edge.reverse=0;
 }
 return kind;
};
function depart(m,edge){
 if(!edge||!m||m.msgType!=="ctxtChg"||m._cp.seq<=edge.seq||!m._cp.ctx)return false;
 var c=m._cp.ctx;
 if(c[0]==="backupparking"||c[1]==="Idle"||camera)return false;
 var kind=context(c[0],c[1]),old=edge.back||edge.origin;
 if(kind===2)return true;
 if(kind===1)return false;
 kind=!old||context(old[0],old[1])===1;
 var once=(edge.reverse||kind)&&!edge.back;
 if(once)edge.origin=edge.back=c;
 if(kind)return false;
 return old[0]!==c[0]||old[1]!==c[1]||!once&&old[2]!==c[2];
}
a.signal=function(m){
 var id=m.msgId,p=m.params&&m.params.payload;
 var edge=a.edge(),c=m._cp.ctx;
 // Reverse needs applied focus plus observed camera, changed safe context,
 // or explicit withdrawal; cached traffic cannot acknowledge it.
 if(c){
 if(c[0]==="backupparking"){
  if(c[1]==="Idle"){if(!cameraSeen)camera=null;}
  else{
   if(!camera)camera=m._cp;
   if(m._cp.focus)cameraSeen=true;
   if(edge&&m._cp.seq>edge.seq){edge.reverse=camera.seq;edge.back=null;}
  }
 }else{
  if(m._cp.focus){
   if(camera&&(cameraSeen||String(c)!==String(camera.base))){camera=null;cameraSeen=false;}
   displayOff=false;
  }
  if(c[1]==="DisplayOff")displayOff=true;
  if(c[0]==="phone"&&!m._cp.focus&&/^(ActiveCall|IncomingCall|CallWaiting|MultipleCallWaiting|BTMultipleCall|OutgoingCall|Connecting)/.test(c[1]))a.busy|=2;
 }
 }
 if(edge===m._cp&&camera)edge.reverse=camera.seq;
 if(edge&&m._cp.seq>edge.seq&&m.uiaId==="carplay"&&id==="TimedSbn_CarplayConnected")edge.ready=m;
 if(edge&&m._cp.seq>edge.seq&&m.uiaId==="system"&&p&&p.appName==="carplay"&&
  /^(StatusMenuVisibleCarPlay|StatusMenuCarPlayWifi)$/.test(id)){
 if(id==="StatusMenuVisibleCarPlay"?p.state==="Visible":p.appStatus==="Available")edge.menu=m;
 else if(edge.menu&&edge.menu.msgId===id)edge.menu=null;
 }
 if(m.uiaId==="common"&&id==="vuiState"&&p)a.busy=a.busy&~16|(a.voice(p.state)?16:0);
 if(m.uiaId==="system"){
 if(id==="StatusPhoneCall"&&p&&/^(Connecting|ActiveCall|IncomingCall|NoCall)$/.test(p.phoneCallStatus)){a.busy=a.busy&~1|(p.phoneCallStatus!=="NoCall"?1:0);}
 if(id==="ShowStateSBN_SiriActive"){a.busy|=4;}
 if(/^(RemoveStateSBN_SiriActive|TimedSBN_SiriError|TimedSBN_VRLoading|TimedSBN_VoiceNotSupported)$/.test(id)){a.busy&=~4;}
 }
 if(m.uiaId==="phone"){
 if(/^(ActiveCallInfo|ConferenceCallInfo|BTMultipleCallCP)$/.test(id)){a.busy|=2;}
 if(id==="NoCallState"){a.busy&=~2;}
 }
 if(depart(m,edge)||(a.busy||displayOff)&&(!edge||m._cp.seq>=edge.seq)){a.cancel();}
};
a.early.forEach(a.signal);a.early=null;
a.run=function(edge,input,trust,focus,next){
 if(Date.now()>=edge.end||input!==edge.k||a.busy){a.cancel();return;}
 if(a.loaded!==7)return;
 var gate=a.check(focus,next);
 if(gate===2)a.cancel();
 if(gate!==0||a.edge()!==edge||!trust||!edge.menu||!edge.menu._cp.delivered||
  !edge.delivered||!edge.ready||!edge.ready._cp.delivered||
  f.websockets._waitMsgArray.length||a.holding)return;
 a.cancel();f.sendEventToMmui("system","SelectCarPlay");
};
a.wrap(f,"_processNewFwkState",null,a.pump);
a.loaded|=4;a.pump();
}(typeof ocCarPlay==="undefined"?null:ocCarPlay,typeof framework==="undefined"?null:framework));
