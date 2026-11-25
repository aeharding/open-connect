const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const folder = process.argv[2], boot = '12345678-1234-1234-1234-123456789abc';
function fixture(shared = {}, load = true) {
  const calls = [], events = {}, timers = [], pendingContexts = [];
  let deferContext=false, background=false, contextHandler, contextCompare, nativeContext, nativeFocus, loading, callEnd;
  let now = 0, clock = 0;
  const state = {name: '', storage: new Map(), ...shared};
  const ctx = {log: {error() {}, addSrcFile() {}, debug() {}, info() {}, warn() {}}, Date: {now: () => now},
    setTimeout(fn, ms = 0) {const t = {fn, at: now + ms, live: true};timers.push(t);return t;},
    clearTimeout(t) {if(t)t.live=false;}, setInterval() {}, clearInterval() {}};
  ctx.window = new Proxy(ctx, {});
  Object.defineProperty(ctx, 'name', {get: () => {if(state.failNameRead)throw Error('name read');return state.name;}, set: v => {
    if(state.failName && v.endsWith(':C'))throw Error('name write');state.name=v;
  }});
  ctx.sessionStorage = {getItem: k => {if(state.failRead)throw Error('storage read');return state.storage.get(k) || null;},
    setItem(k,v) {if(state.failStorage)throw Error('storage write');state.storage.set(k,v);}};
  ctx.document = {body: {}, querySelector(selector) {
    return selector.includes('open-connect-token') ? {getAttribute: key => key === 'data-boot' ? boot : 'a'.repeat(32)} : null;
  },getElementById() {return null;}, addEventListener(key, fn) {(events[key] ||= []).push(fn);},removeEventListener() {}};
  const apps = {system: {_currentContext: {uiaId:'system',ctxtId:'HomeScreen',contextSeq:1}, _contextTable: {Disclaimer: {controlProperties: {Dialog3Ctrl: {
    defaultSelectCallback(control, action) {if(action==='Global.Yes')fw.sendEventToMmui('common',action);}
  }}}}}};
  const fw = ctx.framework = {_browserShown: true, _frameworkState: 1, _FWK_STATE_IDLE: 1,
    _focusStack: [{id:'system'}], _currTmpltInstance: {contextInfo:{uiaId:'system',ctxtId:'HomeScreen',contextSeq:1}},
    common: {_cachedVuiState: null, getCommonTransitionData() {}}, multicontroller: {getMode: () => 'controllerActive'},
    getCurrentApp() {return this._currTmpltInstance.contextInfo.uiaId;},
    getCurrCtxtId() {return this._currTmpltInstance.contextInfo.ctxtId;}, getAppInstance(id) {return apps[id];},
    _initApp() {}, _processNewFwkState() {}, _multicontrollerEventHandler() {return 'stock input';},
    _focusStackChange(ids) {if(nativeFocus)nativeFocus.call(this,ids);else this._focusStack=ids;},
    _handleMessage(id,m) {
      if(id==='phone'&&m.msgId==='NoCallState'&&callEnd)callEnd.call(apps.phone,m);
      if(id==='common'&&m.msgId==='vuiState')this.common._cachedVuiState=m.params.payload.state;return 'stock message';},
    routeMmuiMsg(m) {
      if(m.msgType==='focusStack') {
        if(loading===m.appIdList[0].id)this._loadingAppJsObj=m;
        else this._focusStackChange(m.appIdList);
      }
      if(m.msgType==='ctxtChg'&&m.ctxtId!=='Idle') {
        cache(m);
        if(!background){if(deferContext)pendingContexts.push(m);else apply(m);}
      }
      if(m.msgType==='msg')return this._handleMessage(m.uiaId,m);
    }, sendEventToMmui(...args) {calls.push(args);},
    instantiateControl(id,parent,kind,props) {return {properties:props, divElt:{classList:{add(){}},style:{}},handleControllerEvent(){},setText1(){},setText2(){}};},
    destroyControl() {return 'destroyed';}};
  ctx.Websockets = function () {this._preInitGuiMsgQueue=[];this._waitMsgArray=[];this._hasInitGui=true;};
  ctx.Websockets.prototype._doRouteMmuiMsg=function(text) {
    let m;try {m=JSON.parse(text);}catch{return;}
    if(!this._hasInitGui)this._preInitGuiMsgQueue.push(m);else fw.routeMmuiMsg(m);
  };
  function cache(m) {
    const app=apps[m.uiaId] ||= {_contextTable:{}};
    if(contextHandler) {
      app.isContextDifferent=contextCompare;
      app.uiaId=m.uiaId;
      app.isContextDifferentFrom=x=>contextCompare(app._currentContext,x);
      app.handleContext=function(x){return contextHandler.call(this,x);};
      if(nativeContext){fw._appStack[m.uiaId]=true;nativeContext.call(fw,m);}
      else contextHandler.call(app,m);
    } else {app._currentContext=m;}
  }
  function apply(m) {
    fw._currTmpltInstance.contextInfo=apps[m.uiaId]._currentContext;
  }
  const context = vm.createContext(ctx);
  function source(name, root=folder) {vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),context,{filename:name});}
  if(process.argv[3])vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),context);
  source('carplay.js');
  fw.websockets=Object.assign(Object.create(ctx.Websockets.prototype),{_preInitGuiMsgQueue:[],_waitMsgArray:[],_hasInitGui:true});
  function supports() {
    source('runtime.js');source('dialog.js');source('settings.js');
    ctx.OpenConnect={autoshowState:()=>0,protected:()=>false};
  }
  if(load)supports();
  function send(m) {fw.websockets._doRouteMmuiMsg(JSON.stringify(m));}
  function focus(id='system') {send({msgType:'focusStack',appIdList:[{id}]});}
  function msg(id, payload, uiaId='carplay') {send({msgType:'msg',uiaId,msgId:id,params:{payload}});}
  function session(on, id='phone') {msg('SendCPSessionState',on ? {state:true,serialId:id,btMacAddress:''} : {state:false,serialId:'',btMacAddress:''});}
  function menu(wifi=false, nativeReady=true) {msg(wifi?'StatusMenuCarPlayWifi':'StatusMenuVisibleCarPlay',
    wifi?{appName:'carplay',appStatus:'Available'}:{appName:'carplay',state:'Visible'},'system');if(nativeReady)ready();}
  function ready(){msg('TimedSbn_CarplayConnected',{type:1});}
  function advance(ms=0) {
    const end=now+ms;let t;
    while((t=timers.filter(t=>t.live&&t.at<=end).sort((a,b)=>a.at-b.at)[0])) {
      now=t.at;t.live=false;if(++clock>10000)throw Error('timer loop');t.fn();
    }now=end;
  }
  function native(id, ctxt) {
    send({msgType:'ctxtChg',uiaId:id,ctxtId:ctxt,contextSeq:2});focus(id);
  }
  function connect(wifi=false) {session(true);menu(wifi);advance();}
  function count() {return calls.filter(v=>v[1]==='SelectCarPlay').length;}
  function event(type, values={}) {(events[type]||[]).forEach(fn=>fn({type,...values}));}
  focus();
  return {ctx, fw, state, source, supports, session, menu, ready, msg, send, native, focus, advance, count, connect, event, apps,
    background(id,ctxt,seq=90){background=true;try{send({msgType:'ctxtChg',uiaId:id,ctxtId:ctxt,contextSeq:seq});}finally{background=false;}},
    show(id){apply({uiaId:id});fw._processNewFwkState();},
    contexts(handler,compare){contextHandler=handler;contextCompare=compare;},
    phoneEnd(handler){callEnd=handler;},
    pendingTimers(){return timers.filter(t=>t.live).map(t=>t.at);},
    routing(proto){
      nativeContext=proto._contextChange;nativeFocus=proto._focusStackChange;
      fw._callHandleContext=proto._callHandleContext;fw._captureContext=()=>{};
      fw._appStack={};fw._appInstances=apps;fw.getCurrAppInstance=()=>apps[fw.getCurrentApp()];
      for(const [id,app] of Object.entries(apps)){app.uiaId=id;app.isContextDifferentFrom=x=>contextCompare(app._currentContext,x);}
    },
    delayApp(id){loading=id;},
    finishApp(proto){
      if(proto){
        fw._storeAppLoaded=id=>{fw._appStack[id]=true;};
        proto._appFinishedLoading.call(fw);
      }else fw._focusStackChange(fw._loadingAppJsObj.appIdList);
      loading=null;
    },
    defer(value=true){deferContext=value;},applyContext(){apply(pendingContexts.shift());fw._processNewFwkState();}};
}
let f=fixture();f.connect();assert.equal(f.count(),1,'quiet boot');
f.session(true);f.menu();f.advance();assert.equal(f.count(),1,'duplicate true');
f.session(false);f.connect(true);assert.equal(f.count(),2,'empty-ID disconnect');
let r=fixture(f.state);r.connect();assert.equal(r.count(),0,'connected reload');
r.session(false);r=fixture(r.state);r.connect();assert.equal(r.count(),1,'disconnected reload');
f=fixture({failName:true});f.connect();assert.equal(f.count(),1);assert.ok(f.state.storage.get('oc107').endsWith(':C'));
f.state.name='oc107:'+boot+':A';r=fixture(f.state);r.connect();assert.equal(r.count(),0,'fallback C beats stale A');
r.session(false);r.connect();assert.equal(r.count(),1,'verified A/A reconnect');
f=fixture();f.session(true);f.menu();f.event('mousedown');f.advance();assert.equal(f.count(),0,'touch departure');
f=fixture();f.session(true);f.menu();f.fw._multicontrollerEventHandler('goBack');f.advance();assert.equal(f.count(),0,'commander');
for(const late of [false,true]) {
  f=fixture();if(!late){f.session(true);f.menu();}
  f.fw.websockets._waitMsgArray.push(['{"msgType":"focusStack"}',10]);
  f.fw.websockets._doRouteMmuiMsg(['{"msgType":"focusStack"}',10]);
  f.fw.websockets._waitMsgArray=[];
  if(late){f.session(true);f.menu();}
  f.advance();assert.equal(f.count(),0,'forced flush loses focus trust');
  f.focus();f.advance();assert.equal(f.count(),1,'fresh safe focus restores trust');
}
f=fixture();f.fw.websockets._waitMsgArray.push(['reverse',3]);f.connect();assert.equal(f.count(),0);
f.advance(15001);f.fw.websockets._waitMsgArray=[];f.focus();f.advance();assert.equal(f.count(),0,'no renewed expiry');
f=fixture();f.fw.websockets._hasInitGui=false;f.session(true);f.menu();f.event('keydown',{keyCode:72});
f.fw.websockets._hasInitGui=true;
for(const m of f.fw.websockets._preInitGuiMsgQueue)f.fw.routeMmuiMsg(m);
f.advance();assert.equal(f.count(),0,'pre-init input wins');
for(const status of ['Connecting','ActiveCall','IncomingCall']) {
  f=fixture();f.msg('StatusPhoneCall',{phoneCallStatus:status},'system');f.connect();assert.equal(f.count(),0,status);
  f.msg('StatusPhoneCall',{phoneCallStatus:'NoCall'},'system');f.session(false);f.connect();assert.equal(f.count(),1,'later reconnect');
}
for(const end of ['RemoveStateSBN_SiriActive','TimedSBN_SiriError']) {
  f=fixture();f.msg('ShowStateSBN_SiriActive',{},'system');f.connect();assert.equal(f.count(),0,'Siri over Home');
  f.msg(end,{},'system');f.advance();assert.equal(f.count(),0);f.session(false);f.connect();assert.equal(f.count(),1);
}
f=fixture();f.native('audiosettings','AudioTab');f.connect();assert.equal(f.count(),0,'Settings');
f=fixture();f.native('system','DisplayOff');f.connect();assert.equal(f.count(),0,'DisplayOff');
f=fixture();f.native('fmradio','NowPlaying');f.connect();assert.equal(f.count(),1,'audio context uses stock selection');
for(const touch of [false,true]) {
  f=fixture();f.native('system','Disclaimer');f.fw._initApp('system');
  const button={_isEnabled:true,_hasFocus:true,divElt:{contains:v=>v==='agree'}};
  const dialog=f.fw._currTmpltInstance.dialog3Ctrl={buttonCtrl_0:button};
  f.session(true);f.menu();
  if(touch)f.event('mousedown',{target:'agree'});else f.fw._multicontrollerEventHandler('selectStart');
  f.advance();assert.equal(f.count(),0,'Agree held');
  if(touch)f.event('mouseup',{target:'agree'});else f.fw._multicontrollerEventHandler('select');
  f.apps.system._contextTable.Disclaimer.controlProperties.Dialog3Ctrl.defaultSelectCallback(dialog,'Global.Yes');
  f.native('system','HomeScreen');f.advance();assert.equal(f.count(),1,'stock Agree release');
}
f=fixture();f.ctx.OpenConnect={protected:()=>false,start(){},reopenUSB(){},cancelUSB(){},dispose(){return true;}};
f.session(true);f.menu();f.advance();assert.equal(f.count(),0,'opaque lookup held');
const old=f.fw.instantiateControl('system',f.ctx.document.body,'Dialog3Ctrl',{buttonConfig:{button1:{appData:'cancel'},button2:{appData:'install'}}});
f.fw.destroyControl(old);f.advance();f.session(false);f.connect();assert.equal(f.count(),1,'old Cancel releases lease');
// Critical messages can precede lazy installer modules; preserve their order.
for (const endBefore of [false,true]) {
  f=fixture({},false);
  f.msg('StatusPhoneCall',{phoneCallStatus:'IncomingCall'},'system');
  if(endBefore)f.msg('StatusPhoneCall',{phoneCallStatus:'NoCall'},'system');
  f.session(true);f.menu();
  if(!endBefore)f.msg('StatusPhoneCall',{phoneCallStatus:'NoCall'},'system');
  f.supports();f.advance();
  assert.equal(f.count(),endBefore?1:0,'call guard at actual edge, not module load');
}
f=fixture({},false);f.session(true);f.menu();f.supports();f.advance();assert.equal(f.count(),1,'early session/menu replay');
f=fixture({},false);f.msg('ShowStateSBN_SiriActive',{},'system');f.session(true);f.menu();
f.msg('RemoveStateSBN_SiriActive',{},'system');f.supports();f.advance();assert.equal(f.count(),0,'early Siri consumes edge');
f=fixture({},false);for(let i=0;i<33;i++)f.msg('StatusPhoneCall',{phoneCallStatus:'NoCall'},'system');
f.session(true);f.menu();f.supports();f.advance();assert.equal(f.count(),0,'bounded early queue overflow refuses selection');
f=fixture();f.session(true);f.menu();f.native('backupparking','Camera');f.advance();assert.equal(f.count(),0,'reverse defers');
f.native('system','HomeScreen');f.advance();assert.equal(f.count(),1,'reverse return resumes original edge');
f=fixture();f.session(true);f.menu();f.native('fmradio','NowPlaying');f.advance();assert.equal(f.count(),0,'ordinary user context departure cancels');
f=fixture();f.session(true);f.menu();f.native('netmgmt','Wifi');f.native('system','HomeScreen');f.advance();assert.equal(f.count(),0,'intervening Settings/native departure stays canceled');
console.log('CarPlay: boot/reconnect, provenance, input, focus, early events, calls, Siri and legacy ownership passed');
// USB script generations reuse the one boot-page observer and control wrappers.
f=fixture();
let d=f.fw.instantiateControl('system',f.ctx.document.body,'Dialog3Ctrl',{buttonConfig:{button1:{appData:'done'}}});
assert.equal(f.ctx.ocCarPlay.dialogs,1);
f.supports();assert.equal(f.ctx.ocCarPlay.dialogs,1,'module reload keeps existing modal accounting');
f.fw.destroyControl(d);f.advance();assert.equal(f.ctx.ocCarPlay.dialogs,0);
f.session(false);f.connect();assert.equal(f.count(),1,'modules bind once across generations');
// A native modal can appear between dialog.js and Settings support loading.
f=fixture({},false);f.source('runtime.js');f.source('dialog.js');
d=f.fw.instantiateControl('system',f.ctx.document.body,'Dialog3Ctrl',{buttonConfig:{button1:{appData:'done'}}});
f.fw.destroyControl(d);f.advance();f.source('settings.js');
assert.equal(f.ctx.ocCarPlay.dialogs,0);

