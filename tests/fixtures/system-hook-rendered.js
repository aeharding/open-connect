// Exercise the actual rendered policy, not a separately supplied hidden-ID list.
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const html = fs.readFileSync(process.argv[2], "utf8"), base = Number(process.argv[3]), warning = Number(process.argv[4]);
const start = html.search(/\(function\s*\(fw,\s*applied\)\s*\{/), close = html.indexOf("}(framework,", start);
assert.equal(start >= 0, Boolean(base || warning));
if (start >= 0) { assert(close > start); }
const end = html.indexOf("]));", close);
let calls = 0, method, callback;
const fw = {_appInstances: {}, _initApp(id) {
    const rows = Array.from({length: 13}, (_, i) => ({appData: {appName: "retained" + i, isVisible: true}}));
    rows[10] = {text1Id: "USB1CarPlay", appData: {appName: "carplay", isVisible: false}};
    rows[11] = {appData: {appName: "androidauto", isVisible: false}};
    const app = {_masterEntertainmentDataList: {items: rows}, _masterApplicationDataList: {items: []},
        _USB1EntIndex: 12, _contextTable: {IntroAnimation: {}},
        _StatusMenuVisibleAndroidAutoMsgHandler() {
            calls++; rows[11].appData.isVisible = true; rows[12].appData.isVisible = false;
        }};
    method = app._StatusMenuVisibleAndroidAutoMsgHandler;
    callback = method.bind(app);
    app._messageTable = {StatusMenuVisibleAndroidAuto: callback};
    this._appInstances[id] = app;
}};
if (start >= 0) { vm.runInNewContext(html.slice(start, end + 4), {framework: fw}); }
fw._initApp("system");
const app = fw._appInstances.system;
assert.equal(app._StatusMenuVisibleAndroidAutoMsgHandler === method, !base);
assert.equal(app._messageTable.StatusMenuVisibleAndroidAuto === callback, !base);
const msg = {params: {payload: {appName: "androidauto", state: "Visible"}}};
app._StatusMenuVisibleAndroidAutoMsgHandler(msg);
app._messageTable.StatusMenuVisibleAndroidAuto(msg);
assert.equal(calls, base ? 0 : 2);
assert.equal(app._masterEntertainmentDataList.items[11].appData.isVisible, !base);
assert.equal(app._masterEntertainmentDataList.items[12].appData.isVisible, Boolean(base));
