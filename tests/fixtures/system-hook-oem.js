// Execute exact private OEM list initialization, visibility and menu builders.
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const [systemFile, hookFile] = process.argv.slice(2);
const source = fs.readFileSync(systemFile, "utf8"), hook = fs.readFileSync(hookFile, "utf8");
function method(name) {
    const start = source.indexOf("systemApp.prototype." + name + " = function");
    const end = source.indexOf("\n};", start);
    assert(start >= 0 && end > start, name);
    return source.slice(start, end + 3);
}
const disabled = "stitcher,dab,tv,aharadio,pandora,satradio,xmaudio,xmdata,dvd";
for (const skip of [0, 1]) for (const aa of [0, 1]) for (const cp of [0, 1]) {
    const hidden = disabled + (aa ? "" : ",androidauto");
    const remote = [], displayed = [], box = {log: {info(){}, debug(){}, warn(){}, error(e){throw Error(e);}}};
    const fw = {
        localize: {getRegion(){return "NA";}, REGIONS: {Japan: "JP"}},
        getSharedData(){return "unchanged";},
        _appInstances: {},
        _initApp(id) {
            const app = new box.systemApp();
            app._initEntertainmentDataList();
            app._messageTable = {StatusMenuVisibleAndroidAuto: app._StatusMenuVisibleAndroidAutoMsgHandler.bind(app)};
            app._setRemoteUIButton = function(name, enabled) { remote.push([name, enabled]); };
            // Recreate stale AA visibility; an active wired CarPlay row still
            // owns USB_A's replacement when the applied AA choice is off.
            app._masterEntertainmentDataList.items[10].appData.isVisible = Boolean(cp);
            app._masterEntertainmentDataList.items[11].appData.isVisible = true;
            app._masterEntertainmentDataList.items[12].appData.isVisible = false;
            app._masterApplicationDataList = {items: [{appData: {appName: "xmdata", isVisible: true}}]};
            app._applicationsCtxtWiseAppNames = {VehicleStatusMonitor: []};
            app._indexOfVSMApp = 0;
            app._vehicleConfigurationType = "unchanged";
            app._contextTable = {IntroAnimation: {}};
            app._currentContext = {ctxtId: "Entertainment"};
            app._currentContextTemplate = {list2Ctrl: {setDataList(data){displayed.push(data);}, updateItems(){}}};
            this._appInstances[id] = app;
        }
    };
    box.framework = fw;
    vm.createContext(box);
    vm.runInContext("function systemApp() {}\n" + ["_initEntertainmentDataList", "_buildEntertainmentDataList", "_StatusMenuVisibleMsgHandler", "_StatusMenuVisibleAndroidAutoMsgHandler", "_enableAppListItem"].map(method).join("\n"), box);
    vm.runInContext(hook.replace("/*OPEN_CONNECT_APPLIED*/", skip + "," + JSON.stringify(hidden)), box);
    fw._initApp("system");
    const app = fw._appInstances.system;
    for (const state of ["Visible", "Hidden", "Visible"]) {
        const event = {params: {payload: {appName: "androidauto", state}}};
        app._StatusMenuVisibleAndroidAutoMsgHandler(event);
        app._messageTable.StatusMenuVisibleAndroidAuto(event);
    }
    if (!aa) {
        assert.equal(app._masterEntertainmentDataList.items[11].appData.isVisible, false);
        assert.equal(app._masterEntertainmentDataList.items[12].appData.isVisible, !cp);
        assert.equal(remote.length, 0);
    } else {
        assert(remote.some(([name, enabled]) => name === "androidauto" && enabled));
    }
    assert.equal(app._USB1EntIndex, 12);
    const originalOrder = app._masterEntertainmentDataList.items.map(row => row.appData.appName).join(",");
    for (const name of hidden.split(",")) {
        app._StatusMenuVisibleMsgHandler({params:{payload:{appName:name,state:"Visible"}}});
    }
    const result = app._buildEntertainmentDataList();
    assert.equal(result.itemCount, result.items.length);
    assert(result.items.every(row => !hidden.split(",").includes(row.appData.appName)));
    assert.equal(app._masterApplicationDataList.items[0].appData.isVisible, false);
    assert.equal(app._masterEntertainmentDataList.items.map(row => row.appData.appName).join(","), originalOrder);
    assert(displayed.length > 0);
    assert(displayed.every(menu => menu.items.every(row => !hidden.split(",").includes(row.appData.appName))));
    assert.equal(Boolean(app._contextTable.IntroAnimation.contextInFunction), Boolean(skip));
}
console.log("PASS OEM source lists/late native Visible/displayed menu and USB_A index 12, both disclaimer choices");
