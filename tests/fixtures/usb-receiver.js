const assert=require('node:assert/strict'),fixture=require('./runtime-fixture.js');
const folder=process.argv[2];
function device(){return {_connectedDevs:{A:{},B:{}},_messageTable:{
 TimedSbn_ConnectionStatus(message){this.native=(this.native||0)+1;this.last=message;return 'Mazda banner';}
}};}
function connected(f,app,extra={}){
 return app._messageTable.TimedSbn_ConnectionStatus.call(app,{params:{payload:{status:'Connected',type:'UMASS',usb:'A',...extra}}});
}
function media(token='c'.repeat(32),session='session-ABC123'){return {ok:true,media:{token,session}};}
let app=device(),f=fixture(folder,{usbApp:app,autoMedia:false});f.install();
assert.equal(f.mediaRequests.length,1);f.reply(f.mediaRequests[0],{ok:true,media:null});
const lookups=f.lookups,owner=f.ctx.OpenConnect;
f.advance(90000);assert.equal(f.mediaRequests.length,1,'no idle discovery interval');assert.equal(f.lookups,lookups);
for(const extra of [{type:'IPOD'},{status:'Disconnected'},{usb:'C'}])connected(f,app,extra);
assert.equal(f.mediaRequests.length,1,'unrelated media has no discovery work');
assert.equal(connected(f,app),'Mazda banner');assert.equal(app.native,4,'native handler called exactly once per delivery');
const waiting=f.mediaRequests.at(-1);assert.ok(waiting.url.includes(':15555/'));assert.equal(waiting.body.split('|')[3],'media');
f.nativeSettings();const select=f.list.properties.selectCallback;f.tap();
assert.equal(f.requests.length,1,'cold Settings has its own immediate read during discovery');
f.reply(f.requests[0],f.state());f.endAnimations();assert.equal(f.pages.length,1);assert.equal(f.ctx.OpenConnect,owner);
f.homeScreen();f.reply(waiting,null);f.advance(500);assert.equal(f.mediaRequests.length,3,'event retries missing publication');
f.reply(f.mediaRequests.at(-1),media());f.flush();f.advance(0);
const metadata=f.requests.at(-1);assert.equal(metadata.body.split('|')[3],'settings');
f.reply(metadata,f.state());f.advance(0);assert.ok(f.dialog,'one eligible popup');
assert.equal(f.ctx.OpenConnect,owner);assert.equal(f.list.properties.selectCallback,select);

// A cold app binds after native initialization, before its triggering dispatch.
f=fixture(folder,{autoMedia:false});f.install();f.reply(f.mediaRequests[0],{ok:true,media:null});
app=device();f.fw._appInstances.usbaudio=app;
assert.equal(f.fw._initApp('usbaudio'),app);connected(f,app);
assert.equal(app.native,1);assert.equal(f.mediaRequests.length,2);
const early=f.mediaRequests.at(-1);connected(f,app,{usb:'B'});
assert.ok(early.aborted);f.reply(early,media());
assert.equal(f.scripts.filter(n=>n.src.endsWith('/loader.js')).length,0,'late A read cannot consume B offer');
f.reply(f.mediaRequests.at(-1),media('e'.repeat(32),'session-DEF456'));
const first=f.scripts.find(n=>n.src.endsWith('/loader.js'));f.deliver(first,false);
connected(f,app);f.reply(f.mediaRequests.at(-1),media('f'.repeat(32),'session-GHI789'));
const second=f.scripts.find(n=>n.src.includes('session-GHI789'));
first.onload();assert.equal(f.ctx.__ocMaintenanceLoading,undefined,'late captured A loader stays passive');
f.deliver(second);f.flush();f.advance(0);
assert.equal(f.ctx.__ocMaintenanceGeneration.token,'f'.repeat(32));
first.onload();assert.equal(f.ctx.__ocMaintenanceGeneration.token,'f'.repeat(32),'late A cannot remove B');

// An already-connected app starts one bounded window. Retry and transport
// deadlines share that budget; unsupported/failed listeners do not poll forever.
app=device();app._connectedDevs.A={deviceId:1,type:'UMASS'};
f=fixture(folder,{usbApp:app,autoMedia:false});f.install();
f.advance(65000);const count=f.mediaRequests.length;
f.advance(90000);assert.equal(f.mediaRequests.length,count);assert.equal(f.timers.size,0);
assert.ok(count>1&&count<25,'only bounded requests while discovery is active');

for(const invalid of [media('c'.repeat(32),'../session-ABC123'),media('not-a-token'),{ok:true,media:{session:5,token:5}}]){
 f=fixture(folder,{autoMedia:false});f.install();f.reply(f.mediaRequests[0],invalid);f.advance(90000);
 assert.equal(f.mediaRequests.length,1);assert.equal(f.scripts.filter(n=>n.src.endsWith('/loader.js')).length,0);
}
console.log('USB receiver preserves native callback and installed Settings; eligibility, stale generations and deadlines passed');
