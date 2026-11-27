const assert=require('node:assert/strict'),fixture=require('./runtime-fixture.js');
const folder=process.argv[2];
let f=fixture(folder);f.install();
assert.ok(f.ctx.OpenConnect);assert.equal(f.requests.length,0);
const looked=f.lookups;f.advance(60000);assert.equal(f.lookups,looked,'idle Settings never polls the app');
f.nativeSettings();const owner=f.ctx.OpenConnect,menus=f.ctx.OpenConnectSettings,dialogs=f.ctx.OpenConnectInstaller;
const callback=f.list.properties.selectCallback;
f.usb();assert.equal(f.requests.length,1);assert.match(f.requests[0].url,/:15557/);
assert.equal(f.requests[0].body.split('|')[3],'settings');
f.tap();assert.equal(f.requests.length,2,'Settings read starts while USB metadata remains pending');
assert.match(f.requests[1].url,/:15555/);assert.equal(f.requests[1].body.split('|')[3],'settings');
f.reply(f.requests[1],f.state());assert.equal(f.pages.length,1);f.endAnimations();
assert.equal(f.ctx.OpenConnect,owner);assert.equal(f.ctx.OpenConnectSettings,menus);assert.equal(f.ctx.OpenConnectInstaller,dialogs);
assert.equal(f.list.properties.selectCallback,callback);
f.advance(14000);assert.equal(f.ctx.OpenConnect,owner);assert.equal(f.pages.length,1);
f.reply(f.requests[0],f.metadata());f.advance(0);assert.equal(f.dialog,undefined,'USB does not show a Home popup over Settings');
f.closeUSB();f.advance(1100);assert.equal(f.ctx.OpenConnect,owner);assert.equal(f.list.properties.selectCallback,callback);
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.equal(f.operation('dismiss').length,0,'physical removal is programmatic close');
for(const stage of [0]){
 f=fixture(folder);f.install();f.nativeSettings();const installed=f.ctx.OpenConnect,select=f.list.properties.selectCallback;
 f.usb(stage);f.closeUSB();f.flush();f.advance(0);
 assert.equal(f.ctx.OpenConnect,installed);assert.equal(f.list.properties.selectCallback,select);
 assert.equal(f.requests.length,0,'removed delayed popup does not begin a metadata read');
}
f=fixture(folder,{lateApp:true});f.install();f.nativeSettings();f.tap();f.reply(f.requests[0],f.state());assert.equal(f.pages.length,1);
f=fixture(folder);f.install();f.nativeSettings();f.tap();f.advance(12000);
assert.match(f.dialog.props.title,/Settings unavailable/);assert.equal(f.pages.length,0);
f=fixture(folder);f.install();f.nativeSettings();f.tap();f.homeScreen();f.advance(12000);assert.equal(f.dialog,undefined);
f=fixture(folder);f.install();assert.equal(f.ctx.OpenConnect.openSettings(),true);
assert.equal(f.requests[0].body.split('|')[3],'settings');f.reply(f.requests[0],f.state());f.advance(200);
assert.equal(f.pages.length,1);assert.ok(f.calls.some(c=>c[1]==='SelectSettings'));f.assertNative();
assert.equal([...f.timers.values()].filter(t=>t.repeat===200).length,0);
f=fixture(folder);f.install();f.ctx.OpenConnect.openSettings();f.nativeSettings();f.reply(f.requests[0],f.state());
assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0,'late open intent cannot move a user already elsewhere');
console.log('Installed Settings remains stable and independent through USB loading, slow verification and removal');

// Browser intervals remain registered while invoking their callback, so clearing
// oneself must win over rescheduling. This is also the real fromHome contract.
f=fixture(folder);let ticks=0;
const interval=f.ctx.setInterval(()=>{ticks++;f.ctx.clearInterval(interval);},200);
f.advance(1000);assert.equal(ticks,1);assert.equal(f.timers.has(interval),false);

function select(f,key,params){const p=f.pages.at(-1);p.list2Ctrl.selectCallback(p.list2Ctrl,key,params);f.endAnimations();}
function warm(extra={}){
 const x=fixture(folder);x.install();x.nativeSettings();x.tap();x.reply(x.requests[0],x.state(extra));x.endAnimations();return x;
}
function identities(f,send){
 assert.equal(f.host.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.handleControllerEvent,f.oldInput);
 assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);assert.equal(f.fw.sendEventToMmui,send);
}
// A foreign admitted operation still owns input while its progress is suspended.
// A cached Settings tap must not install wrappers beneath resumed progress.
f=warm();f.homeScreen();const nativeSend=f.fw.sendEventToMmui;
f.usb();f.reply(f.requests.at(-1),f.metadata());f.advance(0);f.pick('install');
const write=f.operation('install')[0];assert.ok(write);f.nativeSettings();const count=f.pages.length;
f.tap();assert.equal(f.pages.length,count);assert.equal(f.host.handleControllerEvent,f.oldInput);assert.equal(f.fw.sendEventToMmui,nativeSend);
f.advance(1000);assert.equal(f.dialog,undefined,'USB progress resumes only at idle Home');
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.advance(1000);assert.equal(f.dialog.props.contentStyle,'style27');
f.ctx.OpenConnectMaintenance.close();identities(f,nativeSend);
f.reply(write,f.state({restart:true}));assert.equal(f.operation('restart').length,0,'closed epoch ignores late write reply');

// An unadmitted recovery read remains transparent to an existing custom page.
f=warm();const page=f.pages.at(-1),pageInput=f.host.handleControllerEvent,pageTransition=f.fw.common.getCommonTransitionData,pageSend=f.fw.sendEventToMmui;
f.usb();f.reply(f.requests.at(-1),f.metadata({pending:true}));f.advance(1000);
assert.equal(f.operation('recover').length,0);assert.equal(f.dialog,undefined);assert.equal(page.cleaned,undefined);
assert.equal(f.host.handleControllerEvent,pageInput);assert.equal(f.fw.common.getCommonTransitionData,pageTransition);assert.equal(f.fw.sendEventToMmui,pageSend);
f.homeScreen();f.advance(1000);assert.equal(f.operation('recover').length,1);f.ctx.OpenConnectMaintenance.close();
assert.equal(f.host.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);

