const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let queued;
const animations=new Map();
const element=require("./ui-element.js");
const ctx = {document: {body: {}}, log: {error(e) { throw Error(e); }},
    setTimeout(fn,ms) { const id={animation:ms===900}; if(id.animation) animations.set(id,fn); else queued=fn; return id; },
    clearTimeout(id) { if(id&&id.animation) animations.delete(id); else queued=null; }};
ctx.window=ctx;
function idle() { const fn=queued; queued=null; if (fn) { fn(); } }
function settle() { while(animations.size) { const [id,fn]=animations.entries().next().value; animations.delete(id); fn(); } }
for (const path of process.argv.slice(2)) { vm.runInNewContext(fs.readFileSync(path, "utf8"), ctx); }
const settings = ctx.OpenConnectSettings;
const open=settings.open;
settings.open=(...args)=>{const result=open(...args);settle();return result;};
const pages = [], calls = [];
const offscreen = {removeChild(node) { node.parentNode = null; }, appendChild(n) { n.parentNode = this; }};
const parent = {removeChild(node) { node.parentNode = null; }, appendChild(n) { n.parentNode = this; }};
const input = () => "stock input", send = (...args) => calls.push(args);
const transition = () => "stock transition";
const host = {divElt: element(parent), list2Ctrl: {},
    handleControllerEvent: input};
const fw = {getCurrentApp: () => "syssettings", getCurrCtxtId: () => "SystemTab",
    _frameworkState: 1, _FWK_STATE_IDLE: 1, _currTmpltInstance: host, _offscreenTemplateParent: offscreen,
    common: {getCommonTransitionData: transition}, multicontroller: {getMode: () => "controllerActive"},
    sendEventToMmui: send,
    instantiateTemplate(app, container, type, props) {
        assert.equal(type, "List2Tmplt"); assert.equal(app, "syssettings"); assert.equal(container, offscreen);
        const ctrl = props.List2Ctrl;
        ctrl.updateItems = (first,last) => {
            assert.ok(first>=0&&last>=first&&last<ctrl.dataList.items.length);
        };
        pages.push({ctrl, list2Ctrl: ctrl, divElt: element(offscreen), events: [],
            cleanUp() { this.cleaned = true; }, handleControllerEvent(e) { this.events.push(e); return "consumed"; }});
        return pages.at(-1);
    }};
let values = {touch: 1, warning: 0}, reply;
const writes = [];
const store = {read: () => values, write(...args) { reply = args.pop(); writes.push(args); }};
const pick = i => {
    const ctrl = pages.at(-1).ctrl, rows = ctrl.dataList.items;
    if(typeof i==="string") i=rows.findIndex(row=>row.appData===i);
    if (rows[i].image1 === "radio") { rows.forEach((row,index) => { row.checked = index === i; }); }
    const result=ctrl.selectCallback(ctrl, rows[i].appData);settle();return result;
};
const back = () => {fw.sendEventToMmui("common", "Global.GoBack");settle();};
assert.equal(typeof settings.open(fw, store), "function");
assert.equal(settings.open(fw, store), false);
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1, "Always enabled");
assert.equal(pages.at(-1).ctrl.dataList.items[0].labelWidth, "wide");
assert.equal(pages.at(-1).ctrl.checkMinChangeInterval,undefined);
pick(0);
let page = pages.at(-1);
assert.deepEqual(Array.from(page.ctrl.dataList.items, row => row.text1), ["Factory behavior", "Always enabled", "Always disabled"]);
assert.equal(page.ctrl.checkMinChangeInterval,0);
assert.deepEqual(Array.from(page.ctrl.dataList.items, r => [r.image1,r.checked]), [["radio",false],["radio",true],["radio",false]]);
assert.equal(host.handleControllerEvent("ccw"), "consumed");
assert.deepEqual(writes, []);
pick(0); pick(1); pick(0);
assert.equal(pages.at(-1),page);
assert.deepEqual(Array.from(page.ctrl.dataList.items,r=>r.checked),[true,false,false]);
assert.deepEqual(writes,[["touch",1,0]]);
back(); assert.equal(pages.at(-1).ctrl.dataList.items[0].label1,"Factory behavior");
back(); assert.equal(host.divElt.style.display,"");
assert.deepEqual(writes,[["touch",1,0]]);
settings.open(fw,store); pick(0); pick(1);
assert.deepEqual(writes,[["touch",1,0]]);
values={touch:0,warning:0}; reply(values);
assert.deepEqual(writes,[["touch",1,0],["touch",0,1]]);
values={touch:1,warning:0}; reply(values);
assert.equal(pages.at(-1).ctrl.title.text1,"Touchscreen");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.checked),[false,true,false]);
back(); pick(1); pick(1); back(); back(); idle();
assert.equal(host.handleControllerEvent,input); assert.equal(fw.sendEventToMmui,send);
values={touch:1,warning:1}; reply(null); // acknowledgement lost after the write
assert.equal(fw.common.getCommonTransitionData,transition); assert.deepEqual(calls,[]);
settings.open(fw,store); pick(0); pick(0); idle(); reply(values);
assert.match(pages.at(-1).ctrl.title.text1,/could not be confirmed/); back();
assert.equal(host.divElt.style.display,"");
assert.equal(settings.open(fw,{read:()=>({touch:3,warning:1})}),false);
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
settle();
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
    modal = {props, divElt: {classList: {add() {}}, style: {}}, handleControllerEvent() {}, setText1(){}, setText2(){}};
    return modal;
};
ctx.document.addEventListener = () => {};
ctx.document.removeEventListener = () => {};
fw.destroyControl = control => { assert.equal(control, modal); modal = null; };
fw.common.handleControllerEvent = input;
settings.open(fw, store);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, r => r.text1),
    ["Touchscreen", "Startup disclaimer", "Apply changes", "Uninstall", "About"]);
