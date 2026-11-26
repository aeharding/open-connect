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
