const assert=require('node:assert/strict'),path=require('node:path'),fixture=require('./runtime-fixture.js');
const folder=path.dirname(process.argv[2]);
let f=fixture(folder);f.install();const installed=f.ctx.OpenConnect;
f.usb(0);f.evaluate('loader.js');assert.equal(f.scripts.filter(n=>n.src.endsWith('maintenance.js')).length,1);
assert.equal(f.ctx.OpenConnect,installed);f.advance(65000);assert.equal(f.ctx.__ocMaintenanceLoading,undefined);
f.flush();f.advance(0);assert.equal(f.requests.length,0);assert.equal(f.ctx.OpenConnect,installed);
f=fixture(folder);f.install();f.usb(0);
const entry=f.ctx.document.getElementById('oc-maintenance-loader');
entry.parentNode.removeChild(entry);
const replacement={id:'oc-maintenance-loader',src:'file:///tmp/other/loader.js',ocToken:'e'.repeat(32)};
f.ctx.document.querySelector('head').appendChild(replacement);replacement.executed=true;
const later={token:replacement.ocToken};f.ctx.__ocMaintenanceLoading=later;
f.advance(65000);assert.equal(f.ctx.__ocMaintenanceLoading,later);
assert.equal(f.ctx.document.getElementById('oc-maintenance-loader'),replacement);
// The script itself is passive. Only a requesting callback with its still-current
// captured node can start a popup; delayed A cannot infer B from B's DOM ID.
f=fixture(folder);f.install();const stale=f.usb(0);
stale.parentNode.removeChild(stale);
const current={id:'oc-maintenance-loader',src:'file:///tmp/new/loader.js',ocToken:'e'.repeat(32),ocPort:15557};
f.ctx.document.querySelector('head').appendChild(current);current.executed=true;
const before=f.scripts.length;f.evaluate('loader.js');assert.equal(f.scripts.length,before);
f.ctx.OpenConnectUSBStart(stale);assert.equal(f.scripts.length,before,'stale captured loader cannot start from B');
f.ctx.OpenConnectUSBStart(current);assert.equal(f.scripts.length,before+1);assert.equal(f.ctx.__ocMaintenanceGeneration.token,current.ocToken);
console.log('USB loader loads only its popup; stale cleanup leaves installed Settings and later entries intact');

// Actual stock Navigate data/callback envelope: ownership starts before delivery.
for(const delay of [100,66000]){
 f=fixture(folder,{installed:false});
 const a=f.legacyUSB(0),holdA=f.ctx.__ocUSBLoading;
 assert.ok(holdA,'legacy entry owns discovery before loader delivery');
 assert.equal(holdA.role,'usb-discovery');f.advance(delay);
 if(delay>65000){assert.equal(a.parentNode,null);assert.equal(f.ctx.__ocUSBLoading,undefined);}
 const b=f.legacyUSB(0,'e'.repeat(32),'session-DEF456'),holdB=f.ctx.__ocUSBLoading;
 assert.notEqual(b,a);assert.equal(a.parentNode,null);assert.equal(holdA.owner,null);
 f.deliver(a); // Native pairs each script's evaluation with its own onload.
 assert.equal(f.ctx.document.getElementById('oc-maintenance-loader'),b);
 assert.equal(f.ctx.__ocUSBLoading,holdB);assert.equal(f.ctx.__ocMaintenanceLoading,undefined);
 assert.equal(f.scripts.filter(n=>n.src.endsWith('/maintenance.js')).length,0,'late A cannot run B');
 f.deliver(b);f.flush();f.advance(0);const client=f.ctx.OpenConnectMaintenance;
 f.reply(f.requests.at(-1),f.metadata({installed:false,installedVersion:'-'}));f.advance(0);
 assert.match(f.dialog.props.title,/Install/);assert.equal(f.ctx.__ocUSBLoading,undefined);
 assert.equal(holdB.owner,null,'first display drops the temporary installed-owner reference');
 a.onload();assert.equal(f.ctx.OpenConnectMaintenance,client,'late A callback cannot close B');
 f.pick('cancel');f.reply(f.operation('dismiss')[0],{ok:true});f.advance(65000);
 assert.equal(f.timers.size,0,'entry and popup deadlines are released after dismissal');
}
f=fixture(folder,{installed:false});
const late=f.legacyUSB(1),helper=f.ctx.document.getElementById('oc-maintenance-popup');
assert.ok(helper);f.advance(65000);
assert.equal(late.parentNode,null);assert.equal(helper.parentNode,null);assert.equal(f.ctx.__ocUSBLoading,undefined);
f.deliver(helper);assert.equal(f.ctx.OpenConnectMaintenance,undefined,'late helper delivery after timeout stays passive');
f.legacyUSB(Infinity,'e'.repeat(32),'session-DEF456');
f.reply(f.requests.at(-1),f.metadata({installed:false,installedVersion:'-'}));f.advance(0);
assert.match(f.dialog.props.title,/Install/,'a timed-out helper does not block the next entry');
// The same entry budget covers metadata and its late session/read callbacks.
f=fixture(folder,{installed:false});f.legacyUSB();
const metadata=f.requests.at(-1),discovery=f.ctx.__ocUSBLoading;
f.advance(65000);assert.equal(f.ctx.__ocUSBLoading,undefined);assert.equal(discovery.owner,null);
assert.equal(f.ctx.OpenConnectMaintenance,null);assert.ok(metadata.aborted);
f.reply(metadata,f.metadata({installed:false,installedVersion:'-'}));f.advance(1000);
assert.equal(f.dialog,undefined);assert.equal(f.timers.size,0,'late metadata cannot renew abandoned discovery');
console.log('Legacy Navigate: bounded pre-delivery ownership, replacement, paired late callbacks and helper timeout passed');