assert.equal(pages.at(-1).ctrl.dataList.items[2].disabled, true);
pick("uninstall"); assert.equal(modal, undefined);
pick("about"); assert.equal(modal.props.text1, "Installed version unavailable.");
back(); back();
store.version = "0.2.1";
store.uninstall = leave => { removals++; leave(); return true; };
settings.open(fw, store);
pick("about"); assert.equal(modal.props.title, "About"); assert.equal(modal.props.text1, "Open Connect 0.2.1");
pick("uninstall"); assert.equal(modal.props.title, "About"); // background list cannot steal the modal
back(); assert.equal(modal, null);
pick("uninstall"); assert.equal(modal.props.buttonConfig.button1.label, "Cancel");
assert.equal(modal.props.initialFocus, 0);
const stale = modal;
back(); stale.props.defaultSelectCallback(stale, "uninstall"); assert.equal(removals, 0);
pick("uninstall"); assert.equal(fw.common.getCommonTransitionData(), "stock transition");
assert.equal(removals, 0); assert.equal(host.divElt.style.display, "");

settings.open(fw, store); pick(0); pick(0); back(); pick("uninstall");
assert.equal(modal.props.buttonConfig.button2.appData, "uninstall");
modal.props.defaultSelectCallback(modal, "cancel");
values = {touch: 0, warning: 1}; reply(values);
pick("uninstall");
const confirmed = modal;
confirmed.props.defaultSelectCallback(confirmed, "uninstall");
confirmed.props.defaultSelectCallback(confirmed, "uninstall");
assert.equal(removals, 1); assert.equal(modal, null); assert.equal(host.divElt.style.display, "");
assert.equal(fw.common.handleControllerEvent, input);
assert.equal(fw.common.getCommonTransitionData, transition);

appName = "syssettings"; context = "SystemTab";
const detachWithModal = settings.attach(fw, app, store);
list.properties.selectCallback(list, "open-connect-settings");
settle();
pick("uninstall");
const detached = modal;
detachWithModal();
assert.equal(modal, null);
detached.props.defaultSelectCallback(detached, "uninstall");
assert.equal(removals, 1);
assert.equal(host.divElt.style.display, "");

// Developer controls use Mazda's actual On/Off callback values. Import shares
// the preference session, so leaving the page cannot race uninstall or writes.
values = {touch: 0, warning: 1, developer: true, uart: 0, ssh: 0, uartCurrent: 0, sshCurrent: 0,
    key: "-", fingerprint: "-", restart: false};
