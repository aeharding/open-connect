/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* USB loads its popup only. Installed Settings is never inspected or replaced. */
var OpenConnectUSBStart=function(entry){
"use strict";
if(!entry||document.getElementById("oc-maintenance-loader")!==entry||
 window.__ocMaintenanceLoading&&window.__ocMaintenanceLoading.entry===entry)return;
var token=entry.ocToken,base=entry.src.slice(0,entry.src.lastIndexOf("/")+1);
if(!/^[a-f0-9]{32}$/.test(token)||entry.ocPort!==15557)return;
if(window.__ocMaintenanceLoading)window.__ocMaintenanceLoading.finish();
var state={token:token,entry:entry,finish:finish},node,stopped=false;
window.__ocMaintenanceGeneration=state;
window.__ocMaintenanceLoading=state;
function current(){return window.__ocMaintenanceGeneration===state;}
function finish(){
 if(stopped)return;stopped=true;clearTimeout(timer);
 [entry,node].forEach(function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);});
 if(window.__ocMaintenanceLoading===state)delete window.__ocMaintenanceLoading;
}
var timer=setTimeout(finish,65000);
utility.loadScript(base+"maintenance.js",{id:"oc-maintenance-popup"},function(){
 if(!stopped&&current()&&document.getElementById("oc-maintenance-loader")===entry&&
   typeof window.OpenConnectMaintenanceStart==="function"){
  OpenConnectMaintenanceStart({token:token,port:15557,role:"usb",current:current});
 }
 finish();
});
node=document.getElementById("oc-maintenance-popup");
};
