const assert=require('node:assert/strict'),fixture=require('./runtime-fixture.js');
const folder=process.argv[2];
function fresh(options={}){const f=fixture(folder,{installed:false,...options});f.usb();return f;}
function metadata(f,extra={}){f.reply(f.requests.at(-1),f.metadata({installed:false,installedVersion:'-',revision:'-',...extra}));f.advance(0);}
function commit(f,extra={}){return f.state({installed:true,installedVersion:f.version,revision:'d'.repeat(64),notice:'installed',restart:true,...extra});}
let f=fresh();assert.equal(f.ctx.OpenConnect,undefined);assert.equal(f.ctx.OpenConnectSettings,undefined);assert.equal(f.ctx.OpenConnectInstaller,undefined);
assert.deepEqual(f.scripts.map(n=>n.src.split('/').at(-1)),['loader.js','maintenance.js']);
metadata(f);assert.deepEqual(Object.values(f.dialog.props.buttonConfig).map(b=>b.appData),['cancel','install']);
f.pick('cancel');assert.equal(f.requests.at(-1).body.split('|')[3],'usb');f.reply(f.requests.at(-1),{ok:true});
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
f=fresh();metadata(f);f.closeUSB();f.advance(1000);assert.equal(f.dialog,undefined);assert.equal(f.operation('dismiss').length,0);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);
f=fresh();metadata(f);f.pick('install');
assert.equal(f.dialog.props.contentStyle,'style27');assert.equal(f.operation('install').length,1);
f.reply(f.operation('install')[0],commit(f));assert.equal(f.operation('restart').length,1);
assert.equal(f.dialog.props.contentStyle,'style27');f.closeUSB();f.advance(1000);
assert.equal(f.ctx.OpenConnectMaintenance.protected(),true,'removal retains an admitted operation');
assert.equal(f.operation('restart').length,1);
// Removal winning before backend admission is an explicit, safe refusal.
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],{ok:false,error:'session_closed'});
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.equal(f.operation('restart').length,0);
// Unknown write results reconcile once and never resend the mutation.
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],null);
assert.equal(f.operation('install').length,1);assert.equal(f.requests.at(-1).body.split('|')[2],'status');
f.reply(f.requests.at(-1),commit(f));assert.equal(f.operation('restart').length,1);
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],{ok:false,error:'stale_state'});
f.reply(f.requests.at(-1),commit(f));assert.equal(f.operation('restart').length,0,'definite refusal cannot become inferred success');
// The chooser exception cannot authorize full write reconciliation or completion.
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],f.metadata({restart:true}));
assert.equal(f.requests.at(-1).body.split('|')[3],'-','small write reply requires a full status');
f.reply(f.requests.at(-1),f.metadata({installed:true,notice:'installed',revision:'d'.repeat(64),restart:true}));
assert.equal(f.operation('restart').length,0,'small readback cannot prove the mutation');
assert.match(f.dialog.props.title,/Unable to confirm/);
for(const missing of ['revision','package','boot','installedVersion','notice','completionReady']){
 f=fixture(folder,{notice:'installed'});f.install();
 const proof=f.proof();delete proof[missing];
 f.reply(f.requests[0],proof);f.advance(0);
 assert.equal(f.dialog,undefined,'completion still requires '+missing);assert.equal(f.ctx.OpenConnectCompletion,null);
}
// Full status and a matching version cannot stand in for a selected-boot proof.
for(const extra of [{boot:'87654321-1234-1234-1234-123456789abc'},
 {installedVersion:'0.3.0-other'},{completionReady:false},{notice:'-'},{revision:'-'},{package:'invalid'}]){
 f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof(extra));
 assert.equal(f.dialog,undefined);assert.equal(f.operation('dismiss').length,0);
}
f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.state({notice:'installed',completionReady:true}));
assert.equal(f.dialog,undefined,'generic status cannot prove completion');
// Pending completion explicitly obtains full state before progress/recovery.
f=fixture(folder,{notice:'installed'});f.install();f.fw.common._vuiHelpDialog={};
f.reply(f.requests[0],{ok:false,error:'operation_pending'});
assert.equal(f.requests.at(-1).body.split('|')[3],'settings');
f.reply(f.requests.at(-1),f.state({pending:true,revision:'e'.repeat(32)}));
assert.equal(f.operation('recover').length,0);
delete f.fw.common._vuiHelpDialog;f.advance(1000);
assert.equal(f.operation('recover').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
// Recovery waits for visible progress and restart reacquires it after VUI.
f=fresh();f.fw.common._vuiHelpDialog={};metadata(f,{pending:true});
assert.equal(f.operation('recover').length,0);assert.equal(f.controls.length,0);
f.advance(2000);assert.equal(f.operation('recover').length,0);
delete f.fw.common._vuiHelpDialog;f.advance(1000);assert.equal(f.operation('recover').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
f.fw.common._vuiHelpDialog={};f.fw.common.handleControllerEvent('help',false);
f.reply(f.operation('recover')[0],commit(f));assert.equal(f.operation('restart').length,0);
delete f.fw.common._vuiHelpDialog;f.advance(1000);assert.equal(f.operation('restart').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
// Completion is installed-package maintenance, not a warm Settings store.
f=fixture(folder,{notice:'installed'});f.install();f.advance(0);
assert.equal(f.requests.length,1);assert.equal(f.requests[0].body.split('|')[3],'completion');
f.reply(f.requests[0],f.proof());f.advance(0);
assert.match(f.dialog.props.title,/installed/);const settings=f.ctx.OpenConnect;
f.pick('settings');assert.equal(f.requests.at(-1).body.split('|')[2],'dismiss');
f.reply(f.requests.at(-1),{ok:true});assert.equal(f.ctx.OpenConnect,settings);
assert.equal(f.requests.at(-1).body.split('|')[3],'settings','Open settings obtains its own cold status');
f.reply(f.requests.at(-1),f.state());f.advance(200);assert.equal(f.pages.length,1);f.assertNative();
// A manual visit suppresses a pending completion locally, without acknowledging it.
f=fixture(folder,{notice:'installed'});f.install();f.nativeSettings();
f.reply(f.requests[0],f.proof());f.advance(0);
assert.equal(f.dialog,undefined);assert.equal(f.operation('dismiss').length,0);
// Separate helpers cannot nest their native input wrappers.
f=fixture(folder);f.install();const old=f.ctx.OpenConnectInstaller;
const close=old.message(f.fw,'Installed message','Text',{button1:{label:'OK',appData:'done'}},()=>{});
f.usb();metadata(f);assert.equal(f.controls.filter(d=>!d.destroyed).length,1);
close();f.advance(1000);assert.equal(f.controls.filter(d=>!d.destroyed).length,1);
f.closeUSB();f.advance(1000);assert.equal(f.controls.filter(d=>!d.destroyed).length,0);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
console.log('Independent maintenance: native dialogs, cancellation, admitted work, recovery and cold completion passed');

// Actual module delivery can interleave independently requested scripts. Neither
// script may infer its endpoint from the other loader's document-wide ID.
f=fixture(folder,{notice:'installed'});f.install(0);f.usb(0);
const passive=f.scripts.filter(n=>n.src.endsWith('maintenance.js'));
for(const node of passive)f.deliver(node,false);
f.advance(0);assert.equal(f.requests.length,0,'executing either asset without its captured onload is passive');
for(const node of passive)node.onload();f.advance(0);
assert.deepEqual(f.requests.map(r=>r.body.split('|')[3]),['completion','settings']);
const untouched=f.ctx.OpenConnectCompletion;
assert.equal(f.ctx.OpenConnectMaintenanceStart({token:'invalid',port:15555,role:'completion',current:()=>true}),null);
assert.equal(f.ctx.OpenConnectMaintenanceStart({token:f.token,port:15557,role:'completion',current:()=>true}),null);
assert.equal(f.ctx.OpenConnectCompletion,untouched,'invalid request cannot close an existing owner');
for(const first of ['completion','usb']){
 f=fixture(folder,{notice:'installed'});f.install(0);f.usb(0);
 const completion=f.scripts.find(n=>n.src.includes('/feature/maintenance.js'));
 const popup=f.scripts.find(n=>n.src.includes('/sessions/')&&n.src.endsWith('maintenance.js'));
 f.deliver(first==='completion'?completion:popup);f.advance(0);
 assert.match(f.requests[0].url,first==='completion'? /:15555/ : /:15557/);
 assert.equal(f.requests[0].body.split('|')[3],first==='completion'?'completion':'settings');
 f.deliver(first==='completion'?popup:completion);f.advance(0);
 const proof=f.requests.find(r=>r.url.includes(':15555'));
 const metadata=f.requests.find(r=>r.url.includes(':15557'));
 f.reply(metadata,f.metadata());f.advance(0);assert.equal(f.dialog,undefined,'USB waits for completion proof');
 f.reply(proof,f.proof());
 const owner=f.ctx.OpenConnectCompletion,shown=f.dialog;
 assert.match(shown.props.title,/installed/);f.advance(2000);
 assert.equal(f.ctx.OpenConnectCompletion,owner);assert.equal(f.dialog,shown,'USB cannot destroy completion');
 // New USB generation supersedes only the queued USB owner.
 const stale=f.ctx.OpenConnectMaintenance;f.usb(Infinity,'e'.repeat(32));
 f.reply(f.requests.at(-1),f.metadata());f.advance(0);
 assert.notEqual(f.ctx.OpenConnectMaintenance,stale);assert.equal(f.dialog,shown);
 f.pick('done');f.reply(f.operation('dismiss').at(-1),{ok:true});f.advance(1000);
 assert.equal(f.ctx.OpenConnectCompletion,null);assert.equal(f.ctx.OpenConnectMaintenance.token,'e'.repeat(32));
 assert.match(f.dialog.props.title,/Reinstall/);f.closeUSB();f.advance(1000);
 assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
}
// A timed-out USB delivery has no autonomous effects on a dismissed notice boot.
f=fixture(folder,{notice:'installed'});f.install();
f.reply(f.requests[0],f.proof());f.pick('done');
f.reply(f.operation('dismiss')[0],{ok:true});f.usb(0);const late=f.scripts.find(n=>!n.executed&&n.src.endsWith('maintenance.js'));
f.advance(65000);const beforeLate=f.allRequests.length;f.deliver(late);f.advance(0);
assert.equal(f.allRequests.length,beforeLate);assert.equal(f.ctx.OpenConnectCompletion,null);assert.equal(f.ctx.OpenConnectMaintenance,undefined);

// Open settings retains one bounded intent while the actual Settings module is
// cold. Its own lightweight read and stock selection happen exactly once.
for(const interrupted of [false,true,'modal','timeout']){
 f=fixture(folder,{notice:'installed'});f.install(0);
 f.deliver(f.scripts.find(n=>n.src.endsWith('maintenance.js')));
 f.reply(f.requests[0],f.proof());f.pick('settings');
 f.reply(f.operation('dismiss')[0],{ok:true});assert.equal(f.requests.length,2);
 assert.equal(f.ctx.OpenConnect.openSettings(),true,'repeated click shares the existing intent');
 if(interrupted===true)f.nativeSettings();
 if(interrupted==='modal')f.fw.common._vuiHelpDialog={};
 if(interrupted==='timeout')f.advance(12000);
 f.flush();f.advance(250);
 const reads=f.operation('status').filter(r=>r.body.split('|')[3]==='settings');
 if(interrupted){
  assert.equal(reads.length,0);assert.equal(f.pages.length,0);assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0);
 }else{
  assert.equal(reads.length,1);f.reply(reads[0],f.state());f.advance(200);f.advance(2000);
  assert.equal(f.pages.length,1);assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,1);
  assert.equal([...f.timers.values()].filter(t=>t.repeat===200).length,0,'successful OpenSettings cancels its interval');
 }
}

// A lost durable dismiss ACK reconciles with the narrow selected-boot proof. Late ACKs and a shared deadline never replay the mutation.
for(const outcome of ['cleared','unchanged','deadline']){
 f=fixture(folder,{notice:'installed'});f.install();
 f.reply(f.requests[0],f.proof());f.pick('settings');
 const dismiss=f.operation('dismiss')[0];f.advance(6000);assert.equal(dismiss.aborted,true);
 const readback=f.requests.at(-1);assert.equal(readback.body.split('|')[3],'completion');
 if(outcome==='deadline')f.advance(6000);
 else f.reply(readback,f.proof({notice:outcome==='cleared'?'-':'installed',completionReady:false}));
 f.reply(dismiss,{ok:true});f.advance(200);
 assert.equal(f.operation('dismiss').length,1,'unknown ACK is never resent');
 const selections=f.calls.filter(c=>c[1]==='SelectSettings');
 if(outcome==='cleared'){
  assert.equal(f.requests.at(-1).body.split('|')[3],'settings');f.reply(f.requests.at(-1),f.state());f.advance(200);
  assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,1);
 }else{assert.equal(selections.length,0);assert.equal(f.pages.length,0);}
}