let importReply;
store.importKey = callback => { importReply = callback; };
settings.open(fw, store);
assert.equal(pages.at(-1).ctrl.dataList.items[2].text1, "Developer options");
pick(2);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, row => row.text1), ["UART", "SSH", "Import public key"]);
assert.equal(pages.at(-1).ctrl.title.titleStyle, "style02");
assert.equal(pages.at(-1).ctrl.title.text2, undefined);
assert.equal(pages.at(-1).ctrl.dataList.items[0].itemStyle, "styleOnOff");
assert.equal(pages.at(-1).ctrl.dataList.items[1].disabled, true);
pick(2);
assert.equal(modal.props.title, "Import public key?");
modal.props.defaultSelectCallback(modal, "cancel");
assert.equal(importReply, undefined);
pick(2); modal.props.defaultSelectCallback(modal, "import");
assert.equal(modal.props.text1, "Importing public key");
values = {...values, key: "c".repeat(64), fingerprint: Array(16).fill("ab").join(":"), restart: true};
importReply(values);
assert.equal(modal.props.title, "Public key imported");
modal.props.defaultSelectCallback(modal, "done");
assert.equal(modal, null);
assert.equal(pages.at(-1).ctrl.dataList.items[1].disabled, false);
const developerCtrl = pages.at(-1).ctrl;
developerCtrl.selectCallback(developerCtrl, "ssh", {additionalData: 1});
assert.equal(modal.props.title, "Enable SSH?");
assert.match(modal.props.text1, /Changes apply after restarting/);
modal.props.defaultSelectCallback(modal, "cancel");
assert.equal(pages.at(-1).ctrl.dataList.items[1].value, 2);
let sshCtrl = pages.at(-1).ctrl;
sshCtrl.selectCallback(sshCtrl, "ssh", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "enable");
assert.deepEqual(writes.at(-1), ["ssh", 0, 1]);
values = {...values, ssh: 1}; reply(values);
values = {...values, restart: false};
const afterSshCtrl = pages.at(-1).ctrl;
afterSshCtrl.selectCallback(afterSshCtrl, "uart", {additionalData: 1});
assert.equal(modal.props.title, "Enable UART?");
modal.props.defaultSelectCallback(modal, "cancel");
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 2);
let uartCtrl = pages.at(-1).ctrl;
uartCtrl.selectCallback(uartCtrl, "uart", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "enable");
const savingUartPage = pages.at(-1);
assert.equal(savingUartPage.ctrl.dataList.items[2].disabled, false);
assert.deepEqual(writes.at(-1), ["uart", 0, 1]);
values = {...values, uart: 1, restart: true}; reply(values);
assert.equal(pages.at(-1), savingUartPage);
assert.equal(savingUartPage.ctrl.dataList.items[2].disabled, false);
// Toggling off and back on while first write is in flight coalesces cleanly.
const beforeCoalesced = writes.length;
const cancelCtrl = pages.at(-1).ctrl;
cancelCtrl.selectCallback(cancelCtrl, "uart", {additionalData: 2});
cancelCtrl.selectCallback(cancelCtrl, "uart", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "enable");
assert.equal(writes.length, beforeCoalesced + 1);
values = {...values, uart: 0}; reply(values);
assert.equal(writes.length, beforeCoalesced + 2);
values = {...values, uart: 1}; reply(values);
assert.equal(pages.at(-1).ctrl.dataList.items[2].disabled, false);
// Keep every fingerprint octet visible in Mazda's fixed-width dialog.
pick(2); modal.props.defaultSelectCallback(modal, "import");
importReply(values);
assert.equal(modal.props.title, "Public key imported");
const fingerprintLines = modal.props.text1.split("\n");
assert.equal(fingerprintLines.length, 4);
assert.equal(fingerprintLines.slice(1, 3).join(":"), values.fingerprint);
assert.equal(fingerprintLines[1].length, 23);
assert.equal(fingerprintLines[2].length, 23);
modal.props.defaultSelectCallback(modal, "done");
back(); back();

