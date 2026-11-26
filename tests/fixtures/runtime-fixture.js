// Native surfaces are simulated; every browser module comes from the product.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const element=require('./ui-element.js');
module.exports=function fixture(folder,options={}){
 const token='a'.repeat(32),usbToken='c'.repeat(32),revision='b'.repeat(64);
 const version=fs.readFileSync(path.join(folder,'VERSION'),'utf8').trim();
 const timers=new Map(),scripts=[],requests=[],mediaRequests=[],allRequests=[],controls=[],pages=[],calls=[],listeners=new Map();
 const parent=element(),head=element();
 parent.children=[];head.children=[];
 for(const p of [parent,head]){
  p.appendChild=function(n){if(n.parentNode&&n.parentNode!==this&&n.parentNode.removeChild)n.parentNode.removeChild(n);n.parentNode=this;if(!this.children.includes(n))this.children.push(n);};
  p.removeChild=function(n){const i=this.children.indexOf(n);if(i!==-1)this.children.splice(i,1);n.parentNode=null;};
 }
 let now=0,next=0,current='system',context='HomeScreen',lookups=0,closedUSB=false,closedBoot=false;
 const oldInput=function(){return 'Mazda input';},oldTransition=function(){return 'Mazda transition';};
 const host={divElt:element(parent),contextInfo:{uiaId:'syssettings',ctxtId:'SystemTab'},handleControllerEvent:oldInput};
 const rowSelect=function(c,value){calls.push(['stock-row',value]);};
 const list={properties:{selectCallback:rowSelect},dataList:{items:[],itemCount:0},
  setDataList(data){this.dataList=data;},updateItems(){}};
 host.list2Ctrl=list;
 const app={_currentContextTemplate:host,_contextTable:{SystemTab:{readyFunction(){
  list.setDataList({items:[{appData:'SelectAbout'}],itemCount:1,itemCountKnown:true});
 }}}};
 const apps=options.lateApp?{}:{syssettings:app};
 if(options.usbApp)apps.usbaudio=options.usbApp;
 const home={divElt:element(parent),contextInfo:{uiaId:'system',ctxtId:'HomeScreen'}};
 const fw={_browserShown:true,_frameworkState:1,_FWK_STATE_IDLE:1,_currTmpltInstance:home,
  _appInstances:apps,_focusStack:[{id:'system'}],transitionsObj:{native:true},
  common:{handleControllerEvent:oldInput,getCommonTransitionData:oldTransition},
  multicontroller:{getMode(){return 'controllerActive';}},
  getCurrentApp(){return current;},getCurrCtxtId(){return context;},
  getAppInstance(id){lookups++;return apps[id];},
  _initApp(id){if(id==='syssettings')apps.syssettings=app;return apps[id];},
  sendEventToMmui(id,event){calls.push([id,event]);if(event==='SelectSettings')nativeSettings();},
  instantiateControl(id,container,kind,props){
   assert.equal(kind,'Dialog3Ctrl');const d={props,divElt:element(container),handleControllerEvent(){},
    setText1(v){props.text1=v;},setText2(v){props.text2=v;}};
   container.appendChild(d.divElt);controls.push(d);return d;
  },destroyControl(d){assert.ok(!d.destroyed);d.destroyed=true;if(d.divElt.parentNode)d.divElt.parentNode.removeChild(d.divElt);},
  instantiateTemplate(id,container,kind,props){
   assert.equal(kind,'List2Tmplt');const p={props,list2Ctrl:props.List2Ctrl,divElt:element(container),
    cleanUp(){assert.ok(!this.cleaned);this.cleaned=true;},handleControllerEvent(){}};
   container.appendChild(p.divElt);p.list2Ctrl.updateItems=()=>{};pages.push(p);return p;
  }};
 function nativeSettings(){
  fw.common.getCommonTransitionData();current='syssettings';context='SystemTab';fw._currTmpltInstance=host;
  if(!apps.syssettings)fw._initApp('syssettings');app._contextTable.SystemTab.readyFunction();
 }
 function homeScreen(){fw.common.getCommonTransitionData();current='system';context='HomeScreen';fw._currTmpltInstance=home;}
 const meta={token,version,notice:options.notice||'-'};
 const ctx={framework:fw,Date:{now:()=>now},log:{error(e){throw Error(e);}},
  document:{body:parent,
   querySelector(q){
    if(q==='head')return head;
    if(q==='.Dialog3Ctrl_Style19_NoTemplateInstance')return controls.find(d=>!d.destroyed&&d.divElt.classes.has('Dialog3Ctrl_Style19_NoTemplateInstance'))?.divElt||null;
    const m=q.match(/open-connect-(token|version|notice)/);
    return m&&options.installed!==false?{getAttribute(){return meta[m[1]];}}:null;
   },getElementById(id){return [...head.children,...parent.children].find(n=>n.id===id);},
   createElement(tag){assert.equal(tag,'script');return {};},
   addEventListener(type,fn,capture){const entries=listeners.get(type)||[];entries.push({fn,capture});listeners.set(type,entries);},
   removeEventListener(type,fn,capture){listeners.set(type,(listeners.get(type)||[]).filter(e=>e.fn!==fn||e.capture!==capture));}},
  setTimeout(fn,ms){const id=++next;timers.set(id,{fn,at:now+ms});return id;},clearTimeout(id){timers.delete(id);},
  setInterval(fn,ms){const id=++next;timers.set(id,{fn,at:now+ms,repeat:ms});return id;},clearInterval(id){timers.delete(id);},
  XMLHttpRequest:function(){
   this.open=(method,url)=>{this.method=method;this.url=url;};this.setRequestHeader=()=>{};
   this.send=body=>{this.body=body;allRequests.push(this);
    const fields=body.split('|');
    if(fields[2]==='status'&&fields[3]==='media'){
     mediaRequests.push(this);
     if(options.autoMedia!==false)ctx.setTimeout(()=>reply(this,{ok:true,media:null}),0);
    }else if(fields[2]==='status'&&fields[3]==='session'){
     if(options.autoSession!==false)ctx.setTimeout(()=>reply(this,{ok:true,closed:this.url.includes(':15557/')?closedUSB:closedBoot}),0);
    }else requests.push(this);
   };
   this.abort=()=>{this.aborted=true;};
  }};
 ctx.window=ctx;const contextVM=vm.createContext(ctx);
 function evaluate(name,url=name){
  let source=fs.readFileSync(path.join(folder,name),'utf8');
  if(options.sourceFor)source=options.sourceFor(url,source);
  vm.runInContext(source,contextVM,{filename:url});
 }
 const append=head.appendChild.bind(head);
 head.appendChild=n=>{append(n);if(n.src)scripts.push(n);};
 ctx.utility={loadScript(url,attrs,done){const n={src:url,...attrs,onload:done};head.appendChild(n);}};
 function deliver(n,load=true){assert.ok(n&&!n.executed,'undelivered script');n.executed=true;evaluate(n.src.split('/').at(-1),n.src);if(load&&n.onload)n.onload();}
 function flush(count=Infinity){let handled=0;
  while(handled<count){const n=scripts.find(n=>!n.executed);if(!n)break;deliver(n);handled++;}
 }
 function advance(ms){const end=now+ms;let count=0;
  while(true){const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;
   assert.ok(++count<10000,'bounded timer progression');const [id,t]=next;now=t.at;
   if(t.repeat)t.at=now+t.repeat;else timers.delete(id);
   t.fn();
  }now=end;
 }
 function reply(r,a,status=200){assert.ok(r,'request exists');r.status=a===null?0:status;r.responseText=a===null?'':JSON.stringify(a);r.readyState=4;r.onreadystatechange();}
 function state(extra={}){return {ok:true,revision,installed:options.installed!==false,retained:false,
  conflict:false,restart:false,pending:false,touch:0,warning:1,notice:'-',version,installedVersion:version,
  base:0,wireless:0,wirelessCurrent:0,carplayAutoshow:0,carplayAutoshowCurrent:0,...extra};}
 // USB chooser metadata deliberately has no physical-audit or preference fields.
 function metadata(extra={}){return {ok:true,revision,installed:options.installed!==false,retained:false,
  restart:false,pending:false,notice:'-',version,installedVersion:version,completionReady:false,...extra};}
 function install(flushCount=Infinity){evaluate('runtime.js');flush(flushCount);advance(0);}
 function usb(flushCount=Infinity,sessionToken=usbToken){
  closedUSB=false;
  const entry={id:'oc-maintenance-loader',src:'file:///tmp/open-connect/sessions/session-'+sessionToken+'/loader.js',ocToken:sessionToken,ocPort:15557};
  head.appendChild(entry);entry.executed=true;evaluate('loader.js',entry.src);ctx.OpenConnectUSBStart(entry);flush(flushCount);advance(0);return entry;
 }
 // Replay the actual stock/dev.22 Navigate argument with shell data substituted.
 function legacyUSB(flushCount=Infinity,sessionToken=usbToken,session='session-ABC123'){
  const runner=fs.readFileSync(path.join(folder,'session.sh'),'utf8');
  const launch=runner.match(/navigate "(javascript:void\(setTimeout[^\n]+)"/)[1]
   .replaceAll('$runtime','/tmp/open-connect/sessions/'+session).replaceAll('$token',sessionToken).replaceAll('$port','15557');
  const source=launch.slice('javascript:'.length);
  require('acorn').parse(source,{ecmaVersion:5});
  vm.runInContext(source,contextVM,{filename:'session.sh:Navigate'});advance(0);
  const entry=ctx.document.getElementById('oc-maintenance-loader');flush(flushCount);advance(0);return entry;
 }
 function pick(action){const d=controls.findLast(d=>!d.destroyed);assert.ok(d,'visible native dialog');d.props.defaultSelectCallback(d,action);advance(0);}
 function tap(){list.properties.selectCallback(list,'open-connect-settings');}
 function endAnimations(){for(const p of [...pages,host])if(!p.cleaned)p.divElt.emit('animationend');}
 function touch(type,target=parent){
  const event={type,target,preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;}};
  for(const entry of [...listeners.get(type)||[]]){entry.fn(event);if(event.stopped)break;}
  if(!event.stopped)calls.push(['touch-target',type]);
  return event;
 }
 function armHome(){
  const fired=[],props={};
  for(const key of ['selectCallback','holdStartCallback','holdStopCallback'])props[key]=()=>fired.push(key);
  const original={...props};
  const button={properties:props,_isEnabled:false,
   _holdTimeoutId:ctx.setTimeout(()=>props.holdStartCallback(),500),
   finishPartialActivity(){assert.equal(this._isEnabled,true);props.holdStopCallback();}};
  fw.common.statusBar={homeBtn:button};
  const messages={};
  for(const [key,field] of [['Global.StartHelp','_vuiHelpDialog'],['Global.StartExamples','_vuiExamplesDialog']]){
   messages[key]=function(){fw.common[field]={};return 'native voice';};
  }
  fw.common._messageTable={...messages};
  return {button,original,messages,fired};
 }
 return {ctx,fw,host,app,list,requests,mediaRequests,allRequests,controls,pages,calls,scripts,timers,meta,token,usbToken,revision,version,
  evaluate,deliver,flush,advance,reply,state,metadata,install,usb,legacyUSB,pick,tap,nativeSettings,homeScreen,endAnimations,touch,listeners,armHome,
  get dialog(){return controls.findLast(d=>!d.destroyed);},get lookups(){return lookups;},get now(){return now;},
  closeUSB(){closedUSB=true;},closeBoot(){closedBoot=true;},oldInput,oldTransition,oldSend:fw.sendEventToMmui,
  operation(op){return requests.filter(r=>r.body.split('|')[2]===op);},
  assertNative(){assert.equal(fw._currTmpltInstance,current==='syssettings'?host:home);assert.equal(fw._frameworkState,1);}};
};