if(process.argv[4]) {
  // Real archived CI17 loader/runtime/dialog/Settings, with local DOM/XHR only.
  function legacy(paused=false) {
    const x=fixture(), requests=[], intervals=[], nodes={}, loads=[];let modal;
    const token='a'.repeat(32), root=process.argv[4];
    const head={appendChild(node) {
      node.parentNode=head;nodes[node.id]=node;
      const run=()=>{x.source(node.src.split('/').at(-1),root);node.onload();};
      if(paused)loads.push(run);else run();
    },removeChild(node){delete nodes[node.id];node.parentNode=null;}};
    x.ctx.document.createElement=()=>({});
    const query=x.ctx.document.querySelector;
    x.ctx.document.querySelector=s=>s==='head'?head:query(s);
    x.ctx.document.getElementById=id=>nodes[id]||null;
    x.ctx.utility={loadScript(src,props,done){head.appendChild({...props,src,onload:done});}};
    x.ctx.setInterval=fn=>{intervals.push(fn);return fn;};
    x.ctx.XMLHttpRequest=function(){this.open=()=>{};this.setRequestHeader=()=>{};this.abort=()=>{};this.send=body=>{this.body=body;requests.push(this);};};
    const create=x.fw.instantiateControl;
    x.fw.instantiateControl=function(){return modal=create.apply(this,arguments);};
    nodes['oc-usb-loader']={src:'file:///tmp/legacy/loader.js',ocToken:token,parentNode:head};
    x.source('loader.js',root);
    const state={ok:true,revision:'b'.repeat(32),installed:true,retained:false,conflict:false,restart:false,pending:false,touch:1,warning:1,notice:'-',version:'0.3.0-dev.17',installedVersion:'0.3.0-dev.18'};
    function reply(v){const q=requests.at(-1);q.status=200;q.readyState=4;q.responseText=JSON.stringify(v);q.onreadystatechange();}
    function resume(){while(loads.length)loads.shift()();reply(state);intervals.forEach(fn=>fn());}
    if(!paused)resume();
    return Object.assign(x,{requests,reply,resume,tick:()=>intervals.forEach(fn=>fn()),state,modal:()=>modal});
  }
  f=legacy(true);assert.ok(f.ctx.__ocUSBLoading,'actual CI17 acquisition marker');
  f.connect();assert.equal(f.count(),0,'paused old loader blocks current dev18 client');
  f.resume();d=f.modal();d.properties.defaultSelectCallback(d,'cancel');f.advance();
  f.session(false);f.connect();assert.equal(f.count(),1,'resumed legacy Cancel unlocks next connection');
  f=legacy();assert.equal(f.ctx.__ocUSBLoading,undefined,'old loader releases bootstrap marker');
  f.connect();assert.equal(f.count(),0,'actual CI17 chooser holds lease after marker clears');
  d=f.modal();d.properties.defaultSelectCallback(d,'cancel');f.advance();
  f.session(false);f.connect();assert.equal(f.count(),1,'actual CI17 Cancel releases lease');
  f=legacy();d=f.modal();d.properties.defaultSelectCallback(d,'install');
  f.reply({ok:false,error:'stale_state'});f.reply(f.state);f.tick();
  d=f.modal();assert.equal(d.properties.buttonConfig.button1.appData,'done');
  d.properties.defaultSelectCallback(d,'done');f.advance();
  f.session(false);f.connect();assert.equal(f.count(),1,'refused old Install Done releases settled owner');
  console.log('Archived CI17 loader: chooser Cancel and refused Install Done recover autoshow');
}