// Legacy scalar Pandora remains available in Audio sources.
const choose = key => {
    const ctrl = pages.at(-1).ctrl;
    const row = ctrl.dataList.items.find(row => row.appData === key);
    assert.ok(row, `missing ${key}`);
    return pick(ctrl.dataList.items.indexOf(row));
};
const toggle = (key, enabled) => {
    const ctrl = pages.at(-1).ctrl;
    ctrl.selectCallback(ctrl, key, {additionalData: enabled ? 1 : 2});
};
const confirm = action => modal.props.defaultSelectCallback(modal, action);
const keys = () => Array.from(pages.at(-1).ctrl.dataList.items, row => row.appData);
values = {...values, pandora: 1};
settings.open(fw, store); choose("sources");
assert.equal(pages.at(-1).ctrl.title.text1, "Audio sources");
assert.deepEqual(keys(), ["pandora"]);
const beforeService = writes.length;
toggle("pandora", false);
assert.match(modal.props.text1, /after restarting Mazda Connect/);
assert.doesNotMatch(modal.props.text1, /Sources/);
confirm("cancel"); idle();
assert.equal(writes.length, beforeService);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 1);
toggle("pandora", false); confirm("apply"); back(); back(); idle();
assert.deepEqual(writes.at(-1), ["pandora", 1, 0]);
values = {...values, pandora: 0, restart: true}; reply(values);

// Legacy Base is now a root checkbox and retains the scalar logging explanation.
values = {...values, base: 0};
settings.open(fw, store);
assert.equal(pages.at(-1).ctrl.dataList.items[2].text1, "Startup optimizations");
assert.equal(pages.at(-1).ctrl.dataList.items[2].hasCaret, false);
toggle("base", true);
assert.match(modal.props.title, /Enable Startup optimizations/);
assert.match(modal.props.text1, /native diagnostic logging/);
confirm("cancel"); idle();
assert.equal(writes.length, beforeService + 1);
toggle("base", true); confirm("apply"); idle();
assert.deepEqual(writes.at(-1), ["base", 0, 1]);
values = {...values, base: 1}; reply(values);
assert.equal(pages.at(-1).ctrl.focussedItem, 2);
toggle("base", false);
assert.match(modal.props.text1, /Restores original native logging/);
confirm("apply"); idle();
values = {...values, base: 0}; reply(values); back();

// Real catalog defaults, labels and wire IDs; no preference schema changes.
const catalog = fs.readFileSync(require("node:path").join(process.argv[3], "../services.tsv"), "utf8")
    .split("\n").filter(line => line && !line.startsWith("#")).map(line => {
        const [id, label, saved, , enable, disable] = line.split("|");
        return {id, label, saved: Number(saved), current: Number(saved), enable, disable};
    });
store.version = fs.readFileSync(require("node:path").join(process.argv[3], "../VERSION"), "utf8").trim();
assert.match(store.version, /^0\.3\.0-dev\.[0-9]+$/);
values = {...values, wireless: 0, wirelessCurrent: 0, wirelessFactory: false,
    carplayAutoshow: 0, carplayAutoshowCurrent: 0, services: catalog};
settings.open(fw, store);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, row => row.text1), [
    "Touchscreen", "Startup disclaimer", "Startup optimizations",
    "CarPlay & Android Auto", "Audio sources", "Developer options", "Apply changes", "Uninstall", "About"
]);
assert.deepEqual(keys(), [0, 1, "base", "phone", "sources", "developer", "restart", "uninstall", "about"]);
assert.equal(pages.at(-1).ctrl.toggleMinChangeInterval, 0);
choose("phone");
assert.equal(pages.at(-1).ctrl.title.text1, "CarPlay & Android Auto");
assert.deepEqual(keys(), ["wireless", 2, "android-auto"]);
assert.equal(pages.at(-1).ctrl.dataList.items[1].label1, "Factory");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items.filter(r => r.itemStyle === "styleOnOff"), r => r.value), [2, 1]);
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 3);
choose("sources"); assert.deepEqual(keys(), ["pandora", "siriusxm"]);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, r => r.value), [1, 1]);
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 4);
choose("developer");
assert.equal(pages.at(-1).ctrl.dataList.items[2].hasCaret, true);
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 5);