// Lost ACK readback is bound to the captured selection, package and boot.
for(const changed of [{revision:'e'.repeat(64)},{package:'e'.repeat(64)},
 {boot:'87654321-1234-1234-1234-123456789abc'},{installedVersion:'0.3.0-other'}]){
 f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof());f.pick('settings');
 const ack=f.operation('dismiss')[0];f.advance(6000);
 f.reply(f.requests.at(-1),f.proof({notice:'-',completionReady:false,...changed}));
 f.reply(ack,{ok:true});f.advance(200);
 assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0);
 assert.equal(f.operation('dismiss').length,1);
}
// A definite stale refusal cannot be upgraded by a later notice readback.
f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof());f.pick('settings');
const beforeRefusal=f.requests.length;f.reply(f.operation('dismiss')[0],{ok:false,error:'stale_state'});
assert.equal(f.requests.length,beforeRefusal);assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0);
assert.match(f.dialog.props.title,/Unable to confirm/);
// Terminal ACK feedback owns its real dialog until OK, then cannot block
// either an already queued or a later eligible USB chooser.
for(const outcome of ['stale','mismatch'])for(const arrival of ['queued','later']){
 f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof());f.pick('settings');
 const ack=f.operation('dismiss')[0];
 if(outcome==='stale')f.reply(ack,{ok:false,error:'stale_state'});
 else{f.advance(6000);f.reply(f.requests.at(-1),f.proof({notice:'-',completionReady:false,package:'e'.repeat(64)}));}
 const owner=f.ctx.OpenConnectCompletion;
 assert.ok(owner);assert.equal(owner.protected(),true);assert.match(f.dialog.props.title,/Unable to confirm/);
 if(arrival==='queued'){f.usb();metadata(f,{installed:true,installedVersion:f.version,revision:'b'.repeat(64)});f.advance(1000);assert.match(f.dialog.props.title,/Unable to confirm/);}
 f.pick('done');assert.equal(f.ctx.OpenConnectCompletion,null,'feedback OK closes terminal completion');
 if(arrival==='later'){f.usb();metadata(f,{installed:true,installedVersion:f.version,revision:'b'.repeat(64)});}
 f.advance(1000);assert.match(f.dialog.props.title,/Reinstall/);
 assert.equal(f.operation('dismiss').length,1);assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0);
}
// A malformed busy response is not a definite refusal and cannot resend ACK.
f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof());f.pick('settings');
f.reply(f.operation('dismiss')[0],{error:'busy'});f.advance(500);
assert.equal(f.operation('dismiss').length,1);assert.equal(f.requests.at(-1).body.split('|')[3],'completion');
f.reply(f.requests.at(-1),f.proof({notice:'-',completionReady:true}));
assert.match(f.dialog.props.title,/Unable to confirm/);f.pick('done');
assert.equal(f.ctx.OpenConnectCompletion,null);assert.equal(f.calls.filter(c=>c[1]==='SelectSettings').length,0);
// Busy is a definite refusal: retry within the original deadline with the same proof.
f=fixture(folder,{notice:'installed'});f.install();f.reply(f.requests[0],f.proof());f.pick('done');
const ackBody=f.operation('dismiss')[0].body;f.reply(f.operation('dismiss')[0],{ok:false,error:'busy'});f.advance(500);
assert.equal(f.operation('dismiss')[1].body,ackBody);f.reply(f.operation('dismiss')[1],{ok:true});
assert.equal(f.ctx.OpenConnectCompletion,null);
// Proof may arrive before Home is idle. Show promptly on eligibility, never early.
f=fixture(folder,{notice:'installed'});f.fw._frameworkState=2;f.install();f.reply(f.requests[0],f.proof());
f.advance(4000);assert.equal(f.dialog,undefined);f.fw._frameworkState=f.fw._FWK_STATE_IDLE;
f.advance(1000);assert.match(f.dialog.props.title,/installed/);