for(const [id,context] of [['system','SystemWarning'],['sysupdate','Update'],['mobile911','Emergency'],['new-app','Unknown']]) {
  f=fixture();f.native(id,context);f.connect();assert.equal(f.count(),0,'unsupported or safety context '+id);
}

// RAM support can finish after Mazda has already instantiated Disclaimer.
f=fixture({},false);f.native('system','Disclaimer');
const lateButton={_isEnabled:true,_hasFocus:true,divElt:{contains:v=>v==='agree'}};
const lateDialog=f.fw._currTmpltInstance.dialog3Ctrl={buttonCtrl_0:lateButton,properties:{...f.apps.system._contextTable.Disclaimer.controlProperties.Dialog3Ctrl}};
f.supports();f.session(true);f.menu();f.event('mousedown',{target:'agree'});f.event('mouseup',{target:'agree'});
lateDialog.properties.defaultSelectCallback(lateDialog,'Global.Yes');f.native('system','HomeScreen');f.advance();
assert.equal(f.count(),1,'already instantiated stock Agree callback is observed');

// Pending camera context precedes both its focus stack and its visible template.
f=fixture();f.apps.backupparking={_currentContext:{ctxtId:'TVMCameraDisplay'}};
f.session(true);f.defer();
f.send({msgType:'ctxtChg',uiaId:'backupparking',ctxtId:'TVMCameraDisplay',contextSeq:2});
f.menu();f.advance();assert.equal(f.count(),0,'pending loaded camera retains priority over old Home');
f.focus('backupparking');f.applyContext();f.advance();assert.equal(f.count(),0,'visible camera holds');
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});
f.focus();f.advance();assert.equal(f.count(),0,'safe focus without applied return still holds');
f.applyContext();f.advance();assert.equal(f.count(),1,'confirmed safe return releases original intent');
// Even a return template cannot reuse Home focus from before the camera request.
f=fixture();f.session(true);f.defer();
f.send({msgType:'ctxtChg',uiaId:'backupparking',ctxtId:'TVMCameraDisplay',contextSeq:2});
f.menu();f.applyContext();f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});
f.applyContext();f.advance();assert.equal(f.count(),0,'return requires a post-camera applied safe focus');
f.focus();f.advance();assert.equal(f.count(),1);
// A later Home action is not exempt merely because reverse happened earlier.
f=fixture();f.session(true);f.native('backupparking','TVMCameraDisplay');
f.native('system','HomeScreen');f.advance();
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});
f.menu();f.advance();assert.equal(f.count(),0,'post-return user departure consumes edge');
// Origin identity is a value snapshot: Mazda may mutate the previous context.
f=fixture();f.session(true);f.fw._currTmpltInstance.contextInfo.contextSeq=2;
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:2});
f.menu();f.advance();assert.equal(f.count(),0,'same Home with a new sequence is user departure');
for(const early of [false,true]) {
  f=fixture({},!early);f.session(true);
  f.msg('vuiState',{state:'Listening'},'common');f.msg('vuiState',{state:'Idle'},'common');
  if(early)f.supports();f.menu();f.advance();assert.equal(f.count(),0,'voice consumes edge before menu or support readiness');
  f.session(false);f.connect();assert.equal(f.count(),1,'voice end permits later reconnect');
}
f=fixture();f.session(true);f.fw.common._cachedVuiState='Processing';f.fw._processNewFwkState();f.advance();
f.fw.common._cachedVuiState='Idle';f.menu();f.advance();assert.equal(f.count(),0,'positive cache cancels before menu');
for(const wifi of [false,true]) {
  f=fixture();f.session(true);f.menu(wifi);
  f.msg(wifi?'StatusMenuCarPlayWifi':'StatusMenuVisibleCarPlay',wifi?{appName:'carplay',appStatus:'Unavailable'}:{appName:'carplay',state:'Hidden'},'system');
  f.advance();assert.equal(f.count(),0,'withdrawn menu cannot release intent');
  f.menu(wifi);f.advance();assert.equal(f.count(),1,'fresh availability can release still-unexpired edge');
}
f=fixture();f.session(true);f.menu();
f.msg('StatusMenuCarPlayWifi',{appName:'carplay',appStatus:'Unavailable'},'system');
f.advance();assert.equal(f.count(),1,'unrelated transport withdrawal preserves matching ready mark');
// An unreadable store may hide this boot's consumed mark; only false re-arms.
f=fixture({failName:true});f.connect();
f.state.failName=false;f.state.failRead=true;f.state.name='oc107:'+boot+':A';
r=fixture(f.state);r.connect();assert.equal(r.count(),0,'throwing fallback read cannot repeat consumed connection');
r.state.failRead=false;r.session(true);r.menu();r.advance();assert.equal(r.count(),0,'read recovery alone cannot re-arm');
r.session(false);r.connect();assert.equal(r.count(),1,'actual disconnect reconciles both stores');
f=fixture();f.connect();f.state.failNameRead=true;r=fixture(f.state);r.connect();assert.equal(r.count(),0,'throwing primary read is also ambiguous');
r.state.failNameRead=false;r.session(false);r.connect();assert.equal(r.count(),1);

