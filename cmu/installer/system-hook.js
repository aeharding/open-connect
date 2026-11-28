/* SPDX-License-Identifier: AGPL-3.0-or-later */
(function(fw,applied){
"use strict";
var initialize=fw._initApp,hidden=","+applied[1]+",";
function invisible(){return false;}
function keepHidden(){}
/* OPEN_CONNECT_AA_BEGIN */
function disableAndroidAuto(app){
var rows=app._masterEntertainmentDataList.items,stale=false,wiredCarPlay=false,i;
function guard(method,event){
var original=app[method];
if(typeof original!=="function")return;
function appliedAndroidAuto(msg){
var payload=msg&&msg.params&&msg.params.payload;
if(payload&&(payload.appName==="androidauto"||(payload.statusMenu&&payload.statusMenu.appName==="androidauto")))return;
return original.apply(this,arguments);
}
app[method]=appliedAndroidAuto;
app._messageTable[event]=appliedAndroidAuto.bind(app);
}
if(hidden.indexOf(",androidauto,")===-1)return;
for(i=0;i<rows.length;i++){
if(rows[i].appData.appName==="androidauto"){stale=rows[i].appData.isVisible;rows[i].disabled=true;}
if(rows[i].text1Id==="USB1CarPlay")wiredCarPlay=rows[i].appData.isVisible;
}
if(stale&&!wiredCarPlay&&rows[app._USB1EntIndex])rows[app._USB1EntIndex].appData.isVisible=true;
guard("_StatusMenuVisibleAndroidAutoMsgHandler","StatusMenuVisibleAndroidAuto");
guard("_StatusMenuVisibleMsgHandler","StatusMenuVisible");
guard("_StatusMenuMsgHandler","StatusMenu");
}
/* OPEN_CONNECT_AA_END */
/* OPEN_CONNECT_SO_BEGIN */
function reorderSources(app){
var original=app._buildEntertainmentDataList;
if(typeof original!=="function")return;
var rank={CarPlayWifi:1,CarPlay:2,AndroidAuto:3,USB_A:4,USB_B:5,BTAudio:6};
app._buildEntertainmentDataList=function(){
var list=original.apply(this,arguments),items,head,tail,i,r;
if(!list||!list.items||list.items.length<2)return list;
items=list.items;head=[];tail=[];
for(i=0;i<items.length;i++){
r=items[i]&&items[i].appData&&rank[items[i].appData.audioSourceId];
if(r)head.push({r:r,i:i,item:items[i]});else tail.push(items[i]);
}
head.sort(function(a,b){return a.r-b.r||a.i-b.i;});
list.items=head.map(function(x){return x.item;}).concat(tail);
list.itemCount=list.items.length;
return list;
};
}
/* OPEN_CONNECT_SO_END */
/* OPEN_CONNECT_NAV_BEGIN */
function installNav(){
var instantiate=fw.instantiateControl;
if(typeof instantiate!=="function")return;
function wrapMainMenu(C){
if(!C||!C.prototype||typeof C.prototype._offsetFocus!=="function"||C.prototype._ocMenuLoop)return;
C.prototype._ocMenuLoop=true;
C.prototype._offsetFocus=function(dir){
var cur=this._getFocus(),i;
if(typeof cur!=="number"||typeof dir!=="number")return;
i=cur+dir;
if(i<0)i=4;else if(i>4)i=0;
if(i!==cur){this._setFocus(i);this._setHighlight(i);}
};
}
function wrapList(C){
if(!C||!C.prototype||C.prototype._ocListLoop)return;
var cw=C.prototype._handleMCCW,ccw=C.prototype._handleMCCCW;
if(typeof cw!=="function"||typeof ccw!=="function")return;
C.prototype._ocListLoop=true;
function step(ctrl,dir,orig,args){
var dl=ctrl.dataList,n,cur,j,t,it;
if(!ctrl._inLetterIndexMulticontroller&&!ctrl._inListReorder&&
ctrl._hasFocus&&ctrl._inputMode==="controller"&&
ctrl.hasDataList&&ctrl.hasDataList()&&
(!ctrl.properties||ctrl.properties.scrollingDuringLoading||!ctrl._inLoading)&&
dl&&dl.itemCountKnown&&dl.items&&(n=dl.itemCount)>1&&dl.items.length>=n){
cur=ctrl._getFocussedIndex();
if(typeof cur==="number"&&cur>=0&&cur<n){
for(j=cur+dir;j>=0&&j<n;j+=dir){
it=dl.items[j];
if(!it||it.itemStyle==="empty"||!it.disabled)return orig.apply(ctrl,args);
}
for(t=dir>0?0:n-1;t!==cur;t+=dir){
it=dl.items[t];
if(!it||it.itemStyle==="empty")return orig.apply(ctrl,args);
if(!it.disabled){ctrl._showFocus(t);return "consumed";}
}
}
}
return orig.apply(ctrl,args);
}
C.prototype._handleMCCW=function(){return step(this,1,cw,arguments);};
C.prototype._handleMCCCW=function(){return step(this,-1,ccw,arguments);};
}
fw.instantiateControl=function(uiaId,parentDiv,name,properties){
var ctrl=instantiate.apply(this,arguments);
if(ctrl){
if(applied[3]&&name==="MainMenuCtrl")wrapMainMenu(ctrl.constructor);
if(name==="List2Ctrl"){
if(applied[3])wrapList(ctrl.constructor);
if(applied[4]&&ctrl.properties&&ctrl.properties.autoscrollTier1Timeout===1500&&
(!properties||properties.autoscrollTier1Timeout===undefined)){
ctrl.properties.autoscrollTier1Timeout=1000;
}
}
}
return ctrl;
};
}
/* OPEN_CONNECT_NAV_END */
function conceal(rows){
var i,data;
if(!applied[1])return;
for(i=0;i<rows.length;i++){
data=rows[i].appData;
if(data&&data.appName&&hidden.indexOf(","+data.appName+",")!==-1){
Object.defineProperty(data,"isVisible",{enumerable:true,get:invisible,set:keepHidden});
}
}
}
function introEntry(){
var app=this;
if(app._openConnectIntroCleanup)app._openConnectIntroCleanup();
var original=fw._templateTransitionCompleteCallback,active=true;
var local=Object.prototype.hasOwnProperty.call(fw,"_templateTransitionCompleteCallback");
function stop(){
active=false;
if(fw._templateTransitionCompleteCallback===complete){
if(local)fw._templateTransitionCompleteCallback=original;
else delete fw._templateTransitionCompleteCallback;
}
if(app._openConnectIntroCleanup===stop)delete app._openConnectIntroCleanup;
}
function complete(){
var incoming=fw._currTmpltInstance;
var changing=fw._frameworkState===fw._FWK_STATE_TMPLT_CHANGE;
var result=original.apply(this,arguments);
if(!active||!changing||!incoming||!incoming.contextInfo)return result;
var info=incoming.contextInfo;
if(info.uiaId==="system"&&(info.ctxtId==="IntroAnimation"||info.ctxtId==="QuickStartLoop"))return result;
stop();
if(info.uiaId!=="system"||info.ctxtId!=="Disclaimer"){
fw.sendEventToMmui("system","DisposeIntroVideo");
fw.sendEventToMmui("system","NotifyDisclaimerEnd");
}
return result;
}
app._openConnectIntroCleanup=stop;
fw._templateTransitionCompleteCallback=complete;
}
if(applied[3]||applied[4])installNav();/* OPEN_CONNECT_NAV_CALL */
fw._initApp=function(id){
var result=initialize.apply(this,arguments),app;
if(id==="system"){
app=this._appInstances[id];
disableAndroidAuto(app);/* OPEN_CONNECT_AA_CALL */
conceal(app._masterEntertainmentDataList.items);
conceal(app._masterApplicationDataList.items);
if(applied[2])reorderSources(app);/* OPEN_CONNECT_SO_CALL */
if(applied[0])app._contextTable.IntroAnimation.contextInFunction=introEntry.bind(app);
}
return result;
};
}(framework,[/*OPEN_CONNECT_APPLIED*/]));