// Each toggle has a cancel-first native dialog, saves the same backend key and
// returns focus to the selected row. Catalog current/restart state stays visible.
for (const id of ["android-auto", "pandora", "siriusxm"]) {
    const group = id === "android-auto" ? "phone" : "sources";
    choose(group);
    const initial = values.services.find(row => row.id === id).saved;
    const index = keys().indexOf(id), before = writes.length;
    toggle(id, !initial);
    assert.equal(modal.props.initialFocus, 0);
    assert.equal(modal.props.buttonConfig.button1.label, "Cancel");
    assert.match(modal.props.text1, /CarPlay and CDs are unchanged/);
    assert.match(modal.props.text1, /after restart/);
    assert.ok(modal.props.text1.length <= 150);
    confirm("cancel"); idle();
    assert.equal(writes.length, before);
    assert.equal(pages.at(-1).ctrl.dataList.items[index].value, initial ? 1 : 2);
    toggle(id, !initial); confirm("apply"); idle();
    assert.deepEqual(writes.at(-1), [id, initial, 1-initial]);
    values = {...values, services: values.services.map(row => row.id === id ? {...row, saved: 1-initial} : row)};
    reply(id === "android-auto" ? null : values); idle(); // lost acknowledgement reconciles, never resends
    assert.equal(writes.length, before+1);
    assert.equal(pages.at(-1).ctrl.focussedItem, index);
    back(); choose(group);
    assert.match(pages.at(-1).ctrl.dataList.items[index].text1, /restart needed/);
    assert.equal(pages.at(-1).ctrl.dataList.items[index].value, initial ? 2 : 1);
    toggle(id, !!initial); confirm("apply"); idle();
    values = {...values, services: values.services.map(row => row.id === id ? {...row, saved: initial} : row)};
    reply(values); back();
}
back();
// Earlier installed catalogs retain their own explanations and do not promise
// the later Sources filtering merely because a newer Settings UI is loaded.
const currentCatalogValues = values;
values = {...values, services: [{id: "pandora", label: "Pandora", saved: 1, current: 1,
    enable: "Pandora will load after Mazda Connect restarts.",
    disable: "Pandora will stop loading after Mazda Connect restarts."}]};
settings.open(fw, store); choose("sources"); toggle("pandora", false);
assert.equal(modal.props.text1, values.services[0].disable);
assert.doesNotMatch(modal.props.text1, /Sources/);
confirm("cancel"); back(); back();
values = currentCatalogValues;
settings.open(fw, store);

// Wireless moved inside Phone. Cancel, factory-enabled refusal and vanished
// status still preserve preference/session ownership and the native Back path.
choose("phone");
const beforeWireless = writes.length;
toggle("wireless", true);
assert.match(modal.props.text1, /restarting Mazda Connect/);
assert.match(modal.props.text1, /Bluetooth/);
confirm("cancel"); idle(); assert.equal(writes.length, beforeWireless);
assert.equal(pages.at(-1).ctrl.focussedItem, 0);
toggle("wireless", true); confirm("apply"); idle();
assert.deepEqual(writes.at(-1), ["wireless", 0, 1]);
values = {...values, wireless: 1}; reply(values);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 1);
toggle("wireless", false);
assert.match(modal.props.text1, /original CarPlay behavior/);
confirm("apply"); idle(); values = {...values, wireless: 0}; reply(values);
back(); back();
values = {...values, wirelessFactory: true};
settings.open(fw, store); choose("phone");
assert.match(pages.at(-1).ctrl.dataList.items[0].text1, /factory enabled/);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 1);
assert.equal(pages.at(-1).ctrl.dataList.items[0].disabled, true);
const beforeFactory = writes.length;
toggle("wireless", false); toggle("wireless", true); idle();
assert.equal(writes.length, beforeFactory); assert.equal(modal, null);
back(); back(); values = {...values, wirelessFactory: false};

for (const action of ["select", "back"]) {
    settings.open(fw, store); choose("phone");
    const available = values, before = writes.length;
    values = null;
    assert.doesNotThrow(() => action === "select" ? toggle("android-auto", false) : back());
    assert.match(pages.at(-1).ctrl.title.text1, /could not be confirmed/);
    back(); values = available; assert.equal(writes.length, before);
}
assert.equal(settings.open(fw, {read: () => ({...values, services: [...values.services, values.services[0]]})}), false);
values = {...values, services: values.services.map(row => row.id === "pandora" ? {...row, current: null} : row)};
settings.open(fw, store); choose("sources");
assert.match(pages.at(-1).ctrl.dataList.items[0].text1, /startup unknown/);
back(); back();

