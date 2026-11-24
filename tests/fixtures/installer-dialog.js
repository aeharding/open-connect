const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const root = process.argv[2];
const listeners = {};
const ctx = {document: {body: {}, addEventListener(k,f) { listeners[k]=f; },
    removeEventListener(k,f) { if(listeners[k]===f) delete listeners[k]; }},
    clearTimeout() {}, log: {error() {}}};
vm.runInNewContext(fs.readFileSync(root, "utf8"), ctx);
const choose = ctx.OpenConnectInstaller.choose;
const calls = [];
const baseInput = function () { return this; };
const baseTransition = function (next) { calls.push(next); return 42; };
const common = Object.create({handleControllerEvent: baseInput, getCommonTransitionData: baseTransition});
let control;
let available = true;
const fw = {
    common, _FWK_STATE_IDLE: "idle", _frameworkState: "idle", _currTmpltInstance: {},
    getCurrentApp() { return "system"; }, getCurrCtxtId() { return "HomeScreen"; },
    multicontroller: {getMode() { return "controllerActive"; }},
    instantiateControl(app, parent, type, props) {
        assert.equal(app, "system");
        assert.equal(parent, ctx.document.body);
        assert.equal(type, "Dialog3Ctrl");
        if (!available) { return null; }
        control = {
            props, divElt: {style: {}, classList: {add() {}}}, events: [],
            setText1(t) { this.props.text1=t; }, setText2(t) { this.props.text2=t; },
            handleControllerEvent(event) { this.events.push(event); }
        };
        return control;
    },
    destroyControl(c) { assert.equal(c,control); calls.push("closed"); }
};
const decision = action => calls.push(action);
assert.equal(typeof choose(fw, false, decision), "function");
assert.equal(choose(fw, false, decision), false);
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.appData), ["cancel","install"]);
assert.equal(control.props.initialFocus, 0);
assert.equal(control.props.titleStyle,"titleStyle01");
for (const tilt of ["left","right","up","down"]) {
    common.handleControllerEvent(tilt+"Start",false);
    common.handleControllerEvent(tilt,false);
}
assert.deepEqual(control.events.splice(1), ["left","right","up","down"]);
common.handleControllerEvent("cw",true);
common.handleControllerEvent("controllerActive",false);
common.handleControllerEvent("cw",false);
assert.deepEqual(control.events, ["controllerActive","controllerActive","cw"]);
let select = control.props.defaultSelectCallback;
select(control,"uninstall");
select({}, "install");
assert.deepEqual(calls, []);
select(control,"install");
select(control,"install");
assert.deepEqual(calls, ["closed","install"]);
assert.equal(common.handleControllerEvent,baseInput);

const dismissRetained=choose(fw,false,decision,"0.2.0-dev.2",true);
assert.equal(control.props.title,"Install Open Connect?");
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.label),["Cancel","Install","Uninstall"]);
dismissRetained();
assert.equal(common.getCommonTransitionData,baseTransition);

for (const from of ["0.3.0-dev.3", "0.3.0-dev.4", "-"]) {
    const cancelUpdate = choose(fw, true, decision, "0.3.0-dev.4", false, from);
    assert.match(control.props.text1, /^From: /);
    assert.ok(control.props.text1.includes("From: " + (from === "-" ? "Unavailable" : from) + "\nTo: 0.3.0-dev.4\n"));
    assert.match(control.props.text1, /Mazda Connect will restart/);
    assert.equal(control.props.title, (from === "-" ? "Install" : from === "0.3.0-dev.4" ? "Reinstall" : "Update") + " Open Connect?");
    cancelUpdate();
}

assert.equal(typeof choose(fw, true, decision), "function");
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.appData), ["cancel","install","uninstall"]);
control.props.defaultSelectCallback(control,"uninstall");
assert.equal(calls.pop(),"uninstall");
assert.equal(typeof choose(fw, false, decision), "function");
common.handleControllerEvent("goBack",false);
assert.equal(calls.pop(),"cancel");

assert.equal(typeof choose(fw, false, () => { throw Error("caller failed"); }), "function");
assert.equal(common.getCommonTransitionData("incoming"),42);
assert.equal(calls.pop(),"incoming");
assert.equal(common.handleControllerEvent,baseInput);
assert.equal(typeof choose(fw,false,decision),"function");
fw._currTmpltInstance={};
control.props.defaultSelectCallback(control,"install");
assert.equal(calls.pop(),"cancel");
common._vuiHelpDialog={};
assert.equal(choose(fw,false,decision),false);
common._vuiHelpDialog=null;
available=false;
assert.equal(choose(fw,true,decision),false);
assert.equal(common.handleControllerEvent,baseInput);

available=true;
const cancelOld=choose(fw,false,decision);
cancelOld();
const cancelNew=choose(fw,false,decision);
cancelOld();
assert.equal(choose(fw,false,decision),false);
assert.equal(common.handleControllerEvent("unrelated-hardkey",false),common);
cancelNew();
assert.equal(Object.hasOwn(common,"handleControllerEvent"),false);
assert.equal(Object.hasOwn(common,"getCommonTransitionData"),false);

