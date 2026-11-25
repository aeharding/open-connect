/* SPDX-License-Identifier: AGPL-3.0-or-later */
var ocCarPlay=(function(f,w){
"use strict";
var el=document.querySelector('meta[name="open-connect-token"]'),boot=el&&el.getAttribute("data-boot");
if(!/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/.test(boot)) return null;
var mark="oc107:"+boot+":",arm,live="",edge,ttl,job;
var k=0,n=0,at,one=true,safe=true,ids,to,last;
var a={busy:0,loaded:0,early:[],cancel:stop,pump:pump,wrap:wrap};
a.copy=function(m){return m&&[m.uiaId,m.ctxtId,m.contextSeq];};
function get(k){try{return (k?w.sessionStorage&&w.sessionStorage.getItem("oc107"):w.name)||"";} catch(e){return null;}}
function save(m){
  var v=mark+m,n=get(0),s=get(1);
  try{if(n!=null&&(!n||n.indexOf("oc107:")===0)) w.name=v;} catch(e){}
  try{if(s||get(0)!==v) w.sessionStorage.setItem("oc107",v);} catch(e){}
  n=get(0); s=get(1);
  return n!=null&&s!=null&&(n===v||s===v)&&(m==="C"||n!==mark+"C"&&s!==mark+"C");
}
arm=[get(0),get(1)].every(function(v){return v!=null&&(v.indexOf(mark)!==0||v===mark+"A");});
function stop(){edge=null; clearTimeout(ttl);}
function soon(){clearTimeout(job); job=setTimeout(pump,0);}
function wrap(o,k,b,e){
  var old=o[k];
  o[k]=function(){
    try{if(b) b.apply(this,arguments);} catch(e){stop();}
    var r=old.apply(this,arguments);
    try{if(e) e.apply(this,arguments);} catch(e){stop();}
    return r;
  };
}
function note(m){
  if(m._cp) return;
  var s=at||{t:Date.now(),k:k};
  Object.defineProperty(m,"_cp",{value:{end:s.t+15000,k:s.k,seq:++n}});
  var p=m.params&&m.params.payload,id=m.msgId;
  if(m.msgType==="focusStack") ids=m.appIdList;
  if(m.msgType==="ctxtChg"){
    var fg=m.uiaId===f.getCurrentApp()||ids&&ids[0].id===m.uiaId;
    if(fg&&m.ctxtId!=="Idle") to=m;
    if(fg||/^(backupparking|phone)$/.test(m.uiaId)||m.ctxtId==="DisplayOff") m._cp.ctx=a.copy(m);
    if(m.uiaId==="backupparking") m._cp.base=a.copy(f._currTmpltInstance&&f._currTmpltInstance.contextInfo);
  }
  if(m.uiaId==="carplay"&&id==="SendCPSessionState"&&p){
    if(p.state===false){stop(); live=""; arm=save("A"); one=false;}
    if(p.state===true&&(typeof p.serialId==="string"&&p.serialId&&p.serialId.length<=256||
        typeof p.btMacAddress==="string"&&/^(?:[\da-f]{2}:){5}[\da-f]{2}$/i.test(p.btMacAddress))){
      id=(p.serialId||"")+"/"+(p.btMacAddress||"");
      if(live===id) return;
      stop(); live=id;
      var ok=arm; arm=false;
      if(save("C")&&ok&&(!one||!k)){
        s=f._currTmpltInstance;
        edge=m._cp; edge.origin=a.copy(s&&s.contextInfo);
        ttl=setTimeout(stop,Math.max(0,edge.end-Date.now()));
      }
      one=false;
    }
  }
  tap(m);
}
function tap(m){
  if(a.signal) a.signal(m);
  else if(m._cp.ctx||/^(vuiState|SendCPSessionState|StatusMenu.*CarPlay.*|StatusPhoneCall|(Active|Conference)CallInfo|BTMultipleCallCP|NoCallState|.*Siri.*|TimedSBN_(VRLoading|VoiceNotSupported))$/.test(m.msgId)){
    if(a.early.length<32) a.early.push(m); else a.busy|=8;
  }
}
wrap(Websockets.prototype,"_doRouteMmuiMsg",function(text){
  if(typeof text!=="string"){safe=false; ids=null;}
  at={t:Date.now(),k:k,len:this._preInitGuiMsgQueue.length};
},function(){
  var list=this._preInitGuiMsgQueue;
  for(var i=at.len; i<list.length; i++) note(list[i]);
  at=null; soon();
});
wrap(f,"routeMmuiMsg",note,soon);
wrap(f,"_focusStackChange",null,function(){
  if(ids===f._focusStack) safe=true;
  var id=f._focusStack[0].id,c=f.getAppInstance(id);
  c=a.copy(c&&c._currentContext)||[id,"",0];
  a.focus=++n;
  if(String(c)!==String(last)) tap({msgType:"ctxtChg",_cp:{seq:n,ctx:c,focus:1}});
  last=c;
  soon();
});
wrap(f,"_handleMessage",null,function(id,m){
  note(m); m._cp.delivered=true;
  soon();
});
function act(e){if(!a.agree||!a.agree(e)){k++; stop();}}
a.user=act;
["mousedown","mouseup","keydown"].forEach(function(k){document.addEventListener(k,act,true);});
wrap(f,"_multicontrollerEventHandler",function(e){
  if(!/^(touch|controller)Active$/.test(e)) act(e);
});
function pump(){if(edge&&a.run) a.run(edge,k,safe,ids,to);}
a.edge=function(){return edge;};
return a;
}(framework,window));