// Unsent recovery may be superseded. Delayed old callbacks cannot revive it or
// close the new generation, even while both wait for native voice to finish.
f=fresh();f.fw.common._vuiHelpDialog={};metadata(f,{pending:true});
const waiting=f.ctx.OpenConnectMaintenance;assert.equal(waiting.protected(),false);assert.equal(f.operation('recover').length,0);
f.usb(Infinity,'e'.repeat(32));assert.notEqual(f.ctx.OpenConnectMaintenance,waiting);
metadata(f,{pending:true});delete f.fw.common._vuiHelpDialog;f.advance(1000);
assert.equal(f.operation('recover').length,1);assert.equal(f.operation('recover')[0].body.split('|')[0],'e'.repeat(32));
// Repeated delivery of the same token still belongs to the new captured loader.
f=fresh();metadata(f);const sameToken=f.ctx.OpenConnectMaintenance;f.usb();metadata(f);
assert.notEqual(f.ctx.OpenConnectMaintenance,sameToken);assert.ok(f.dialog);f.advance(1000);assert.ok(f.dialog);
// A new published generation can recover OC1 after an older write has finished
// bounded reconciliation in an unresolved state. Removal alone cannot release
// that uncertainty; replacement must not replay the old Install either.
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],null);metadata(f,{pending:true});
assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);f.closeUSB();f.advance(1000);
assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);
f.usb(Infinity,'e'.repeat(32));metadata(f,{pending:true});f.advance(1000);
assert.equal(f.operation('install').length,1);assert.equal(f.operation('recover').length,1);
assert.equal(f.operation('recover')[0].body.split('|')[0],'e'.repeat(32));