function bootClient(notice='-') {
  const x=fixture({},false), loads=[], intervals=[], requests=[], token='a'.repeat(32);
  const query=x.ctx.document.querySelector;
  const head={appendChild(node){loads.push(()=>{x.source(node.src.split('/').at(-1));node.onload();});}};
  x.ctx.document.querySelector=s=>s==='head'?head:s.includes('open-connect-version')?{getAttribute:()=> '0.3.0-dev.18'}:
    s.includes('open-connect-notice')?{getAttribute:()=>notice}:query(s);
  x.ctx.document.createElement=()=>({});
  x.ctx.setInterval=fn=>{intervals.push(fn);return fn;};
  x.ctx.XMLHttpRequest=function(){this.open=()=>{};this.setRequestHeader=()=>{};this.abort=()=>{};this.send=body=>{this.body=body;requests.push(this);};};
  x.source('runtime.js');
  return Object.assign(x,{token,requests,complete(){while(loads.length)loads.shift()();},tick(){intervals.forEach(fn=>fn());}});
}
f=bootClient();f.session(true);f.menu();f.advance();assert.equal(f.count(),0,'ordinary boot awaits real support callbacks');
f.complete();assert.equal(f.count(),1,'ready callback pumps first connection without another message');
f=bootClient('installed');f.complete();f.tick();assert.equal(f.requests.length,1);
f.advance(34000);f.session(true);f.advance();f.ctx.OpenConnect.cancelUSB(f.token);
f.advance(1001);f.menu();f.advance();assert.equal(f.count(),0,'proof expiry cannot send the same canceled edge');
f.session(false);f.connect();assert.equal(f.count(),1,'expired superseded proof does not block later sessions');
console.log('Astra regressions: pending reverse, ownership, proof expiry, startup, input/voice, menu withdrawal and storage ambiguity passed');

