/* SPDX-License-Identifier: AGPL-3.0-or-later */
var ocCarPlay=(function (f) {
"use strict";
var meta=document.querySelector('meta[name="open-connect-token"]'), boot=meta&&meta.getAttribute("data-boot");
if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(boot)) return null;
var mark="oc107:"+boot+":", armed, live="", edge, timer, turn;
var input=0, seq=0, at, fresh=true, trust=true, focus, next;
var a={busy: 0, loaded: 0, early: [], cancel: stop, pump: pump, wrap: wrap};
function read(k) { try { return (k ? window.sessionStorage&&window.sessionStorage.getItem("oc107") : window.name)||""; } catch (ignore) { return null; } }
function persist(mode) {
  var value=mark + mode, n=read(0), s=read(1);
  try { if (n!=null&&(!n||n.indexOf("oc107:")===0)) { window.name=value; } } catch (ignore) {}
  try { if (s||read(0)!==value) { window.sessionStorage.setItem("oc107", value); } } catch (ignore) {}
  n=read(0); s=read(1);
  return n!=null&&s!=null&&(n===value||s===value)&&(mode==="C"||n!==mark + "C"&&s!==mark + "C");
}
armed=[read(0), read(1)].every(function (v) { return v!=null&&(v.indexOf(mark)!==0||v===mark + "A"); });
function stop() { edge=null; clearTimeout(timer); }
function later() { clearTimeout(turn); turn=setTimeout(pump, 0); }
function wrap(object, key, before, after) {
  var old=object[key];
  object[key]=function () {
    try { if (before) before.apply(this, arguments); } catch (ignore) { stop(); }
    var result=old.apply(this, arguments);
    try { if (after) after.apply(this, arguments); } catch (ignore) { stop(); }
    return result;
  };
}
function track(m) {
  if (m._cp) return;
  var s=at||{time: Date.now(), input: input};
  Object.defineProperty(m, "_cp", {value: {until: s.time + 15000, input: s.input, order: ++seq}});
  var p=m.params&&m.params.payload, id=m.msgId;
  if (m.msgType==="focusStack") { focus=m.appIdList; a.focus=m._cp.order; }
  if (m.msgType==="ctxtChg") next=m;
  if (m.uiaId==="carplay"&&id==="SendCPSessionState"&&p) {
    if (p.state===false) { stop(); live=""; armed=persist("A"); fresh=false; }
    if (p.state===true&&(typeof p.serialId==="string"&&p.serialId&&p.serialId.length<=256||
        typeof p.btMacAddress==="string"&&/^(?:[a-f0-9]{2}:){5}[a-f0-9]{2}$/i.test(p.btMacAddress))) {
      var phone=(p.serialId||"") + "/" + (p.btMacAddress||"");
      if (live===phone) return;
      stop(); live=phone;
      var ok=armed; armed=false;
      if (persist("C")&&ok&&(!fresh||!input)) {
        s=f._currTmpltInstance; s=s&&s.contextInfo;
        edge=m._cp; edge.origin=s&&[s.uiaId,s.ctxtId,s.contextSeq];
        timer=setTimeout(stop, Math.max(0, edge.until - Date.now()));
      }
      fresh=false;
    }
  }
  if (a.signal) a.signal(m);
  else if (/^(vuiState|SendCPSessionState|StatusMenu.*CarPlay.*|StatusPhoneCall|(Active|Conference)CallInfo|BTMultipleCallCP|NoCallState|.*Siri.*|TimedSBN_(VRLoading|VoiceNotSupported))$/.test(id)) {
    if (a.early.length<32) a.early.push(m); else a.busy|=8;
  }
}
wrap(Websockets.prototype, "_doRouteMmuiMsg", function (text) {
  if (typeof text!=="string") { trust=false; focus=null; }
  at={time: Date.now(), input: input, length: this._preInitGuiMsgQueue.length};
}, function () {
  var queue=this._preInitGuiMsgQueue;
  for (var i=at.length; i < queue.length; i++) track(queue[i]);
  at=null; later();
});
wrap(f, "routeMmuiMsg", track, later);
wrap(f, "_focusStackChange", null, function () { if (focus===f._focusStack) { trust=true; } later(); });
wrap(f, "_handleMessage", null, function (id, m) {
  track(m); m._cp.delivered=true;
  later();
});
wrap(f, "_processNewFwkState", null, later);
function user(event) { if (!a.agree||!a.agree(event)) { input++; stop(); } }
a.user=user;
["mousedown", "mouseup", "keydown"].forEach(function (key) { document.addEventListener(key, user, true); });
wrap(f, "_multicontrollerEventHandler", function (event) {
  if (!/^(touch|controller)Active$/.test(event)) { user(event); }
});
function pump() { if (edge&&a.run) { a.run(edge, input, trust, focus, next); } }
a.edge=function () { return edge; };
return a;
}(framework));