// Native Listening uses an SBN, with neither Help nor Examples present. Check
// every active stock voice state both before Recover and just before Restart.
for(const voice of ['Playing Prompt','Listening','Processing','Playing Terminating Prompt']){
 f=fresh();f.fw.common._cachedVuiState=voice;metadata(f,{pending:true});f.advance(1000);
 assert.equal(f.operation('recover').length,0);assert.equal(f.dialog,undefined);
 f.fw.common._cachedVuiState='Idle';f.advance(1000);assert.equal(f.operation('recover').length,1);
 f.fw.common._cachedVuiState=voice;f.reply(f.operation('recover')[0],commit(f));
 assert.equal(f.operation('restart').length,0);assert.equal(f.dialog,undefined);
 assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
 f.fw.common._cachedVuiState='Idle';f.advance(1000);assert.equal(f.operation('restart').length,1);
}

// Real registered capture listeners must suppress touch before it reaches the
// native target during progress, and disappear on a native interruption.
f=fresh();metadata(f);f.pick('install');
for(const type of ['mousedown','mouseup','click']){
 const event=f.touch(type);assert.equal(event.defaultPrevented,true);assert.equal(event.stopped,true);
}
assert.equal(f.calls.filter(c=>c[0]==='touch-target').length,0);
f.fw.common._cachedVuiState='Listening';f.touch('mousedown');
assert.equal(f.dialog,undefined);assert.equal(f.touch('click').stopped,undefined);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);

