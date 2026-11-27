const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),element=require("./ui-element.js");
function fixture() {
    const timers=new Map(),pages=[],calls=[],dialogs=[],inputs=[];
    let now=0,id=0,writes=[],reply,busy=false,restarts=0,refreshes=0,fresh;
    let values={touch:0,warning:1,restart:false,base:0,wireless:0,wirelessCurrent:0,
        carplayAutoshow:0,carplayAutoshowCurrent:0,developer:true,uart:0,ssh:0,key:"-",services:[
            {id:"android-auto",label:"Android Auto",saved:1,current:1,enable:"Enable",disable:"Disable"},
            {id:"pandora",label:"Pandora",saved:1,current:1,enable:"Enable",disable:"Disable"}]};
    const offscreen={removeChild(n){assert.equal(n.parentNode,this);n.parentNode=null;},
        appendChild(n){if(n.parentNode)n.parentNode.removeChild(n);n.parentNode=this;}};
    const appends=[];
    const parent={removeChild(n){assert.equal(n.parentNode,this);n.parentNode=null;},
        appendChild(n){
            if(n.parentNode===offscreen)appends.push({node:n,classes:new Set(n.classes)});
            if(n.parentNode&&n.parentNode!==this)n.parentNode.removeChild(n);
            n.parentNode=this;
        }};
    const input=(...args)=>{inputs.push(args);return "stock input";},send=(...args)=>calls.push(args),transition=()=>"stock transition";
    const host={divElt:element(parent),list2Ctrl:{},handleControllerEvent:input};
    const focus=[{id:"syssettings"}],nativeTransitions={owned:"Mazda"};
    let mode="controllerActive";
    const fw={_currTmpltInstance:host,_frameworkState:1,_FWK_STATE_IDLE:1,_focusStack:focus,transitionsObj:nativeTransitions,
        _offscreenTemplateParent:offscreen,
        getCurrentApp:()=>"syssettings",getCurrCtxtId:()=>"SystemTab",sendEventToMmui:send,
        common:{getCommonTransitionData:transition,handleControllerEvent:input},multicontroller:{getMode:()=>mode},
        instantiateTemplate(app,container,kind,props){
            assert.equal(kind,"List2Tmplt");assert.equal(container,offscreen);
            const p={list2Ctrl:props.List2Ctrl,divElt:element(offscreen),cleaned:0,events:[],
                cleanUp(){assert.equal(this.cleaned++,0);},handleControllerEvent(e){this.events.push(e);}};
            p.list2Ctrl.updateItems=(a,b)=>assert.equal(a,b);pages.push(p);return p;
        },instantiateControl(app,container,kind,props){
            assert.equal(kind,"Dialog3Ctrl");const d={props,divElt:element(container),handleControllerEvent(){},setText1(){},setText2(){}};dialogs.push(d);return d;
        },destroyControl(d){assert.ok(!d.destroyed);d.destroyed=true;}};
    const ctx={document:{body:element(),addEventListener(){},removeEventListener(){}},log:{error(e){throw Error(e);}},
        setTimeout(fn,ms){timers.set(++id,{at:now+ms,fn});return id;},clearTimeout(id){timers.delete(id);},
        ocCarPlay:{loaded:7,cancel(){calls.push("cancel CarPlay");}}};ctx.window=ctx;
    for(const p of process.argv.slice(2))vm.runInNewContext(fs.readFileSync(p,"utf8"),ctx);
    const settings=ctx.OpenConnectSettings;
    const store={read:()=>values,write(...args){reply=args.pop();writes.push(args);},busy:()=>busy,
        restart(leave){restarts++;leave();return true;},refresh(done){refreshes++;fresh=done;}};
    const page=()=>pages.at(-1),row=k=>page().list2Ctrl.dataList.items.find(r=>r.appData===k);
    const pick=k=>{assert.ok(row(k),String(k));page().list2Ctrl.selectCallback(page().list2Ctrl,k);};
    function advance(ms){const end=now+ms;while(true){
        const n=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!n)break;
        timers.delete(n[0]);now=n[1].at;n[1].fn();}now=end;}
    function unchanged(){assert.equal(fw._currTmpltInstance,host);assert.equal(fw._frameworkState,1);
        assert.equal(fw._focusStack,focus);assert.equal(fw.transitionsObj,nativeTransitions);}
    return {fw,host,store,settings,pages,calls,dialogs,timers,inputs,appends,page,row,pick,advance,unchanged,input,send,transition,
        setMode(m){mode=m;},
        open:()=>settings.open(fw,store),end:()=>page().divElt.emit("animationend"),back:()=>fw.sendEventToMmui("common","Global.GoBack"),
        values(v){values=v;},get value(){return values;},busy(v){busy=v;},get writes(){return writes;},ack(v){values=v;reply(v);},
        get restarts(){return restarts;},get refreshes(){return refreshes;},fresh(v){fresh(v);},get dialog(){return dialogs.at(-1);},
        confirm(action){const d=dialogs.at(-1);d.props.defaultSelectCallback(d,action);}};
}
const incoming="Transitions_slideInRightTmpltWithStatusLeftBtn_0_400",backwards="Transitions_slideInLeftTmpltWithStatusLeftBtn_0_400";
let f=fixture();f.open();f.unchanged();
assert.ok(f.page().divElt.classes.has(incoming));assert.ok(f.host.divElt.classes.has("Transitions_slideOutLeftTmpltWithStatusLeftBtn_0_400"));
f.page().divElt.emit("animationend",{target:{}});assert.equal(f.host.divElt.style.display,"");
f.end();assert.equal(f.host.divElt.style.display,"none");assert.equal(f.timers.size,0);
for(const path of [["phone",2],["sources"],["developer"],[0],[1]]) {
    for(const key of path){const old=f.page();f.pick(key);assert.ok(f.page().divElt.classes.has(incoming));
        assert.equal(old.cleaned,0);f.end();assert.equal(old.cleaned,1);f.unchanged();}
    for(const key of path){const old=f.page();f.back();assert.ok(f.page().divElt.classes.has(backwards));
        assert.equal(old.cleaned,0);f.end();assert.equal(old.cleaned,1);f.unchanged();}
}
// Rapid Back, late/child events and missing events have independent finite cleanup.
const root=f.page();f.pick("phone");const child=f.page(),stale=[...child.divElt.listeners.get("animationend")][0];
f.back();assert.equal(root.cleaned,1);assert.equal(child.cleaned,0);assert.ok(f.page().divElt.classes.has(backwards));
stale({target:child.divElt});assert.equal(child.cleaned,0);f.end();f.advance(2000);assert.equal(child.cleaned,1);
f.back();assert.ok(f.host.divElt.classes.has(backwards));f.back();assert.equal(f.fw.sendEventToMmui,f.send);
assert.deepEqual(f.calls.at(-1),["common","Global.GoBack"]);assert.equal(f.host.divElt.style.display,"");assert.equal(f.timers.size,0);
// Stock Common sends Global.GoBack, then falls through to its cached host's
// goBack handler for Commander input. Touch LeftButton Back sends only the event.
for(const source of ["commander","touch"])for(const completion of ["event","timeout"]){
    f=fixture();f.open();f.end();const root=f.page(),sent=f.calls.length;
    f.back();if(source==="commander")f.host.handleControllerEvent("goBack");
    assert.equal(root.cleaned,0);assert.equal(f.inputs.length,0);assert.equal(f.calls.length,sent);
    assert.ok(f.host.divElt.classes.has(backwards));
    assert.ok(root.divElt.classes.has("Transitions_slideOutRightTmpltWithStatusLeftBtn_0_400"));
    assert.equal(f.host.divElt.style.display,"");f.unchanged();
    f.advance(399);assert.equal(root.cleaned,0);assert.ok(f.host.divElt.classes.has(backwards));
    if(completion==="event"){
        f.advance(1);f.host.divElt.emit("animationend");
    }else{
        f.advance(500);assert.equal(root.cleaned,0);f.advance(1);
    }
    assert.equal(root.cleaned,1);assert.equal(f.timers.size,0);
    assert.equal(f.host.handleControllerEvent,f.input);assert.equal(f.fw.sendEventToMmui,f.send);
    assert.equal(f.fw.common.getCommonTransitionData,f.transition);assert.equal(f.host.divElt.classes.size,0);
    assert.equal(root.divElt.classes.size,0);assert.equal(f.host.handleControllerEvent("cw"),"stock input");
    assert.deepEqual(f.inputs,[["cw"]]);f.host.divElt.emit("animationend");f.advance(1000);
    assert.equal(root.cleaned,1);const close=f.open();assert.equal(typeof close,"function");close();
    assert.equal(f.timers.size,0);f.unchanged();
}
// Real host input and native transitions still interrupt the leaving slide.
for(const event of ["cw","touchActive","controllerActive"]){
    f=fixture();f.open();f.end();const root=f.page();f.back();f.host.handleControllerEvent("goBack");
    assert.equal(f.host.handleControllerEvent(event),"stock input");assert.deepEqual(f.inputs,[[event]]);
    assert.equal(root.cleaned,1);assert.equal(f.timers.size,0);f.unchanged();
}
for(const ctxtId of ["HomeScreen","Navigation","BackupCameraDisplay"]){
    f=fixture();f.open();f.end();const root=f.page();f.back();f.host.handleControllerEvent("goBack");
    const next={contextInfo:{ctxtId}};f.fw._currTmpltInstance=next;f.fw._frameworkState=2;
    assert.equal(f.fw.common.getCommonTransitionData(next),"stock transition");
    assert.equal(root.cleaned,1);assert.equal(f.timers.size,0);assert.equal(f.host.handleControllerEvent,f.input);
    assert.equal(f.fw._currTmpltInstance,next);assert.equal(f.fw._frameworkState,2);
    f.host.divElt.emit("animationend");f.advance(1000);assert.equal(root.cleaned,1);
}
for(const event of ["Global.IntentHome","Global.IntentNavigation"]) {
    f=fixture();f.open();f.pick("phone");const p=f.page();f.fw.sendEventToMmui("common",event);
    assert.equal(p.cleaned,1);assert.equal(f.host.divElt.style.display,"");assert.equal(f.timers.size,0);
    assert.deepEqual(f.calls.at(-1),["common",event]);f.unchanged();
}
for(const ctxtId of ["BackupCameraDisplay","HomeScreen","Active"]) {
    f=fixture();f.open();f.pick("sources");const p=f.page(),late=[...p.divElt.listeners.get("animationend")][0];
    const next={contextInfo:{ctxtId}};f.fw._currTmpltInstance=next;f.fw._frameworkState=2;
    assert.equal(f.fw.common.getCommonTransitionData(next),"stock transition");assert.equal(f.fw._currTmpltInstance,next);
    assert.equal(f.fw._frameworkState,2);assert.equal(f.host.handleControllerEvent,f.input);assert.equal(f.fw.sendEventToMmui,f.send);
    assert.equal(p.cleaned,1);assert.equal(f.timers.size,0);late({target:p.divElt});assert.equal(p.cleaned,1);
    assert.equal(p.divElt.listeners.get("animationend").size,0);assert.equal(f.host.divElt.classes.size,0);
}
for(const flag of ["_vuiHelpDialog","_vuiExamplesDialog"]) {
    f=fixture();f.open();f.fw.common[flag]={};f.host.handleControllerEvent("select");
    assert.equal(f.host.divElt.style.display,"");assert.equal(f.timers.size,0);
}
f=fixture();f.open();f.advance(899);assert.equal(f.host.divElt.style.display,"");f.advance(1);assert.equal(f.host.divElt.style.display,"none");
f.pick("phone");const old=f.page();f.pick(2);f.advance(900);assert.equal(old.cleaned,1);
// Warm attachment performs zero refreshes; cold callbacks cannot reopen a detached host.
f=fixture();const ctrl={properties:{selectCallback(){}},dataList:{items:[{appData:"SelectAbout"}],itemCount:1},setDataList(d){this.dataList=d;},updateItems(){}};
f.host.list2Ctrl=ctrl;const app={_currentContextTemplate:f.host,_contextTable:{SystemTab:{readyFunction(){}}}};
let detach=f.settings.attach(f.fw,app,f.store);ctrl.properties.selectCallback(ctrl,"open-connect-settings");
assert.equal(f.refreshes,0);assert.equal(f.pages.length,1);f.host.handleControllerEvent("cw");assert.equal(f.refreshes,0);detach();
const cached=f.value;f.values(null);detach=f.settings.attach(f.fw,app,f.store);const count=f.pages.length;
ctrl.properties.selectCallback(ctrl,"open-connect-settings");assert.equal(f.refreshes,1);assert.equal(f.pages.length,count);
detach();f.values(cached);f.fresh(true);assert.equal(f.pages.length,count);
// Apply enables immediately from draft, stays enabled during saves, and drains queued writes behind progress before restart.
f=fixture();f.values({...f.value,touchCurrent:0,warningCurrent:1,baseCurrent:0,restartFixed:false});
f.open();f.end();
assert.ok(f.appends.length>=1);
assert.ok(f.appends[0].classes.has("Transitions_Init_OffscreenRight"));
assert.deepEqual(f.page().events,["acceptFocusInit","controllerActive"]);
// Touch mode receives acceptFocusInit first, then touchActive so no Commander highlight remains.
f.setMode("touchActive");f.pick("developer");assert.deepEqual(f.page().events,[]);
assert.ok(f.appends.at(-1).classes.has("Transitions_Init_OffscreenRight"));
f.end();assert.deepEqual(f.page().events,["acceptFocusInit","touchActive"]);
f.back();assert.ok(f.appends.at(-1).classes.has("Transitions_Init_OffscreenLeft"));
f.end();f.setMode("controllerActive");
assert.equal(f.row("restart").disabled,true);f.pick("restart");assert.equal(f.dialog,undefined);
f.pick(0);f.end();f.pick(1);assert.deepEqual(f.writes,[["touch",0,1]]);
f.back();f.end();assert.equal(f.row("restart").disabled,false);
// Toggling back to booted value disables Apply immediately (before and after ACK).
f.pick(0);f.end();f.pick(0);f.back();f.end();assert.equal(f.row("restart").disabled,true);
f.ack({...f.value,touch:1,restart:true});assert.deepEqual(f.writes,[["touch",0,1],["touch",1,0]]);
f.ack({...f.value,touch:0,restart:false});assert.equal(f.row("restart").disabled,true);
// Toggling while slow write is in flight keeps Apply enabled; confirming Apply drains save behind progress then restarts.
f.pick(0);f.end();f.pick(1);f.back();f.end();assert.equal(f.row("restart").disabled,false);
f.pick("restart");assert.match(f.dialog.props.text1,/Restart Mazda Connect/);
assert.deepEqual(Object.values(f.dialog.props.buttonConfig).map(b=>b.label),["Cancel","Restart"]);
assert.ok(f.dialog.divElt.classes.has("Transitions_fadeIn_0_200"));
const cancelled=f.dialog;f.confirm("cancel");cancelled.props.defaultSelectCallback(cancelled,"restart");assert.equal(f.restarts,0);
f.pick("restart");f.confirm("restart");assert.equal(f.restarts,0);
assert.equal(f.dialog.props.text1,"Applying changes");
f.ack({...f.value,touch:1,restart:true});assert.equal(f.restarts,1);
assert.equal(f.host.divElt.style.display,"");assert.equal(f.fw.common.getCommonTransitionData,f.transition);assert.equal(f.timers.size,0);
// Failed save behind queued Apply aborts restart and shows error page.
f=fixture();f.open();f.end();f.pick(0);f.end();f.pick(1);f.back();f.end();
f.pick("restart");f.confirm("restart");assert.equal(f.dialog.props.text1,"Applying changes");
f.ack(null);assert.equal(f.restarts,0);assert.match(f.page().list2Ctrl.title.text1,/could not be confirmed/);
f.fw.sendEventToMmui("common","Global.IntentHome");assert.equal(f.timers.size,0);
// Toggling UART keeps Import public key enabled; confirming Import drains UART write then runs importKey and unlocks SSH.
f=fixture();let importCb=null;f.store.importKey=cb=>{importCb=cb;};
f.open();f.end();f.pick("developer");f.end();
assert.equal(f.row("import").disabled,false);
f.page().list2Ctrl.selectCallback(f.page().list2Ctrl,"uart",{additionalData:1});f.confirm("enable");
assert.deepEqual(f.writes,[["uart",0,1]]);
assert.equal(f.row("import").disabled,false);
f.pick("import");f.confirm("import");assert.equal(f.dialog.props.text1,"Importing public key");assert.equal(importCb,null);
f.ack({...f.value,uart:1,restart:true});assert.equal(typeof importCb,"function");
const imported={...f.value,uart:1,key:"c".repeat(64),fingerprint:Array(16).fill("ab").join(":"),restart:true};
f.values(imported);importCb(imported);
assert.equal(f.dialog.props.title,"Public key imported");assert.equal(f.row("ssh").disabled,false);
f.confirm("done");f.fw.sendEventToMmui("common","Global.IntentHome");assert.equal(f.timers.size,0);
// About cannot leave Apply stale when the pending save finishes behind it.
f=fixture();f.open();f.end();f.pick(0);f.end();f.pick(1);f.back();f.end();f.pick("about");
const aboutRoot=f.page();assert.equal(f.row("restart").disabled,false);
f.ack({...f.value,touch:1,restart:true});assert.equal(f.dialog.destroyed,undefined);
f.confirm("done");assert.equal(f.page(),aboutRoot);assert.equal(f.row("restart").disabled,false);
f.pick("restart");assert.equal(f.dialog.props.buttonConfig.button2.label,"Restart");f.confirm("cancel");
f.fw.sendEventToMmui("common","Global.IntentHome");assert.equal(f.timers.size,0);
// Confirming Uninstall during an in-flight write discards unsent drafts, waits for settlement, then removes.
f=fixture();let removals=0;f.store.uninstall=leave=>{removals++;leave();return true;};f.open();f.end();
f.pick(0);f.end();f.pick(1);f.back();f.end();f.pick(1);f.end();f.pick(0);f.back();f.end();
assert.equal(f.writes.length,1);
f.pick("uninstall");assert.equal(f.dialog.props.buttonConfig.button2.appData,"uninstall");
f.confirm("uninstall");assert.equal(removals,0);assert.equal(f.dialog.props.text1,"Removing Open Connect");
f.ack({...f.value,touch:1,restart:true});assert.equal(removals,1);assert.equal(f.writes.length,1);
assert.equal(f.host.divElt.style.display,"");assert.equal(f.timers.size,0);
// Selecting a radio choice during its incoming slide completes Mazda focus initialization on the retained page.
f=fixture();f.open();f.end();f.pick(0);
const slidingTouch=f.page();assert.deepEqual(slidingTouch.events,[]);
f.pick(1);assert.deepEqual(f.writes,[["touch",0,1]]);
assert.equal(f.page(),slidingTouch);
assert.deepEqual(slidingTouch.events,["acceptFocusInit","controllerActive"]);
f.ack({...f.value,touch:1,restart:true});f.fw.sendEventToMmui("common","Global.IntentHome");assert.equal(f.timers.size,0);
console.log("Settings UX: offscreen slides, Mazda focus order, immediate drafting and queued actions passed");

// Commander selects the third touch mode, then reverses it without touch input.
f=fixture();f.open();assert.equal(f.row(0).text1,"Touchscreen");f.pick(0);f.end();
assert.deepEqual(Array.from(f.page().list2Ctrl.dataList.items,r=>r.text1),
    ["Factory behavior","Always enabled","Always disabled"]);
f.pick(2);assert.deepEqual(f.writes,[["touch",0,2]]);
f.ack({...f.value,touch:2,restart:true});f.back();f.end();
assert.equal(f.row(0).label1,"Always disabled");f.pick(0);f.end();f.pick(0);
assert.deepEqual(f.writes,[["touch",0,2],["touch",2,0]]);
f.ack({...f.value,touch:0,restart:true});f.fw.sendEventToMmui("common","Global.IntentHome");
// The error page has a numeric Commander appData, not an entries[] index.
f=fixture();f.open();f.pick(0);f.pick(2);f.ack(null);
assert.match(f.page().list2Ctrl.title.text1,/could not be confirmed/);f.end();
f.pick(0);f.advance(900);assert.equal(f.host.divElt.style.display,"");
f.unchanged();assert.equal(f.timers.size,0);
