const assert=require('node:assert/strict'),path=require('node:path'),fixture=require('./runtime-fixture.js');
const f=fixture(path.dirname(process.argv[2]));f.install();const ui=f.ctx.OpenConnectInstaller;
assert.equal(ui.choose,undefined);assert.equal(ui.complete,undefined,'installed helper has no installer popup');
const close=ui.message(f.fw,'Title','Text',{button1:{label:'OK',appData:'done'}},()=>{});
assert.equal(typeof close,'function');assert.equal(ui.message(f.fw,'Another','Text',{},()=>{}),false);
const d=f.dialog;close();assert.equal(d.destroyed,true);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
f.nativeSettings();assert.equal(ui.claim(f.fw),true);
const p=ui.progress(f.fw,'Applying changes','Do not turn off the car.',()=>{});
assert.equal(p.update('Restarting Mazda Connect','Do not turn off the car.'),true);
assert.equal(f.dialog.props.contentStyle,'style27');p.close();ui.release(f.fw);
assert.equal(f.fw.common.handleControllerEvent,f.oldInput);assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
ui.about(f.fw,f.version,()=>{});assert.match(f.dialog.props.text1,/Open Connect/);f.pick('done');
ui.confirmUninstall(f.fw,false,()=>{});assert.deepEqual(Object.values(f.dialog.props.buttonConfig).map(b=>b.appData),['cancel','uninstall']);
f.pick('cancel');assert.equal(f.fw.common._openConnectDialog,undefined);
console.log('Installed dialog helper: native input, progress, About and uninstall lifecycle passed');
for(const event of ['Global.StartHelp','Global.StartExamples']){
 const x=fixture(path.dirname(process.argv[2]));x.install();const helper=x.ctx.OpenConnectInstaller,home=x.armHome();
 assert.equal(helper.claim(x.fw),true);const progress=helper.progress(x.fw,'Applying','Keep power on',()=>{});
 assert.ok(progress);assert.equal(home.button._holdTimeoutId,null);assert.equal(home.button._isEnabled,false);
 for(const key of ['select','selectStart','goBack','cw','ccw','left','right','up','down'])assert.equal(x.fw.common.handleControllerEvent(key,false),undefined);
 for(const type of ['mousedown','mouseup','click']){const e=x.touch(type);assert.equal(e.stopped,true);assert.equal(e.defaultPrevented,true);}
 x.advance(600);assert.deepEqual(home.fired,[],'prearmed hold is released without firing any callback');
 assert.equal(x.fw.common._messageTable[event](),'native voice');assert.equal(x.dialog,undefined);
 assert.equal(x.fw.common.handleControllerEvent,x.oldInput);assert.equal(x.fw.common.getCommonTransitionData,x.oldTransition);
 for(const key of Object.keys(home.original))assert.equal(home.button.properties[key],home.original[key]);
 for(const key of Object.keys(home.messages))assert.equal(x.fw.common._messageTable[key],home.messages[key]);
 assert.equal(x.touch('click').stopped,undefined);helper.release(x.fw);
}
console.log('Installed native progress: touch/commander suppression, Home hold cleanup and exact Help/Examples restoration passed');
