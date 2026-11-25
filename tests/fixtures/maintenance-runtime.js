const assert=require('node:assert/strict'),fixture=require('./runtime-fixture.js');
const folder=process.argv[2];
function fresh(options={}){const f=fixture(folder,{installed:false,...options});f.usb();return f;}
function full(f,extra={}){f.reply(f.requests.at(-1),f.state({installed:false,installedVersion:'-',revision:'-',...extra}));f.advance(0);}
function commit(f,extra={}){return f.state({installed:true,installedVersion:f.version,revision:'d'.repeat(64),notice:'installed',restart:true,...extra});}
let f=fresh();assert.equal(f.ctx.OpenConnect,undefined);assert.equal(f.ctx.OpenConnectSettings,undefined);assert.equal(f.ctx.OpenConnectInstaller,undefined);
assert.deepEqual(f.scripts.map(n=>n.src.split('/').at(-1)),['loader.js','maintenance.js']);
full(f);assert.deepEqual(Object.values(f.dialog.props.buttonConfig).map(b=>b.appData),['cancel','install']);
f.pick('cancel');assert.equal(f.requests.at(-1).body.split('|')[3],'usb');f.reply(f.requests.at(-1),{ok:true});
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
f=fresh();full(f);f.closeUSB();f.advance(1000);assert.equal(f.dialog,undefined);assert.equal(f.operation('dismiss').length,0);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);
f=fresh();full(f);f.pick('install');
assert.equal(f.dialog.props.contentStyle,'style27');assert.equal(f.operation('install').length,1);
f.reply(f.operation('install')[0],commit(f));assert.equal(f.operation('restart').length,1);
assert.equal(f.dialog.props.contentStyle,'style27');f.closeUSB();f.advance(1000);
assert.equal(f.ctx.OpenConnectMaintenance.protected(),true,'removal retains an admitted operation');
assert.equal(f.operation('restart').length,1);
// Removal winning before backend admission is an explicit, safe refusal.
f=fresh();full(f);f.pick('install');f.reply(f.operation('install')[0],{ok:false,error:'session_closed'});
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.equal(f.operation('restart').length,0);
// Unknown write results reconcile once and never resend the mutation.
f=fresh();full(f);f.pick('install');f.reply(f.operation('install')[0],null);
assert.equal(f.operation('install').length,1);assert.equal(f.requests.at(-1).body.split('|')[2],'status');
f.reply(f.requests.at(-1),commit(f));assert.equal(f.operation('restart').length,1);
f=fresh();full(f);f.pick('install');f.reply(f.operation('install')[0],{ok:false,error:'stale_state'});
f.reply(f.requests.at(-1),commit(f));assert.equal(f.operation('restart').length,0,'definite refusal cannot become inferred success');
// Recovery waits for visible progress and restart reacquires it after VUI.
f=fresh();f.fw.common._vuiHelpDialog={};full(f,{pending:true});
assert.equal(f.operation('recover').length,0);assert.equal(f.controls.length,0);
f.advance(2000);assert.equal(f.operation('recover').length,0);
delete f.fw.common._vuiHelpDialog;f.advance(1000);assert.equal(f.operation('recover').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
f.fw.common._vuiHelpDialog={};f.fw.common.handleControllerEvent('help',false);
f.reply(f.operation('recover')[0],commit(f));assert.equal(f.operation('restart').length,0);
delete f.fw.common._vuiHelpDialog;f.advance(1000);assert.equal(f.operation('restart').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
// Completion is installed-package maintenance, not a warm Settings store.
f=fixture(folder,{notice:'installed'});f.install();f.advance(0);
assert.equal(f.requests.length,1);assert.equal(f.requests[0].body.split('|')[3],'completion');
f.reply(f.requests[0],f.state({notice:'installed',completionReady:true}));f.advance(0);
assert.match(f.dialog.props.title,/installed/);const settings=f.ctx.OpenConnect;
f.pick('settings');assert.equal(f.requests.at(-1).body.split('|')[2],'dismiss');
f.reply(f.requests.at(-1),{ok:true});assert.equal(f.ctx.OpenConnect,settings);
assert.equal(f.requests.at(-1).body.split('|')[3],'settings','Open settings obtains its own cold status');
f.reply(f.requests.at(-1),f.state());f.advance(200);assert.equal(f.pages.length,1);f.assertNative();
// A manual visit suppresses a pending completion locally, without acknowledging it.
f=fixture(folder,{notice:'installed'});f.install();f.nativeSettings();
f.reply(f.requests[0],f.state({notice:'installed',completionReady:true}));f.advance(0);
assert.equal(f.dialog,undefined);assert.equal(f.operation('dismiss').length,0);
// Separate helpers cannot nest their native input wrappers.
f=fixture(folder);f.install();const old=f.ctx.OpenConnectInstaller;
const close=old.message(f.fw,'Installed message','Text',{button1:{label:'OK',appData:'done'}},()=>{});
f.usb();full(f);assert.equal(f.controls.filter(d=>!d.destroyed).length,1);
close();f.advance(1000);assert.equal(f.controls.filter(d=>!d.destroyed).length,1);
f.closeUSB();f.advance(1000);assert.equal(f.controls.filter(d=>!d.destroyed).length,0);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
console.log('Independent maintenance: native dialogs, cancellation, admitted work, recovery and cold completion passed');