// Stock GuiFramework treats Idle as a no-op, including background CarPlay.
f=fixture();f.send({msgType:'ctxtChg',uiaId:'carplay',ctxtId:'Idle',contextSeq:7});f.focus();
f.connect();assert.equal(f.count(),1,'background Idle does not block a Home connection');
f.session(false);f.send({msgType:'ctxtChg',uiaId:'carplay',ctxtId:'Idle',contextSeq:8});f.connect();
assert.equal(f.count(),2,'background Idle also preserves later reconnects');
f=fixture();f.session(true);f.defer();
f.send({msgType:'ctxtChg',uiaId:'backupparking',ctxtId:'TVMCameraDisplay',contextSeq:2});
f.send({msgType:'ctxtChg',uiaId:'carplay',ctxtId:'Idle',contextSeq:7});f.menu();f.advance();
assert.equal(f.count(),0,'ignoring Idle cannot replace a real pending camera transition');
f.focus('backupparking');f.applyContext();f.advance();assert.equal(f.count(),0);
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();f.applyContext();f.advance();
assert.equal(f.count(),1,'original pending reverse still requires a confirmed safe return');

// DisplayOff is irreversible for the current generation, even before lazy
// Settings evaluation and after the latest context has already become Home.
f=bootClient();f.native('system','Disclaimer');f.session(true);f.menu();
f.native('system','DisplayOff');f.native('system','HomeScreen');
f.complete();f.advance();assert.equal(f.count(),0,'early DisplayOff survives Home replacement');
f.session(false);f.connect();assert.equal(f.count(),1,'DisplayOff does not block an actual subsequent connection');

// Applied reverse return must be recorded before another MMUI event, without
// depending on whether the zero-delay eligibility timer gets a turn.
for(const yieldTimer of [false,true]) {
  f=fixture();f.session(true);f.native('backupparking','TVMCameraDisplay');
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();
  if(yieldTimer)f.advance();
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:4});f.menu();f.advance();
  assert.equal(f.count(),0,'second Home entry cancels with timer turn='+yieldTimer);
}
// The first session can precede both a validator binding and menu readiness.
f=bootClient('installed');f.session(true);
assert.doesNotThrow(()=>f.complete(),'installed-notice ownership query waits for validator');
assert.equal(f.count(),0);f.menu();f.tick();assert.equal(f.requests.length,1);
const proof=f.requests[0];proof.status=200;proof.readyState=4;
proof.responseText=JSON.stringify({ok:true,revision:'b'.repeat(32),installed:true,retained:false,conflict:false,
  restart:false,pending:false,touch:1,warning:1,notice:'installed',version:'0.3.0-dev.18',
  installedVersion:'0.3.0-dev.18',carplayAutoshow:1,carplayAutoshowCurrent:1,completionReady:true});
proof.onreadystatechange();f.advance();assert.equal(f.count(),0,'completion proof keeps priority after validation binds');
console.log('Final review regressions: Idle no-op, early DisplayOff, event-ordered reverse return and lazy validator passed');
// Replay the same reverse/Home ordering when all messages preceded Settings.
f=bootClient();f.session(true);f.native('backupparking','TVMCameraDisplay');
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:4});f.menu();
f.complete();f.advance();assert.equal(f.count(),0,'second lazy Home entry cannot become the reverse return');
f=bootClient();f.session(true);f.native('backupparking','TVMCameraDisplay');
f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();f.menu();
f.complete();f.advance();assert.equal(f.count(),1,'one safe lazy reverse return preserves startup opportunity');

