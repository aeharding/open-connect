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
for (const skip of [0, 1]) {
    const displayed = [], box = {log: {info(){}, debug(){}, error(e){throw Error(e);}}};
    const fw = {
        localize: {getRegion(){return "NA";}, REGIONS: {Japan: "JP"}},
        getSharedData(){return "unchanged";},
        _appInstances: {},
        _initApp(id) {
            const app = new box.systemApp();
            app._initEntertainmentDataList();
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
    vm.runInContext("function systemApp() {}\n" + ["_initEntertainmentDataList", "_buildEntertainmentDataList", "_StatusMenuVisibleMsgHandler"].map(method).join("\n"), box);
    vm.runInContext(hook.replace("/*OPEN_CONNECT_APPLIED*/", skip + "," + JSON.stringify(disabled)), box);
    fw._initApp("system");
    const app = fw._appInstances.system;
    assert.equal(app._USB1EntIndex, 12);
    const originalOrder = app._masterEntertainmentDataList.items.map(row => row.appData.appName).join(",");
    for (const name of disabled.split(",")) {
        app._StatusMenuVisibleMsgHandler({params:{payload:{appName:name,state:"Visible"}}});
    }
    const result = app._buildEntertainmentDataList();
    assert.equal(result.itemCount, result.items.length);
    assert(result.items.every(row => !disabled.split(",").includes(row.appData.appName)));
    assert.equal(app._masterApplicationDataList.items[0].appData.isVisible, false);
    assert.equal(app._masterEntertainmentDataList.items.map(row => row.appData.appName).join(","), originalOrder);
    assert(displayed.length > 0);
    assert(displayed.every(menu => menu.items.every(row => !disabled.split(",").includes(row.appData.appName))));
    assert.equal(Boolean(app._contextTable.IntroAnimation.contextInFunction), Boolean(skip));
}
console.log("PASS OEM source lists/late native Visible/displayed menu and USB_A index 12, both disclaimer choices");