// Full uncertain-write reconciliation is bounded and never replays a write.
f=fresh();metadata(f);f.pick('install');const uncertain=f.operation('install')[0];f.advance(185000);
assert.equal(uncertain.aborted,true);assert.equal(f.requests.at(-1).body.split('|')[3],'-');
f.advance(12000);f.reply(uncertain,commit(f));f.advance(1000);
assert.equal(f.operation('install').length,1);assert.equal(f.operation('restart').length,0);
assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);assert.match(f.dialog.props.title,/Unable to confirm/);
console.log('Maintenance regressions: staged roles, completion priority, cold intent, ACK deadlines, replacement, native VUI and touch capture passed');
for(const event of ['Global.StartHelp','Global.StartExamples']){
 f=fresh();metadata(f);const home=f.armHome();f.pick('install');
 assert.equal(home.button._holdTimeoutId,null);assert.equal(home.button._isEnabled,false);f.advance(600);assert.deepEqual(home.fired,[]);
 for(const key of ['select','selectStart','goBack','cw','ccw','left','right','up','down'])assert.equal(f.fw.common.handleControllerEvent(key,false),undefined);
 assert.equal(f.fw.common._messageTable[event](),'native voice');assert.equal(f.dialog,undefined);
 assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
 for(const key of Object.keys(home.original))assert.equal(home.button.properties[key],home.original[key]);
 for(const key of Object.keys(home.messages))assert.equal(f.fw.common._messageTable[key],home.messages[key]);
 assert.equal(f.touch('click').stopped,undefined);assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);
 f.ctx.OpenConnectMaintenance.close();assert.equal(f.fw.common._openConnectOperation,undefined);
}

