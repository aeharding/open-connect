const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const names = [
    ["fmradio", "FMRadio", "FmRadio"],
    ["amradio", "AMRadio", "AmRadio"],
    ["dab", "DAB", "DabRadio"],
    ["satradio", "SatRadio", "SdarsRadio"],
    ["xmaudio", "XmAudio", "XMAudio"],
    ["aharadio", "AhaRadio", "AhaRadio"],
    ["pandora", "Pandora", "Pandora"],
    ["stitcher", "Stitcher", "StitcherItem"],
    ["btaudio", "BTAudio", "Bluetooth"],
    ["carplay", "CarPlayWifi", "CarPlay"],
    ["carplay", "CarPlay", "USB1CarPlay"],
    ["androidauto", "AndroidAuto", "USB1AndroidAuto"],
    ["", "USB_A", "UsbAudioA"],
    ["", "USB_B", "UsbAudioB"],
    ["cd", "CD", "CdPlayer"],
    ["auxin", "AuxIn", "AuxIn"],
    ["dvd", "DVD", "DVDItem"],
    ["tv", "TV", "TVItem"],
];

function fixture(skip, hidden, sourceOrder) {
    const order = [], factoryIntro = function () { order.push("factoryIntro"); };
    const fw = {
        _appInstances: {},
        _initApp(id) {
            order.push("initialize:" + id);
            const items = names.map(([appName, audioSourceId, text1Id]) => ({
                appData: {appName, audioSourceId, isVisible: true},
                text1Id,
                disabled: false
            }));
            this._appInstances[id] = {
                _masterEntertainmentDataList: {items},
                _USB1EntIndex: items.findIndex(r => r.appData.audioSourceId === "USB_A"),
                _USB2EntIndex: items.findIndex(r => r.appData.audioSourceId === "USB_B"),
                _masterApplicationDataList: {items: [{appData: {appName: "xmdata", isVisible: true}}]},
                _messageTable: {},
                _contextTable: {IntroAnimation: {contextInFunction: factoryIntro}},
                _buildEntertainmentDataList() {
                    const out = [];
                    for (let i = 0; i < this._masterEntertainmentDataList.items.length; i++) {
                        if (this._masterEntertainmentDataList.items[i].appData.isVisible) {
                            out.push(this._masterEntertainmentDataList.items[i]);
                        }
                    }
                    return {itemCountKnown: true, itemCount: out.length, items: out, vuiSupport: true};
                }
            };
            return "initialized";
        }
    };
    const box = {framework: fw};
    vm.createContext(box);
    const args = sourceOrder === undefined
        ? JSON.stringify(skip) + "," + JSON.stringify(hidden)
        : JSON.stringify(skip) + "," + JSON.stringify(hidden) + "," + JSON.stringify(sourceOrder);
    vm.runInContext(source.replace("/*OPEN_CONNECT_APPLIED*/", args), box);
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
    assert.equal(rows.findIndex(row => row.appData.audioSourceId === "USB_A"), t.app._USB1EntIndex);
    assert.equal(rows[t.app._USB1EntIndex - 2].text1Id, "USB1CarPlay");
    assert.equal(rows[t.app._USB1EntIndex - 1].text1Id, "USB1AndroidAuto");
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
    const t = fixture(0, "", 0);
    assert(t.app._masterEntertainmentDataList.items.every(row => row.appData.isVisible));
    assert.equal(t.app._contextTable.IntroAnimation.contextInFunction, t.factoryIntro);
    const built = t.app._buildEntertainmentDataList();
    assert.equal(built.items[0].appData.audioSourceId, "FMRadio");
}
{
    // Issue #216: Phone & media first reorders ONLY _buildEntertainmentDataList() output,
    // preserving _masterEntertainmentDataList order & Mazda _USB1EntIndex arithmetic,
    // and composing cleanly with concealed Base/Pandora/SiriusXM/Android Auto rows.
    const disabled = ["stitcher", "dab", "tv", "aharadio", "dvd", "pandora", "satradio", "xmaudio", "xmdata", "androidauto"];
    const t = fixture(1, disabled.join(","), 1);
    const master = t.app._masterEntertainmentDataList.items;
    assert.equal(master[0].appData.audioSourceId, "FMRadio");
    assert.equal(master[t.app._USB1EntIndex].appData.audioSourceId, "USB_A");
    assert.equal(master[t.app._USB1EntIndex - 2].text1Id, "USB1CarPlay");
    assert.equal(master[t.app._USB1EntIndex - 1].text1Id, "USB1AndroidAuto");
    const built = t.app._buildEntertainmentDataList();
    assert.equal(built.itemCount, built.items.length);
    assert.equal(built.vuiSupport, true);
    assert.deepEqual(
        Array.from(built.items, r => r.appData.audioSourceId),
        ["CarPlayWifi", "CarPlay", "USB_A", "USB_B", "BTAudio", "FMRadio", "AMRadio", "CD", "AuxIn"]
    );
    // Live reload re-applies the ordering hook cleanly.
    t.fw._initApp("system");
    const rebuilt = t.fw._appInstances.system._buildEntertainmentDataList();
    assert.deepEqual(
        Array.from(rebuilt.items, r => r.appData.audioSourceId),
        ["CarPlayWifi", "CarPlay", "USB_A", "USB_B", "BTAudio", "FMRadio", "AMRadio", "CD", "AuxIn"]
    );
    // With all sources visible (no hidden services), AndroidAuto sits right after CarPlay.
    const tAll = fixture(0, "", 1);
    assert.equal(tAll.app._contextTable.IntroAnimation.contextInFunction, tAll.factoryIntro);
    assert.deepEqual(
        Array.from(tAll.app._buildEntertainmentDataList().items.slice(0, 8), r => r.appData.audioSourceId),
        ["CarPlayWifi", "CarPlay", "AndroidAuto", "USB_A", "USB_B", "BTAudio", "FMRadio", "AMRadio"]
    );
}
console.log("System hook preserves source indices, applied policy, late visibility, source order, reload and factory Intro");