// Retain installed preference coalescing across Back/re-entry and reconcile an
// uncertain ACK with a full read. A new desired value uses the reconciled fence.
f=warm();select(f,0);select(f,1);f.advance(250);
const first=f.operation('set')[0];assert.deepEqual(first.body.split('|').slice(1),[f.revision,'set','touch','0','1']);
select(f,0);f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
f.homeScreen();f.nativeSettings();f.tap();f.endAnimations();assert.equal(f.operation('set').length,1);
f.reply(first,null);const readback=f.requests.at(-1);assert.equal(readback.body.split('|')[3],'-');
f.reply(readback,f.state({touch:1,revision:'d'.repeat(64),restart:true}));
const second=f.operation('set')[1];assert.ok(second);assert.deepEqual(second.body.split('|').slice(1),['d'.repeat(64),'set','touch','1','0']);
f.reply(second,f.state({touch:0,revision:'e'.repeat(64),restart:false}));
f.reply(first,f.state({touch:1,revision:'d'.repeat(64),restart:true}));
f.reply(readback,f.state({touch:1,revision:'d'.repeat(64),restart:true}));
f.advance(1000);assert.equal(f.operation('set').length,2);assert.equal(f.operation('restart').length,0);
select(f,0);assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[0].image1,'radio');
f.homeScreen();assert.equal(f.ctx.OpenConnect.protected(),false);

// Keep installed import's unknown-ACK contract in the actual runtime, rather than
// retaining the unreachable duplicate implementation in USB maintenance.
const developer={developer:true,uart:0,ssh:0,uartCurrent:0,sshCurrent:0,key:'-',fingerprint:'-'};
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,1);f.reply(f.operation('import')[0],null);
assert.equal(f.requests.at(-1).body.split('|')[3],'-');
f.reply(f.requests.at(-1),f.state({...developer,key:'d'.repeat(64),fingerprint:Array(16).fill('aa').join(':'),revision:'e'.repeat(64)}));
assert.match(f.dialog.props.title,/Public key imported/);assert.equal(f.operation('import').length,1);assert.equal(f.operation('restart').length,0);f.pick('done');

// Installed maintenance and its dialog helper must yield to native SBN voice,
// resume the same operation and actually capture touch during visible progress.
for(const voice of ['Playing Prompt','Listening','Processing','Playing Terminating Prompt']){
 f=warm();select(f,'uninstall');f.fw.common._cachedVuiState=voice;f.pick('uninstall');
 assert.equal(f.operation('uninstall').length,0,'stale confirm cannot start during voice');
 f.fw.common._cachedVuiState='Idle';select(f,'uninstall');f.pick('uninstall');
 assert.equal(f.operation('uninstall').length,1);
 for(const type of ['mousedown','mouseup','click']){const event=f.touch(type);assert.equal(event.defaultPrevented,true);assert.equal(event.stopped,true);}
 assert.equal(f.calls.filter(c=>c[0]==='touch-target').length,0);
 f.fw.common._cachedVuiState=voice;f.reply(f.operation('uninstall')[0],f.state({installed:false,revision:'-',restart:true}));
 assert.equal(f.operation('restart').length,0);assert.equal(f.dialog,undefined);
 assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
 assert.equal(f.touch('click').stopped,undefined);
 f.fw.common._cachedVuiState='Idle';f.advance(250);assert.equal(f.operation('restart').length,1);
}
console.log('Installed regressions: interval cancellation, suspended ownership, exact restoration, saves/import ACKs, epoch and native touch/voice passed');

// Missing, explicitly refused and malformed acknowledgements each use one full
// read. Only a missing ACK with changed saved values can establish success.
for(const ack of [null,{ok:false,error:'stale_state'},{ok:true}]){
 f=warm();const send=f.oldSend;select(f,0);select(f,1);f.advance(250);
 f.reply(f.operation('set')[0],ack);assert.equal(f.requests.at(-1).body.split('|')[3],'-');
 f.reply(f.requests.at(-1),f.state({touch:1,revision:'d'.repeat(64)}));f.endAnimations();
 assert.equal(f.operation('set').length,1);assert.equal(f.operation('restart').length,0);
 if(ack===null){assert.equal(f.ctx.OpenConnect.protected(),true,'page still owns installed Settings');}
 else if(ack.ok===true)assert.match(f.pages.at(-1).list2Ctrl.title.text1,/Restart Mazda Connect/);
 // The Settings failure callback owns its UI. An extra runtime modal would
 // cover its transition restorer and reinstall a discarded page after Home.
 assert.equal(f.dialog,undefined);f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();identities(f,send);
 assert.equal(f.ctx.OpenConnect.protected(),!!(ack&&ack.ok===true),'malformed ACK retains unresolved claim');
}
f=warm();const failedSend=f.oldSend;select(f,0);select(f,1);f.advance(250);
f.reply(f.operation('set')[0],null);f.reply(f.requests.at(-1),f.state());f.endAnimations();
assert.match(f.pages.at(-1).list2Ctrl.title.text1,/Restart Mazda Connect/);assert.equal(f.dialog,undefined);
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();identities(f,failedSend);assert.equal(f.ctx.OpenConnect.protected(),true);

// Preserve the carplay-autoshow wire alias and its real uncertain-save readback.
f=warm();select(f,'phone');select(f,2);select(f,1);f.pick('apply');f.advance(250);
assert.deepEqual(f.operation('set')[0].body.split('|').slice(2),['set','carplay-autoshow','0','1']);
f.reply(f.operation('set')[0],null);f.reply(f.requests.at(-1),f.state({carplayAutoshow:1,revision:'d'.repeat(64)}));
assert.equal(f.operation('set').length,1);f.homeScreen();assert.equal(f.ctx.OpenConnect.protected(),false);

// Installed admission precedes teardown, but no write may cross an ineligible
// progress surface. Here native voice starts as the owner's page is cleaned up.
f=warm();const ownerPage=f.pages.at(-1),cleanup=ownerPage.cleanUp;
ownerPage.cleanUp=function(){assert.ok(f.fw.common._openConnectOperation,'claim precedes page cleanup');cleanup.call(this);f.fw.common._cachedVuiState='Listening';};
select(f,'uninstall');f.pick('uninstall');assert.equal(ownerPage.cleaned,true);assert.equal(f.operation('uninstall').length,0);
assert.ok(f.fw.common._openConnectOperation);assert.equal(f.dialog,undefined);
f.advance(1000);assert.equal(f.operation('uninstall').length,0);f.fw.common._cachedVuiState='Idle';f.advance(250);
assert.equal(f.operation('uninstall').length,1);assert.equal(f.dialog.props.contentStyle,'style27');

