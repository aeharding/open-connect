const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let queued;
const ctx = {document: {body: {}}, log: {error(e) { throw Error(e); }}, setTimeout(fn) { queued=fn; return 1; }, clearTimeout() { queued=null; }};
function idle() { const fn=queued; queued=null; if (fn) { fn(); } }
for (const path of process.argv.slice(2)) { vm.runInNewContext(fs.readFileSync(path, "utf8"), ctx); }
const settings = ctx.OpenConnectSettings;
const pages = [], calls = [];
const parent = {removeChild(node) { node.parentNode = null; }};
const input = () => "stock input", send = (...args) => calls.push(args);
const transition = () => "stock transition";
const host = {divElt: {style: {display: ""}, parentNode: parent}, list2Ctrl: {},
    handleControllerEvent: input};
const fw = {getCurrentApp: () => "syssettings", getCurrCtxtId: () => "SystemTab",
    _frameworkState: 1, _FWK_STATE_IDLE: 1, _currTmpltInstance: host,
    common: {getCommonTransitionData: transition}, multicontroller: {getMode: () => "controllerActive"},
    sendEventToMmui: send,
    instantiateTemplate(app, container, type, props) {
        assert.equal(type, "List2Tmplt"); assert.equal(app, "syssettings"); assert.equal(container, parent);
        const ctrl = props.List2Ctrl;
        ctrl.updateItems = (first,last) => { assert.equal(first,0); assert.equal(last,1); };
        pages.push({ctrl, list2Ctrl: ctrl, divElt: {parentNode: parent}, events: [],
            cleanUp() { this.cleaned = true; }, handleControllerEvent(e) { this.events.push(e); return "consumed"; }});
        return pages.at(-1);
    }};
let values = {touch: 1, warning: 0}, reply;
const writes = [];
const store = {read: () => values, write(...args) { reply = args.pop(); writes.push(args); }};
const pick = i => {
    const ctrl = pages.at(-1).ctrl, rows = ctrl.dataList.items;
    if (rows[i].image1 === "radio") { rows.forEach((row,index) => { row.checked = index === i; }); }
    return ctrl.selectCallback(ctrl, rows[i].appData);
};
const back = () => fw.sendEventToMmui("common", "Global.GoBack");
assert.equal(typeof settings.open(fw, store), "function");
assert.equal(settings.open(fw, store), false);
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1, "Allow");
assert.equal(pages.at(-1).ctrl.checkMinChangeInterval,undefined);
pick(0);
let page = pages.at(-1);
assert.deepEqual(Array.from(page.ctrl.dataList.items, row => row.text1), ["Factory Default", "Allow"]);
assert.equal(page.ctrl.checkMinChangeInterval,0);
assert.deepEqual(Array.from(page.ctrl.dataList.items, r => [r.image1,r.checked]), [["radio",false],["radio",true]]);
assert.equal(host.handleControllerEvent("ccw"), "consumed");
assert.deepEqual(writes, []);
pick(0); pick(1); pick(0);
assert.equal(pages.at(-1),page);
assert.deepEqual(Array.from(page.ctrl.dataList.items,r=>r.checked),[true,false]);
assert.deepEqual(writes,[]);
back(); assert.equal(pages.at(-1).ctrl.dataList.items[0].label1,"Default");
back(); assert.equal(host.divElt.style.display,"");
idle(); assert.deepEqual(writes,[["touch",1,0]]);
settings.open(fw,store); pick(0); pick(1); idle();
assert.deepEqual(writes,[["touch",1,0]]);
values={touch:0,warning:0}; reply(values);
assert.deepEqual(writes,[["touch",1,0],["touch",0,1]]);
values={touch:1,warning:0}; reply(values);
assert.equal(pages.at(-1).ctrl.title.text1,"Touchscreen While Driving");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.checked),[false,true]);
back(); pick(1); pick(1); back(); back(); idle();
assert.equal(host.handleControllerEvent,input); assert.equal(fw.sendEventToMmui,send);
values={touch:1,warning:1}; reply(null); // acknowledgement lost after the write
assert.equal(fw.common.getCommonTransitionData,transition); assert.deepEqual(calls,[]);
settings.open(fw,store); pick(0); pick(0); idle(); reply(values);
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/); back();
assert.equal(host.divElt.style.display,"");
assert.equal(settings.open(fw,{read:()=>({touch:2,warning:1})}),false);
console.log("Native radio selection is immediate; saves coalesce across Back and re-entry");

const baseSelect = (c, value) => "stock:" + value;
const stockRows = [{appData: "language"}, {appData: "SelectAbout"}];
const list = {dataList: {items: stockRows, itemCount: 2}, properties: {selectCallback: baseSelect},
    setDataList(data) { this.dataList = data; this.rendered = 0; },
    updateItems(first,last) { assert.equal(first,0); this.rendered = last + 1; }};
