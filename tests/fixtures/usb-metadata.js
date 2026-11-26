// Feed unmodified shell backend stdout through the actual USB loader and popup.
// Usage: node tests/fixtures/usb-metadata.js cmu/installer fresh|pending < reply.json
const assert=require('node:assert/strict'),fs=require('node:fs'),fixture=require('./runtime-fixture.js');
const [folder,expected]=process.argv.slice(2);
assert.ok(expected==='fresh'||expected==='pending','expected fresh or pending');
const raw=JSON.parse(fs.readFileSync(0,'utf8'));
const f=fixture(folder,{installed:false});f.usb();
const read=f.requests.at(-1);
assert.equal(read.body.split('|')[3],'settings');
f.reply(read,raw);f.advance(0);
assert.deepEqual(f.allRequests.slice(0,3).map(r=>r.body.split('|')[3]),['session','settings','session'],
 'probe before and after metadata');
assert.equal(Object.hasOwn(raw,'conflict'),false,'exercise the unaudited backend shape');
if(expected==='fresh'){
 assert.equal(raw.pending,false);assert.equal(raw.installed,false);
 assert.equal(f.dialog.props.title,'Install Open Connect?');
 assert.deepEqual(Object.values(f.dialog.props.buttonConfig).map(b=>b.appData),['cancel','install']);
 f.pick('install');
}else assert.equal(raw.pending,true);
const op=expected==='fresh'?'install':'recover';
assert.equal(f.operation(op).length,1);
assert.equal(f.operation(op)[0].body.split('|')[1],raw.revision);
assert.match(f.operation(op)[0].url,/:15557\/control$/);
assert.equal(f.dialog.props.contentStyle,'style27');
assert.equal(f.operation('restart').length,0);
console.log('Raw USB metadata accepted; '+op+' admitted under native progress');