// One shared restart/readback deadline bounds uncertainty; a late restart ACK
// cannot release the unresolved claim or send a second restart.
f=warm({restart:true});select(f,'restart');f.pick('restart');const reboot=f.operation('restart')[0];
f.reply(reboot,null);assert.equal(f.requests.at(-1).body.split('|')[3],'-');f.advance(12000);
assert.match(f.dialog.props.title,/Unable to confirm/);assert.equal(f.ctx.OpenConnect.protected(),true);
f.reply(reboot,f.state({restart:true}));f.advance(1000);assert.equal(f.operation('restart').length,1);
console.log('Retained installed contracts: refused/malformed ACKs, failure UI ownership, CarPlay wire alias, admission and shared restart deadline passed');

// Capture the store at the actual attach boundary without replacing its methods.
// A write invalidates an older in-flight refresh before that refresh can change
// cache or notify its queued subscribers, even if it replies after the write ACK.
f=fixture(folder);f.install(1);
const settingsScript=f.scripts.find(n=>n.src.endsWith('/settings.js'));f.deliver(settingsScript,false);
let store;const attach=f.ctx.OpenConnectSettings.attach;
f.ctx.OpenConnectSettings.attach=function(fw,app,actual){store=actual;return attach.apply(this,arguments);};settingsScript.onload();
store.refresh(()=>{});f.reply(f.requests[0],f.state());let obsolete=0;
store.refresh(()=>obsolete++);const staleRead=f.requests.at(-1);let written=0;
store.write('touch',0,1,actual=>{assert.equal(actual.touch,1);written++;});
f.reply(f.operation('set')[0],f.state({touch:1,revision:'d'.repeat(64)}));
f.reply(staleRead,f.state({touch:0,revision:f.revision}));
assert.equal(written,1);assert.equal(obsolete,0);assert.equal(store.read().touch,1);assert.equal(store.read().revision,'d'.repeat(64));
// A fresh read's first subscriber can itself start a new epoch. Later subscribers
// to the invalidated read must not install a page or use its admission state.
store.refresh(()=>store.write('touch',1,0,()=>{}));store.refresh(()=>obsolete++);
f.reply(f.requests.at(-1),f.state({touch:1,revision:'d'.repeat(64)}));assert.equal(obsolete,0);assert.equal(f.operation('set').length,2);

// The stock SelectSettings event may fail to produce a Tab. Its bounded page
// waiter must cancel itself on exhaustion as well as on successful entry.
f=fixture(folder);f.install();f.fw.sendEventToMmui=(id,event)=>f.calls.push([id,event]);
f.ctx.OpenConnect.openSettings();f.reply(f.requests[0],f.state());f.advance(8000);
assert.equal(f.pages.length,0);assert.equal([...f.timers.values()].filter(t=>t.repeat===200).length,0);
console.log('Epoch regressions: stale refresh cache/subscribers are fenced; exhausted Home entry cancels its interval');

// A normal saved service reply unlocks Apply. A queued choice back to the
// applied value uses the first revision, then no longer needs a restart.
for(const queued of [false,true]){
 const row={id:'pandora',label:'Pandora',saved:1,current:1,enable:'Enable Pandora',disable:'Disable Pandora'};
 f=warm({services:[row]});select(f,'sources');
 select(f,'pandora',{additionalData:2});f.pick('apply');f.advance(250);
 const first=f.operation('set')[0];
 assert.deepEqual(first.body.split('|').slice(1),[f.revision,'set','pandora','1','0']);
 if(queued){select(f,'pandora',{additionalData:1});f.pick('apply');f.advance(250);}
 assert.equal(f.operation('set').length,1);
 f.reply(first,f.state({services:[{...row,saved:0}],revision:'d'.repeat(64),restart:true}));
 if(queued){
  const next=f.operation('set')[1];assert.ok(next);
  assert.deepEqual(next.body.split('|').slice(1),['d'.repeat(64),'set','pandora','0','1']);
  f.reply(next,f.state({services:[row]}));
 }
 const service=f.pages.at(-1).list2Ctrl.dataList.items.find(r=>r.appData==='pandora');
 assert.equal(/restart needed/.test(service.text1),!queued);
 f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
 const apply=f.pages.at(-1).list2Ctrl.dataList.items.find(r=>r.appData==='restart');
 assert.equal(apply.disabled,queued);
 assert.equal(f.operation('status').length,1,'confirmed saves do not fetch another view');
 assert.equal(f.operation('restart').length,0);
}

// Admission time and the backend's bounded reboot handoff have separate budgets.
// Exercise the real Settings owner with the current cohort's narrow ACK.
for(const delay of [0,11000]){
 f=warm({restart:true});select(f,'restart');f.pick('restart');
 const request=f.operation('restart')[0];f.advance(delay);
 f.reply(request,{ok:true,restarting:true});
 f.advance(1000);assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 f.advance(10999);assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 f.advance(1);assert.match(f.dialog.props.title,/Unable to confirm/);
 assert.equal(f.ctx.OpenConnect.protected(),true);assert.equal(f.operation('restart').length,1);
 f.reply(request,{ok:true,restarting:true});f.advance(1000);
 assert.equal(f.operation('restart').length,1);assert.match(f.dialog.props.title,/Unable to confirm/);
}
for(const answer of [null,{ok:false,error:'state_changed'},{ok:true,restarting:false},{ok:true},'legacy']){
 f=warm({restart:true});select(f,'restart');f.pick('restart');
 const request=f.operation('restart')[0];f.advance(11000);f.reply(request,answer==='legacy'?f.state({restart:true}):answer);
 assert.equal(f.requests.at(-1).body.split('|')[3],'-','restart uncertainty reads full physical state');
 f.advance(1000);assert.match(f.dialog.props.title,/Unable to confirm/);
 assert.equal(f.operation('restart').length,1);assert.equal(f.ctx.OpenConnect.protected(),true);
 f.reply(request,{ok:true,restarting:true});f.advance(15000);assert.equal(f.operation('restart').length,1);
}
console.log('Settings restart: late narrow ACK gets full handoff; negative/lost/malformed stays bounded without replay');
f=warm({restart:true});select(f,'restart');f.pick('restart');
const silentRestart=f.operation('restart')[0];f.advance(12000);
assert.equal(silentRestart.aborted,true);assert.match(f.dialog.props.title,/Unable to confirm/);
f.reply(silentRestart,{ok:true,restarting:true});f.advance(15000);
assert.equal(f.operation('restart').length,1);assert.equal(f.ctx.OpenConnect.protected(),true);

