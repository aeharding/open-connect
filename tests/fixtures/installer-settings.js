const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ctx = {};
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
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
        pages.push({ctrl, list2Ctrl: ctrl, divElt: {parentNode: parent}, events: [],
            cleanUp() { this.cleaned = true; }, handleControllerEvent(e) { this.events.push(e); return "consumed"; }});
        return pages.at(-1);
    }};
let values = {touch: 1, warning: 0}, reply;
const writes = [];
const store = {read: () => values, write(...args) { reply = args.pop(); writes.push(args); }};
const pick = i => { const p = pages.at(-1); return p.ctrl.selectCallback(p.ctrl, p.ctrl.dataList.items[i].appData); };
const back = () => fw.sendEventToMmui("common", "Global.GoBack");
assert.equal(typeof settings.open(fw, store), "function");
assert.equal(settings.open(fw, store), false);
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1, "Always");
pick(0);
let page = pages.at(-1);
assert.deepEqual(Array.from(page.ctrl.dataList.items, r => [r.image1,r.checked]), [["radio",false],["radio",true]]);
assert.equal(host.handleControllerEvent("ccw"), "consumed");
assert.deepEqual(writes, []);
pick(0);
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1,"Saving setting…");
assert.ok(page.cleaned);
page.ctrl.selectCallback(page.ctrl,1); pick(0);
assert.deepEqual(writes, [["touch",1,0]]);
values = {touch: 0, warning: 0}; reply(values);
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1,"Default");
page.ctrl.selectCallback(page.ctrl, 1);
pick(1); back();
assert.equal(pages.at(-1).ctrl.title.text1,"Open Connect");
pick(1); pick(1); back(); reply({touch: 0, warning: 1});
assert.equal(host.divElt.style.display, "");
assert.equal(host.handleControllerEvent, input); assert.equal(fw.sendEventToMmui, send);
assert.equal(fw.common.getCommonTransitionData, transition); assert.deepEqual(calls, []);
settings.open(fw,store); pick(0); pick(1); reply(values);
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/);
assert.equal(fw.common.getCommonTransitionData(), "stock transition");
assert.ok(pages.every(p => p.cleaned)); assert.equal(host.divElt.style.display, "");
assert.equal(settings.open(fw,{read:()=>({touch:2,warning:1})}),false);
console.log("Mazda settings menu, single-choice pages, confirmed save, back and interrupted context passed");

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
settings.open(fw,store); pick(1); pick(1); reply(null);
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/);
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1,"Return to Mazda Settings");
back(); assert.equal(host.divElt.style.display,"");
