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
        ctrl.updateItems = (first,last) => {
            if (first === 2) { assert.equal(last,2); }
            else { assert.equal(first,0); assert.equal(last,1); }
        };
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

appName = "syssettings"; context = "SystemTab";
const detachWithModal = settings.attach(fw, app, store);
list.properties.selectCallback(list, "open-connect-settings");
pick(2);
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
back(); pick(3);
assert.match(modal.props.text1, /Finishing your settings change/);
back(); back();
values = {...values, key: "c".repeat(64), fingerprint: Array(16).fill("ab").join(":"), restart: true};
importReply(values);
assert.equal(modal, null);
settings.open(fw, store); pick(2);
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
idle();
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
assert.equal(savingUartPage.ctrl.dataList.items[2].disabled, true);
idle();
assert.deepEqual(writes.at(-1), ["uart", 0, 1]);
values = {...values, uart: 1, restart: true}; reply(values);
assert.equal(pages.at(-1), savingUartPage);
assert.equal(savingUartPage.ctrl.dataList.items[2].disabled, false);
// Cancelling an unsent change also releases the Import control, without a write.
const beforeCoalesced = writes.length;
const cancelCtrl = pages.at(-1).ctrl;
cancelCtrl.selectCallback(cancelCtrl, "uart", {additionalData: 2});
cancelCtrl.selectCallback(cancelCtrl, "uart", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "enable");
assert.equal(pages.at(-1).ctrl.dataList.items[2].disabled, true);
idle();
assert.equal(writes.length, beforeCoalesced);
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

// Service choices are separate, default running, and take effect after restart.
values = {...values, pandora: 1};
settings.open(fw, store);
assert.equal(pages.at(-1).ctrl.dataList.items[2].text1, "Services");
assert.equal(pages.at(-1).ctrl.dataList.items[2].hasCaret, true);
pick(2);
assert.equal(pages.at(-1).ctrl.title.text1, "Services");
let servicesCtrl = pages.at(-1).ctrl;
assert.equal(servicesCtrl.dataList.items[0].hasCaret, false);
assert.equal(servicesCtrl.dataList.items[0].value, 1);
const beforeService = writes.length;
servicesCtrl.selectCallback(servicesCtrl, "pandora", {additionalData: 2});
assert.equal(modal.props.title, "Disable Pandora?");
assert.match(modal.props.text1, /after restarting/);
modal.props.defaultSelectCallback(modal, "cancel");
idle();
assert.equal(writes.length, beforeService);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 1);
servicesCtrl = pages.at(-1).ctrl;
servicesCtrl.selectCallback(servicesCtrl, "pandora", {additionalData: 2});
modal.props.defaultSelectCallback(modal, "apply");
back(); back(); idle();
assert.deepEqual(writes.at(-1), ["pandora", 1, 0]);
values = {...values, pandora: 0, restart: true}; reply(values);
settings.open(fw, store); pick(2);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 2);
back();
assert.equal(pages.at(-1).ctrl.focussedItem, 2);
pick(3); back();
assert.equal(pages.at(-1).ctrl.focussedItem, 3);
back();

// The measured base preset is independent of Pandora and only saved after its
// confirmation. Both directions explain restart, with no navigation caret.
values = {...values, base: 0};
settings.open(fw, store); pick(2);
let baseCtrl = pages.at(-1).ctrl;
assert.deepEqual(Array.from(baseCtrl.dataList.items, x => x.text1), ["Base optimizations", "Pandora"]);
assert.equal(baseCtrl.dataList.items[0].value, 2);
assert.equal(baseCtrl.dataList.items[0].hasCaret, false);
const beforeBase = writes.length;
baseCtrl.selectCallback(baseCtrl, "base", {additionalData: 1});
assert.equal(modal.props.title, "Enable Base optimizations?");
assert.match(modal.props.text1, /native diagnostic logging/);
assert.doesNotMatch(modal.props.text1, /DAB|TV|Stitcher/);
assert.match(modal.props.text1, /after restarting/);
modal.props.defaultSelectCallback(modal, "cancel"); idle();
assert.equal(writes.length, beforeBase);
baseCtrl = pages.at(-1).ctrl;
baseCtrl.selectCallback(baseCtrl, "base", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "apply");
back(); back(); idle();
assert.deepEqual(writes.at(-1), ["base", 0, 1]);
values = {...values, base: 1, restart: true}; reply(values);
settings.open(fw, store); pick(2);
assert.equal(pages.at(-1).ctrl.dataList.items[0].value, 1);
assert.equal(pages.at(-1).ctrl.dataList.items[1].value, 2);
baseCtrl = pages.at(-1).ctrl;
baseCtrl.selectCallback(baseCtrl, "base", {additionalData: 2});
assert.equal(modal.props.title, "Disable Base optimizations?");
assert.match(modal.props.text1, /Restores original native logging/);
assert.doesNotMatch(modal.props.text1, /DAB|TV|Stitcher/);
modal.props.defaultSelectCallback(modal, "apply"); idle();
assert.deepEqual(writes.at(-1), ["base", 1, 0]);
values = {...values, base: 0}; reply(values);
back(); back();

