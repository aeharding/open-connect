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
 f.legacyUSB();const metadata=f.requests.at(-1),discovery=f.ctx.__ocUSBLoading;
 assert.equal(discovery.owner,client,'temporary discovery lets the old owner cancel for Settings writes');
 assert.equal(discovery.wait,undefined,'discovery carries no shared Settings read');
 f.nativeSettings();f.tap();f.endAnimations();
 assert.equal(f.pages.length,2,'cached old Settings first tap remains independent of USB metadata');
 assert.equal(f.requests.at(-1),metadata);f.homeScreen();identities(f);
 f.reply(metadata,f.metadata({installedVersion:oldVersion}));f.advance(0);
 assert.equal(f.ctx.__ocUSBLoading,undefined);assert.equal(discovery.owner,null,'first display releases discovery');
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

for(const stage of ['loader','helper','metadata']){
 const f=fixture(folder,{sourceFor(url,source){return url.includes('/sessions/')?source:legacy[url.split('/').at(-1)]||source;}});
 const oldVersion=legacy.VERSION.trim();f.meta.version=oldVersion;f.install();f.advance(500);
 const client=f.ctx.OpenConnect,menus=f.ctx.OpenConnectSettings,dialogs=f.ctx.OpenConnectInstaller;
 f.legacyUSB(stage==='loader'?0:stage==='helper'?1:Infinity);
 const discovery=f.ctx.__ocUSBLoading,metadata=stage==='metadata'?f.requests.at(-1):null;
 f.nativeSettings();const row=f.list.properties.selectCallback;f.tap();
 const read=f.requests.at(-1);
 assert.ok(read.url.includes(':15555/'),'cold first tap reads the installed endpoint immediately during '+stage);
 assert.notEqual(read,metadata);f.reply(read,f.state({version:oldVersion,installedVersion:oldVersion}));f.endAnimations();
 assert.equal(f.pages.length,1);assert.equal(f.ctx.__ocUSBLoading,discovery,'a read does not cancel discovery');
 select(f,0);select(f,1);f.advance(1000);
 assert.equal(f.operation('set').length,1,'deliberate old-owner preference write cancels '+stage+' discovery');
 assert.equal(discovery.owner,null);assert.equal(f.ctx.OpenConnectMaintenance,stage==='metadata'?null:undefined);
 f.reply(f.operation('set')[0],f.state({version:oldVersion,installedVersion:oldVersion,touch:1,revision:'d'.repeat(64)}));
 if(metadata)f.reply(metadata,f.metadata({installedVersion:oldVersion}));
 f.flush();f.advance(66000);
 assert.equal(f.dialog,undefined,'late delivery/reply cannot reopen canceled discovery');
 assert.equal(f.ctx.__ocUSBLoading,undefined);f.homeScreen();identities(f);
 assert.equal(f.ctx.OpenConnect,client);assert.equal(f.ctx.OpenConnectSettings,menus);
 assert.equal(f.ctx.OpenConnectInstaller,dialogs);assert.equal(f.list.properties.selectCallback,row);
}
console.log('Actual dev.22 cold first tap and deliberate Settings write cancel only transient loader/helper/metadata discovery');