// Current Base keeps the Navigation warning with Wireless enabled. Longest
// enable body fits the fixed native dialog without the previous verbose copy.
for (const version of [store.version]) for (const wireless of [0, 1]) {
    store.version = version;
    values = {...values, base: 0, wireless};
    settings.open(fw, store); toggle("base", true);
    assert.match(modal.props.text1, /background logging and unused services/);
    assert.equal(/Mazda Navigation about 20 s/.test(modal.props.text1), wireless === 1);
    assert.ok(modal.props.text1.length <= 125);
    confirm("cancel"); back();
}
store.version = "0.3.0-dev.20";

// A fresh-status response must not reopen Settings after detach or navigation.
let freshReply;
store.refresh = done => { freshReply = done; };
const cachedRead=store.read;
store.read=()=>null;
let deferredDetach = settings.attach(fw, app, store);
let beforeDeferred = pages.length;
list.properties.selectCallback(list, "open-connect-settings");
assert.equal(pages.length, beforeDeferred);
deferredDetach(); freshReply(true); assert.equal(pages.length, beforeDeferred);
deferredDetach = settings.attach(fw, app, store);
list.properties.selectCallback(list, "open-connect-settings");
const selectedTemplate = fw._currTmpltInstance;
fw._currTmpltInstance = {divElt: host.divElt, list2Ctrl: {}};
freshReply(true); assert.equal(pages.length, beforeDeferred);
fw._currTmpltInstance = selectedTemplate;
deferredDetach(); delete store.refresh;
store.read=cachedRead;

// Ownership begins before the debounce timer and survives Back until ack.
let allow=true, pendingStates=[];
store.pending = value => { pendingStates.push(value); return !value || allow; };
settings.open(fw,store); pick(0);
const beforePending=writes.length;
allow=false; pick(1-values.touch);
assert.equal(queued,null);
assert.equal(pages.at(-1).ctrl.dataList.items[values.touch].checked,true);
allow=true; pick(1-values.touch);
assert.equal(pendingStates.at(-1),true);
back(); back(); idle();
assert.equal(writes.length,beforePending+1);
assert.equal(pendingStates.at(-1),true);
values={...values,touch:1-values.touch}; reply(values);
assert.equal(pendingStates.at(-1),false);

// Autoshow retains radio confirmation, wire ID and two-level Back focus.
settings.open(fw,store); choose("phone"); choose(2);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.text1),["Factory behavior","Automatically show"]);
const beforeAutoshow=writes.length;
pick(1); assert.match(modal.props.text1,/restart/i); assert.equal(writes.length,beforeAutoshow);
confirm("cancel");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.checked),[true,false]);
pick(1); confirm("apply"); idle();
assert.deepEqual(writes.at(-1),["carplay-autoshow",0,1]);
values={...values,carplayAutoshow:1}; reply(values); back();
assert.equal(pages.at(-1).ctrl.title.text1, "CarPlay & Android Auto");
assert.equal(pages.at(-1).ctrl.focussedItem, 1);
assert.equal(pages.at(-1).ctrl.dataList.items[1].label1, "Auto");
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 3); back();
assert.equal(settings.validStatus({...values,ok:true,revision:"-",installed:true,retained:false,conflict:false,restart:true,pending:false,version:store.version,wirelessCurrent:0}),true);
assert.equal(settings.open(fw,{read:()=>({...values,carplayAutoshowCurrent:2})}),false);

// Issue #216: Source order lives in Audio sources, writes wire key source-order,
// drives restart state, preserves two-level Back focus, and validates bit pairs.
values={...values,sourceOrder:0,sourceOrderCurrent:0,restart:false,carplayAutoshow:0,carplayAutoshowCurrent:0};
settings.open(fw,store); choose("sources");
assert.equal(pages.at(-1).ctrl.title.text1, "Audio sources");
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1, "Source order");
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1, "Factory");
choose(3);
assert.equal(pages.at(-1).ctrl.title.text1, "Source order");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.text1),["Factory order","Phone & media first"]);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.checked),[true,false]);
pick(1); idle();
assert.deepEqual(writes.at(-1),["source-order",0,1]);
values={...values,sourceOrder:1,restart:true}; reply(values); back();
assert.equal(pages.at(-1).ctrl.title.text1, "Audio sources");
assert.equal(pages.at(-1).ctrl.focussedItem, 0);
assert.equal(pages.at(-1).ctrl.dataList.items[0].label1, "Phone first");
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 4); back();
assert.equal(settings.open(fw,{read:()=>({...values,sourceOrderCurrent:2})}),false);