// Status can become unavailable while a page is open. Keep Back usable and
// refuse the new selection without sending a write.
const beforeUnavailable = writes.length;
const availableValues = values;
settings.open(fw, store); pick(2);
values = null;
const unavailableServices = pages.at(-1).ctrl;
assert.doesNotThrow(() => unavailableServices.selectCallback(unavailableServices, "pandora", {additionalData: 2}));
assert.match(pages.at(-1).ctrl.title.text1, /could not be confirmed/);
back();
values = availableValues;
settings.open(fw, store); pick(3);
values = null;
assert.doesNotThrow(back);
assert.match(pages.at(-1).ctrl.title.text1, /could not be confirmed/);
back();
values = availableValues;
assert.equal(writes.length, beforeUnavailable);

// Wireless is a main-page checkbox; Cancel never saves, and nested-page Back
// returns to the correct row after its insertion. Older status hid this row.
values = {...values, wireless: 0, wirelessCurrent: 0};
settings.open(fw, store);
let wirelessCtrl = pages.at(-1).ctrl;
assert.equal(wirelessCtrl.dataList.items[2].text1, "Wireless CarPlay");
assert.equal(wirelessCtrl.dataList.items[2].value, 2);
assert.equal(wirelessCtrl.dataList.items[2].hasCaret, false);
const beforeWireless = writes.length;
wirelessCtrl.selectCallback(wirelessCtrl, "wireless", {additionalData: 1});
assert.equal(modal.props.title, "Enable Wireless CarPlay?");
assert.match(modal.props.text1, /restarting Mazda Connect/);
assert.match(modal.props.text1, /Bluetooth/);
modal.props.defaultSelectCallback(modal, "cancel"); idle();
assert.equal(writes.length, beforeWireless);
assert.equal(pages.at(-1).ctrl.dataList.items[2].value, 2);
wirelessCtrl = pages.at(-1).ctrl;
wirelessCtrl.selectCallback(wirelessCtrl, "wireless", {additionalData: 1});
modal.props.defaultSelectCallback(modal, "apply");
back(); idle();
assert.deepEqual(writes.at(-1), ["wireless", 0, 1]);
values = {...values, wireless: 1, wirelessCurrent: 0, restart: true}; reply(values);
settings.open(fw, store);
assert.equal(pages.at(-1).ctrl.dataList.items[2].value, 1);
pick(3); back();
assert.equal(pages.at(-1).ctrl.focussedItem, 3);
pick(4); back();
assert.equal(pages.at(-1).ctrl.focussedItem, 4);
wirelessCtrl = pages.at(-1).ctrl;
wirelessCtrl.selectCallback(wirelessCtrl, "wireless", {additionalData: 2});
assert.equal(modal.props.title, "Disable Wireless CarPlay?");
assert.match(modal.props.text1, /original CarPlay behavior/);
modal.props.defaultSelectCallback(modal, "apply"); idle();
assert.deepEqual(writes.at(-1), ["wireless", 1, 0]);
values = {...values, wireless: 0}; reply(values);
back();

// A disappearing status while backing out must not break native Back.
settings.open(fw, store); pick(3);
const availableWirelessValues = values;
values = null;
assert.doesNotThrow(back);
assert.match(pages.at(-1).ctrl.title.text1, /could not be confirmed/);
back();
values = availableWirelessValues;

