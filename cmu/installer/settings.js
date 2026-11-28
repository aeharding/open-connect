/* SPDX-License-Identifier: AGPL-3.0-or-later */
var OpenConnectSettings=(function(){
"use strict";
var active=false,waiting=null,session=null,dialogs=OpenConnectInstaller;
var entries=[
{key:"touch",title:"Touchscreen",choices:["Factory behavior","Always enabled","Always disabled"]},
{key:"warning",title:"Startup disclaimer",choices:["Show","Skip"]},
{key:"carplayAutoshow",title:"Show CarPlay on connection",choices:["Factory behavior","Automatically show"]},
{key:"sourceOrder",title:"Source order",choices:["Factory order","Phone & media first"]}
];
var own=Object.prototype.hasOwnProperty,optKeys=["carplayAutoshow","sourceOrder","menuLoop","holdScroll"];
function bit(v){return v===0||v===1;}
function has(o,k){return o[k]!==undefined;}
function isFn(f){return typeof f==="function";}
function optional(v){return v===undefined||bit(v);}

function validServices(rows){
if(rows===undefined)return true;
if(!Array.isArray(rows)||rows.length<1||rows.length>16)return false;
var prev="";
return rows.every(function(r){
if(!r||!/^[a-z][a-z0-9-]{0,31}$/.test(r.id)||r.id<=prev||
/^(touch|warning|base|wireless|uart|ssh|carplay-autoshow|source-order|menu-loop|hold-scroll)$/.test(r.id)||
!bit(r.saved)||(r.current!==null&&!bit(r.current)))return false;
prev=r.id;
return["label","enable","disable"].every(function(k){
return typeof r[k]==="string"&&r[k].length>0&&r[k].length<=(k==="label"?64:256)&&!/[\x00-\x1f\x7f]/.test(r[k]);
});});}
var versionRE=/^[0-9]+(?:\.[0-9]+){1,3}(?:[-.][a-zA-Z0-9.-]+)?$/;
function validStatus(s){
return s&&s.ok===true&&valid(s)&&/^(?:-|[a-f0-9]{32}|[a-f0-9]{64})$/.test(s.revision)&&
["installed","retained","conflict","restart","pending"].every(function(k){return typeof s[k]==="boolean";})&&
(s.wireless===undefined||bit(s.wirelessCurrent))&&
(s.developer===undefined||(typeof s.developer==="boolean"&&bit(s.uart)&&bit(s.ssh)&&
bit(s.uartCurrent)&&bit(s.sshCurrent)&&/^(?:-|[a-f0-9]{64})$/.test(s.key)&&/^(?:-|[a-f0-9:]{47})$/.test(s.fingerprint)))&&
versionRE.test(s.version)&&(s.installedVersion===undefined||s.installedVersion==="-"||versionRE.test(s.installedVersion));
}
function service(v,k){
var rows=v&&v.services,i;
for(i=0;rows&&i<rows.length;i++)if(rows[i].id===k)return rows[i];
return null;
}
function preference(v,k){var r=service(v,k);return r?r.saved:v[k];}
function valid(v){
return v&&validServices(v.services)&&(bit(v.touch)||v.touch===2)&&bit(v.warning)&&
optional(v.pandora)&&optional(v.base)&&optKeys.every(function(k){return bitPair(v,k);})&&
optional(v.wireless)&&(v.wirelessFactory===undefined||typeof v.wirelessFactory==="boolean");
}
function bitPair(s,k){return s[k]===undefined||(bit(s[k])&&bit(s[k+"Current"]));}
function toggle(t,on,k){return{text1:t,itemStyle:"styleOnOff",value:on?1:2,hasCaret:false,appData:k};}

function slide(f,t,b,d,r,par){
var a=f.divElt,e=t.divElt,tm,fn=false,p="Transitions_",s="TmpltWithStatusLeftBtn_0_400";
var init=p+"Init_Offscreen"+(b?"Left":"Right");
var out=p+"slideOut"+(b?"Right":"Left")+s;
var into=p+"slideIn"+(b?"Left":"Right")+s;
function fin(ev){
if(fn||ev&&ev!==true&&ev.target!==e)return;
fn=true;clearTimeout(tm);
e.removeEventListener("animationend",fin,false);
a.classList.remove(out);e.classList.remove(into);e.classList.remove(init);
if(t.endTransitionTo)t.endTransitionTo();
d(ev===true);
}
e.addEventListener("animationend",fin,false);
e.classList.add(init);par.appendChild(e);
if(r!==undefined)e.style.display=r;
if(f.startTransitionFrom)f.startTransitionFrom();
a.classList.add(out);e.classList.add(into);
tm=setTimeout(fin,900);
return fin;
}

function replace(obj,k,fn){
var prev=obj[k],loc=own.call(obj,k);obj[k]=fn;
return function(){if(obj[k]!==fn)return;if(loc)obj[k]=prev;else delete obj[k];};
}

function settingsApp(id){return /^(sys|veh|audio)settings$/.test(id);}
function voice(fw){
var c=fw.common;
return c._vuiHelpDialog||c._vuiExamplesDialog||
/^(Playing Prompt|Listening|Processing|Playing Terminating Prompt)$/.test(c._cachedVuiState);
}
function inTab(fw){
return settingsApp(fw.getCurrentApp())&&/Tab$/.test(fw.getCurrCtxtId())&&
fw._frameworkState===fw._FWK_STATE_IDLE&&!voice(fw)&&!dialogs.foreign(fw);
}

function preferences(st){
function rd(){try{return st.read();}catch(e){return null;}}
var sv=rd(),ks=Object.keys;
if(!valid(sv)||sv.pending||sv.conflict)return null;
if(session&&session.owner===st)return session;
var wn={},bs=false,qu=null,qd=false,pr={owner:st,failure:null,changed:null};
function pd(v){return!st.pending||st.pending(v);}
function df(v,k){var c=k+"Current";return has(sv,c)&&v[k]!==sv[c];}
function needR(v){
if(!has(sv,"touchCurrent"))return!!(sv.restart||ks(wn).some(function(k){return preference(sv,k)!==wn[k];}));
if(sv.restartFixed||v.touch!==sv.touchCurrent||df(v,"warning")||
(has(v,"base")&&df(v,"base"))||
(has(v,"wireless")&&!v.wirelessFactory&&df(v,"wireless"))||
optKeys.some(function(k){return has(v,k)&&df(v,k);})||
(v.developer&&(df(v,"uart")||df(v,"ssh"))))return true;
return!!(v.services&&v.services.some(function(r){return r.current!==null&&r.saved!==r.current;}));
}
pr.values=function(){
if(!bs&&!ks(wn).length){var c=rd();if(!valid(c))return null;sv=c;}
var v={};
ks(sv).forEach(function(k){v[k]=own.call(wn,k)?wn[k]:sv[k];});
if(sv.services)v.services=sv.services.map(function(r){
return{id:r.id,label:r.label,saved:own.call(wn,r.id)?wn[r.id]:r.saved,current:r.current,enable:r.enable,disable:r.disable};
});
v.restart=needR(v);
return v;
};
function dr(ok){var n=qu;qu=null;qd=false;if(n)n(ok);}
function fl(){
var k2=ks(wn);if(bs)return;
if(!k2.length){pd(false);dr(!pr.failure);return;}
var k=k2[0],req=wn[k];
if(preference(sv,k)===req){delete wn[k];fl();if(pr.changed)pr.changed(false);return;}
bs=true;var ans=false;
function fn(ac,out){
if(ans)return;ans=true;bs=false;
if(out==="restart")wn={};else if(!valid(ac))ac=rd();
if(valid(ac))sv=ac;
var rec=out==="reconciled",fa=(!!out&&!rec)||!valid(ac)||preference(ac,k)!==req;
if(fa){wn={};pr.failure=out==="restart"?"restart":k;pd(false);if(pr.changed)pr.changed(true);dr(false);return;}
if(rec&&qd)dr(false);
if(wn[k]===req)delete wn[k];
fl();if(pr.changed)pr.changed(rec?"sync":false);
}
try{st.write(k.replace(/[A-Z]/g,function(c){return"-"+c.toLowerCase();}),preference(sv,k),req,fn);}
catch(e){fn(null);}
}
pr.pending=function(){return bs||ks(wn).length>0;};
pr.select=function(k,v){
if(!pd(true)){if(pr.revert)pr.revert();return;}
pr.failure=null;wn[k]=v;if(pr.changed)pr.changed(false);fl();
};
pr.queue=function(fn,drop){if(drop)wn={};if(!pr.pending()){fn(!pr.failure);return;}qu=fn;qd=!!drop;fl();};
pr.cancelQueue=function(){qu=null;qd=false;};
pr.task=function(call,done){
if(pr.pending()||!isFn(call)||!pd(true)){done(null);return;}
bs=true;var ans=false;
function fn(ac,fa){
if(ans)return;ans=true;bs=false;
var rec=fa==="reconciled",ok=valid(ac)&&(!fa||rec);
if(valid(ac))sv=ac;
if(!ok){
wn={};pd(false);
if(fa==="restart"){pr.failure=fa;if(pr.changed)pr.changed(true);dr(false);}
else{dr(false);if(!done(null,fa)&&pr.changed)pr.changed("sync");}
return;
}
if(rec&&qd)dr(false);
if(!done(ac)&&pr.changed)pr.changed("sync");
fl();
}
try{call(fn);}catch(e){fn(null);}
};
return(session=pr);
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
prefs.changed=prefs.revert=null;while(undo.length)undo.pop()();
discard(page);host.divElt.style.display=oldD;
if(fw.common._openConnectPage===close)delete fw.common._openConnectPage;
active=false;
}
function ask(t,x,l,a,d){return dialogs.message(fw,t,x,{button1:{label:"Cancel",appData:"cancel"},button2:{label:l,appData:a}},d);}
function render(index,focus,back){
if(moving)moving(true);
ns=false;
var v=prefs.failure?null:prefs.values();
if(!v){index="unknown";focus=0;}
var rows=[],title="Open Connect",i,row;
function action(t,k,c,d){rows.push({text1:t,itemStyle:"style01",hasCaret:!!c,appData:k,disabled:!!d});}
function entry(i){
var e=entries[i];
if(has(v,e.key))rows.push({text1:e.title,label1:i===2?["Factory","Auto"][v.carplayAutoshow]:i===3?["Factory","Phone first"][v.sourceOrder]:e.choices[v[e.key]],
itemStyle:"style06",labelWidth:i?"normal":"wide",hasCaret:true,appData:i});
}
function integrations(phone){
if(v.services)v.services.forEach(function(s){
if((s.id==="android-auto")===phone)rows.push(toggle(s.label+(s.current===null?" (startup unknown)":s.current!==s.saved?" (restart needed)":""),s.saved,s.id));
});
else if(!phone&&has(v,"pandora"))rows.push(toggle("Pandora",v.pandora,"pandora"));
}
if(index===null){
entry(0);entry(1);
if(has(v,"base"))rows.push(toggle("Startup optimizations",v.base,"base"));
if(has(v,"wireless")||has(v,"carplayAutoshow")||service(v,"android-auto"))action("CarPlay & Android Auto","phone",true);
if(v.services||has(v,"pandora")||has(v,"sourceOrder"))action("Audio sources","sources",true);
if(has(v,"menuLoop")||has(v,"holdScroll"))action("Commander Dial","dial",true);
if(isFn(store.exportPrefs)||isFn(store.importPrefs))action("Backup & restore","backup",true);
if(v.developer)action("Developer options","developer",true);
action("Apply changes","restart",false,!canRestart());
action("Uninstall","uninstall",false,!isFn(store.uninstall));
action("About","about");
}else if(index==="phone"){
title="CarPlay & Android Auto";
if(has(v,"wireless"))rows.push({text1:"Wireless CarPlay"+(v.wirelessFactory?" (factory enabled)":""),
itemStyle:"styleOnOff",value:v.wirelessFactory||v.wireless?1:2,disabled:v.wirelessFactory===true,hasCaret:false,appData:"wireless"});
entry(2);integrations(true);
}else if(index==="unknown"){
title=prefs.failure==="restart"?"Restart Mazda Connect":"Change could not be confirmed";
action("Return to Mazda Settings",0);
}else if(index==="sources"){title="Audio sources";entry(3);integrations(false);
}else if(index==="dial"){
title="Commander Dial";
if(has(v,"menuLoop"))rows.push(toggle("Wrap-around menus & lists",v.menuLoop,"menuLoop"));
if(has(v,"holdScroll"))rows.push(toggle("Faster hold-scroll",v.holdScroll,"holdScroll"));
}else if(index==="backup"){
title="Backup & restore";
action("Export preferences","exportPrefs",true,!isFn(store.exportPrefs));
action("Import preferences","importPrefs",true,!isFn(store.importPrefs));
}else if(index==="developer"){
title="Developer options";
rows.push(toggle("UART",v.uart,"uart"));
row=toggle("SSH",v.ssh,"ssh");row.disabled=v.key==="-";rows.push(row);
action("Import public key","import",true,!isFn(store.importKey));
}else{
row=entries[index];title=row.title;
for(i=0;i<row.choices.length;i++)rows.push({text1:row.choices[i],image1:"radio",checked:i===v[row.key],itemStyle:"style03",hasCaret:false,appData:i});
}
for(i=0;i<rows.length;i++)if(rows[i].appData===focus)break;
var lp={dataList:{itemCountKnown:true,itemCount:rows.length,items:rows},titleConfiguration:"listTitle",
title:{text1:title,titleStyle:"style02"},smallItemText:true,focussedItem:i<rows.length?i:0,selectCallback:select};
lp[typeof index==="number"?"checkMinChangeInterval":"toggleMinChangeInterval"]=0;
var off=fw._offscreenTemplateParent,next=fw.instantiateTemplate("syssettings",off||parent,"List2Tmplt",{List2Ctrl:lp});
if(!next)return false;
var old=page||host,anim=!!off&&(!page||choice!==index);
page=next;choice=index;
function focusPage(){next.handleControllerEvent("acceptFocusInit");next.handleControllerEvent(fw.multicontroller.getMode());}
if(anim){
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
return v&&v.restart===true&&isFn(store.restart)&&!(store.busy&&store.busy()&&!prefs.pending());
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
prefs.queue(function(ok){if(!ok)ns=false;endWait(w);if(ok&&current())runAction(a);},a==="uninstall");
}
function confirmToggle(origin,item,label,text,on,desired,act){
act=act||"apply";
dismiss=ask((on?"Enable ":"Disable ")+label+"?",text,on?"Enable":"Disable",act,function(a){
dismiss=null;if(a===act&&current())prefs.select(item,desired);
if(a!=="closed"&&current()&&choice===origin)render(origin,item);
});
}
function usbTask(origin,item,call,qt,qx,ql,qa,wt,doneMsg){
dismiss=ask(qt,qx,ql,qa,function(a){
dismiss=null;if(a!==qa||!current())return;
var w=showWait(wt);if(!w)return;
prefs.queue(function(ok){
if(!ok||!current()){if(!ok)ns=false;endWait(w);return;}
prefs.task(call,function(act){
if(current()&&choice===origin&&(!wait||wait===w))ns=false;
endWait(w);if(!current()||choice!==origin||wait)return false;
if(dismiss)dismiss();
render(origin,item);
if(choice!==origin)return true;
var m=doneMsg(act);
dismiss=dialogs.message(fw,m[0],m[1],{button1:{label:"OK",appData:"done"}},function(){dismiss=null;});
return true;
});});});
}
function select(control,item,params){
if(!current()||dismiss||wait||!page||control!==page.list2Ctrl)return;
if(moving)moving(false);
var d=params&&params.additionalData,v,on,desired,row,label,text;
if(choice===null&&/^(developer|phone|sources|dial|backup)$/.test(item)){render(item,0);return;}
if(choice==="phone"&&item===2||choice==="sources"&&item===3){v=prefs.values();if(v)render(item,v[entries[item].key]);return;}
if(choice==="backup"){
if(item==="exportPrefs"&&isFn(store.exportPrefs))usbTask("backup",item,store.exportPrefs,"Export preferences?","Save your settings to open-connect.prefs on the USB drive.","Export","export","Exporting preferences",function(act){return act?["Preferences exported","Saved to open-connect.prefs on the USB drive."]:["Export failed","Insert one FAT32 USB drive and try again."];});
else if(item==="importPrefs"&&isFn(store.importPrefs))usbTask("backup",item,store.importPrefs,"Import preferences?","Load settings from open-connect.prefs on the USB drive. Changes apply "+R,"Import","import","Importing preferences",function(act){return act?["Preferences imported","Changes apply "+R]:["Import failed","Use one FAT32 USB drive with a valid open-connect.prefs file."];});
return;
}
if(choice==="phone"&&item==="wireless"||choice==="dial"&&(item==="menuLoop"||item==="holdScroll")||choice===null&&item==="base"||choice==="phone"||choice==="sources"){
if(d!==1&&d!==2)return;
on=d===1;desired=on?1:0;v=prefs.values();
if(!v){render("unknown",0);return;}
if(item==="wireless"){
if(v.wirelessFactory===true||v.wireless===undefined||v.wireless===desired)return;
label="Wireless CarPlay";
text=on?"Changes apply "+R+" Then select Apple CarPlay in Mazda's Wi-Fi settings and pair your iPhone over Bluetooth."+(v.base?" Delays Mazda Navigation about 20 s.":""):"Restores the original CarPlay behavior "+R;
}else if(choice==="dial"){
if(v[item]===undefined||v[item]===desired)return;
label=item==="menuLoop"?"Wrap-around menus & lists":"Faster hold-scroll";
text=item==="menuLoop"?(on?"Wraps Commander Dial focus across menu and list ends. Applies "+R:"Restores factory stop-at-ends navigation "+R):
(on?"Starts list hold-scroll sooner (1.0 s instead of 1.5 s). Applies "+R:"Restores the factory 1.5 s hold-scroll delay "+R);
}else{
row=service(v,item);
if(item!=="base"&&!row&&!(item==="pandora"&&!v.services))return;
if(preference(v,item)===undefined||preference(v,item)===desired)return;
label=item==="base"?"Startup optimizations":row?row.label:"Pandora";
text=item==="base"?(on?(v.services?"Reduces background logging and unused services. Applies after restart.":"Reduces native diagnostic logging. Applies after restart."):
(v.services?"Restores original logging and startup behavior "+R:"Restores original native logging "+R)):row?(on?row.enable:row.disable):"Changes apply "+R;
if(item==="base"&&on&&v.wireless)text+=" Wireless CarPlay delays Mazda Navigation about 20 s.";
}
confirmToggle(choice,item,label,text,on,desired);return;
}
if(choice==="developer"){
if((item==="uart"||item==="ssh")&&(d===1||d===2)){
v=prefs.values();if(!v){render("unknown",0);return;}
if(item==="ssh"&&v.key==="-")return;
if(d===1&&v[item]===0){
confirmToggle("developer",item,item==="uart"?"UART":"SSH",item==="uart"?"Passwordless root access over UART. Changes apply after restart.":"Changes apply "+R,true,1,"enable");return;
}
prefs.select(item,d===1?1:0);
}else if(item==="import"&&isFn(store.importKey)){
usbTask("developer","import",store.importKey,"Import public key?","Put open-connect.pub on the USB drive. RSA and ECDSA public keys are supported. The imported key will be replaced.","Import","import","Importing public key",function(act){
return act?["Public key imported","Fingerprint (MD5):\n"+act.fingerprint.slice(0,23)+"\n"+act.fingerprint.slice(24)+"\nEnable SSH when ready."]:
["Key could not be imported","Use one USB drive with open-connect.pub: an RSA key of at least 2048 bits or an ECDSA public key. Private keys and Ed25519 are not supported."];
});}
return;
}
if(choice===null&&item==="about"){dismiss=dialogs.about(fw,store.version,function(a){dismiss=null;if(a!=="closed"&&current())prefs.changed(false);});return;}
if(choice===null&&item==="restart"){if(canRestart())dismiss=ask("Apply changes?","Restart Mazda Connect to apply your saved changes.","Restart","restart",maintain);return;}
if(choice===null&&item==="uninstall"&&isFn(store.uninstall)){dismiss=dialogs.confirmUninstall(fw,prefs.pending(),maintain);return;}
if(choice==="unknown"){if(item===0){prefs.failure=null;close();}return;}
if(typeof item!=="number"||item<0||item>=(choice===null?entries.length:entries[choice].choices.length))return;
if(choice===null){v=prefs.values();if(v&&has(v,entries[item].key))render(item,v[entries[item].key]);return;}
if(choice===2&&item===1){
v=prefs.values();if(!v){render("unknown",0);return;}
if(preference(v,"carplayAutoshow")===0){
dismiss=ask("Automatically show CarPlay?","Opens CarPlay when your phone connects. Applies "+R,"Enable","apply",function(a){
dismiss=null;if(current()){if(a==="apply")prefs.select("carplayAutoshow",1);else if(a!=="closed")render(choice,0);}
});return;
}
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
else if(choice!==null&&choice!=="unknown")render(choice===2?"phone":choice===3?"sources":null,choice,true);
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

function attach(fw,app,st){
function tmpl(){return app._currentContextTemplate;}
var en=app._contextTable.SystemTab,orig=en.readyFunction,ls=null,rel=null,cp=null,id="open-connect-settings";
function bind(){
var h=tmpl();
if(!h||!h.list2Ctrl||h.list2Ctrl===ls)return;
if(rel)rel(false);
ls=h.list2Ctrl;
var ct=ls,set=ct.setDataList,sel=ct.properties.selectCallback;
var uS=replace(ct.properties,"selectCallback",function(c,v){
if(c===ct&&v===id){
var h2=tmpl();
var sh=function(fr){
if(ls!==ct||fw._currTmpltInstance!==h2||tmpl()!==h2)return;
if(!fr){if(st.unavailable)st.unavailable();return;}
var o=open(fw,st);if(o)cp=o;
};
var ca;
try{ca=st.read();}catch(e){}
if(valid(ca)&&!ca.pending&&!ca.conflict)sh(true);
else if(st.refresh)st.refresh(sh);
return;
}
return sel.apply(this,arguments);
});
function withE(d){
var n=d&&d.itemCount,it=d&&d.items;
if(!it||!n||it.length<n||it[n-1].appData!=="SelectAbout"||
it.some(function(r){return r&&r.appData===id;}))return set.apply(this,arguments);
var c={},k;
for(k in d)if(own.call(d,k))c[k]=d[k];
c.items=it.slice(0,n);
c.items.splice(n-1,0,{text1:"Open Connect",itemStyle:"style01",hasCaret:true,appData:id});
c.itemCount=n+1;
return set.call(ct,c);
}
var uD=replace(ct,"setDataList",withE);
rel=function(vis){
if(cp){cp();cp=null;}
uS();uD();
if(!vis)return;
var d=ct.dataList,rw=d.items.filter(function(r){return r.appData!==id;});
if(rw.length!==d.itemCount){
set.call(ct,{itemCountKnown:true,itemCount:rw.length,items:rw,vuiSupport:d.vuiSupport});
if(rw.length)ct.updateItems(0,rw.length-1);
}
};
}
function rep(){if(ls&&ls.dataList.itemCount)ls.updateItems(0,ls.dataList.itemCount-1);}
if(fw.getCurrCtxtId()==="SystemTab"&&fw._currTmpltInstance===tmpl()){
bind();
if(ls){if(!ls.dataList.items.some(function(r){return r.appData===id;}))ls.setDataList(ls.dataList);rep();}
}
var uR=replace(en,"readyFunction",function(){bind();var r=orig.apply(this,arguments);rep();return r;});
return function detach(){uR();if(rel)rel(tmpl()&&tmpl().list2Ctrl===ls);ls=rel=null;};
}
function fromHome(fw,st,res){
if(active||waiting||fw._frameworkState!==fw._FWK_STATE_IDLE||voice(fw)||
fw.common._openConnectDialog||dialogs.foreign(fw)||
fw.getCurrentApp()!=="system"||fw.getCurrCtxtId()!=="HomeScreen")return false;
var at=0,tm=setInterval(function(){
var a=fw.getCurrentApp();
if(inTab(fw)&&open(fw,st)){cn();res(true);}
else if(++at>=40||(a!=="system"&&!settingsApp(a))||
(a==="system"&&fw.getCurrCtxtId()!=="HomeScreen")||
(settingsApp(a)&&fw._frameworkState===fw._FWK_STATE_IDLE&&!inTab(fw))){cn();res(false);}
},200);
function cn(){clearInterval(tm);if(waiting===cn)waiting=null;}
waiting=cn;
try{fw.sendEventToMmui("system","SelectSettings");}
catch(e){cn();throw e;}
return cn;
}

return{open:open,fromHome:fromHome,attach:attach,validStatus:validStatus,
blocked:function(){return active||waiting||session&&session.pending();}};
}());

(function(a,f){
if(!a||a.loaded&4)return;
var cam,camS,dOff;
function own(c){return c&&c.autoshowState();}
a.owner=function(){
if(f.common._openConnectOperation||window.__ocCompletionLoading||window.__ocMaintenanceLoading||
document.getElementById("oc-maintenance-loader"))return 2;
return own(window.OpenConnectCompletion)||own(window.OpenConnectMaintenance)||
(window.OpenConnect?own(window.OpenConnect):1);
};
function ctxKind(id,ctx){
if(id==="backupparking"||/^(IntroAnimation|QuickStartLoop|Disclaimer)$/.test(ctx))return 1;
if(id==="emnavi"&&ctx==="Active")return 0;
return id==="system"?(/^(HomeScreen|Entertainment)$/.test(ctx)?0:2):
/^(fmradio|amradio|usbaudio|btaudio|auxin|satradio|xmaudio|cd|dvd|tv|stitcher|aharadio|pandora|dab)$/.test(id)?0:2;
}
a.check=function(focus,next){
var g=a.owner(),h=f._currTmpltInstance,id=f.getCurrentApp(),c=f.common,s=OpenConnectSettings,e=a.edge(),ci=h&&h.contextInfo;
if(g)return g;
if(a.dialogs||s.blocked&&s.blocked()||dOff)return 2;
if(cam||!h||!c||!focus||f._focusStack!==focus||focus[0].id!==id||
ci.uiaId!==id||f._frameworkState!==f._FWK_STATE_IDLE||!f._browserShown)return 1;
var ctx=ci.ctxtId,app=f.getAppInstance(id);
if(!app||!app._currentContext||app._currentContext.ctxtId!==ctx||
next&&e&&next._cp.seq>Math.max(e.seq,a.focus||0)&&next._cp.ctx&&
(next.uiaId!==id||next.contextSeq!==ci.contextSeq))return 1;
if(a.voice(c._cachedVuiState,c))return 2;
var k=ctxKind(id,ctx),old=e&&e.origin;
if(e&&!k&&old&&ctxKind(old[0],old[1])!==1&&
(old[0]!==id||old[1]!==ctx||!e.reverse&&old[2]!==ci.contextSeq))return 2;
if(e&&!k&&(!old||ctxKind(old[0],old[1])===1))e.origin=a.copy(ci);
if(e&&e.reverse){
if(k||a.focus<=e.reverse)return 1;
e.origin=a.copy(ci);e.reverse=0;
}
return k;
};
function depart(m,e){
var p=m&&m._cp,c=p&&p.ctx;
if(!e||!m||m.msgType!=="ctxtChg"||p.seq<=e.seq||!c)return false;
if(c[0]==="backupparking"||c[1]==="Idle"||cam)return false;
var k=ctxKind(c[0],c[1]),old=e.back||e.origin;
if(k===2)return true;
if(k===1)return false;
k=!old||ctxKind(old[0],old[1])===1;
var once=(e.reverse||k)&&!e.back;
if(once)e.origin=e.back=c;
if(k)return false;
return old[0]!==c[0]||old[1]!==c[1]||!once&&old[2]!==c[2];
}
a.signal=function(m){
var id=m.msgId,pl=m.params&&m.params.payload,e=a.edge(),p=m._cp,c=p.ctx;
if(c){
if(c[0]==="backupparking"){
if(c[1]==="Idle"){if(!camS)cam=null;}
else{
if(!cam)cam=p;
if(p.focus)camS=true;
if(e&&p.seq>e.seq){e.reverse=cam.seq;e.back=null;}
}
}else{
if(p.focus){
if(cam&&(camS||String(c)!==String(cam.base))){cam=null;camS=false;}
dOff=false;
}
if(c[1]==="DisplayOff")dOff=true;
if(c[0]==="phone"&&!p.focus&&/^(ActiveCall|IncomingCall|CallWaiting|MultipleCallWaiting|BTMultipleCall|OutgoingCall|Connecting)/.test(c[1]))a.busy|=2;
}
}
if(e===p&&cam)e.reverse=cam.seq;
if(e&&p.seq>e.seq&&m.uiaId==="carplay"&&id==="TimedSbn_CarplayConnected")e.ready=m;
if(e&&p.seq>e.seq&&m.uiaId==="system"&&pl&&pl.appName==="carplay"&&
/^(StatusMenuVisibleCarPlay|StatusMenuCarPlayWifi)$/.test(id)){
if(id==="StatusMenuVisibleCarPlay"?pl.state==="Visible":pl.appStatus==="Available")e.menu=m;
else if(e.menu&&e.menu.msgId===id)e.menu=null;
}
if(m.uiaId==="common"&&id==="vuiState"&&pl)a.busy=a.busy&~16|(a.voice(pl.state)?16:0);
if(m.uiaId==="system"){
if(id==="StatusPhoneCall"&&pl&&/^(Connecting|ActiveCall|IncomingCall|NoCall)$/.test(pl.phoneCallStatus))a.busy=a.busy&~1|(pl.phoneCallStatus!=="NoCall"?1:0);
if(id==="ShowStateSBN_SiriActive")a.busy|=4;
if(/^(RemoveStateSBN_SiriActive|TimedSBN_SiriError|TimedSBN_VRLoading|TimedSBN_VoiceNotSupported)$/.test(id))a.busy&=~4;
}
if(m.uiaId==="phone"){
if(/^(ActiveCallInfo|ConferenceCallInfo|BTMultipleCallCP)$/.test(id))a.busy|=2;
if(id==="NoCallState")a.busy&=~2;
}
if(depart(m,e)||(a.busy||dOff)&&(!e||p.seq>=e.seq))a.cancel();
};
a.early.forEach(a.signal);a.early=null;
a.run=function(e,inp,trust,focus,next){
if(Date.now()>=e.end||inp!==e.k||a.busy){a.cancel();return;}
if(a.loaded!==7)return;
var g=a.check(focus,next);
if(g===2)a.cancel();
if(g!==0||a.edge()!==e||!trust||!e.menu||!e.menu._cp.delivered||
!e.delivered||!e.ready||!e.ready._cp.delivered||
f.websockets._waitMsgArray.length||a.holding)return;
a.cancel();f.sendEventToMmui("system","SelectCarPlay");
};
a.wrap(f,"_processNewFwkState",null,a.pump);
a.loaded|=4;a.pump();
}(typeof ocCarPlay==="undefined"?null:ocCarPlay,typeof framework==="undefined"?null:framework));
