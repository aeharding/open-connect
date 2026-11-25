/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* USB loads its popup only. Installed Settings is never inspected or replaced. */
(function(){
"use strict";
var entry=document.getElementById("oc-maintenance-loader");
if(!entry||window.__ocMaintenanceLoading)return;
var token=entry.ocToken,base=entry.src.slice(0,entry.src.lastIndexOf("/")+1);
var state={token:token},node,stopped=false;
window.__ocMaintenanceLoading=state;
function finish(){
 if(stopped)return;stopped=true;clearTimeout(timer);
 [entry,node].forEach(function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);});
 if(window.__ocMaintenanceLoading===state)delete window.__ocMaintenanceLoading;
}
var timer=setTimeout(finish,65000);
utility.loadScript(base+"maintenance.js",{id:"oc-maintenance-popup"},finish);
node=document.getElementById("oc-maintenance-popup");
}());
