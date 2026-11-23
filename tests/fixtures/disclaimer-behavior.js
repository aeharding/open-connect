// Exercise the real private OEM context and completed-frame dispatchers.
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const [candidate, base, frameworkFile, hookFile] = process.argv.slice(2);
const source = fs.readFileSync(candidate, 'utf8');
const start = source.indexOf('"IntroAnimation" : {');
const stop = source.indexOf('"QuickStartLoop" : {', start);
const literal = '({' + source.slice(start, stop) + '})';
const frameworkSource = fs.readFileSync(frameworkFile, 'utf8');
const callbackStart = frameworkSource.indexOf('GuiFramework.prototype._templateTransitionCompleteCallback = function()');
const callbackEnd = frameworkSource.indexOf('GuiFramework.prototype.changeLanguage = function', callbackStart);
assert(callbackStart >= 0 && callbackEnd > callbackStart);

function fixture(withIntro = false) {
    const events = [], order = [], timers = [];
    const box = {log: {addSrcFile(){}, info(){}, warn(){}, debug(){},
        error(e){throw Error(e)}, writeError(e){throw e}}, setTimeout(fn){timers.push(fn)},
        utility: {removeHTMLElement(id){order.push('removed:' + id)}}};
    vm.createContext(box);
    vm.runInContext(fs.readFileSync(base, 'utf8'), box);
    vm.runInContext('function GuiFramework(){}\n' + frameworkSource.slice(callbackStart, callbackEnd), box);
    const fw = Object.create(box.GuiFramework.prototype);
    Object.assign(fw, {
        _FWK_STATE_TMPLT_CHANGE: 'change', _FWK_STATE_IDLE: 'idle', _frameworkState: 'idle',
        _browserShown: false, _appInstances: {}, _templateInstances: {}, debugMode: false,
        common: {commonControlsUpdateComplete(){order.push('common')}},
        debug: {contextChanged(){order.push('debug')}}, multicontroller: {getMode(){return 'focus'}},
        _multicontrollerEventHandler(){order.push('controller')},
        _hideTemplateSurfaces(){order.push('hidden'); return true},
        showOperaSurface(){order.push('shown')},
        sendEventToMmui(...args){events.push(args); order.push(args[1])}
    });
    box.framework = fw;
    function app(id) {
        const a = {};
        new box.BaseApp().init(a, id);
        box.app = a;
        a._masterEntertainmentDataList = {items: []};
        a._masterApplicationDataList = {items: []};
        a._contextTable = id === 'system' ? vm.runInContext('(function(){return ' + literal + '}).call(app)', box) : {};
        for (const name of ['HomeScreen', 'Disclaimer', 'NoteOnUseData', 'QuickStartLoop']) {
            a._contextTable[name] = {displayedFunction(){order.push('displayed:' + id + '.' + name)}};
        }
        fw._appInstances[id] = a;
        return a;
    }
    fw._initApp = app;
    vm.runInContext(fs.readFileSync(hookFile, 'utf8').replace('/*OPEN_CONNECT_APPLIED*/', '1,""'), box);
    const system = fw._initApp('system'), original = fw._templateTransitionCompleteCallback;
    system.handleContext({ctxtId: 'IntroAnimation'});
    const intro = {divElt:{id:'intro'}, contextInfo:{uiaId:'system',ctxtId:'IntroAnimation'},
        properties:{}, cleanUp(){order.push('intro-cleaned')}};
    if (withIntro) system._currentContextTemplate = intro;
    function frame(id, context, changing = true) {
        const a = fw._appInstances[id] || app(id);
        a.handleContext({ctxtId:context});
        const incoming = {divElt:{id:id + context},contextInfo:{uiaId:id,ctxtId:context},properties:{}};
        a._currentContextTemplate = incoming;
        fw._currentAppUiaId = id; fw._currTmpltInstance = incoming;
        fw._templateInstances = {[incoming.divElt.id]:{uiaId:id,instance:incoming}};
        if (withIntro && id === 'system' && a._outgoingContextTemplate === intro) {
            fw._templateInstances.intro = {uiaId:'system',instance:intro};
        }
        fw._frameworkState = changing ? 'change' : 'idle';
        fw._templateTransitionCompleteCallback();
    }
    function cleanup() { return events.filter(e => e[1] === 'DisposeIntroVideo' || e[1] === 'NotifyDisclaimerEnd'); }
    return {fw, system, original, frame, cleanup, events, order, timers};
}

for (const withIntro of [false, true]) {
    const t = fixture(withIntro);
    assert.equal(t.cleanup().length, 0); // No disposal at context entry or before a completed frame.
    t.frame('system', 'HomeScreen', false); // An ignored completion is not a displayed screen.
    assert.equal(t.cleanup().length, 0);
    const bound = t.fw._templateTransitionCompleteCallback.bind(t.fw);
    t.frame('system', 'HomeScreen');
    assert.deepEqual(t.cleanup(), [['system','DisposeIntroVideo'],['system','NotifyDisclaimerEnd']]);
    assert(t.order.indexOf('DisposeIntroVideo') > t.order.indexOf('displayed:system.HomeScreen'));
    assert(t.order.indexOf('DisposeIntroVideo') > t.order.indexOf('hidden'));
    assert.equal(t.fw._templateTransitionCompleteCallback, t.original);
    assert(!Object.hasOwn(t.fw, '_templateTransitionCompleteCallback'));
    assert(!Object.hasOwn(t.system, '_openConnectIntroCleanup'));
    // A previously bound callback still delegates, but cannot dispose twice.
    t.fw._frameworkState = 'change'; bound();
    assert.equal(t.cleanup().length, 2);
    assert.equal(t.timers.length, 1); // The OEM first-frame initialization still runs once.
    t.timers[0]();
    assert(t.events.some(e => e[1] === 'InitializeGuiComplete'));
}
{
    // Regression: focus moves to CarPlay without any outgoing Intro template.
    const t = fixture();
    t.system.handleContext({ctxtId:'HomeScreen'});
    assert.equal(t.system._outgoingContextTemplate, null);
    t.frame('carplay', 'NoteOnUseData');
    assert.equal(t.cleanup().length, 2);
    assert(t.order.indexOf('DisposeIntroVideo') > t.order.indexOf('displayed:carplay.NoteOnUseData'));
}
{
    const t = fixture();
    t.frame('system', 'IntroAnimation');
    t.frame('system', 'QuickStartLoop');
    assert.equal(t.cleanup().length, 0);
    t.frame('system', 'HomeScreen');
    assert.equal(t.cleanup().length, 2);
}
{
    const t = fixture(true);
    t.frame('system', 'Disclaimer'); // Stock Disclaimer retains ownership of its cleanup.
    t.frame('system', 'HomeScreen');
    assert.equal(t.cleanup().length, 0);
    assert(t.order.includes('displayed:system.Disclaimer'));
    assert.equal(t.fw._templateTransitionCompleteCallback, t.original);
}
{
    const t = fixture();
    const inner = t.fw._templateTransitionCompleteCallback;
    const external = function(){ return inner.apply(this, arguments); };
    t.fw._templateTransitionCompleteCallback = external;
    t.frame('system', 'HomeScreen');
    assert.equal(t.fw._templateTransitionCompleteCallback, external); // Preserve a later owner.
    assert.equal(t.cleanup().length, 2);
}
console.log('PASS actual OEM incoming-frame lifecycle: missing Intro template, CarPlay focus, no early/duplicate cleanup, stock Disclaimer ownership, delegation and restoration');