host.list2Ctrl = list;
let readyCalls = 0;
const stockReady = () => { readyCalls++; };
const app = {_contextTable: {SystemTab: {readyFunction: stockReady}}, _currentContextTemplate: host};
const detach = settings.attach(fw,app,store);
assert.equal(list.dataList.items.length, 3);
assert.equal(stockRows.length, 2); assert.equal(list.rendered, 3);
const refreshed = [{appData:"language"},{appData:"distance"},{appData:"SelectAbout"}];
list.setDataList({items:refreshed, itemCount:3, vuiSupport:false});
assert.deepEqual(Array.from(list.dataList.items,r=>r.appData),["language","distance","open-connect-settings","SelectAbout"]);
assert.equal(list.dataList.vuiSupport,false);
list.dataList.items[list.dataList.itemCount-1].disabled=true;
assert.equal(refreshed[2].disabled,true);
assert.equal(list.properties.selectCallback(list,"language"),"stock:language");
app._contextTable.SystemTab.readyFunction();
assert.equal(list.dataList.itemCount,4);
list.properties.selectCallback(list,"open-connect-settings");
assert.equal(host.divElt.style.display,"none");
back();
detach(); assert.equal(app._contextTable.SystemTab.readyFunction,stockReady);
assert.equal(readyCalls,1); assert.equal(list.rendered,3); assert.equal(list.properties.selectCallback,baseSelect);

let appName="system", context="HomeScreen", tick, success;
ctx.setInterval = fn => { tick = fn; return 42; };
ctx.clearInterval = () => { tick = null; };
fw.getCurrentApp=()=>appName; fw.getCurrCtxtId=()=>context;
assert.equal(typeof settings.fromHome(fw,store,r=>{ success=r; }),"function");
assert.deepEqual(calls.at(-1), ["system","SelectSettings"]);
tick(); assert.equal(success,undefined);
appName="syssettings"; context="ClockTab"; tick(); assert.equal(success,true); assert.equal(tick,null);
back();
appName="system"; context="HomeScreen"; settings.fromHome(fw,store,r=>{success=r;});
appName="communication"; context="Phone"; tick(); assert.equal(success,false); assert.equal(tick,null);

appName="audiosettings"; context="SoundTab";
settings.open(fw,store); pick(1); pick(0); idle(); reply(null);
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/);
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1,"Return to Mazda Settings");
back(); assert.equal(host.divElt.style.display,"");
settings.open(fw,store); pick(1); pick(0); idle();
fw.common._vuiHelpDialog = {};
reply(null);
delete fw.common._vuiHelpDialog;
assert.equal(host.divElt.style.display,"");
assert.equal(host.handleControllerEvent,input); assert.equal(fw.sendEventToMmui,send);

settings.open(fw,store); back(); // dismiss the earlier interrupted failure
settings.open(fw,store); pick(1); pick(0); idle();
const originalRead = store.read; store.read=()=>{ throw Error("readback offline"); };
assert.doesNotThrow(()=>reply(null));
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/);
store.read=originalRead; back();

// The actual settings and dialog modules share one OEM input and transition owner.
let modal, removals = 0;
fw.instantiateControl = (app, parent, type, props) => {
    assert.equal(type, "Dialog3Ctrl");
    assert.equal(parent, ctx.document.body);
    modal = {props, divElt: {classList: {add() {}}}, handleControllerEvent() {}};
    return modal;
};
fw.destroyControl = control => { assert.equal(control, modal); modal = null; };
fw.common.handleControllerEvent = input;
settings.open(fw, store);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, r => r.text1),
    ["Touchscreen While Driving", "Startup disclaimer", "Uninstall", "About"]);
assert.equal(pages.at(-1).ctrl.dataList.items[2].disabled, true);
pick(2); assert.equal(modal, undefined);
pick(3); assert.equal(modal.props.text1, "Installed version unavailable.");
back(); back();
store.version = "0.2.1";
store.uninstall = () => { removals++; };
settings.open(fw, store);
pick(3); assert.equal(modal.props.title, "About"); assert.equal(modal.props.text1, "Open Connect 0.2.1");
pick(2); assert.equal(modal.props.title, "About"); // background list cannot steal the modal
back(); assert.equal(modal, null);
pick(2); assert.equal(modal.props.buttonConfig.button1.label, "Cancel");
assert.equal(modal.props.initialFocus, 0);
const stale = modal;
back(); stale.props.defaultSelectCallback(stale, "uninstall"); assert.equal(removals, 0);
pick(2); assert.equal(fw.common.getCommonTransitionData(), "stock transition");
assert.equal(removals, 0); assert.equal(host.divElt.style.display, "");

settings.open(fw, store); pick(0); pick(0); back(); pick(2);
assert.match(modal.props.text1, /Finishing your settings change/);
assert.equal(modal.props.buttonConfig.button2, undefined); back();
idle(); values = {touch: 0, warning: 1}; reply(values);
pick(2);
const confirmed = modal;
confirmed.props.defaultSelectCallback(confirmed, "uninstall");
confirmed.props.defaultSelectCallback(confirmed, "uninstall");
assert.equal(removals, 1); assert.equal(modal, null); assert.equal(host.divElt.style.display, "");
assert.equal(fw.common.handleControllerEvent, input);
assert.equal(fw.common.getCommonTransitionData, transition);
