/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnectSettings=(function(){
"use strict";
var active=false,waiting=null,session=null,dialogs=OpenConnectInstaller;
var entries=[
{key:"touch",title:"Touchscreen",choices:["Factory behavior","Always enabled","Always disabled"]},
{key:"warning",title:"Startup disclaimer",choices:["Show","Skip"]},
{key:"carplayAutoshow",title:"Show CarPlay on connection",choices:["Factory behavior","Automatically show"]}
];
var own=Object.prototype.hasOwnProperty;
function bit(v){return v===0||v===1;}
function optional(v){return v===undefined||bit(v);}

function validServices(rows){
if(rows===undefined)return true;
if(!Array.isArray(rows)||rows.length<1||rows.length>16)return false;
var previous="";
return rows.every(function(row){
if(!row||!/^[a-z][a-z0-9-]{0,31}$/.test(row.id)||row.id<=previous||
/^(touch|warning|base|wireless|uart|ssh|carplay-autoshow)$/.test(row.id)||
!bit(row.saved)||(row.current!==null&&!bit(row.current)))return false;
previous=row.id;
return["label","enable","disable"].every(function(k){
return typeof row[k]==="string"&&row[k].length>0&&
row[k].length<=(k==="label"?64:256)&&!/[\x00-\x1f\x7f]/.test(row[k]);
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
function service(v,k){
var rows=v&&v.services,i;
for(i=0;rows&&i<rows.length;i++)if(rows[i].id===k)return rows[i];
return null;
}
function preference(v,k){
var r=service(v,k);
return r?r.saved:v[k];
}
function valid(v){
return v&&validServices(v.services)&&(bit(v.touch)||v.touch===2)&&bit(v.warning)&&
optional(v.pandora)&&optional(v.base)&&autoshow(v)&&optional(v.wireless)&&
(v.wirelessFactory===undefined||typeof v.wirelessFactory==="boolean");
}
function autoshow(s){return s.carplayAutoshow===undefined||(bit(s.carplayAutoshow)&&bit(s.carplayAutoshowCurrent));}
function toggle(t,on,k){return{text1:t,itemStyle:"styleOnOff",value:on?1:2,hasCaret:false,appData:k};}

function slide(from,to,back,done,reveal,parent){
var a=from.divElt,b=to.divElt,timer,finished=false;
var init=back?"Transitions_Init_OffscreenLeft":"Transitions_Init_OffscreenRight";
var out="Transitions_slideOut"+(back?"Right":"Left")+"TmpltWithStatusLeftBtn_0_400";
var into="Transitions_slideIn"+(back?"Left":"Right")+"TmpltWithStatusLeftBtn_0_400";
function finish(ev){
if(finished||ev&&ev!==true&&ev.target!==b)return;
finished=true;clearTimeout(timer);
b.removeEventListener("animationend",finish,false);
a.classList.remove(out);b.classList.remove(into);b.classList.remove(init);
if(to.endTransitionTo)to.endTransitionTo();
done(ev===true);
}
b.addEventListener("animationend",finish,false);
b.classList.add(init);parent.appendChild(b);
if(reveal!==undefined)b.style.display=reveal;
if(from.startTransitionFrom)from.startTransitionFrom();
a.classList.add(out);b.classList.add(into);
timer=setTimeout(finish,900);
return finish;
}

function replace(obj,k,fn){
var prev=obj[k],loc=own.call(obj,k);
obj[k]=fn;
return function(){
if(obj[k]!==fn)return;
if(loc)obj[k]=prev;else delete obj[k];
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
function read(){try{return store.read();}catch(e){return null;}}
var saved=read();
if(!valid(saved)||saved.pending||saved.conflict)return null;
if(session&&session.owner===store)return session;
var wanted={},busy=false,queued=null,qd=false,prefs={owner:store,failure:null,changed:null};
function pending(v){return!store.pending||store.pending(v);}
function diff(v,k,c){return saved[c]!==undefined&&v[k]!==saved[c];}
function needsRestart(v){
if(saved.touchCurrent===undefined)return!!(saved.restart||Object.keys(wanted).some(function(k){return preference(saved,k)!==wanted[k];}));
if(saved.restartFixed||v.touch!==saved.touchCurrent||diff(v,"warning","warningCurrent")||
(v.base!==undefined&&diff(v,"base","baseCurrent"))||
(v.wireless!==undefined&&!v.wirelessFactory&&diff(v,"wireless","wirelessCurrent"))||
(v.carplayAutoshow!==undefined&&diff(v,"carplayAutoshow","carplayAutoshowCurrent"))||
(v.developer&&(diff(v,"uart","uartCurrent")||diff(v,"ssh","sshCurrent"))))return true;
return!!(v.services&&v.services.some(function(r){return r.current!==null&&r.saved!==r.current;}));
}
prefs.values=function(){
if(!busy&&!Object.keys(wanted).length){var c=read();if(!valid(c))return null;saved=c;}
var v={};
Object.keys(saved).forEach(function(k){v[k]=own.call(wanted,k)?wanted[k]:saved[k];});
if(saved.services)v.services=saved.services.map(function(r){
return{id:r.id,label:r.label,saved:own.call(wanted,r.id)?wanted[r.id]:r.saved,current:r.current,enable:r.enable,disable:r.disable};
});
v.restart=needsRestart(v);
return v;
};
function drain(ok){var n=queued;queued=null;qd=false;if(n)n(ok);}
function flush(){
var keys=Object.keys(wanted);
if(busy)return;
if(!keys.length){pending(false);drain(!prefs.failure);return;}
var key=keys[0],req=wanted[key];
if(preference(saved,key)===req){delete wanted[key];flush();if(prefs.changed)prefs.changed(false);return;}
busy=true;var ans=false;
function finish(actual,out){
if(ans)return;ans=true;busy=false;
if(out==="restart")wanted={};else if(!valid(actual))actual=read();
if(valid(actual))saved=actual;
var rec=out==="reconciled",failed=(!!out&&!rec)||!valid(actual)||preference(actual,key)!==req;
if(failed){
wanted={};prefs.failure=out==="restart"?"restart":key;
pending(false);if(prefs.changed)prefs.changed(true);drain(false);return;
}
if(rec&&qd)drain(false);
if(wanted[key]===req)delete wanted[key];
flush();if(prefs.changed)prefs.changed(rec?"sync":false);
}
try{store.write(key==="carplayAutoshow"?"carplay-autoshow":key,preference(saved,key),req,finish);}
catch(e){finish(null);}
}
prefs.pending=function(){return busy||Object.keys(wanted).length>0;};
prefs.select=function(k,v){
if(!pending(true)){if(prefs.revert)prefs.revert();return;}
prefs.failure=null;wanted[k]=v;if(prefs.changed)prefs.changed(false);flush();
};
prefs.queue=function(fn,drop){if(drop)wanted={};if(!prefs.pending()){fn(!prefs.failure);return;}queued=fn;qd=!!drop;flush();};
prefs.cancelQueue=function(){queued=null;qd=false;};
prefs.importKey=function(done){
if(prefs.pending()||typeof store.importKey!=="function"||!pending(true)){done(null);return;}
busy=true;var ans=false;
function finish(actual,failed){
if(ans)return;ans=true;busy=false;
var rec=failed==="reconciled",ok=valid(actual)&&(!failed||rec);
if(valid(actual))saved=actual;
if(!ok){
wanted={};pending(false);
if(failed==="restart"){prefs.failure=failed;if(prefs.changed)prefs.changed(true);drain(false);}
else{drain(false);if(!done(null,failed)&&prefs.changed)prefs.changed("sync");}
return;
}
if(rec&&qd)drain(false);
if(!done(actual)&&prefs.changed)prefs.changed("sync");
flush();
}
try{store.importKey(finish);}catch(e){finish(null);}
};
return(session=prefs);
}

function open(fw,store){
var host=fw._currTmpltInstance;
if(active||!inTab(fw)||!host||!host.list2Ctrl)return false;
var prefs=preferences(store);if(!prefs)return false;
var page,choice,dismiss=null,wait=null,moving=null,closed=false,leaving=false,ns=false,undo=[];
var parent=host.divElt.parentNode,oldD=host.divElt.style.display,tab=fw.getCurrCtxtId();
var R="after restarting Mazda Connect.",T="Try again in a moment.";
function current(){return!closed&&!leaving&&fw._currTmpltInstance===host&&inTab(fw)&&fw.getCurrCtxtId()===tab;}
function endWait(w){if(w&&wait!==w)return;w=wait;wait=null;if(w)w.close();}
function discard(p){if(p){p.cleanUp();if(p.divElt.parentNode)p.divElt.parentNode.removeChild(p.divElt);}}
function close(){
if(closed)return;closed=true;prefs.cancelQueue();
if(moving)moving(true);endWait();if(dismiss)dismiss();
prefs.changed=prefs.revert=null;
while(undo.length)undo.pop()();
discard(page);host.divElt.style.display=oldD;
if(fw.common._openConnectPage===close)delete fw.common._openConnectPage;
active=false;
}
function ask(t,x,l,a,d){return dialogs.message(fw,t,x,{button1:{label:"Cancel",appData:"cancel"},button2:{label:l,appData:a}},d);}
function render(index,focus,back){
if(moving)moving(true);
ns=false;
var values=prefs.failure?null:prefs.values();
if(!values){index="unknown";focus=0;}
var rows=[],title="Open Connect",i,row;
function action(t,k,c,d){rows.push({text1:t,itemStyle:"style01",hasCaret:!!c,appData:k,disabled:!!d});}
function entry(i){
var e=entries[i];
if(values[e.key]!==undefined)rows.push({text1:e.title,label1:i===2?["Factory","Auto"][values.carplayAutoshow]:e.choices[values[e.key]],
itemStyle:"style06",labelWidth:i?"normal":"wide",hasCaret:true,appData:i});
}
function integrations(phone){
if(values.services)values.services.forEach(function(s){
if((s.id==="android-auto")===phone)rows.push(toggle(s.label+(s.current===null?" (startup unknown)":s.current!==s.saved?" (restart needed)":""),s.saved,s.id));
});
else if(!phone&&values.pandora!==undefined)rows.push(toggle("Pandora",values.pandora,"pandora"));
}
if(index===null){
entry(0);entry(1);
if(values.base!==undefined)rows.push(toggle("Startup optimizations",values.base,"base"));
if(values.wireless!==undefined||values.carplayAutoshow!==undefined||service(values,"android-auto"))action("CarPlay & Android Auto","phone",true);
if(values.services||values.pandora!==undefined)action("Audio sources","sources",true);
if(values.developer)action("Developer options","developer",true);
action("Apply changes","restart",false,!canRestart());
action("Uninstall","uninstall",false,typeof store.uninstall!=="function");
action("About","about");
}else if(index==="phone"){
title="CarPlay & Android Auto";
if(values.wireless!==undefined)rows.push({text1:"Wireless CarPlay"+(values.wirelessFactory?" (factory enabled)":""),
itemStyle:"styleOnOff",value:values.wirelessFactory||values.wireless?1:2,disabled:values.wirelessFactory===true,hasCaret:false,appData:"wireless"});
entry(2);integrations(true);
}else if(index==="unknown"){
title=prefs.failure==="restart"?"Restart Mazda Connect":"Change could not be confirmed";
action("Return to Mazda Settings",0);
}else if(index==="sources"){title="Audio sources";integrations(false);
}else if(index==="developer"){
title="Developer options";
rows.push(toggle("UART",values.uart,"uart"));
row=toggle("SSH",values.ssh,"ssh");row.disabled=values.key==="-";rows.push(row);
action("Import public key","import",true,typeof store.importKey!=="function");
}else{
row=entries[index];title=row.title;
for(i=0;i<row.choices.length;i++)rows.push({text1:row.choices[i],image1:"radio",checked:i===values[row.key],itemStyle:"style03",hasCaret:false,appData:i});
}
for(i=0;i<rows.length;i++)if(rows[i].appData===focus)break;
var lp={dataList:{itemCountKnown:true,itemCount:rows.length,items:rows},titleConfiguration:"listTitle",
title:{text1:title,titleStyle:"style02"},smallItemText:true,focussedItem:i<rows.length?i:0,selectCallback:select};
if(typeof index==="number")lp.checkMinChangeInterval=0;else lp.toggleMinChangeInterval=0;
var offscreen=fw._offscreenTemplateParent;
var next=fw.instantiateTemplate("syssettings",offscreen||parent,"List2Tmplt",{List2Ctrl:lp});
if(!next)return false;
var old=page||host,animate=!!offscreen&&(!page||choice!==index);
page=next;choice=index;
function focusPage(){next.handleControllerEvent("acceptFocusInit");next.handleControllerEvent(fw.multicontroller.getMode());}
if(animate){
moving=slide(old,next,back,function(c){
moving=null;if(old===host)host.divElt.style.display="none";else discard(old);
if(!c&&!closed&&page===next)focusPage();
},undefined,parent);
}else{
if(next.divElt.parentNode!==parent)parent.appendChild(next.divElt);
if(old===host)host.divElt.style.display="none";else discard(old);
focusPage();
}
return true;
}
function canRestart(){
var v=prefs.values();
return v&&v.restart===true&&typeof store.restart==="function"&&!(store.busy&&store.busy()&&!prefs.pending());
}
function showWait(t){endWait();wait=dialogs.progress(fw,t,"Do not turn off the car.",function(){wait=null;prefs.cancelQueue();if(ns)prefs.changed("sync");});return wait;}
function runAction(a){
  if(a==="restart"&&!canRestart()){prefs.changed(false);return;}
  if(store[a](close))return;
  dismiss=dialogs.message(fw,T,"Another action is finishing.",{button1:{label:"OK",appData:"done"}},function(a){dismiss=null;if(a!=="closed"&&current())prefs.changed(false);});
}
function maintain(a){
  dismiss=null;if(!current()||(a!=="restart"&&a!=="uninstall"))return;
  if(a==="restart"&&!canRestart()){prefs.changed(false);return;}
  if(!prefs.pending()){runAction(a);return;}
  var w=showWait(a==="restart"?"Applying changes":"Removing Open Connect");if(!w)return;
  prefs.queue(function(ok){
    if(!ok)ns=false;
    endWait(w);
    if(ok&&current())runAction(a);
  },a==="uninstall");
}
function select(control,item,params){
if(!current()||dismiss||wait||!page||control!==page.list2Ctrl)return;
if(moving)moving(false);
var d=params&&params.additionalData;
if(choice===null&&/^(developer|phone|sources)$/.test(item)){render(item,0);return;}
if(choice==="phone"&&item===2){var v=prefs.values();if(v)render(2,v.carplayAutoshow);return;}
if(choice==="phone"&&item==="wireless"){
if(d!==1&&d!==2)return;
var v=prefs.values(),on=d===1;
if(!v||v.wirelessFactory===true||v.wireless===undefined||v.wireless===(on?1:0))return;
dismiss=ask((on?"Enable":"Disable")+" Wireless CarPlay?",on?"Changes apply "+R+" Then select Apple CarPlay in Mazda's Wi-Fi settings and pair your iPhone over Bluetooth."+
(v.base?" Delays Mazda Navigation about 20 s.":""):"Restores the original CarPlay behavior "+R,on?"Enable":"Disable","apply",function(a){
dismiss=null;if(a==="apply"&&current())prefs.select("wireless",on?1:0);
if(a!=="closed"&&current()&&choice==="phone")render("phone","wireless");
});return;
}
if(choice===null&&item==="base"||choice==="phone"||choice==="sources"){
if(d!==1&&d!==2)return;
var on=d===1,desired=on?1:0,v=prefs.values();
if(!v){render("unknown",0);return;}
var row=service(v,item);
if(item!=="base"&&!row&&!(item==="pandora"&&!v.services))return;
if(preference(v,item)===undefined||preference(v,item)===desired)return;
var label=item==="base"?"Startup optimizations":row?row.label:"Pandora";
var text=item==="base"?(on?(v.services?"Reduces background logging and unused services. Applies after restart.":"Reduces native diagnostic logging. Applies after restart."):
(v.services?"Restores original logging and startup behavior "+R:"Restores original native logging "+R)):row?(on?row.enable:row.disable):"Changes apply "+R;
if(item==="base"&&on&&v.wireless)text+=" Wireless CarPlay delays Mazda Navigation about 20 s.";
var origin=choice;
dismiss=ask((on?"Enable ":"Disable ")+label+"?",text,on?"Enable":"Disable","apply",function(a){
dismiss=null;if(a==="apply"&&current())prefs.select(item,desired);
if(a!=="closed"&&current()&&choice===origin)render(origin,item);
});return;
}
if(choice==="developer"){
if((item==="uart"||item==="ssh")&&(d===1||d===2)){
var v=prefs.values();if(item==="ssh"&&v.key==="-")return;
if(d===1&&v[item]===0){
dismiss=ask(item==="uart"?"Enable UART?":"Enable SSH?",item==="uart"?"Passwordless root access over UART. Changes apply after restart.":"Changes apply "+R,"Enable","enable",function(a){
dismiss=null;if(a==="enable"&&current())prefs.select(item,1);
if(a!=="closed"&&current()&&choice==="developer")render("developer",item);
});return;
}
prefs.select(item,d===1?1:0);
}else if(item==="import"&&typeof store.importKey==="function"){
  dismiss=ask("Import public key?","Put open-connect.pub on the USB drive. RSA and ECDSA public keys are supported. The imported key will be replaced.","Import","import",function(a){
    dismiss=null;if(a!=="import"||!current())return;
    var w=showWait("Importing public key");if(!w)return;
    prefs.queue(function(ok){
      if(!ok||!current()){if(!ok)ns=false;endWait(w);return;}
      prefs.importKey(function(act){
        if(current()&&choice==="developer"&&(!wait||wait===w))ns=false;
        endWait(w);if(!current()||choice!=="developer"||wait)return false;
        if(dismiss)dismiss();
        render("developer","import");
        if(choice!=="developer")return true;
        dismiss=dialogs.message(fw,act?"Public key imported":"Key could not be imported",
        act?"Fingerprint (MD5):\n"+act.fingerprint.slice(0,23)+"\n"+act.fingerprint.slice(24)+"\nEnable SSH when ready.":
        "Use one USB drive with open-connect.pub: an RSA key of at least 2048 bits or an ECDSA public key. Private keys and Ed25519 are not supported.",
        {button1:{label:"OK",appData:"done"}},function(){dismiss=null;});
        return true;
      });
    });
  });
}
return;
}
if(choice===null&&item==="about"){dismiss=dialogs.about(fw,store.version,function(a){dismiss=null;if(a!=="closed"&&current())prefs.changed(false);});return;}
if(choice===null&&item==="restart"){if(canRestart())dismiss=ask("Apply changes?","Restart Mazda Connect to apply your saved changes.","Restart","restart",maintain);return;}
if(choice===null&&item==="uninstall"&&typeof store.uninstall==="function"){dismiss=dialogs.confirmUninstall(fw,prefs.pending(),maintain);return;}
if(choice==="unknown"){if(item===0){prefs.failure=null;close();}return;}
if(typeof item!=="number"||item<0||item>=(choice===null?entries.length:entries[choice].choices.length))return;
if(choice===null){var v=prefs.values();if(v&&v[entries[item].key]!==undefined)render(item,v[entries[item].key]);return;}
if(choice===2&&item===1&&preference(prefs.values(),"carplayAutoshow")===0){
dismiss=ask("Automatically show CarPlay?","Opens CarPlay when your phone connects. Applies "+R,"Enable","apply",function(a){
dismiss=null;if(current()){if(a==="apply")prefs.select("carplayAutoshow",1);else if(a!=="closed")render(choice,0);}
});return;
}
prefs.select(entries[choice].key,item);
}
if(!render(null,0))return false;
active=true;fw.common._openConnectPage=close;
if(store.opened)store.opened();
if(typeof ocCarPlay!=="undefined"&&ocCarPlay)ocCarPlay.cancel();
prefs.revert=function(){if(current())render(choice,0);};
prefs.changed=function(failed){
if(failed==="sync"){
if(dismiss)dismiss();
if(!current()){close();return;}
if(wait){ns=true;return;}
var c=page&&page.list2Ctrl,fi=c&&c.dataList.items[c.focussedItem];
render(choice,fi?fi.appData:0);return;
}
if(!failed){
if(ns&&!wait){prefs.changed("sync");return;}
if(current()&&choice===null&&!dismiss&&!wait){
page.list2Ctrl.dataList.items.forEach(function(r,i){if(r.appData==="restart"){r.disabled=!canRestart();page.list2Ctrl.updateItems(i,i);}});
}return;
}
ns=false;endWait();if(dismiss)dismiss();if(current())render("unknown",0);else close();
};
var transition=fw.common.getCommonTransitionData;
undo.push(replace(fw.common,"getCommonTransitionData",function(){close();return transition.apply(this,arguments);}));
var input=host.handleControllerEvent;
undo.push(replace(host,"handleControllerEvent",function(e){
if(leaving&&e==="goBack")return;
if(!current()){close();return input.apply(this,arguments);}
return page.handleControllerEvent.apply(page,arguments);
}));
var send=fw.sendEventToMmui;
undo.push(replace(fw,"sendEventToMmui",function(app,ev){
if(leaving||/^(Global.Intent|SelectHome|SelectNavigation)/.test(ev))close();
if(current()&&app==="common"&&(ev==="Global.GoBack"||ev==="Global.MenuUp")){
if(wait)return;
if(dismiss)dismiss();
else if(choice!==null&&choice!=="unknown")render(choice===2?"phone":null,choice,true);
else{
if(choice==="unknown")prefs.failure=null;
if(moving)moving(true);leaving=true;
if(fw._offscreenTemplateParent)moving=slide(page,host,true,close,oldD,parent);else close();
}return;
}
return send.apply(this,arguments);
}));
return close;
}

function attach(fw,app,store){
function tmpl(){return app._currentContextTemplate;}
var entry=app._contextTable.SystemTab;
var orig=entry.readyFunction;
var list=null,release=null,closePage=null;
var id="open-connect-settings";
function bind(){
var host=tmpl();
if(!host||!host.list2Ctrl||host.list2Ctrl===list)return;
if(release)release(false);
list=host.list2Ctrl;
var ctrl=list,set=ctrl.setDataList,sel=ctrl.properties.selectCallback;
var undoSelect=replace(ctrl.properties,"selectCallback",function(c,v){
if(c===ctrl&&v===id){
var h=tmpl();
var show=function(fresh){
if(list!==ctrl||fw._currTmpltInstance!==h||tmpl()!==h)return;
if(!fresh){if(store.unavailable)store.unavailable();return;}
var o=open(fw,store);if(o)closePage=o;
};
var cached;
try{cached=store.read();}catch(e){}
if(valid(cached)&&!cached.pending&&!cached.conflict)show(true);
else if(store.refresh)store.refresh(show);
return;
}
return sel.apply(this,arguments);
});
function withEntry(data){
var count=data&&data.itemCount,items=data&&data.items;
if(!items||!count||items.length<count||items[count-1].appData!=="SelectAbout"||
items.some(function(r){return r&&r.appData===id;}))return set.apply(this,arguments);
var copy={},k;
for(k in data)if(own.call(data,k))copy[k]=data[k];
copy.items=items.slice(0,count);
copy.items.splice(count-1,0,{text1:"Open Connect",itemStyle:"style01",hasCaret:true,appData:id});
copy.itemCount=count+1;
return set.call(ctrl,copy);
}
var undoSet=replace(ctrl,"setDataList",withEntry);
release=function(visible){
if(closePage){closePage();closePage=null;}
undoSelect();undoSet();
if(!visible)return;
var data=ctrl.dataList,rows=data.items.filter(function(r){return r.appData!==id;});
if(rows.length!==data.itemCount){
set.call(ctrl,{itemCountKnown:true,itemCount:rows.length,items:rows,vuiSupport:data.vuiSupport});
if(rows.length)ctrl.updateItems(0,rows.length-1);
}
};
}
function repaint(){
if(list&&list.dataList.itemCount){list.updateItems(0,list.dataList.itemCount-1);}
}
if(fw.getCurrCtxtId()==="SystemTab"&&fw._currTmpltInstance===tmpl()){
bind();
if(list){
if(!list.dataList.items.some(function(r){return r.appData===id;}))list.setDataList(list.dataList);
repaint();
}
}
var undoReady=replace(entry,"readyFunction",function(){
bind();
var res=orig.apply(this,arguments);
repaint();
return res;
});
return function detach(){
undoReady();
if(release)release(tmpl()&&tmpl().list2Ctrl===list);
list=release=null;
};
}
function fromHome(fw,store,result){
if(active||waiting||fw._frameworkState!==fw._FWK_STATE_IDLE||voice(fw)||
fw.common._openConnectDialog||dialogs.foreign(fw)||
fw.getCurrentApp()!=="system"||fw.getCurrCtxtId()!=="HomeScreen")return false;
var attempts=0;
var timer=setInterval(function(){
var app=fw.getCurrentApp();
if(inTab(fw)&&open(fw,store)){cancel();result(true);}
else if(++attempts>=40||(app!=="system"&&!settingsApp(app))||
(app==="system"&&fw.getCurrCtxtId()!=="HomeScreen")||
(settingsApp(app)&&fw._frameworkState===fw._FWK_STATE_IDLE&&!inTab(fw))){cancel();result(false);}
},200);
function cancel(){clearInterval(timer);if(waiting===cancel)waiting=null;}
waiting=cancel;
try{fw.sendEventToMmui("system","SelectSettings");}
catch(e){cancel();throw e;}
return cancel;
}

return{open:open,fromHome:fromHome,attach:attach,validStatus:validStatus,
blocked:function(){return active||waiting||session&&session.pending();}};
}());

(function(a,f){
if(!a||a.loaded&4)return;
var cam,camS,dOff;
function owner(c){return c&&c.autoshowState();}
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
if(gate)return gate;
if(a.dialogs||s.blocked&&s.blocked()||dOff)return 2;
if(cam||!h||!c||!focus||f._focusStack!==focus||focus[0].id!==id||
h.contextInfo.uiaId!==id||f._frameworkState!==f._FWK_STATE_IDLE||!f._browserShown)return 1;
var ctx=h.contextInfo.ctxtId,app=f.getAppInstance(id);
if(!app||!app._currentContext||app._currentContext.ctxtId!==ctx||
next&&edge&&next._cp.seq>Math.max(edge.seq,a.focus||0)&&next._cp.ctx&&
(next.uiaId!==id||next.contextSeq!==h.contextInfo.contextSeq))return 1;
if(a.voice(c._cachedVuiState,c))return 2;
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
if(c[0]==="backupparking"||c[1]==="Idle"||cam)return false;
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
if(c){
if(c[0]==="backupparking"){
if(c[1]==="Idle"){if(!camS)cam=null;}
else{
if(!cam)cam=m._cp;
if(m._cp.focus)camS=true;
if(edge&&m._cp.seq>edge.seq){edge.reverse=cam.seq;edge.back=null;}
}
}else{
if(m._cp.focus){
if(cam&&(camS||String(c)!==String(cam.base))){cam=null;camS=false;}
dOff=false;
}
if(c[1]==="DisplayOff")dOff=true;
if(c[0]==="phone"&&!m._cp.focus&&/^(ActiveCall|IncomingCall|CallWaiting|MultipleCallWaiting|BTMultipleCall|OutgoingCall|Connecting)/.test(c[1]))a.busy|=2;
}
}
if(edge===m._cp&&cam)edge.reverse=cam.seq;
if(edge&&m._cp.seq>edge.seq&&m.uiaId==="carplay"&&id==="TimedSbn_CarplayConnected")edge.ready=m;
if(edge&&m._cp.seq>edge.seq&&m.uiaId==="system"&&p&&p.appName==="carplay"&&
/^(StatusMenuVisibleCarPlay|StatusMenuCarPlayWifi)$/.test(id)){
if(id==="StatusMenuVisibleCarPlay"?p.state==="Visible":p.appStatus==="Available")edge.menu=m;
else if(edge.menu&&edge.menu.msgId===id)edge.menu=null;
}
if(m.uiaId==="common"&&id==="vuiState"&&p)a.busy=a.busy&~16|(a.voice(p.state)?16:0);
if(m.uiaId==="system"){
if(id==="StatusPhoneCall"&&p&&/^(Connecting|ActiveCall|IncomingCall|NoCall)$/.test(p.phoneCallStatus))a.busy=a.busy&~1|(p.phoneCallStatus!=="NoCall"?1:0);
if(id==="ShowStateSBN_SiriActive")a.busy|=4;
if(/^(RemoveStateSBN_SiriActive|TimedSBN_SiriError|TimedSBN_VRLoading|TimedSBN_VoiceNotSupported)$/.test(id))a.busy&=~4;
}
if(m.uiaId==="phone"){
if(/^(ActiveCallInfo|ConferenceCallInfo|BTMultipleCallCP)$/.test(id))a.busy|=2;
if(id==="NoCallState")a.busy&=~2;
}
if(depart(m,edge)||(a.busy||dOff)&&(!edge||m._cp.seq>=edge.seq))a.cancel();
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