// Issue #213: Commander Dial submenu exposes independent menuLoop & holdScroll toggles,
// writes wire keys menu-loop & hold-scroll, drives restart state, and preserves Back focus.
values={...values,sourceOrder:0,sourceOrderCurrent:0,menuLoop:0,menuLoopCurrent:0,holdScroll:0,holdScrollCurrent:0,restart:false};
settings.open(fw,store); choose("dial");
assert.equal(pages.at(-1).ctrl.title.text1, "Commander Dial");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.text1),["Wrap-around menus & lists","Faster hold-scroll"]);
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items,r=>r.value),[2,2]);
let dialCtrl=pages.at(-1).ctrl;
dialCtrl.selectCallback(dialCtrl,"menuLoop",{additionalData:1});
assert.equal(modal.props.title,"Enable Wrap-around menus & lists?");
confirm("cancel"); assert.equal(pages.at(-1).ctrl.dataList.items[0].value,2);
dialCtrl=pages.at(-1).ctrl;
dialCtrl.selectCallback(dialCtrl,"menuLoop",{additionalData:1});
confirm("apply"); idle();
assert.deepEqual(writes.at(-1),["menu-loop",0,1]);
values={...values,menuLoop:1,restart:true}; reply(values);
dialCtrl=pages.at(-1).ctrl;
dialCtrl.selectCallback(dialCtrl,"holdScroll",{additionalData:1});
assert.equal(modal.props.title,"Enable Faster hold-scroll?");
confirm("apply"); idle();
assert.deepEqual(writes.at(-1),["hold-scroll",0,1]);
values={...values,holdScroll:1,restart:true}; reply(values);
back(); assert.equal(pages.at(-1).ctrl.focussedItem, 5); back();
assert.equal(settings.open(fw,{read:()=>({...values,menuLoopCurrent:2})}),false);
assert.equal(settings.open(fw,{read:()=>({...values,holdScrollCurrent:2})}),false);

// Null prefs.values() while inside Developer options or CarPlay autoshow renders unknown state safely without throwing.
let allowRead = true;
const flakyStore = {...store, read: () => (allowRead ? values : null)};
settings.open(fw, flakyStore); choose("developer");
allowRead = false;
pages.at(-1).ctrl.selectCallback(pages.at(-1).ctrl, "uart", {additionalData: 1});
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1, "Return to Mazda Settings");
allowRead = true; back();
settings.open(fw, flakyStore); choose("phone"); choose(2);
allowRead = false;
pick(1);
assert.equal(pages.at(-1).ctrl.dataList.items[0].text1, "Return to Mazda Settings");
allowRead = true; back();

// Issue #130: Backup & restore submenu is gated on store.exportPrefs/importPrefs,
// prompts cancel-first, runs queued tasks, shows result dialogs, and returns Back focus.
let exportReply = null, importPrefsReply = null;
const backupStore = {...store, exportPrefs: cb => { exportReply = cb; }, importPrefs: cb => { importPrefsReply = cb; }};
settings.open(fw, backupStore);
choose("backup");
assert.equal(pages.at(-1).ctrl.title.text1, "Backup & restore");
assert.deepEqual(Array.from(pages.at(-1).ctrl.dataList.items, r => r.appData), ["exportPrefs", "importPrefs"]);
pick(0);
assert.equal(modal.props.title, "Export preferences?");
assert.equal(modal.props.initialFocus, 0);
confirm("cancel"); assert.equal(exportReply, null);
pick(0); confirm("export"); idle();
assert.ok(exportReply);
exportReply(values);
assert.equal(modal.props.title, "Preferences exported");
confirm("done");
pick(1);
assert.equal(modal.props.title, "Import preferences?");
confirm("import"); idle();
assert.ok(importPrefsReply);
importPrefsReply(null, true);
assert.equal(modal.props.title, "Import failed");
confirm("done");
pick(1); confirm("import"); idle();
values = {...values, touch: 2, restart: true};
importPrefsReply(values);
assert.equal(modal.props.title, "Preferences imported");
confirm("done");
back();
assert.equal(pages.at(-1).ctrl.dataList.items[pages.at(-1).ctrl.focussedItem].appData, "backup");
back();
console.log("Reorganized native menus preserve defaults, confirmations, wire keys, restart state and Back focus");
