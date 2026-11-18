const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const root = process.argv[2];
const ctx = {document: {body: {}}, log: {error() {}}};
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
            props, divElt: {classList: {add() {}}}, events: [],
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
assert.equal(common.getCommonTransitionData,baseTransition);

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
assert.equal(control.props.title,"Open Connect 0.1.0-dev.1 installed");
assert.deepEqual(Object.values(control.props.buttonConfig).map(b=>b.label),["Done","Open settings"]);
control.props.defaultSelectCallback(control,"install");
assert.ok(Object.hasOwn(common,"handleControllerEvent"));
control.props.defaultSelectCallback(control,"settings");
assert.equal(calls.pop(),"settings");
assert.throws(()=>choose(fw,false,decision,"USB?"));