// Factory wireless is already available: show a checked, disabled row without
// turning that into an Open Connect preference or allowing a confirmation/write.
values = {...values, wireless: 0, wirelessCurrent: 0, wirelessFactory: true};
settings.open(fw, store);
wirelessCtrl = pages.at(-1).ctrl;
assert.match(wirelessCtrl.dataList.items[2].text1, /factory enabled/);
assert.equal(wirelessCtrl.dataList.items[2].value, 1);
assert.equal(wirelessCtrl.dataList.items[2].disabled, true);
const beforeFactory = writes.length, factoryModal = modal;
wirelessCtrl.selectCallback(wirelessCtrl, "wireless", {additionalData: 2});
wirelessCtrl.selectCallback(wirelessCtrl, "wireless", {additionalData: 1});
idle();
assert.equal(writes.length, beforeFactory);
assert.equal(modal, factoryModal);
assert.equal(values.wireless, 0);
back();
values = {...values, wirelessFactory: false};
settings.open(fw, store);
assert.equal(pages.at(-1).ctrl.dataList.items[2].value, 2);
assert.equal(pages.at(-1).ctrl.dataList.items[2].disabled, false);
back();

// A fresh-status response must not reopen Settings after detach or navigation.
appName = "syssettings"; context = "SystemTab";
let freshReply;
store.refresh = done => { freshReply = done; };
let deferredDetach = settings.attach(fw, app, store);
let beforeDeferred = pages.length;
list.properties.selectCallback(list, "open-connect-settings");
assert.equal(pages.length, beforeDeferred);
deferredDetach(); freshReply(true);
assert.equal(pages.length, beforeDeferred);
deferredDetach = settings.attach(fw, app, store);
list.properties.selectCallback(list, "open-connect-settings");
const selectedTemplate = fw._currTmpltInstance;
fw._currTmpltInstance = {divElt: host.divElt, list2Ctrl: {}};
freshReply(true);
assert.equal(pages.length, beforeDeferred);
fw._currTmpltInstance = selectedTemplate;
deferredDetach(); delete store.refresh;

// Current catalog rows carry their own saved bit through the real write queue.
values = {...values, base: 0, services: [
    {id: "android-auto", label: "Android Auto", saved: 1, current: 1,
        enable: "Android Auto will load after restart.", disable: "Android Auto will stop after restart."},
    {id: "pandora", label: "Pandora", saved: 0, current: null,
        enable: "Pandora will load after restart.", disable: "Pandora will stop after restart."}
]};
settings.open(fw, store);
let catalogMain = pages.at(-1).ctrl;
catalogMain.selectCallback(catalogMain, "services");
let catalogCtrl = pages.at(-1).ctrl;
assert.deepEqual(Array.from(catalogCtrl.dataList.items, row => row.appData), ["base", "android-auto", "pandora"]);
assert.match(catalogCtrl.dataList.items[2].text1, /startup unknown/);
const beforeCatalog = writes.length;
catalogCtrl.selectCallback(catalogCtrl, "android-auto", {additionalData: 2});
assert.equal(modal.props.title, "Disable Android Auto?");
assert.match(modal.props.text1, /Android Auto will stop/);
modal.props.defaultSelectCallback(modal, "cancel"); idle();
assert.equal(writes.length, beforeCatalog);
assert.equal(pages.at(-1).ctrl.focussedItem, 1);
catalogCtrl = pages.at(-1).ctrl;
catalogCtrl.selectCallback(catalogCtrl, "android-auto", {additionalData: 2});
modal.props.defaultSelectCallback(modal, "apply"); idle();
assert.deepEqual(writes.at(-1), ["android-auto", 1, 0]);
// State commits even when the response is lost; no duplicate request.
values = {...values, services: values.services.map(row => row.id === "android-auto" ? {...row, saved: 0} : row)};
reply(null); idle();
assert.equal(writes.length, beforeCatalog + 1);
assert.equal(pages.at(-1).ctrl.dataList.items[1].value, 2);
assert.match(pages.at(-1).ctrl.dataList.items[1].text1, /restart needed/);
assert.equal(pages.at(-1).ctrl.dataList.items[2].value, 2);
back(); back();
assert.equal(settings.open(fw, {read: () => ({...values, services: [...values.services, values.services[0]]})}), false);

// Current catalog-backed Base includes qualified leaves, unlike dev.9 scalar status.
settings.open(fw, store);
let newBaseMain = pages.at(-1).ctrl; newBaseMain.selectCallback(newBaseMain, "services");
let newBaseCtrl = pages.at(-1).ctrl; newBaseCtrl.selectCallback(newBaseCtrl, "base", {additionalData: 1});
assert.match(modal.props.text1, /DAB, TV and Stitcher/);
modal.props.defaultSelectCallback(modal, "cancel"); back(); back();
