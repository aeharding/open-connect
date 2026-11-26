// Keep the actual dev.22 installed client alive beneath the dev.23 USB popup.
// Git supplies reviewed historical source; no copied compatibility runtime.
const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const fixture=require('./runtime-fixture.js'),folder=process.argv[2];
const base='71472aa42892a48e1f1b4a9562d8e8e6aa9def3a',legacy={};
for(const name of ['runtime.js','dialog.js','settings.js','VERSION']){
 legacy[name]=execFileSync('git',['show',base+':cmu/installer/'+name],{cwd:path.resolve(folder),encoding:'utf8'});
}
function select(f,key){const p=f.pages.at(-1);p.list2Ctrl.selectCallback(p.list2Ctrl,key);f.endAnimations();}
function identities(f){
 assert.equal(f.fw.common.handleControllerEvent,f.oldInput);
 assert.equal(f.fw.common.getCommonTransitionData,f.oldTransition);
 assert.equal(f.host.handleControllerEvent,f.oldInput);
 assert.equal(f.fw.sendEventToMmui,f.oldSend);
}
for(const outcome of ['restart','refused','superseded']){
 const f=fixture(folder,{sourceFor(url,source){
  return url.includes('/sessions/')?source:legacy[url.split('/').at(-1)]||source;
 }});
 const oldVersion=legacy.VERSION.trim();f.meta.version=oldVersion;
 f.install();f.advance(500);f.nativeSettings();f.tap();
 f.reply(f.requests.at(-1),f.state({version:oldVersion,installedVersion:oldVersion}));f.endAnimations();
 assert.equal(f.pages.length,1);f.homeScreen();identities(f);
 const client=f.ctx.OpenConnect,menus=f.ctx.OpenConnectSettings,dialogs=f.ctx.OpenConnectInstaller;
 const row=f.list.properties.selectCallback;
 f.usb();const metadata=f.requests.at(-1);
 assert.equal(f.ctx.__ocUSBLoading,undefined,'metadata discovery takes no legacy admission claim');
 f.nativeSettings();f.tap();f.endAnimations();
 assert.equal(f.pages.length,2,'cached old Settings first tap remains independent of USB metadata');
 assert.equal(f.requests.at(-1),metadata);f.homeScreen();identities(f);
 f.reply(metadata,f.metadata({installedVersion:oldVersion}));f.advance(0);
 assert.match(f.dialog.props.title,/Update/);f.pick('install');
 const write=f.operation('install')[0],claim=f.ctx.__ocUSBLoading;
 assert.ok(claim,'admitted mutation uses legacy foreign claim');
 assert.equal(f.dialog.props.contentStyle,'style27');
 f.nativeSettings();f.tap();f.endAnimations();
 assert.equal(f.pages.length,3,'the actual old Settings page can open during native interruption');
 const transition=f.fw.common.getCommonTransitionData,send=f.fw.sendEventToMmui,input=f.host.handleControllerEvent;
 select(f,0);select(f,1);f.advance(1000);
 assert.equal(f.operation('set').length,0,'old runtime refuses Set during admitted USB work');
 assert.equal(f.dialog,undefined,'USB progress does not cover the old page');
 assert.equal(f.fw.common.getCommonTransitionData,transition);
 assert.equal(f.fw.sendEventToMmui,send);assert.equal(f.host.handleControllerEvent,input);
 if(outcome==='refused'){
  f.reply(write,{ok:false,error:'preflight_failed'});
  f.reply(f.requests.at(-1),f.state());f.advance(1000);
  assert.equal(f.ctx.__ocUSBLoading,undefined,'definite refusal releases only its admission');
 }else{
  f.reply(write,f.state({restart:true,notice:'installed',revision:'d'.repeat(64)}));f.advance(1000);
  assert.equal(f.operation('restart').length,0,'Restart waits for idle Home too');
  assert.equal(f.ctx.__ocUSBLoading,claim,'suspended admitted work retains its legacy claim');
 }
 assert.equal(f.dialog,undefined);
 f.fw.sendEventToMmui('common','Global.IntentHome');f.homeScreen();identities(f);
 f.fw._frameworkState=2;f.advance(1000);
 assert.equal(f.dialog,undefined,'transitioning Home is not idle Home');
 assert.equal(f.operation('restart').length,0);
 f.fw._frameworkState=f.fw._FWK_STATE_IDLE;
 f.advance(1000);
 if(outcome!=='refused'){
  assert.equal(f.operation('restart').length,1);assert.equal(f.dialog.props.contentStyle,'style27');
 }
 if(outcome==='superseded'){
  const foreign={};f.ctx.__ocUSBLoading=foreign;f.ctx.OpenConnectMaintenance.close();
  assert.equal(f.ctx.__ocUSBLoading,foreign,'cleanup cannot release another admission identity');
 }else{
  f.ctx.OpenConnectMaintenance.close();assert.equal(f.ctx.__ocUSBLoading,undefined);
 }
 identities(f);
 assert.equal(f.ctx.OpenConnect,client);assert.equal(f.ctx.OpenConnectSettings,menus);
 assert.equal(f.ctx.OpenConnectInstaller,dialogs);assert.equal(f.list.properties.selectCallback,row);
 f.reply(write,f.state({restart:true}));f.advance(1000);identities(f);
 assert.equal(f.operation('install').length,1);assert.equal(f.operation('set').length,0);
}
console.log('Actual dev.22 Settings with dev.23 popup: transparent discovery, legacy admission, Home-only restart and exact callbacks passed');
