/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Run the actual supplied OEM transition callback, not a reimplementation.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const [frameworkPath, probePath] = process.argv.slice(2);
function fixture(session, brokenLog = false) {
    const timers = [], messages = [], calls = [], images = [];
    const body = {nodeType: 1, parentNode: null};
    const node = {nodeType: 1, parentNode: body,
        getBoundingClientRect() {return {left: 0, top: 0, right: 800, bottom: 480};}};
    const ctx = vm.createContext({
        log: {addSrcFile() {}, info() {}, debug() {},
            jciLogger: {JCILog(message) {if (brokenLog) throw Error("logger"); messages.push(message);}}},
        window: {openConnectStartupSession: session, innerWidth: 800, innerHeight: 480, getComputedStyle(n) {
            return n.style || {display: "block", visibility: "visible", opacity: "1"};
        }},
        Image: function() {images.push(this);}, document: {body}, setTimeout(fn) {timers.push(fn);}
    });
    vm.runInContext(fs.readFileSync(frameworkPath, "utf8"), ctx);
    vm.runInContext(fs.readFileSync(probePath, "utf8").replaceAll("@GENERATION@", "a".repeat(32)), ctx);
    const t = {divElt: node, contextInfo: {uiaId: "system", ctxtId: "HomeScreen", contextSeq: 42}};
    const fw = Object.create(ctx.GuiFramework.prototype);
    Object.assign(fw, {
        _frameworkState: "transition", _FWK_STATE_TMPLT_CHANGE: "transition", _FWK_STATE_IDLE: "idle",
        _browserShown: false, _currTmpltInstance: t, _templateInstances: {},
        _currentAppUiaId: "system", debugMode: false,
        _hideTemplateSurfaces() {calls.push("surfaces");return false;},
        common: {commonControlsUpdateComplete() {calls.push("controls");}},
        debug: {contextChanged() {calls.push("context");}},
        _appInstances: {system: {templateDisplayed(arg) {
            assert.equal(arg, t); calls.push("displayed"); fw._browserShown = true;
        }}},
        multicontroller: {getMode() {return "touch";}},
        _multicontrollerEventHandler() {calls.push("input");}
    });
    if (!brokenLog) assert.deepEqual(messages, ["framework ERROR oc_ready.js[1] OCRENDER|" + "a".repeat(32) + "|probe-loaded"]);
    messages.length = 0;
    function drain() {while (timers.length) timers.shift()();}
    return {ctx, fw, t, node, body, timers, messages, calls, images, drain};
}
{
    const x = fixture();
    x.fw._templateTransitionCompleteCallback();
    assert.deepEqual(x.calls, ["surfaces", "controls", "context", "displayed", "input"]);
    assert.equal(x.messages.length, 0);
    x.timers.shift()();
    assert.equal(x.messages.length, 0);
    x.drain();
    assert.equal(x.messages.length, 1);
    x.fw._frameworkState = "transition";
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.messages.length, 1);
}
for (const mutate of [
    x => x.t.contextInfo.ctxtId = "IntroAnimation",
    x => x.t.contextInfo.ctxtId = "Disclaimer",
    x => x.node.parentNode = null,
    x => x.node.style = {display: "none", visibility: "visible", opacity: "1"},
    x => x.node.style = {display: "block", visibility: "hidden", opacity: "1"},
    x => x.body.style = {display: "block", visibility: "visible", opacity: "0"},
    x => x.node.getBoundingClientRect = () => ({left: 0, top: 0, right: 0, bottom: 0}),
    x => x.fw._appInstances.system.templateDisplayed = () => {}
]) {
    const x = fixture(); mutate(x);
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.messages.length, 0);
}
for (const mutate of [
    x => x.fw._currTmpltInstance = {...x.t},
    x => x.fw._frameworkState = "loadingApp",
    x => x.t.contextInfo.contextSeq++,
    x => x.node.parentNode = null
]) {
    const x = fixture(); x.fw._templateTransitionCompleteCallback();
    mutate(x); x.drain(); assert.equal(x.messages.length, 0);
}
{
    const x = fixture();
    x.fw._appInstances.system.templateDisplayed = () => {throw Error("broken callback");};
    assert.throws(() => x.fw._templateTransitionCompleteCallback(), /broken callback/);
    x.drain(); assert.equal(x.messages.length, 0);
}
{
    const x = fixture(); x.fw._frameworkState = "loadingApp";
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.messages.length, 0);
}
{
    const x = fixture();
    x.fw._appInstances.system.templateDisplayed = () => {
        x.fw._browserShown = true; x.t.contextInfo.contextSeq++;
    };
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.messages.length, 0);
}
{
    const token = "a".repeat(32) + ".01234567-89ab-cdef-0123-456789abcdef";
    const x = fixture({port: 48637, token}, true);
    x.fw._templateTransitionCompleteCallback();
    assert.equal(x.images.length, 0); x.drain();
    assert.equal(x.images.length, 1);
    assert.equal(x.images[0].src, "http://127.0.0.1:48637/" + token);
    x.images[0].onerror(); // HTTP204 is allowed; no DOM or repeated send.
    x.fw._frameworkState = "transition";
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.images.length, 1);
}
for (const session of [
    {port: 48637, token: "old"},
    {port: 0, token: "a".repeat(32) + ".01234567-89ab-cdef-0123-456789abcdef"},
    {port: 48637, token: "b".repeat(32) + ".01234567-89ab-cdef-0123-456789abcdef"}
]) {
    const x = fixture(session); x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.images.length, 0);
}
{
    const x = fixture();
    x.node.style = {display: "block", visibility: "visible", opacity: "0"};
    x.fw._templateTransitionCompleteCallback();
    x.timers.shift()(); assert.equal(x.messages.length, 0);
    x.node.style.opacity = "1";
    x.timers.shift()(); assert.equal(x.messages.length, 0);
    x.timers.shift()(); assert.equal(x.messages.length, 1);
}
{
    const x = fixture();
    x.node.style = {display: "block", visibility: "visible", opacity: "0"};
    x.fw._templateTransitionCompleteCallback(); x.drain();
    assert.equal(x.messages.length, 0); assert.equal(x.timers.length, 0);
    x.node.style.opacity = "1"; x.drain();
    assert.equal(x.messages.length, 0); // No unbounded late adoption.
}
{
    const token = "a".repeat(32) + ".01234567-89ab-cdef-0123-456789abcdef";
    const x = fixture({port: 48637, token});
    x.ctx.Image = function () {throw Error("image blocked");};
    x.fw._templateTransitionCompleteCallback();
    assert.doesNotThrow(x.drain);
    assert.equal(x.messages.length, 2);
    assert.match(x.messages[0], /HomeScreen$/);
    assert.match(x.messages[1], /transport-error.*image blocked/);
}
console.log("PASS actual OEM transition ordering; delayed once-only Home acknowledgement; intro, hidden, detached, changed, stalled and thrown paths refused");
