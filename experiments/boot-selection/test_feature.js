/* Test actual supplied OEM dispatcher and script loader; no OEM code included. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const [utility, framework, index, destination] = process.argv.slice(2);
const appended = [];
const context = vm.createContext({
    log: {debug() {}, addSrcFile() {}},
    window: {},
    document: {
        createElement(tag) { return {tag}; },
        querySelector(selector) {
            assert.equal(selector, "head");
            return {appendChild(node) { appended.push(node); }};
        }
    }
});
vm.runInContext(fs.readFileSync(utility, "utf8"), context);
vm.runInContext(fs.readFileSync(framework, "utf8"), context);
const actual = context.GuiFramework.prototype._addAppFiles;
const untouched = new context.Utility();
let constructed = 0, initialized = 0;
context.BaseApp = function() {
    constructed++;
    context.utility.loadScript("apps/system/js/systemApp.js");
    assert.equal(appended.at(-1).src, destination);
};
context.GuiFramework = function() {
    constructed++;
    this.init = function() {
        initialized++;
        const state = {_rtlLanguage: false};
        actual.call(state, "system", {originalMessage: true});
        assert.equal(appended.at(-1).src, destination);
        assert.equal(state._filesToLoad.systemApp, false);
        actual.call(state, "fmradio");
        assert.equal(appended.at(-1).src, "apps/fmradio/js/fmradioApp.js");
        assert.ok(appended.some(x => x.href === "apps/system/css/systemApp.css"));
    };
};
const html = fs.readFileSync(index, "utf8");
const body = html.match(/<body>\s*<script type="text\/javascript">([\s\S]*?)<\/script>/);
assert.ok(body);
vm.runInContext(body[1], context);
assert.equal(constructed, 2);
assert.equal(initialized, 1);
let called = 0;
context.utility.loadScript("apps/system/js/systemApp.js", {lang: "en"}, function(args) {
    called++;
    assert.equal(args[0], "loaded");
});
assert.equal(appended.at(-1).lang, "en");
appended.at(-1).onload("loaded");
assert.equal(called, 1);
untouched.loadScript("apps/system/js/systemApp.js");
assert.equal(appended.at(-1).src, "apps/system/js/systemApp.js");
console.log("PASS actual OEM loading order, selected system JS, other apps/CSS, callback and instance isolation");