// Connections can start while a temporary context is already on screen.
for(const [id,ctx] of [['backupparking','TVMCameraDisplay'],['system','Disclaimer']]) {
  for(const yieldTimer of [false,true]) {
    f=fixture();f.native(id,ctx);f.session(true);
    f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();
    if(yieldTimer)f.advance();
    f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:4});f.menu();f.advance();
    assert.equal(f.count(),0,'temporary-origin second Home cancels '+ctx+' timer='+yieldTimer);
  }
  f=fixture();f.native(id,ctx);f.session(true);
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();f.menu();f.advance();
  assert.equal(f.count(),1,'single safe return remains eligible from '+ctx);
}

// A later reverse interruption must retain the safe screen established after
// connecting on a temporary screen, including before lazy Settings loads.
for(const lazy of [false,true]) {
  for(const [id,ctx] of [['backupparking','TVMCameraDisplay'],['system','Disclaimer']]) {
    for(const returned of ['HomeScreen','Entertainment']) {
      for(const yieldTimer of [false,true]) {
        f=lazy?bootClient():fixture();f.native(id,ctx);f.session(true);
        f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();
        if(yieldTimer)f.advance();
        f.native('backupparking','TVMCameraDisplay');
        f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:returned,contextSeq:5});f.focus();f.menu();
        if(lazy)f.complete();f.advance();
        assert.equal(f.count(),returned==='HomeScreen'?1:0,
          'temporary '+ctx+' -> Home -> reverse -> '+returned+' lazy='+lazy+' timer='+yieldTimer);
      }
    }
  }
}
console.log('Temporary-origin reverse preserves Home baseline: ready/lazy Home and Entertainment controls passed');

function mutationReplay(handler,compare,label) {
  f=bootClient();f.contexts(handler,compare);f.native('system','Disclaimer');f.session(true);
  f.native('backupparking','TVMCameraDisplay');
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:13});f.focus();
  const first=f.apps.system._currentContext;
  assert.ok(f.ctx.ocCarPlay.early.some(m=>m._cp.ctx&&m._cp.ctx[1]==='HomeScreen'&&m._cp.ctx[2]===13),'applied Home identity snapshotted');
  assert.ok(first,'first Home retained by BaseApp');
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:14});
  assert.equal(first.contextSeq,14,label+' really mutated the prior received object');
  f.menu();f.complete();f.advance();assert.equal(f.count(),0,label+' preserves original event sequence across lazy load');
  f.session(false);f.connect();assert.equal(f.count(),1,label+' permits a later real connection');
  f=bootClient();f.contexts(handler,compare);f.native('system','Disclaimer');f.session(true);
  f.native('backupparking','TVMCameraDisplay');
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:13});f.focus();f.menu();
  f.complete();f.advance();assert.equal(f.count(),1,label+' single-return control');
}
function differentContext(a,b) {return !a||!b||a.uiaId!==b.uiaId||a.ctxtId!==b.ctxtId;}
mutationReplay(function(m) {
  if(this.isContextDifferent(this._currentContext,m))this._currentContext=m;
  else this._currentContext.contextSeq=m.contextSeq;
},differentContext,'authored mutable-context fixture');
if(process.argv[3]) {
  const stock={guiConfig:{testMode:false},log:{addSrcFile(){},debug(){},info(){},warn(){},error(){},writeError(){}}};
  const base=path.join(path.dirname(process.argv[3]),'BaseApp.js');
  vm.runInNewContext(fs.readFileSync(base,'utf8'),stock,{filename:base});
  mutationReplay(stock.BaseApp.prototype._handleContext,stock.BaseApp.prototype._isContextDifferent,'stock v74 BaseApp');
  console.log('Stock BaseApp Home 13 -> 14 mutation replay passed');
}
console.log('Remaining P2 regressions: temporary-origin baseline and immutable early contexts passed');