// Uninstall proof can arrive at the end of its readback window. Restart gets
// its own admission window when progress can actually send, even after VUI.
for(const pause of [0,15000]){
 f=warm();select(f,'uninstall');f.pick('uninstall');
 f.reply(f.operation('uninstall')[0],null);const proof=f.requests.at(-1);
 assert.equal(proof.body.split('|')[3],'-');f.advance(11000);
 if(pause)f.fw.common._cachedVuiState='Listening';
 f.reply(proof,f.state({installed:false,retained:false,revision:'-',restart:true}));
 if(pause){
  assert.equal(f.operation('restart').length,0);f.advance(pause);
  f.fw.common._cachedVuiState='Idle';f.advance(1000);
 }
 const request=f.operation('restart')[0];assert.ok(request);
 f.advance(11000);assert.equal(request.aborted,undefined);
 f.reply(request,{ok:true,restarting:true});f.advance(1000);
 assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 assert.equal(f.operation('uninstall').length,1);assert.equal(f.operation('restart').length,1);
}
// Full readback can prove Uninstall, never the restart that follows it.
for(const answer of [null,{ok:false,error:'state_changed'},{ok:true}]){
 f=warm();select(f,'uninstall');f.pick('uninstall');
 const removed=f.state({installed:false,retained:false,revision:'-',restart:true});
 f.reply(f.operation('uninstall')[0],removed);const restart=f.operation('restart')[0];
 f.advance(1000);f.reply(restart,answer);const readback=f.requests.at(-1);
 assert.equal(readback.body.split('|')[3],'-');f.reply(readback,removed);
 assert.match(f.dialog.props.title,answer&&answer.ok===false?/Unable to finish/:/Unable to confirm/);
 const feedback=f.dialog;f.reply(restart,{ok:true,restarting:true});f.reply(readback,removed);f.advance(15000);
 assert.equal(f.dialog,feedback);assert.equal(f.operation('restart').length,1);
 assert.equal(f.ctx.OpenConnect.protected(),!(answer&&answer.ok===false));
}
console.log('Settings restart owns a fresh send deadline after late write proof/VUI; completed readback cannot prove reboot');

