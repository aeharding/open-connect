const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const token = "a".repeat(32), revision = "b".repeat(32);
function fixture(previous, loadingUSB) {
    const requests = [], intervals = [], timeouts = [], choices = [], messages = [];
    const fw = {_browserShown: true, getAppInstance() { return app; }};
    const app = {}, nodes = {};
    if (loadingUSB) { nodes["oc-usb-loader"] = {ocToken: token}; }
    let store, now = 0;
    const ctx = {
        OpenConnect: previous,
        document: {querySelector() { return null; }, getElementById(id) { return nodes[id]; }},
        framework: fw,
        utility: {loadScript(url, attrs, done) {
            nodes[attrs.id] = {parentNode: {removeChild() { delete nodes[attrs.id]; }}};
            done();
        }},
        setTimeout(fn, ms) { const timer = {fn, ms, at: now + ms, active: true}; timeouts.push(timer); return timer; },
        clearTimeout(timer) { if (timer) { timer.active = false; } },
        setInterval(fn) { intervals.push(fn); return fn; }, clearInterval() {},
        XMLHttpRequest: function () {
            this.open = (method, url) => { this.method = method; this.url = url; };
            this.setRequestHeader = (name, value) => { this.type = value; };
            this.send = body => { this.body = body; requests.push(this); };
            this.abort = () => { this.aborted = true; };
        },
        OpenConnectInstaller: {
            choose(fw, installed, done, version, retained, installedVersion) {
                choices.push({installed, retained, done, version, installedVersion}); return () => {};
            },
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
        return {ok: true, revision, installed: false, retained: false, conflict: false,
            restart: false, pending: false, touch: 0, warning: 0, notice: "-", version: "0.2.0-dev.1", ...extra};
    }
    return {ctx, requests, choices, messages, reply, state,
        tick() { intervals.forEach(fn => fn()); },
        advance(ms) {
            const end = now + ms;
            let timer;
            while ((timer = timeouts.filter(t => t.active && t.at <= end).sort((a, b) => a.at - b.at)[0])) {
                now = timer.at; timer.active = false; timer.fn();
            }
            now = end;
        },
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

// Maintenance must distinguish the installed package from the staged client.
f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.4", installedVersion: "0.3.0-dev.3"}));
f.tick();
assert.equal(f.choices[0].installedVersion, "0.3.0-dev.3");
assert.equal(f.choices[0].version, "0.3.0-dev.4");
assert.equal(f.store.version, "0.3.0-dev.3");
f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({installed: true, installedVersion: "-"}));
f.tick();
assert.equal(f.choices[0].installedVersion, "-");
assert.equal(f.store.version, undefined);

// A complete access-preserving reinstall can exceed the former one-minute cap.
f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({installed: true}));
f.tick(); f.choices[0].done("install");
const slowInstall = f.requests[1];
f.advance(120000);
assert.equal(slowInstall.aborted, undefined);
assert.equal(f.requests.length, 2);
f.reply(slowInstall, f.state({installed: true, restart: true}));
assert.match(f.requests[2].body, /\|restart\|/);
// A missing response still expires once and reconciles without resending.
f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state());
f.tick(); f.choices[0].done("install");
const lostInstall = f.requests[1];
f.advance(185000);
assert.equal(lostInstall.aborted, true);
assert.equal(f.requests.filter(r => r.body.includes("|install|")).length, 1);
assert.equal(f.requests.at(-1).body, token + "|-|status|-|-|-");

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
assert.equal(f.ctx.OpenConnect.reopenUSB(token), true);
f.reply(f.requests[2], f.state({installed: true, notice: "installed"}));
f.tick();
assert.equal(f.choices[1].complete, true); // Cold USB handoff preserves that notice too.
f.ctx.OpenConnect.dispose();
const count = f.requests.length;
f.choices[0].done("cancel"); // Teardown never dismisses a durable completion notice.
assert.equal(f.requests.length, count);

// Loading, cancellation and failed status must leave the installed client alive.
let disposed = 0;
const previous = {dispose() { disposed++; }};
f = fixture(previous, true);
f.ctx.OpenConnect.cancelUSB(token); // Script evaluated, loader onload has not run.
assert.equal(f.ctx.OpenConnect, previous);
assert.equal(disposed, 0);
f = fixture(previous);
assert.equal(disposed, 0);
f.ctx.OpenConnect.start(token, true);
f.ctx.OpenConnect.cancelUSB(token);
assert.equal(f.ctx.OpenConnect, previous);
f.reply(f.requests[0], f.state({installed: true}));
assert.equal(disposed, 0); // Late response cannot take over after cancellation.
f = fixture(previous);
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], null);
assert.equal(f.ctx.OpenConnect, previous);
assert.equal(disposed, 0);
f = fixture(previous);
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true}));
assert.equal(disposed, 1);
f.tick();
const installedClient = f.ctx.OpenConnect;
assert.equal(installedClient.reopenUSB(token), true);
f.reply(f.requests[1], f.state({installed: true}));
f.ctx.OpenConnect.cancelUSB(token);
assert.equal(f.ctx.OpenConnect, installedClient);
f.store.write("touch", 0, 1, () => {});
assert.equal(f.requests[2].body, token + "|" + revision + "|set|touch|0|1");

f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true, notice: "installed"}));
f.tick();
assert.equal(f.choices[0].complete, true);
f.ctx.OpenConnect.reopenUSB(token);
f.tick(); // Old cached notice cannot decide this insertion before fresh status.
f.reply(f.requests[1], f.state({installed: true, restart: true, notice: "restart"}));
f.tick();
assert.equal(f.choices[1].installed, true);
f.ctx.OpenConnect.reopenUSB(token);
f.ctx.OpenConnect.cancelUSB(token);
f.reply(f.requests[2], f.state({installed: true}));
f.tick();
assert.equal(f.choices.length, 2); // Cancellation also covers a pending status read.
f.ctx.OpenConnect.reopenUSB(token);
f.reply(f.requests[3], f.state({pending: true}));
assert.equal(f.requests[4].body, token + "|" + revision + "|recover|-|-|-");
console.log("Installer POST contract, recovery and uncertain-acknowledgement behavior passed");

f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({retained: true}));
f.tick();
assert.equal(f.choices[0].retained, true);
f.choices[0].done("uninstall");
assert.equal(f.requests[1].body, token + "|" + revision + "|uninstall|-|-|-");
f.reply(f.requests[1], f.state({revision: "-", restart: true}));
assert.equal(f.requests[2].body, token + "|-|restart|-|-|-");
