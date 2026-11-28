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

function fixture(skip, hidden, sourceOrder, menuLoop, holdScroll) {
    const order = [], factoryIntro = function () { order.push("factoryIntro"); };
    const fw = {
        _appInstances: {},
        instantiateControl(uiaId, parentDiv, name, properties) {
            if (name === "MainMenuCtrl") return new box.MainMenuCtrl(uiaId, parentDiv, name, properties);
            if (name === "List2Ctrl") return new box.List2Ctrl(uiaId, parentDiv, name, properties);
            return null;
        },
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
    vm.runInContext(`
        function MainMenuCtrl() { this._focus = 2; this._hi = 2; }
        MainMenuCtrl.prototype._getFocus = function() { return this._focus; };
        MainMenuCtrl.prototype._setFocus = function(i) { this._focus = i; };
        MainMenuCtrl.prototype._setHighlight = function(i) { this._hi = i; };
        MainMenuCtrl.prototype._offsetFocus = function(dir) {
            var i = this._getFocus() + dir;
            if (i < 0) i = 0;
            if (i > 4) i = 4;
            if (i !== this._getFocus()) { this._setFocus(i); this._setHighlight(i); }
        };
        function List2Ctrl(uiaId, parentDiv, controlId, properties) {
            this.properties = { autoscrollTier1Timeout: 1500, scrollingDuringLoading: false };
            if (properties) { for (var k in properties) this.properties[k] = properties[k]; }
            this._hasFocus = true;
            this._inputMode = "controller";
            this._inLetterIndexMulticontroller = false;
            this._inListReorder = false;
            this._inLoading = false;
            this.dataList = null;
            this._focused = 0;
            this.calls = [];
        }
        List2Ctrl.prototype.hasDataList = function() { return !!(this.dataList && this.dataList.items && this.dataList.itemCount > 0); };
        List2Ctrl.prototype._getFocussedIndex = function() { return this._focused; };
        List2Ctrl.prototype._showFocus = function(idx) { this.calls.push(["showFocus", idx]); this._focused = idx; };
        List2Ctrl.prototype._handleMCCW = function() { this.calls.push(["stockCW"]); return "consumed"; };
        List2Ctrl.prototype._handleMCCCW = function() { this.calls.push(["stockCCW"]); return "consumed"; };
    `, box);
    const parts = [JSON.stringify(skip), JSON.stringify(hidden)];
    if (menuLoop !== undefined || holdScroll !== undefined) {
        parts.push(JSON.stringify(sourceOrder || 0), JSON.stringify(menuLoop || 0), JSON.stringify(holdScroll || 0));
    } else if (sourceOrder !== undefined) {
        parts.push(JSON.stringify(sourceOrder));
    }
    const origInstantiate = fw.instantiateControl;
    vm.runInContext(source.replace("/*OPEN_CONNECT_APPLIED*/", parts.join(",")), box);
    assert.equal(fw._initApp("system"), "initialized");
    return {fw, box, order, factoryIntro, origInstantiate, app: fw._appInstances.system};
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
{
    // Issue #213: Factory off leaves instantiateControl untouched.
    const tOff = fixture(0, "", 0, 0, 0);
    assert.equal(tOff.fw.instantiateControl, tOff.origInstantiate);
    const mmOff = tOff.fw.instantiateControl("system", null, "MainMenuCtrl", {});
    mmOff._focus = 0; mmOff._offsetFocus(-1); assert.equal(mmOff._focus, 0);
    const lOff = tOff.fw.instantiateControl("syssettings", null, "List2Ctrl", {});
    assert.equal(lOff.properties.autoscrollTier1Timeout, 1500);

    // Issue #213: holdScroll=1 alone changes default autoscrollTier1Timeout 1500->1000
    // without touching explicit caller timeouts or wrapping MainMenu/List2.
    const tHold = fixture(0, "", 0, 0, 1);
    const mmHold = tHold.fw.instantiateControl("system", null, "MainMenuCtrl", {});
    mmHold._focus = 4; mmHold._offsetFocus(1); assert.equal(mmHold._focus, 4);
    const lDefault = tHold.fw.instantiateControl("syssettings", null, "List2Ctrl", {});
    assert.equal(lDefault.properties.autoscrollTier1Timeout, 1000);
    const lExplicit = tHold.fw.instantiateControl("syssettings", null, "List2Ctrl", {autoscrollTier1Timeout: 1500});
    assert.equal(lExplicit.properties.autoscrollTier1Timeout, 1500);
    const lCustom = tHold.fw.instantiateControl("syssettings", null, "List2Ctrl", {autoscrollTier1Timeout: 2000});
    assert.equal(lCustom.properties.autoscrollTier1Timeout, 2000);
    lDefault.dataList = {itemCountKnown: true, itemCount: 2, items: [{disabled: false}, {disabled: false}]};
    lDefault._focused = 1;
    assert.equal(lDefault._handleMCCW(), "consumed");
    assert.equal(JSON.stringify(lDefault.calls), JSON.stringify([["stockCW"]]));

    // Issue #213: menuLoop=1 alone wraps MainMenuCtrl and List2Ctrl cleanly while
    // preserving factory autoscrollTier1Timeout=1500 and all safety guards.
    const tLoop = fixture(0, "", 0, 1, 0);
    const mm = tLoop.fw.instantiateControl("system", null, "MainMenuCtrl", {});
    mm._focus = 0; mm._offsetFocus(-1); assert.equal(mm._focus, 4); assert.equal(mm._hi, 4);
    mm._offsetFocus(1); assert.equal(mm._focus, 0); assert.equal(mm._hi, 0);
    mm._offsetFocus(1); assert.equal(mm._focus, 1);
    mm._focus = -1; mm._offsetFocus(-1); assert.equal(mm._focus, 4);
    mm._focus = -1; mm._offsetFocus(1); assert.equal(mm._focus, 0);
    // Second instantiation stays idempotent.
    const mm2 = tLoop.fw.instantiateControl("system", null, "MainMenuCtrl", {});
    mm2._focus = 4; mm2._offsetFocus(1); assert.equal(mm2._focus, 0);

    const list = tLoop.fw.instantiateControl("syssettings", null, "List2Ctrl", {});
    assert.equal(list.properties.autoscrollTier1Timeout, 1500);
    // Disabled first & last items: enabled range is [1, 2, 3].
    list.dataList = {
        itemCountKnown: true,
        itemCount: 5,
        items: [{disabled: true}, {disabled: false}, {disabled: false}, {disabled: false}, {disabled: true}]
    };
    const popCall = () => JSON.stringify(list.calls.pop());
    list._focused = 3;
    assert.equal(list._handleMCCW(), "consumed");
    assert.equal(popCall(), JSON.stringify(["showFocus", 1]));
    assert.equal(list._focused, 1);
    assert.equal(list._handleMCCCW(), "consumed");
    assert.equal(popCall(), JSON.stringify(["showFocus", 3]));
    assert.equal(list._focused, 3);
    // Middle move falls through to stock.
    list._focused = 2;
    list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._handleMCCCW(); assert.equal(popCall(), JSON.stringify(["stockCCW"]));
    // Guards fall through to stock: null focus, letter index, reorder, loading, unknown count, single enabled item, sparse item.
    list._focused = null; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._focused = 3;
    list._inLetterIndexMulticontroller = true; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._inLetterIndexMulticontroller = false;
    list._inListReorder = true; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._inListReorder = false;
    list._inLoading = true; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._inLoading = false;
    list._inputMode = "touch"; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list._inputMode = "controller";
    list.dataList.itemCountKnown = false; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list.dataList.itemCountKnown = true;
    list.dataList = {itemCountKnown: true, itemCount: 2, items: [{disabled: true}, {disabled: false}]};
    list._focused = 1; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list.dataList = {itemCountKnown: true, itemCount: 2, items: [undefined, {disabled: false}]};
    list._focused = 1; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    // Lazy-loaded List2Ctrl placeholder slots ({itemStyle: "empty"}) must fall through to stock.
    list.dataList = {
        itemCountKnown: true,
        itemCount: 3,
        items: [{disabled: false}, {disabled: false}, {itemStyle: "empty"}]
    };
    list._focused = 0; list._handleMCCCW(); assert.equal(popCall(), JSON.stringify(["stockCCW"]));
    list._focused = 1; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));
    list.dataList = {
        itemCountKnown: true,
        itemCount: 3,
        items: [{itemStyle: "empty"}, {disabled: false}, {disabled: false}]
    };
    list._focused = 2; list._handleMCCW(); assert.equal(popCall(), JSON.stringify(["stockCW"]));

    // Both menuLoop=1 and holdScroll=1 active together.
    const tBoth = fixture(1, "pandora", 1, 1, 1);
    const lBoth = tBoth.fw.instantiateControl("syssettings", null, "List2Ctrl", {});
    assert.equal(lBoth.properties.autoscrollTier1Timeout, 1000);
    lBoth.dataList = {itemCountKnown: true, itemCount: 2, items: [{disabled: false}, {disabled: false}]};
    lBoth._focused = 1; lBoth._handleMCCW(); assert.equal(lBoth._focused, 0);
}
console.log("System hook preserves source indices, applied policy, late visibility, source order, nav conveniences, reload and factory Intro");
