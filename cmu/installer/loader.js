/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* USB loads its popup only. Installed Settings is never inspected or replaced. */
var OpenConnectUSBStart=function(entry){
"use strict";
if(!entry||document.getElementById("oc-maintenance-loader")!==entry||
 window.__ocMaintenanceLoading&&window.__ocMaintenanceLoading.entry===entry)return;
var token=entry.ocToken,base=entry.src.slice(0,entry.src.lastIndexOf("/")+1),discovery=entry.ocDiscovery;
if(!/^[a-f0-9]{32}$/.test(token)||entry.ocPort!==15557||
 window.OpenConnectMaintenance&&window.OpenConnectMaintenance.busy&&window.OpenConnectMaintenance.busy()){
 if(discovery)discovery.cancel();
 if(entry.parentNode)entry.parentNode.removeChild(entry);
 return;
}
if(window.__ocMaintenanceLoading)window.__ocMaintenanceLoading.finish();
var prev=window.__ocMaintenanceGeneration;
var state={token:token,entry:entry,finish:finish},node,stopped=false;
window.__ocMaintenanceGeneration=state;
window.__ocMaintenanceLoading=state;
function current(){return window.__ocMaintenanceGeneration===state;}
function finish(){
 if(stopped)return;stopped=true;clearTimeout(timer);
 [entry,node].forEach(function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);});
 if(window.__ocMaintenanceLoading===state)delete window.__ocMaintenanceLoading;
}
// Legacy entry already owns the deadline, including time before this delivery.
if(discovery)discovery.stop=finish;
var timer=discovery?null:setTimeout(finish,65000);
utility.loadScript(base+"maintenance.js",{id:"oc-maintenance-popup"},function(){
 if(!stopped&&current()&&document.getElementById("oc-maintenance-loader")===entry&&
   typeof window.OpenConnectMaintenanceStart==="function"){
  var client=OpenConnectMaintenanceStart({token:token,port:15557,role:"usb",current:current,discovery:discovery});
  if(!client){
   if(window.__ocMaintenanceGeneration===state)window.__ocMaintenanceGeneration=prev;
   if(discovery)discovery.cancel();
  }
 }else if(discovery)discovery.cancel();
 finish();
});
node=document.getElementById("oc-maintenance-popup");
};