// The USB popup consumes an operation ACK without inventing Settings state.
for(const delay of [0,11000]){
 f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],commit(f));
 const request=f.operation('restart')[0];f.advance(delay);
 f.reply(request,{ok:true,restarting:true});
 f.advance(1000);assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 f.advance(10999);assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 f.advance(1);assert.match(f.dialog.props.title,/Unable to confirm/);
 assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);assert.equal(f.operation('restart').length,1);
 f.reply(request,{ok:true,restarting:true});f.advance(1000);
 assert.equal(f.operation('restart').length,1);assert.match(f.dialog.props.title,/Unable to confirm/);
}
for(const answer of [null,{ok:false,error:'state_changed'},{ok:true,restarting:false},{ok:true},'legacy']){
 f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],commit(f));
 const request=f.operation('restart')[0];f.advance(11000);f.reply(request,answer==='legacy'?f.state({restart:true}):answer);
 assert.equal(f.requests.at(-1).body.split('|')[3],'-','restart uncertainty reads full physical state');
 f.advance(1000);assert.match(f.dialog.props.title,/Unable to confirm/);
 assert.equal(f.operation('restart').length,1);assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);
 f.reply(request,{ok:true,restarting:true});f.advance(15000);assert.equal(f.operation('restart').length,1);
}
console.log('USB restart: late narrow ACK gets full handoff; negative/lost/malformed stays bounded without replay');
f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],commit(f));
const silentRestart=f.operation('restart')[0];f.advance(12000);
assert.equal(silentRestart.aborted,true);assert.match(f.dialog.props.title,/Unable to confirm/);
f.reply(silentRestart,{ok:true,restarting:true});f.advance(15000);
assert.equal(f.operation('restart').length,1);assert.equal(f.ctx.OpenConnectMaintenance.protected(),true);

// A late Install proof and native voice cannot consume restart admission time.
for(const pause of [0,15000]){
 f=fresh();metadata(f);f.pick('install');
 f.reply(f.operation('install')[0],null);const proof=f.requests.at(-1);
 assert.equal(proof.body.split('|')[3],'-');f.advance(11000);
 if(pause)f.fw.common._cachedVuiState='Listening';
 f.reply(proof,commit(f));
 if(pause){
  assert.equal(f.operation('restart').length,0);f.advance(pause);
  f.fw.common._cachedVuiState='Idle';f.advance(1000);
 }
 const request=f.operation('restart')[0];assert.ok(request);
 f.advance(11000);assert.equal(request.aborted,undefined);
 f.reply(request,{ok:true,restarting:true});f.advance(1000);
 assert.match(f.dialog.props.text1,/Restarting Mazda Connect/);
 assert.equal(f.operation('install').length,1);assert.equal(f.operation('restart').length,1);
}
// A settled Install readback cannot acknowledge its lost/negative restart.
for(const answer of [null,{ok:false,error:'state_changed'},{ok:true}]){
 f=fresh();metadata(f);f.pick('install');f.reply(f.operation('install')[0],commit(f));
 const restart=f.operation('restart')[0];f.advance(1000);f.reply(restart,answer);
 const readback=f.requests.at(-1);assert.equal(readback.body.split('|')[3],'-');f.reply(readback,commit(f));
 assert.match(f.dialog.props.title,answer&&answer.ok===false?/Unable to finish/:/Unable to confirm/);
 const feedback=f.dialog;f.reply(restart,{ok:true,restarting:true});f.reply(readback,commit(f));f.advance(15000);
 assert.equal(f.dialog,feedback);assert.equal(f.operation('restart').length,1);
 assert.equal(f.ctx.OpenConnectMaintenance.protected(),!(answer&&answer.ok===false));
}
console.log('USB restart owns a fresh send deadline after late write proof/VUI; completed readback cannot prove reboot');
