const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const names = ["fmradio", "amradio", "dab", "satradio", "xmaudio", "pandora",
    "stitcher", "aharadio", "dvd", "auxin", "usbaudio", "carplay"];

function fixture(skip, hidden) {
    const order = [], factoryIntro = function () { order.push("factoryIntro"); };
    const fw = {
        _appInstances: {},
        _initApp(id) {
            order.push("initialize:" + id);
            this._appInstances[id] = {
                _masterEntertainmentDataList: {items: names.map(name => ({
                    appData: {appName: name, isVisible: true}, disabled: false
                }))},
                _masterApplicationDataList: {items: [{appData: {appName: "xmdata", isVisible: true}}]},
                _contextTable: {IntroAnimation: {contextInFunction: factoryIntro}}
            };
            return "initialized";
        }
    };
    const box = {framework: fw};
    vm.createContext(box);
    vm.runInContext(source.replace("/*OPEN_CONNECT_APPLIED*/", JSON.stringify(skip) + "," + JSON.stringify(hidden)), box);
    assert.equal(fw._initApp("system"), "initialized");
    return {fw, box, order, factoryIntro, app: fw._appInstances.system};
}

for (const skip of [0, 1]) {
    const disabled = ["stitcher", "dab", "tv", "aharadio", "pandora", "satradio", "xmaudio", "xmdata", "dvd"];
    const t = fixture(skip, disabled.join(","));
    const rows = t.app._masterEntertainmentDataList.items;
    const originalOrder = rows.map(row => row.appData.appName);
    // Both availability and late native Visible updates must leave selected
    // rows absent. Preserve master entries and indices used by USB/CarPlay.
    for (const row of rows) {
        row.disabled = false;
        row.appData.isVisible = true;
        assert.equal(row.appData.isVisible, !disabled.includes(row.appData.appName));
    }
    assert.deepEqual(rows.map(row => row.appData.appName), originalOrder);
    assert.equal(rows.findIndex(row => row.appData.appName === "usbaudio"), 10);
    const satelliteData = t.app._masterApplicationDataList.items[0].appData;
    satelliteData.isVisible = true;
    assert.equal(satelliteData.isVisible, false);
    assert(rows.filter(row => row.appData.isVisible).every(row => !disabled.includes(row.appData.appName)));
    if (!skip) assert.equal(t.app._contextTable.IntroAnimation.contextInFunction, t.factoryIntro);
    else assert.notEqual(t.app._contextTable.IntroAnimation.contextInFunction, t.factoryIntro);
    // Replacement of the USB/Settings client is separate from the page hook.
    t.box.OpenConnect = {saved: "all-on", dispose() { delete t.box.OpenConnect; }};
    t.box.OpenConnect.dispose();
    const before = t.app;
    t.fw._initApp("system");
    assert.notEqual(t.fw._appInstances.system, before);
    assert.equal(t.fw._appInstances.system._masterEntertainmentDataList.items[6].appData.isVisible, false);
}
{
    const t = fixture(0, "");
    assert(t.app._masterEntertainmentDataList.items.every(row => row.appData.isVisible));
    assert.equal(t.app._contextTable.IntroAnimation.contextInFunction, t.factoryIntro);
}
console.log("System hook preserves source indices, applied policy, late visibility, reload and factory Intro");
