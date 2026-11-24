/* SPDX-License-Identifier: AGPL-3.0-or-later */
var ocCarPlay=(function (f) {
"use strict";
var tag=document.querySelector('meta[name="open-connect-token"]'), boot=tag&&tag.getAttribute("data-boot");
if (!/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/.test(boot)) return null;
var mark="oc107:"+boot+":", armed, live="", edge, timer, job;
var input=0,seq=0,at,fresh=true,trust=true,focus,next;
var a={busy: 0, loaded: 0, early: [], cancel: stop, pump: pump, wrap: wrap};
a.copy=function (m) { return m&&[m.uiaId,m.ctxtId,m.contextSeq]; };
function read(k) { try { return (k ? window.sessionStorage&&window.sessionStorage.getItem("oc107") : window.name)||""; } catch (e) { return null; } }
function persist(mode) {
  var v=mark + mode, n=read(0), s=read(1);
  try { if (n!=null&&(!n||n.indexOf("oc107:")===0)) { window.name=v; } } catch (e) {}
  try { if (s||read(0)!==v) { window.sessionStorage.setItem("oc107", v); } } catch (e) {}
  n=read(0); s=read(1);
  return n!=null&&s!=null&&(n===v||s===v)&&(mode==="C"||n!==mark + "C"&&s!==mark + "C");
}
armed=[read(0), read(1)].every(function (v) { return v!=null&&(v.indexOf(mark)!==0||v===mark + "A"); });
function stop() { edge=null; clearTimeout(timer); }
function later() { clearTimeout(job); job=setTimeout(pump, 0); }
function wrap(obj, key, pre, post) {
  var old=obj[key];
  obj[key]=function () {
    try { if (pre) pre.apply(this, arguments); } catch (e) { stop(); }
    var res=old.apply(this, arguments);
    try { if (post) post.apply(this, arguments); } catch (e) { stop(); }
    return res;
  };
}
function track(m) {
  if (m._cp||m.msgType==="ctxtChg"&&m.ctxtId==="Idle") return;
  var s=at||{time: Date.now(), input: input};
  Object.defineProperty(m, "_cp", {value: {until: s.time + 15000, input: s.input, order: ++seq}});
  var p=m.params&&m.params.payload, id=m.msgId;
  if (m.msgType==="focusStack") { focus=m.appIdList; a.focus=m._cp.order; }
  if (m.msgType==="ctxtChg") next=m;
  if (m.uiaId==="carplay"&&id==="SendCPSessionState"&&p) {
    if (p.state===false) { stop(); live=""; armed=persist("A"); fresh=false; }
    if (p.state===true&&(typeof p.serialId==="string"&&p.serialId&&p.serialId.length<=256||
        typeof p.btMacAddress==="string"&&/^(?:[\da-f]{2}:){5}[\da-f]{2}$/i.test(p.btMacAddress))) {
      var peer=(p.serialId||"") + "/" + (p.btMacAddress||"");
      if (live===peer) return;
      stop(); live=peer;
      var ok=armed; armed=false;
      if (persist("C")&&ok&&(!fresh||!input)) {
        s=f._currTmpltInstance;
        edge=m._cp; edge.origin=a.copy(s&&s.contextInfo);
        timer=setTimeout(stop, Math.max(0, edge.until - Date.now()));
      }
      fresh=false;
    }
  }
  if (a.signal) a.signal(m);
  else if (m.msgType==="ctxtChg"||/^(vuiState|SendCPSessionState|StatusMenu.*CarPlay.*|StatusPhoneCall|(Active|Conference)CallInfo|BTMultipleCallCP|NoCallState|.*Siri.*|TimedSBN_(VRLoading|VoiceNotSupported))$/.test(id)) {
    if (a.early.length<32) a.early.push(m); else a.busy|=8;
  }
}
wrap(Websockets.prototype, "_doRouteMmuiMsg", function (text) {
  if (typeof text!=="string") { trust=false; focus=null; }
  at={time: Date.now(), input: input, length: this._preInitGuiMsgQueue.length};
}, function () {
  var list=this._preInitGuiMsgQueue;
  for (var i=at.length; i < list.length; i++) track(list[i]);
  at=null; later();
});
wrap(f, "routeMmuiMsg", track, later);
wrap(f, "_focusStackChange", null, function () { if (focus===f._focusStack) { trust=true; } later(); });
wrap(f, "_handleMessage", null, function (id, m) {
  track(m); m._cp.delivered=true;
  later();
});
wrap(f, "_processNewFwkState", null, later);
function user(e) { if (!a.agree||!a.agree(e)) { input++; stop(); } }
a.user=user;
["mousedown", "mouseup", "keydown"].forEach(function (key) { document.addEventListener(key, user, true); });
wrap(f, "_multicontrollerEventHandler", function (e) {
  if (!/^(touch|controller)Active$/.test(e)) { user(e); }
});
function pump() { if (edge&&a.run) { a.run(edge, input, trust, focus, next); } }
a.edge=function () { return edge; };
return a;
}(framework));
