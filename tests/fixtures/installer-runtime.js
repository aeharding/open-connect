const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const token = "a".repeat(32), revision = "b".repeat(32);
function fixture() {
    const requests = [], intervals = [], timeouts = [], choices = [], messages = [];
    const fw = {_browserShown: true, getAppInstance() { return app; }};
    const app = {}, nodes = {};
    let store;
    const ctx = {
        document: {querySelector() { return null; }, getElementById(id) { return nodes[id]; }},
        framework: fw,
        utility: {loadScript(url, attrs, done) {
            nodes[attrs.id] = {parentNode: {removeChild() { delete nodes[attrs.id]; }}};
            done();
        }},
        setTimeout(fn, ms) { timeouts.push({fn, ms}); return fn; }, clearTimeout() {},
        setInterval(fn) { intervals.push(fn); return fn; }, clearInterval() {},
        XMLHttpRequest: function () {
            this.open = (method, url) => { this.method = method; this.url = url; };
            this.setRequestHeader = (name, value) => { this.type = value; };
            this.send = body => { this.body = body; requests.push(this); };
            this.abort = () => {};
        },
        OpenConnectInstaller: {
            choose(fw, installed, done) { choices.push({installed, done}); return () => {}; },
            message(fw, title, text, buttons, done) { messages.push({title, text, buttons, done}); return () => {}; },
            complete(fw, version, done) { choices.push({complete: true, done}); return () => {}; }
        },
        OpenConnectSettings: {attach(fw, app, value) { store = value; return () => {}; }}
    };
    ctx.window = ctx;
    vm.runInNewContext(source, ctx);
    function reply(request, value) {
        request.status = value ? 200 : 0;
        request.responseText = value ? JSON.stringify(value) : "";
        request.readyState = 4;
        request.onreadystatechange();
    }
    function state(extra = {}) {
        return {ok: true, revision, installed: false, undo: false, conflict: false,
            restart: false, pending: false, touch: 0, warning: 0, notice: "-", version: "0.2.0-dev.1", ...extra};
    }
    return {ctx, requests, choices, messages, reply, state,
        tick() { intervals.forEach(fn => fn()); },
        retry() { const index = timeouts.findIndex(t => t.ms === 500); assert.ok(index >= 0); timeouts.splice(index, 1)[0].fn(); },
        get store() { return store; }};
}
let f = fixture();
f.ctx.OpenConnect.start(token, true);
assert.equal(f.requests[0].body, token + "|-|status|-|-|-");
f.reply(f.requests[0], f.state());
f.tick();
assert.equal(f.choices.length, 1);
f.choices[0].done("install");
const install = f.requests[1];
assert.equal(install.method, "POST");
assert.equal(install.url, "http://127.0.0.1:35555/control");
assert.equal(install.type, "text/plain");
assert.equal(install.body, token + "|" + revision + "|install|-|-|-");
f.ctx.OpenConnect.cancelUSB(token); // Removing USB cannot abort an in-flight mutation.
f.reply(install, f.state({installed: true, restart: true, revision: "c".repeat(32)}));
assert.equal(f.requests[2].body, token + "|" + "c".repeat(32) + "|restart|-|-|-");
f.reply(install, f.state({installed: true, restart: true})); // Duplicate readyState event.
assert.equal(f.requests.length, 3);

f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true}));
f.tick();
let saved;
f.store.write("touch", 0, 1, value => { saved = value; });
assert.equal(f.requests[1].body, token + "|" + revision + "|set|touch|0|1");
f.reply(f.requests[1], null);
assert.equal(f.requests[2].body, token + "|-|status|-|-|-");
f.reply(f.requests[2], f.state({installed: true, touch: 1}));
assert.equal(saved.touch, 1);
assert.equal(f.requests.filter(r => r.body.includes("|set|")).length, 1);

f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({pending: true}));
assert.equal(f.requests[1].body, token + "|" + revision + "|recover|-|-|-");
f.tick();
assert.equal(f.choices.length, 0); // Internal recovery, no misleading fresh-install choice.
f.reply(f.requests[1], {ok: false, error: "state_changed"});
f.tick();
assert.ok(f.messages.some(m => /Nothing was overwritten/.test(m.text)));
assert.equal(f.requests.filter(r => r.body.includes("|recover|")).length, 1);

f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], null);
f.tick();
assert.equal(f.messages.length, 1); // Connection errors remain visible without cached state.

f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], {ok: false, error: "busy"});
assert.equal(f.messages.length, 0);
f.retry();
assert.equal(f.requests[1].body, token + "|-|status|-|-|-");
f.reply(f.requests[1], f.state({installed: true, notice: "installed"}));
f.tick();
assert.equal(f.choices[0].complete, true); // Leaving USB inserted preserves completion.
f.ctx.OpenConnect.dispose();
const count = f.requests.length;
f.choices[0].done("cancel"); // Teardown never dismisses a durable completion notice.
assert.equal(f.requests.length, count);
console.log("Installer POST contract, recovery and uncertain-acknowledgement behavior passed");