// Mazda caches non-focused app contexts without changing the displayed page.
// Contacts can arrive before or after the CarPlay edge, including during load.
function backgroundReplay(stock) {
function make(lazy) {
  const x=lazy?bootClient():fixture();
  if(stock){x.contexts(stock.BaseApp.prototype._handleContext,stock.BaseApp.prototype._isContextDifferent);x.routing(stock.GuiFramework.prototype);if(stock.phoneApp)x.phoneEnd(stock.phoneApp.prototype._NoCallStateMsgHandler);}
  return x;
}
for(const lazy of [false,true]) {
  for(const before of [false,true]) {
    for(const [id,ctxt] of [['contacts','Contacts'],['sms','Inbox'],['btaudio','NowPlaying']]) {
      f=make(lazy);
      if(before)f.background(id,ctxt);f.session(true);
      if(!before)f.background(id,ctxt);f.menu();
      if(lazy)f.complete();f.advance();
      assert.equal(f.count(),1,'background cache does not block Home '+id+' before='+before+' lazy='+lazy);
    }
  }
  // Focus makes an otherwise background context a real departure. A later
  // background update cannot erase it, even if Home returns before lazy load.
  f=make(lazy);f.session(true);
  f.background('fmradio','NowPlaying',2);f.background('contacts','Contacts',3);
  f.focus('fmradio');f.show('fmradio');f.focus();f.show('system');f.menu();
  if(lazy)f.complete();f.advance();
  assert.equal(f.count(),0,'applied audio focus departure survives background cache and return lazy='+lazy);
  for(const [id,ctxt] of [['phone','ActiveCall'],['system','DisplayOff']]) {
    f=make(lazy);f.session(true);f.background(id,ctxt);f.menu();
    if(lazy)f.complete();f.advance();assert.equal(f.count(),0,'background safety remains binding '+id+' lazy='+lazy);
  }
  f=make(lazy);f.session(true);f.background('backupparking','TVMCameraDisplay');f.menu();
  if(lazy)f.complete();f.advance();assert.equal(f.count(),0,'pending reverse remains binding lazy='+lazy);
  f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();f.advance();
  assert.equal(f.count(),1,'safe focused return releases reverse lazy='+lazy);
  f=make(lazy);f.native('emnavi','Active');f.session(true);f.menu();
  if(lazy)f.complete();f.advance();assert.equal(f.count(),1,'active Mazda Nav is eligible lazy='+lazy);
}
f=make(false);f.native('emnavi','NaviPreparing');f.connect();
assert.equal(f.count(),0,'unqualified Nav preparation stays guarded');
// Priority requests can precede the connection while their templates and
// focus changes have not applied. Background cache traffic cannot clear them.
for(const lazy of [false,true]) {
  for(const [id,ctxt,nav] of [['backupparking','TVMCameraDisplay',false],['phone','ActiveCall',false],['system','DisplayOff',true]]) {
    f=make(lazy);if(nav)f.native('emnavi','Active');
    f.background(id,ctxt);f.session(true);f.background('contacts','Contacts');f.menu();
    if(lazy)f.complete();f.advance();
    assert.equal(f.count(),0,'pre-edge priority '+ctxt+' lazy='+lazy);
  }
  for(const contacts of [false,true]) {
    f=make(lazy);f.session(true);f.background('backupparking','TVMCameraDisplay');
    if(contacts)f.background('contacts','Contacts');f.focus();f.menu();
    if(lazy)f.complete();f.advance();
    assert.equal(f.count(),0,'unchanged Home cannot acknowledge pending reverse contacts='+contacts+' lazy='+lazy);
    f.focus('backupparking');f.show('backupparking');
    f.background('backupparking','Idle');
    if(contacts)f.background('contacts','Contacts');f.focus();f.show('system');f.advance();
    assert.equal(f.count(),1,'actual cached Home return releases reverse contacts='+contacts+' lazy='+lazy);
  }
  f=make(lazy);f.session(true);f.background('contacts','Contacts',2);f.delayApp('contacts');
  f.focus('contacts');f.focus();f.finishApp(stock&&stock.GuiFramework.prototype);
  f.show('contacts');f.focus();f.show('system');f.menu();
  if(lazy)f.complete();f.advance();
  assert.equal(f.count(),0,'delayed applied Contacts departure survives newer Home ingress lazy='+lazy);
}
for(const pairs of [16,40]) {
  f=make(true);f.session(true);
  for(let i=0;i<pairs;i++){f.background('contacts','Contacts',10+i);f.focus();}
  assert.ok(f.ctx.ocCarPlay.early.length<10,'unchanged focus/background cache stay outside bounded history');
  f.menu();f.complete();f.advance();assert.equal(f.count(),1,'benign startup traffic retains first edge pairs='+pairs);
  f.session(false);f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:50});
  f.focus();f.connect();assert.equal(f.count(),2,'benign startup traffic retains reconnect pairs='+pairs);
}
// All native call dialogs retain priority before a phone-focus or status event.
for(const lazy of [false,true]) {
  for(const ctxt of ['IncomingCall','ActiveCall','CallWaiting','MultipleCallWaiting','BTMultipleCall']) {
    f=make(lazy);f.background('phone',ctxt);f.session(true);f.menu();
    if(lazy)f.complete();f.advance();assert.equal(f.count(),0,'pre-edge call dialog '+ctxt+' lazy='+lazy);
    f.msg('NoCallState',{},'phone');f.session(false);f.connect();
    assert.equal(f.count(),1,'explicit call end permits subsequent connection '+ctxt+' lazy='+lazy);
  }
  for(const tick of [false,true]) {
    f=make(lazy);f.session(true);f.native('backupparking','TVMCameraDisplay');
    f.background('system','DisplayOff');if(tick)f.advance();
    f.send({msgType:'ctxtChg',uiaId:'system',ctxtId:'HomeScreen',contextSeq:3});f.focus();f.menu();
    if(lazy)f.complete();f.advance();
    assert.equal(f.count(),0,'DisplayOff consumes the generation during camera ownership lazy='+lazy+' tick='+tick);
    f.session(false);f.connect();assert.equal(f.count(),1,'observed wake allows a later connection');
  }
  for(const refocus of [false,true]) {
    f=make(lazy);f.background('phone','ActiveCall');const cached=f.apps.phone._currentContext;
    f.msg('NoCallState',{},'phone');assert.equal(f.apps.phone._currentContext,cached,'NoCallState retains native cached context');
    if(refocus){f.focus('phone');f.show('phone');}
    if(lazy)f.complete();
    if(refocus){f.connect();assert.equal(f.count(),0,'phone display still guards selection after call-end');}
    f.focus();f.show('system');f.session(false);f.connect();
    assert.equal(f.count(),1,'cached phone focus cannot revive an ended call refocus='+refocus+' lazy='+lazy);
    f.session(false);f.background('phone','ActiveCall',91);f.connect();
    assert.equal(f.count(),1,'a genuinely new call context restores priority');
  }
}
// Missing critical history is not resolved by an unrelated CarPlay disconnect.
for(const priority of ['camera','call']) {
  f=make(true);for(let i=0;i<32;i++)f.menu(false,false);
  if(priority==='camera')f.background('backupparking','TVMCameraDisplay');
  else f.msg('StatusPhoneCall',{phoneCallStatus:'IncomingCall'},'system');
  assert.equal(f.ctx.ocCarPlay.early.length,32,'bounded queue actually filled');
  assert.ok(f.ctx.ocCarPlay.busy&8,'critical history was dropped');
  f.session(true);f.menu();f.complete();f.advance();assert.equal(f.count(),0,'overflow prevents first selection '+priority);
  f.session(false);f.connect();assert.equal(f.count(),0,'disconnect cannot resolve dropped '+priority+' history');
}
// Native SessionActive/WifiAvailable precede resource_status becoming ready.
// Only a delivered native ready message releases the request; time alone cannot.
for(const lazy of [false,true]) {
  f=make(lazy);f.session(true);f.menu(false,false);if(lazy)f.complete();
  f.advance();assert.equal(f.count(),0,'menu availability alone cannot select lazy='+lazy);
  f.advance(200);f.ready();f.advance();assert.equal(f.count(),1,'native ready releases immediately lazy='+lazy);
  f.ready();f.menu();f.advance();assert.equal(f.count(),1,'duplicate ready never retries');
  f=make(lazy);f.session(true);f.menu(false,false);if(lazy)f.complete();
  f.advance(750);assert.equal(f.count(),0,'elapsed time cannot substitute for native readiness');
  f.advance(1000);assert.equal(f.count(),0,'still waiting for genuine native readiness');
  f.ready();f.advance();assert.equal(f.count(),1,'a later ready cue releases once');
  f=make(lazy);f.session(true);f.menu(false,false);f.native('syssettings','SystemTab');
  if(lazy)f.complete();f.advance(751);assert.equal(f.count(),0,'Settings departure cancels pending readiness');
  f=make(lazy);f.session(true);f.menu(false,false);f.native('backupparking','TVMCameraDisplay');
  if(lazy)f.complete();f.ready();f.advance(751);assert.equal(f.count(),0,'camera keeps priority over ready cue');
  f.native('system','HomeScreen');f.advance();assert.equal(f.count(),1,'confirmed safe return may use delivered ready cue');
}
f=make(false);f.session(true);f.menu(false,false);
const pendingReady={msgType:'msg',uiaId:'carplay',msgId:'TimedSbn_CarplayConnected',params:{payload:{type:1}},
  _cp:{seq:f.ctx.ocCarPlay.edge().seq+100,delivered:false}};