const complete=ctx.OpenConnectInstaller.complete;
assert.equal(typeof complete(fw,"0.1.0-dev.1",decision),"function");
assert.equal(control.props.title,"Open Connect installed");
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.label),["Done","Open settings"]);
control.props.defaultSelectCallback(control,"install");
assert.ok(Object.hasOwn(common,"handleControllerEvent"));
control.props.defaultSelectCallback(control,"settings");
assert.equal(calls.pop(),"settings");
assert.throws(()=>choose(fw,false,decision,"USB?"));
assert.equal(typeof ctx.OpenConnectInstaller.message(fw,"Open Connect","Changes saved.",
    {button1:{label:"Cancel",appData:"cancel"}},decision),"function");
assert.equal(control.props.text1,"Changes saved.");
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.appData),["cancel"]);
common.handleControllerEvent("goBack",false);
assert.equal(calls.pop(),"cancel");
assert.equal(common.handleControllerEvent,baseInput);

// Progress owns local input, not native surfaces. Existing Home callbacks are
// released with the same semantics as Mazda's short-and-hold Button control.
let homeEvents = [], cleared;
ctx.clearTimeout = t => { cleared=t; };
const home = {properties: {selectCallback() { homeEvents.push("select"); },
    holdStartCallback() { homeEvents.push("hold"); }, holdStopCallback() { homeEvents.push("stop"); }},
    _isEnabled: true, _isDown: true, _isHeld: true, _holdTimeoutId: 10,
    _groupTouch: {selectMode: "touch", focused: true},
    finishPartialActivity() {
        if (this._groupTouch.selectMode && this._isEnabled) {
            if(this._isHeld) this.properties.holdStopCallback();
            this._isHeld=this._isDown=this._groupTouch.focused=false;
            this._groupTouch.selectMode=null;
        }
    }};
common.statusBar={homeBtn: home};
let suspended=0;
function acquire() {
    return ctx.OpenConnectInstaller.progress(fw,"Installing Open Connect","Do not turn off the car.",()=>suspended++);
}
for (const enabled of [true,false]) {
    home._holdTimeoutId=10; home._isEnabled=enabled; home._isDown=home._isHeld=true; home._groupTouch.selectMode="touch";
    const callbacks={...home.properties};
    const v=acquire();
    assert.ok(v); assert.equal(cleared,10); assert.equal(home._isDown,false);
    assert.equal(home._isHeld,false); assert.equal(home._groupTouch.focused,false);
    assert.equal(home._isEnabled,enabled);
    home.properties.holdStartCallback(); home.properties.selectCallback();
    assert.deepEqual(homeEvents,[]);
    assert.equal(control.props.contentStyle,"style27"); assert.equal(control.props.fullScreen,true);
    assert.equal(control.props.title,undefined); assert.equal(control.props.buttonConfig,undefined);
    assert.equal(control.props.meter.meterPath,"common/images/IndeterminateMeter_2.png");
    assert.equal(control.divElt.style.top,"0px");
    for (const event of ["goBack","cw","ccw","select","lostFocus","rightStart","up"])
        common.handleControllerEvent(event,false);
    assert.equal(control.events.length,0);
    let consumed=0;
    listeners.mouseup({preventDefault(){consumed++;},stopImmediatePropagation(){consumed++;}});
    assert.equal(consumed,2);
    assert.equal(v.update("Restarting Mazda Connect","Do not turn off the car."),true);
    assert.equal(control.props.text1,"Restarting Mazda Connect");
    v.close(); v.close();
    assert.deepEqual({...home.properties},callbacks);
    assert.equal(Object.keys(listeners).length,0);
    home.properties.selectCallback(); assert.equal(homeEvents.pop(),"select");
}
for (const kind of ["Help","Examples"]) {
    let delegated=false;
    const handler=function () {
        delegated=true;
        assert.equal(common.handleControllerEvent,baseInput);
        assert.equal(Object.keys(listeners).length,0);
        common["_vui"+kind+"Dialog"]={};
        return 7;
    };
    common._messageTable={["Global.Start"+kind]:handler};
    let v=acquire(); assert.ok(v);
    assert.equal(common._messageTable["Global.Start"+kind](),7);
    assert.ok(delegated); assert.equal(acquire(),false);
    common["_vui"+kind+"Dialog"]=null;
    assert.equal(common._messageTable["Global.Start"+kind],handler);
    v=acquire(); assert.ok(v);
    // An overlay appearing without a transition yields the very next input.
    common["_vui"+kind+"Dialog"]={};
    assert.equal(common.handleControllerEvent("cw"),common);
    assert.equal(Object.keys(listeners).length,0);
    common["_vui"+kind+"Dialog"]=null;
}
let v=acquire(); assert.ok(v);
assert.equal(common.getCommonTransitionData("camera"),42);
assert.equal(Object.keys(listeners).length,0);
v=acquire(); assert.ok(v); v.close(); // Runtime can rearm once on eligible return.