// Uncertain saves belong to the Settings page, with the same restart guidance
// on re-entry. Drive the real mutation, readback deadline and native callbacks.
for(const op of ['set','import'])for(const leave of [false,true]){
 f=warm(developer);const send=f.oldSend;
 if(op==='set'){select(f,0);select(f,1);f.advance(250);}
 else{select(f,'developer');select(f,'import');f.pick('import');}
 const mutation=f.operation(op)[0],lostAt=f.now;
 f.reply(mutation,null);const read=f.requests.at(-1);
 if(leave){f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();}
 f.advance(11999);
 if(op==='import'&&!leave)assert.equal(f.dialog.props.text1,'Importing public key');
 else assert.equal(f.dialog,undefined);
 if(!leave)assert.doesNotMatch(f.pages.at(-1).list2Ctrl.title.text1,/Restart Mazda Connect/);
 f.advance(1);f.endAnimations();assert.equal(f.now-lostAt,12000);
 assert.equal(f.dialog,undefined,'page feedback never gets an extra runtime modal');
 assert.equal(f.operation(op).length,1);assert.equal(read.aborted,true);
 if(!leave){
  assert.match(f.pages.at(-1).list2Ctrl.title.text1,/Restart Mazda Connect/);
  f.tap();assert.equal(f.dialog,undefined,'an active failure page owns its feedback');
  select(f,0);assert.equal(f.fw.common._openConnectPage,undefined);
 }
 f.homeScreen();identities(f,send);f.nativeSettings();const count=f.requests.length,start=f.now;
 f.tap();assert.equal(f.now-start,0);assert.equal(f.requests.length,count);
 assert.match(f.dialog.props.text1,/Restart Mazda Connect before making more changes/);
 const guidance=f.dialog;f.tap();assert.equal(f.dialog,guidance,'repeat taps share one modal');
 f.reply(mutation,f.state({touch:1,key:'d'.repeat(64),revision:'e'.repeat(64)}));
 f.reply(read,f.state({touch:1,key:'d'.repeat(64),revision:'e'.repeat(64)}));
 f.advance(60000);assert.equal(f.dialog,guidance);assert.equal(f.requests.length,count);
 f.fw.common.getCommonTransitionData();assert.equal(guidance.destroyed,true);identities(f,send);
 guidance.props.defaultSelectCallback(guidance,'done');assert.equal(f.dialog,undefined);
 f.tap();assert.match(f.dialog.props.text1,/Restart Mazda Connect before making more changes/);
 f.pick('done');assert.equal(f.ctx.OpenConnect.protected(),true);assert.equal(f.operation(op).length,1);
}
// Import failure belongs to the live preference session, including a different
// page opened before the reply was lost. Queued values must not replace it.
for(const navigation of ['back','reenter','queued']){
 f=warm(developer);select(f,'developer');
 if(navigation==='queued'){
  select(f,'uart',{additionalData:1});f.pick('enable');
  select(f,'import');f.pick('import');
  const setOp=f.operation('set')[0];
  f.reply(setOp,f.state({...developer,uart:1,restart:true}));
  const mutation=f.operation('import')[0];
  f.reply(mutation,null);const read=f.requests.at(-1);
  f.advance(12000);f.endAnimations();
  assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Restart Mazda Connect',navigation);
  assert.equal(f.operation('import').length,1);assert.equal(f.operation('set').length,1);
  assert.equal(f.ctx.OpenConnect.protected(),true);assert.equal(f.dialog,undefined);
  f.reply(mutation,f.state({...developer,uart:1,key:'d'.repeat(64),revision:'e'.repeat(64)}));
  f.reply(read,f.state({...developer,uart:1,key:'d'.repeat(64),revision:'e'.repeat(64)}));
  f.advance(1000);assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Restart Mazda Connect');
  assert.equal(f.operation('set').length,1);assert.equal(f.operation('restart').length,0);
  continue;
 }
 select(f,'import');f.pick('import');
 const mutation=f.operation('import')[0];
 if(navigation==='back'){
  f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
 }else{
  f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
  f.nativeSettings();f.tap();f.endAnimations();
 }
 f.reply(mutation,null);const read=f.requests.at(-1);
 f.advance(12000);f.endAnimations();
 assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Restart Mazda Connect',navigation);
 assert.equal(f.operation('import').length,1);assert.equal(f.operation('set').length,0);
 assert.equal(f.ctx.OpenConnect.protected(),true);assert.equal(f.dialog,undefined);
 f.reply(mutation,f.state({...developer,key:'d'.repeat(64),revision:'e'.repeat(64)}));
 f.reply(read,f.state({...developer,key:'d'.repeat(64),revision:'e'.repeat(64)}));
 f.advance(1000);assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Restart Mazda Connect');
 assert.equal(f.operation('set').length,0);assert.equal(f.operation('restart').length,0);
}
// Definite input refusal retains key-specific help and permits another action.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
f.reply(f.operation('import')[0],{ok:false,error:'invalid_public_key'});f.reply(f.requests.at(-1),f.state(developer));
assert.equal(f.dialog.props.title,'Key could not be imported');assert.match(f.dialog.props.text1,/open-connect.pub/);
f.pick('done');select(f,'import');f.pick('import');assert.equal(f.operation('import').length,2);
// A selected old client can receive a definite restart-required refusal after
// Update. Give restart guidance while retaining a usable Apply action.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
f.reply(f.operation('import')[0],{ok:false,error:'restart_required'});
f.reply(f.requests.at(-1),f.state({...developer,restart:true}));f.endAnimations();
assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Restart Mazda Connect');
assert.equal(f.dialog,undefined);
assert.equal(f.operation('import').length,1);assert.equal(f.operation('set').length,0);
select(f,0);assert.equal(f.ctx.OpenConnect.protected(),false);f.tap();f.endAnimations();select(f,'restart');
assert.equal(f.dialog.props.title,'Apply changes?');f.pick('restart');
assert.equal(f.operation('restart').length,1);assert.equal(f.operation('import').length,1);
// An unavailable first read remains a normal retry, with no mutation fence.
f=fixture(folder);f.install();f.nativeSettings();f.tap();f.advance(12000);
assert.match(f.dialog.props.text1,/could not be reached. Try again/);f.pick('done');
const retry=f.requests.length;f.tap();assert.equal(f.requests.length,retry+1);f.reply(f.requests.at(-1),f.state());
assert.ok(f.fw.common._openConnectPage);assert.equal(f.dialog,undefined);assert.equal(f.operation('set').length,0);
// Stale save refusal while Uninstall is queued must cancel Uninstall rather than remove a newer revision.
f=warm({touch:1,touchCurrent:1,warning:1,warningCurrent:1,restart:false});
select(f,0);select(f,0);assert.equal(f.operation('set').length,1);
f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
select(f,'uninstall');f.pick('uninstall');
assert.equal(f.dialog.props.text1,'Removing Open Connect');assert.equal(f.operation('uninstall').length,0);
f.reply(f.operation('set')[0],{ok:false,error:'stale_state'});
f.reply(f.requests.at(-1),f.state({touch:1,touchCurrent:1,warning:1,warningCurrent:1,revision:'b'.repeat(64)}));
f.endAnimations();
assert.equal(f.operation('uninstall').length,0,'stale refusal must never authorize uninstall of a newer revision');
assert.equal(f.dialog,undefined);
assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Change could not be confirmed');
// Declined native progress control must prevent key import and queued Apply changes from sending.
f=warm(developer);select(f,'developer');
const origCreate=f.fw.instantiateControl;
f.fw.instantiateControl=function(a,c,k,p){
 if(k==='Dialog3Ctrl'&&p&&p.text1==='Importing public key')return null;
 return origCreate.apply(this,arguments);
};
select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,0,'declined progress dialog must block import');
assert.equal(f.dialog,undefined);
// Refused key import after leaving and re-entering Settings must cancel queued Uninstall.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,1);
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
select(f,'uninstall');f.pick('uninstall');
assert.equal(f.dialog.props.text1,'Removing Open Connect');assert.equal(f.operation('uninstall').length,0);
f.reply(f.operation('import')[0],{ok:false,error:'stale_state'});
f.reply(f.requests.at(-1),f.state({...developer,revision:'c'.repeat(64)}));
f.endAnimations();
assert.equal(f.operation('uninstall').length,0,'refused import must never release queued uninstall against a newer revision');
assert.equal(f.dialog,undefined);
// Lost Set ACK reconciled via readback with unrelated changes preserves preference reconciliation
// while cancelling queued Uninstall so the user must freshly confirm against the new revision.
f=warm({touch:1,touchCurrent:1,warning:1,warningCurrent:1,restart:false});
select(f,0);select(f,0);assert.equal(f.operation('set').length,1);
f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
select(f,'uninstall');f.pick('uninstall');
assert.equal(f.dialog.props.text1,'Removing Open Connect');assert.equal(f.operation('uninstall').length,0);
f.reply(f.operation('set')[0],null);
f.reply(f.requests.at(-1),f.state({touch:0,touchCurrent:1,warning:0,warningCurrent:1,restart:true,revision:'d'.repeat(64)}));
f.endAnimations();
assert.equal(f.operation('uninstall').length,0,'unacknowledged readback must never transfer uninstall confirmation to an unrelated revision');
assert.equal(f.dialog,undefined);
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Show','preference reconciliation stays intact');
// An open Uninstall prompt opened BEFORE lost-ACK Set readback must be invalidated and page refreshed.
f=warm({touch:1,touchCurrent:1,warning:1,warningCurrent:1,restart:false});
select(f,0);select(f,0);assert.equal(f.operation('set').length,1);
f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
select(f,'uninstall');const openPrompt=f.dialog;assert.equal(openPrompt.props.buttonConfig.button2.appData,'uninstall');
f.reply(f.operation('set')[0],null);
f.reply(f.requests.at(-1),f.state({touch:0,touchCurrent:1,warning:0,warningCurrent:1,restart:true,revision:'e'.repeat(64)}));
f.endAnimations();
assert.equal(openPrompt.destroyed,true,'reconciliation must invalidate an open Uninstall prompt');
assert.equal(f.dialog,undefined);
assert.equal(f.operation('uninstall').length,0);
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Show','root page refreshes to reconciled values');
// An open Uninstall prompt opened BEFORE lost-ACK Import readback (after Home+re-entry) must also be invalidated.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,1);
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
select(f,'uninstall');const importPrompt=f.dialog;assert.equal(importPrompt.props.buttonConfig.button2.appData,'uninstall');
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,key:'f'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),warning:0,revision:'f'.repeat(64)}));
f.endAnimations();
assert.equal(importPrompt.destroyed,true,'reconciled import must invalidate an open Uninstall prompt');
assert.equal(f.dialog,undefined);
assert.equal(f.operation('uninstall').length,0);
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Show');
// A refused Import while an unsent touch draft is displayed on Root must immediately revert the visible label.
f=warm({...developer,touch:1,touchCurrent:1});select(f,'developer');select(f,'import');f.pick('import');
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
select(f,0);select(f,0);f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[0].label1,'Factory behavior');
f.reply(f.operation('import')[0],{ok:false,error:'invalid_public_key'});
f.reply(f.requests.at(-1),f.state({...developer,touch:1,touchCurrent:1}));
f.endAnimations();
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[0].label1,'Always enabled','discarded draft must revert visibly immediately');
// Already-confirmed Uninstall followed by lost Import ACK readback must cancel Uninstall and refresh Root.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,1);
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
select(f,'uninstall');f.pick('uninstall');
assert.equal(f.dialog.props.text1,'Removing Open Connect');assert.equal(f.operation('uninstall').length,0);
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,key:'f'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),warning:0,revision:'f'.repeat(64)}));
f.endAnimations();
assert.equal(f.operation('uninstall').length,0,'reconciled import must cancel already-confirmed uninstall');
assert.equal(f.dialog,undefined);
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Show');
// Queued Apply behind lost Import ACK whose readback clears restart must refresh Root to the reconciled values.
f=warm({...developer,warning:1,warningCurrent:0,restart:true});select(f,'developer');select(f,'import');f.pick('import');
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Skip');
select(f,'restart');f.pick('restart');assert.equal(f.dialog.props.text1,'Applying changes');
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),warning:0,warningCurrent:0,restart:false,revision:'e'.repeat(64)}));
f.endAnimations();
assert.equal(f.operation('restart').length,0);assert.equal(f.dialog,undefined);
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[1].label1,'Show','root must refresh after queued Apply closes');
// Reconciled Set/Import or refused Import arriving during native voice retires stale page rather than leaving stale labels.
for(const mode of ['set-rec','import-rec','import-refuse']){
 f=warm({...developer,touch:1,touchCurrent:1,warning:1,warningCurrent:1});
 if(mode==='set-rec'){
  select(f,0);select(f,0);f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
 }else{
  select(f,'developer');select(f,'import');f.pick('import');
  f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
  f.nativeSettings();f.tap();f.endAnimations();
  if(mode==='import-refuse'){select(f,0);select(f,0);f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();}
 }
 f.fw.common._cachedVuiState='Listening';
 const op=mode==='set-rec'?f.operation('set')[0]:f.operation('import')[0];
 f.reply(op,mode==='import-refuse'?{ok:false,error:'invalid_public_key'}:null);
 f.reply(f.requests.at(-1),f.state(mode==='import-refuse'?{...developer,touch:1,touchCurrent:1,warning:1,warningCurrent:1}:
  {...developer,touch:0,touchCurrent:1,warning:0,warningCurrent:1,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 f.fw.common._cachedVuiState='Idle';
 assert.equal(f.fw.common._openConnectPage,undefined,mode+' must retire stale page when voice owns screen');
}
// Deferred sync behind Apply when native voice starts AFTER readback and BEFORE the queued Set ACK must still retire stale page.
f=warm({...developer,touch:1,touchCurrent:1,warning:1,warningCurrent:1,restart:false});
select(f,'developer');select(f,'import');f.pick('import');
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();
select(f,0);select(f,0);f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
select(f,'restart');f.pick('restart');assert.equal(f.dialog.props.text1,'Applying changes');
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,touch:1,touchCurrent:1,warning:0,warningCurrent:1,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
const queuedSet=f.operation('set')[0];assert.ok(queuedSet);
f.fw.common._cachedVuiState='Listening';
f.reply(queuedSet,f.state({...developer,touch:0,touchCurrent:1,warning:0,warningCurrent:1,restart:true,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'f'.repeat(64)}));
f.fw.common._cachedVuiState='Idle';
assert.equal(f.fw.common._openConnectPage,undefined,'deferred sync must retire stale page when voice starts before queued Set ACK');
// Reconciled Import while staying on Developer options must rebuild Developer options only once, focused on Import.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
const pagesBefore=f.pages.length;
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
assert.equal(f.pages.length,pagesBefore+1,'reconciled Import on Developer page must render once, not twice');
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[f.pages.at(-1).list2Ctrl.focussedItem].appData,'import');
// Touch-cancelling Import progress during voice, then Back -> Apply or Uninstall in the SAME session:
// successful Import ACK must not close the newer progress dialog or cancel the queued action.
for(const action of ['restart','uninstall']){
 f=warm({...developer,warning:1,warningCurrent:0,restart:true});select(f,'developer');select(f,'import');f.pick('import');
 f.fw.common._cachedVuiState='Listening';
 f.touch('mousedown');
 f.fw.common._cachedVuiState='Idle';
 assert.equal(f.dialog,undefined);
 f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
 select(f,action);f.pick(action);
 assert.equal(f.operation(action).length,0);
 f.reply(f.operation('import')[0],f.state({...developer,warning:1,warningCurrent:0,restart:true,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 assert.equal(f.operation(action).length,1,'same-session '+action+' must proceed after touch-cancelled Import ACK');
}
// Reconciled Import after touch-cancelling progress during Listening -> Idle must still render Developer page only once, focused on Import.
f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
f.fw.common._cachedVuiState='Listening';
f.touch('mousedown');
f.fw.common._cachedVuiState='Idle';
const pagesAfterCancel=f.pages.length;
f.reply(f.operation('import')[0],null);
f.reply(f.requests.at(-1),f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
assert.equal(f.pages.length,pagesAfterCancel+1,'reconciled Import after progress dismissal must render Developer page once');
assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[f.pages.at(-1).list2Ctrl.focussedItem].appData,'import');
// An open second Developer confirmation must be retired before presenting Import result,
// keeping late selection inert and restoring Home transition callbacks cleanly.
for(const kind of ['ack','reconcile','refuse']){
 f=warm(developer);
 select(f,'developer');select(f,'import');f.pick('import');
 f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
 select(f,'import');const staleConfirm=f.dialog;assert.equal(staleConfirm.props.title,'Import public key?');
 const op=f.operation('import')[0];
 const okState=f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)});
 if(kind==='ack'){f.reply(op,okState);}
 else if(kind==='reconcile'){f.reply(op,null);f.reply(f.requests.at(-1),okState);}
 else{f.reply(op,{ok:false,error:'invalid_public_key'});f.reply(f.requests.at(-1),f.state(developer));}
 assert.equal(staleConfirm.destroyed,true,kind+' must retire stale confirmation before presenting result');
 assert.equal(f.dialog.props.title,kind==='refuse'?'Key could not be imported':'Public key imported');
 staleConfirm.props.defaultSelectCallback(staleConfirm,'import');
 assert.equal(f.operation('import').length,1,'late selection on retired confirmation must stay inert');
 f.fw.sendEventToMmui('common','Global.IntentHome');
 assert.equal(f.dialog,undefined);
 assert.equal(f.fw.common.getCommonTransitionData.name,'oldTransition','Home must restore original transition callback');
}
// Direct Import ACK after Home/re-entry OR while voice resumes must invalidate a stale second Import prompt.
for(const path of ['reenter','voice']){
 f=warm(developer);select(f,'developer');select(f,'import');f.pick('import');
 if(path==='reenter'){
  f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
  f.nativeSettings();f.tap();f.endAnimations();select(f,'developer');
 }else{
  f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
 }
 select(f,'import');const secondPrompt=f.dialog;assert.equal(secondPrompt.props.title,'Import public key?');
 if(path==='voice')f.fw.common._cachedVuiState='Listening';
 f.reply(f.operation('import')[0],f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 if(path==='voice')f.fw.common._cachedVuiState='Idle';
 assert.equal(secondPrompt.destroyed,true,path+' direct Import ACK must retire stale confirmation');
 secondPrompt.props.defaultSelectCallback(secondPrompt,'import');
 assert.equal(f.operation('import').length,1,path+' retired prompt must not send a second Import');
}
// Retiring an open Enable UART? or Enable SSH? prompt on Import completion builds Developer options only once.
for(const toggleItem of ['uart','ssh']){
 const baseState=toggleItem==='ssh'?{...developer,key:'a'.repeat(64),fingerprint:Array(16).fill('cd').join(':')}:developer;
 for(const kind of ['ack','reconcile','refuse']){
  f=warm(baseState);select(f,'developer');select(f,'import');f.pick('import');
  f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
  select(f,toggleItem,{additionalData:1});assert.match(f.dialog.props.title,new RegExp('Enable '+toggleItem.toUpperCase()+'\\?'));
  const beforePages=f.pages.length;
  const op=f.operation('import')[0];
  const okState=f.state({...baseState,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)});
  if(kind==='ack'){f.reply(op,okState);}
  else if(kind==='reconcile'){f.reply(op,null);f.reply(f.requests.at(-1),okState);}
  else{f.reply(op,{ok:false,error:'invalid_public_key'});f.reply(f.requests.at(-1),f.state(baseState));}
  assert.equal(f.pages.length,beforePages+1,toggleItem+'/'+kind+' must build Developer options once');
  assert.equal(f.pages.at(-1).list2Ctrl.dataList.items[f.pages.at(-1).list2Ctrl.focussedItem].appData,'import');
 }
}
// Late direct Import ACK while viewing Touchscreen (Always disabled) preserves focus on Always disabled;
// selecting the focused row sends zero writes.
f=warm({...developer,touch:2,touchCurrent:2});select(f,'developer');select(f,'import');f.pick('import');
f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
f.nativeSettings();f.tap();f.endAnimations();select(f,0);
assert.equal(f.pages.at(-1).list2Ctrl.focussedItem,2);
f.reply(f.operation('import')[0],f.state({...developer,touch:2,touchCurrent:2,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
const touchPage=f.pages.at(-1).list2Ctrl;
assert.equal(touchPage.focussedItem,2,'sync refresh must preserve focused Touchscreen choice');
select(f,touchPage.dataList.items[touchPage.focussedItem].appData);
assert.equal(f.operation('set').length,0,'selecting already-active focused choice must send zero writes');
// Retiring an open Wireless CarPlay or CarPlay Autoshow prompt on late Import ACK builds the page only once.
for(const cp of ['wireless','autoshow']){
 f=warm({...developer,wireless:0,wirelessCurrent:0,wirelessFactory:false,carplayAutoshow:0,carplayAutoshowCurrent:0});
 select(f,'developer');select(f,'import');f.pick('import');
 f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();
 f.nativeSettings();f.tap();f.endAnimations();select(f,'phone');
 if(cp==='wireless'){select(f,'wireless',{additionalData:1});assert.equal(f.dialog.props.title,'Enable Wireless CarPlay?');}
 else{select(f,2);select(f,1);assert.equal(f.dialog.props.title,'Automatically show CarPlay?');}
 const beforeCp=f.pages.length;
 f.reply(f.operation('import')[0],f.state({...developer,wireless:0,wirelessCurrent:0,wirelessFactory:false,carplayAutoshow:0,carplayAutoshowCurrent:0,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 assert.equal(f.pages.length,beforeCp+1,cp+' prompt retirement on sync must render once');
 assert.equal(f.dialog,undefined);
}
// Touch-cancelling Import #1 and queuing Import #2 on Developer options keeps Import #2's progress active
// by identity with zero page builds when Import #1 finishes, sends Import #2, and presents Import #2's result cleanly.
f=warm({...developer});select(f,'developer');select(f,'import');f.pick('import');
assert.equal(f.operation('import').length,1);
f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
assert.equal(f.dialog,undefined);
select(f,'import');f.pick('import');
const secondWait=f.dialog,beforeFirstReply=f.pages.length;
assert.equal(secondWait.props.text1,'Importing public key');
assert.equal(f.operation('import').length,1);
f.reply(f.operation('import')[0],f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
assert.equal(f.dialog,secondWait,'queued Import #2 progress must keep exact dialog identity when Import #1 finishes');
assert.equal(f.pages.length,beforeFirstReply,'Import #1 handoff must build zero templates behind Import #2 progress');
assert.equal(f.operation('import').length,2,'queued Import #2 must start after Import #1 finishes');
f.reply(f.operation('import')[1],f.state({...developer,key:'f'.repeat(64),fingerprint:Array(16).fill('cd').join(':'),revision:'f'.repeat(64)}));
assert.equal(f.dialog.props.title,'Public key imported');
assert.ok(f.dialog.props.text1.includes('cd:cd:cd'));
// If queued Import #2 fails via restart_required or 12 s readback timeout, Settings must build
// exactly one Restart Mazda Connect guidance template and retain its incoming slide animation.
for(const mode of ['restart_required','timeout']){
 f=warm({...developer});
 f.fw._offscreenTemplateParent={appendChild(n){n.parentNode=this;},removeChild(n){n.parentNode=null;}};
 select(f,'developer');select(f,'import');f.pick('import');
 f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
 select(f,'import');f.pick('import');
 const w2=f.dialog,pagesAtHandoff=f.pages.length;
 f.reply(f.operation('import')[0],f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 assert.equal(f.dialog,w2);assert.equal(f.pages.length,pagesAtHandoff);
 assert.equal(f.operation('import').length,2);
 if(mode==='restart_required'){
  f.reply(f.operation('import')[1],{ok:false,error:'restart_required'});
  f.reply(f.requests.at(-1),f.state({...developer,key:'e'.repeat(64),fingerprint:Array(16).fill('ab').join(':'),revision:'e'.repeat(64)}));
 }else{
  f.reply(f.operation('import')[1],null);
  f.advance(12000);
 }
 assert.equal(f.pages.length,pagesAtHandoff+1,mode+': failure must build Restart Mazda Connect exactly once');
 const guidance=f.pages.at(-1);
 assert.equal(guidance.cleaned,undefined);
 assert.equal(guidance.list2Ctrl.title.text1,'Restart Mazda Connect');
 assert.ok(guidance.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),mode+': incoming slide class must remain active');
 f.endAnimations();
 assert.equal(guidance.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),false);
}
// A second preference save failing behind queued Apply changes or Import public key after the first
// save reconciles must build Restart Mazda Connect once, retain and complete its slide, and send zero queued actions.
for(const action of ['restart','import']){
 for(const mode of ['restart_required','timeout']){
  f=warm({...developer,touch:0,touchCurrent:0,uart:0,uartCurrent:0});
  f.fw._offscreenTemplateParent={appendChild(n){n.parentNode=this;},removeChild(n){n.parentNode=null;}};
  if(action==='restart'){
   select(f,0);select(f,1);select(f,2);
   f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
   select(f,'restart');f.pick('restart');
  }else{
   select(f,'developer');select(f,'uart',{additionalData:1});f.pick('enable');
   select(f,'uart',{additionalData:2});
   select(f,'import');f.pick('import');
  }
  const waitDlg=f.dialog,pagesBefore=f.pages.length;
  assert.equal(f.operation('set').length,1);
  f.reply(f.operation('set')[0],null);
  const mid=action==='restart'
   ?f.state({...developer,touch:1,touchCurrent:0,restart:true,revision:'d'.repeat(64)})
   :f.state({...developer,uart:1,uartCurrent:0,restart:true,revision:'d'.repeat(64)});
  f.reply(f.requests.at(-1),mid);
  assert.equal(f.dialog,waitDlg,action+'/'+mode+': progress dialog stays open across reconciled save #1');
  assert.equal(f.pages.length,pagesBefore,action+'/'+mode+': reconciled save #1 builds zero pages behind progress');
  assert.equal(f.operation('set').length,2);
  if(mode==='restart_required'){
   f.reply(f.operation('set')[1],{ok:false,error:'restart_required'});
   f.reply(f.requests.at(-1),mid);
  }else{
   f.reply(f.operation('set')[1],null);
   f.advance(12000);
  }
  assert.equal(f.pages.length,pagesBefore+1,action+'/'+mode+': failed save #2 must build guidance once');
  const g=f.pages.at(-1);
  assert.equal(g.cleaned,undefined);
  assert.equal(g.list2Ctrl.title.text1,'Restart Mazda Connect');
  assert.ok(g.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),action+'/'+mode+': incoming slide must remain active');
  f.endAnimations();
  assert.equal(g.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),false);
  assert.equal(f.operation(action).length,0,action+'/'+mode+': failed save #2 must send zero queued actions');
 }
}
// A refused Import whose full status read confirms conflict:true while Apply changes or Uninstall is queued
// must build Change could not be confirmed once, retain and complete its slide, and send zero maintenance requests.
for(const action of ['restart','uninstall']){
 f=warm({...developer,touch:1,touchCurrent:0,restart:true});
 f.fw._offscreenTemplateParent={appendChild(n){n.parentNode=this;},removeChild(n){n.parentNode=null;}};
 select(f,'developer');select(f,'import');f.pick('import');
 assert.equal(f.operation('import').length,1);
 f.fw.common._cachedVuiState='Listening';f.touch('mousedown');f.fw.common._cachedVuiState='Idle';
 f.fw.sendEventToMmui('common','Global.GoBack');f.endAnimations();
 select(f,action);f.pick(action);
 const pagesBefore=f.pages.length;
 f.reply(f.operation('import')[0],{ok:false,error:'state_changed'});
 f.reply(f.requests.at(-1),f.state({...developer,conflict:true,installedVersion:'-',restart:true}));
 assert.equal(f.dialog,undefined);
 assert.equal(f.pages.length,pagesBefore+1,action+': conflict readback must build guidance once');
 const g=f.pages.at(-1);
 assert.equal(g.cleaned,undefined);
 assert.equal(g.list2Ctrl.title.text1,'Change could not be confirmed');
 assert.ok(g.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),action+': incoming slide must remain active');
 f.endAnimations();
 assert.equal(g.divElt.classes.has('Transitions_slideInRightTmpltWithStatusLeftBtn_0_400'),false);
 assert.equal(f.operation(action).length,0,action+': conflict readback must send zero maintenance requests');
}
// Same conflict readback while staying on Developer options must show Change could not be confirmed without
// layering the unrelated invalid-key help dialog on top.
f=warm({...developer,touch:1,touchCurrent:0,restart:true});
f.fw._offscreenTemplateParent={appendChild(n){n.parentNode=this;},removeChild(n){n.parentNode=null;}};
select(f,'developer');select(f,'import');f.pick('import');
const devPages=f.pages.length;
f.reply(f.operation('import')[0],{ok:false,error:'state_changed'});
f.reply(f.requests.at(-1),f.state({...developer,conflict:true,installedVersion:'-',restart:true}));
assert.equal(f.pages.length,devPages+1);
assert.equal(f.pages.at(-1).list2Ctrl.title.text1,'Change could not be confirmed');
assert.equal(f.dialog,undefined,'conflict guidance on Developer options must not show invalid-key dialog');
f.endAnimations();
console.log('Unconfirmed preference/import saves show restart guidance at 12 s and immediately on re-entry; late replies stay inert');