f.ctx.ocCarPlay.signal(pendingReady);f.advance();assert.equal(f.count(),0,'ingress alone is not delivered ready');
pendingReady._cp.delivered=true;f.ctx.ocCarPlay.pump();assert.equal(f.count(),1,'delivered native ready releases selection');
f=make(false);f.session(true);f.ready();f.advance();assert.equal(f.count(),0,'ready alone still requires matching menu');
f.menu(false,false);f.advance();assert.equal(f.count(),1,'ready before menu remains eligible');
f=make(false);f.ready();f.session(true);f.menu(false,false);f.advance();
assert.equal(f.count(),0,'stale ready before session does not release selection');
f.advance(750);assert.equal(f.count(),0,'stale cue is not replaced by elapsed time');
f.ready();f.advance();assert.equal(f.count(),1);
f=make(false);f.session(true);f.menu(false,false);f.advance(500);f.session(false);
f.session(true);f.menu(false,false);f.advance(250);assert.equal(f.count(),0,'elapsed time cannot release the new generation');
f.ready();f.advance();assert.equal(f.count(),1,'new generation native ready releases once');
f=make(true);f.session(true);f.menu(false,false);f.ready();
assert.ok(f.ctx.ocCarPlay.early.some(m=>m.msgId==='TimedSbn_CarplayConnected'),'native ready retained before Settings support loads');
f.complete();f.advance();assert.equal(f.count(),1,'early ready replays with original generation');
for(const lazy of [false,true]) {
  for(const nav of [false,true]) {
    for(const menuAt of [35,810]) {
      f=make(lazy);if(nav)f.native('emnavi','Active');f.session(true);
      f.advance(menuAt);f.menu(false,false);if(lazy)f.complete();f.advance();
      assert.equal(f.count(),0,'menu at '+menuAt+' cannot bypass missing ready lazy='+lazy+' nav='+nav);
      if(menuAt<750){f.advance(750-menuAt);assert.equal(f.count(),0,'750ms does not dispatch');}
      f.advance(900-Math.max(menuAt,750));f.ready();f.advance();
      assert.equal(f.count(),1,'slow native ready dispatches at900ms lazy='+lazy+' nav='+nav);
    }
  }
}
f=make(false);f.session(true);
for(let i=0;i<8;i++){
  f.menu(false,false);f.msg('StatusMenuVisibleCarPlay',{appName:'carplay',state:'Hidden'},'system');
}
f.advance();assert.deepEqual(f.pendingTimers(),[15000],'visibility cycles leave only the original expiry timer');
f.session(false);f.advance();assert.deepEqual(f.pendingTimers(),[],'disconnect leaves no readiness/fallback timer');
f=make(false);f.session(true);f.menu(false,false);f.fw._frameworkState=2;f.advance(15001);
f.fw._frameworkState=1;f.ready();f.advance();assert.equal(f.count(),0,'readiness cannot renew expired intent');
f=make(false);
let idleTimers=0;
const origSetTimeout=f.ctx.setTimeout;
f.ctx.setTimeout=(fn,ms)=>{idleTimers++;return origSetTimeout(fn,ms);};
for(let i=0;i<100;i++){
  f.msg('StatusUpdateAudio',{value:i},'system');
  f.advance();
}
assert.equal(idleTimers,0,'idle UI messages schedule zero timers without a pending connection');
assert.deepEqual(f.pendingTimers(),[],'no pending timers after idle traffic');
f.ctx.setTimeout=origSetTimeout;
f.msg('StatusPhoneCall',{phoneCallStatus:'IncomingCall'},'system');
f.session(true);f.menu(false,false);f.ready();f.advance();
assert.equal(f.count(),0,'pre-connection safety tracking still suppresses after idle traffic');
console.log('Live regressions: non-focused cache, applied focus history, safety priority, active Nav and idle timer guard passed');

}
backgroundReplay();
if(process.argv[3]) {
  const stock={guiConfig:{testMode:false},log:{addSrcFile(){},debug(){},info(){},warn(){},error(){},writeError(){}}};
  for(const name of ["BaseApp.js","GuiFramework.js"]) {
    const source=path.join(path.dirname(process.argv[3]),name);
    vm.runInNewContext(fs.readFileSync(source,"utf8"),stock,{filename:source});
  }
  if(process.argv[5]) {
    stock.framework={registerAppLoaded(){}};stock.clearInterval=()=>{};
    vm.runInNewContext(fs.readFileSync(process.argv[5],'utf8'),stock,{filename:process.argv[5]});
  }
  backgroundReplay(stock);
  console.log("Exact stock GuiFramework context/cache/focus and BaseApp replays passed");
}
