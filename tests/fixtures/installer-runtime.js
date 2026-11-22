const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const token = "a".repeat(32), revision = "b".repeat(32);
function fixture(previous, loadingUSB, boot) {
    const requests = [], intervals = [], timeouts = [], choices = [], messages = [], loads = [];
    const fw = {_browserShown: true, getAppInstance() { return app; }};
    const app = {}, nodes = {};
    if (loadingUSB) { nodes["oc-usb-loader"] = {ocToken: token,
        src: "file:///tmp/open-connect/sessions/session-test/loader.js"}; }
    let store, now = 0;
    const ctx = {
        OpenConnect: previous,
        document: {querySelector(selector) {
            const match = selector.match(/open-connect-(token|version|notice)/);
            return boot && match ? {getAttribute() { return match[1] === "token" ? token : boot[match[1]]; }} : null;
        }, getElementById(id) { return nodes[id]; }},
        framework: fw,
        utility: {loadScript(url, attrs, done) {
            loads.push(url);
            nodes[attrs.id] = {parentNode: {removeChild() { delete nodes[attrs.id]; }}};
            done();
        }},
        setTimeout(fn, ms) { const timer = {fn, ms, at: now + ms, active: true}; timeouts.push(timer); return timer; },
        clearTimeout(timer) { if (timer) { timer.active = false; } },
        setInterval(fn) { intervals.push(fn); return fn; }, clearInterval() {},
        Date: {now() { return now; }},
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
    return {ctx, requests, choices, messages, loads, reply, state,
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
// Cancelling a newer maintenance client does not expose services unsupported by
// the installed selector. Existing choices still use the same request contract.
f = fixture();
f.ctx.OpenConnect.start(token, true);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.6",
    installedVersion: "0.3.0-dev.5"}));
f.tick(); f.choices[0].done("cancel");
assert.equal(f.store.read().pandora, undefined);
f.store.write("touch", 0, 1, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|touch|0|1");
f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.6",
    installedVersion: "0.3.0-dev.6", pandora: 0}));
f.tick();
assert.equal(f.store.read().pandora, 0);
assert.equal(f.store.read().base, undefined);
f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.7",
    installedVersion: "0.3.0-dev.7", pandora: 1, base: 0}));
f.tick();
assert.equal(f.store.read().base, 0);
f.store.write("base", 0, 1, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|base|0|1");
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

// Wireless uses the same request shape and keeps the applied boot selection
// separate from the saved preference while a restart is pending.
f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true, wireless: 1, wirelessCurrent: 1}));
f.tick();
assert.equal(f.store.read().wireless, 1);
assert.equal(f.store.read().wirelessCurrent, 1);
f.store.write("wireless", 1, 0, () => {});
assert.equal(f.requests[1].body, token + "|" + revision + "|set|wireless|1|0");
f.reply(f.requests[1], f.state({installed: true, wireless: 0, wirelessCurrent: 1, restart: true}));
assert.equal(f.store.read().wireless, 0);

assert.equal(f.store.read().wirelessCurrent, 1);
assert.equal(f.store.read().restart, true);

f = fixture();
f.ctx.OpenConnect.start(token, false);
f.reply(f.requests[0], f.state({installed: true, wireless: 0, wirelessCurrent: 0, wirelessFactory: true}));
f.tick();
assert.equal(f.store.read().wirelessFactory, true);
assert.equal(f.store.read().wireless, 0);

// A normal installed boot attaches its RAM-only menu without backend work.
f = fixture(null, false, {version: "0.3.0-dev.9", notice: "-"});
f.tick();
assert.equal(f.requests.length, 0);
assert.deepEqual(f.loads, ["file:///tmp/open-connect/feature/dialog.js",
    "file:///tmp/open-connect/feature/settings.js"]);
assert.equal(f.store.version, "0.3.0-dev.9");
assert.equal(f.store.read(), null);
let refreshed;
f.store.refresh(ok => { refreshed = ok; });
assert.equal(f.requests[0].body, token + "|-|status|-|-|-");
f.reply(f.requests[0], null); // SM's listener has not bound yet.
assert.equal(refreshed, undefined);
f.retry();
f.reply(f.requests[1], f.state({installed: true, revision: "d".repeat(32)}));
assert.equal(refreshed, true);
f.store.write("touch", 0, 1, () => {});
assert.equal(f.requests[2].body, token + "|" + "d".repeat(32) + "|set|touch|0|1");
// Re-enter the existing preference session while its save is still pending.
let reopen;
f.store.refresh(ok => { reopen = ok; });
assert.equal(reopen, true);
assert.equal(f.requests.length, 3);

// Completion is local boot data; its action obtains a fresh revision first.
f = fixture(null, false, {version: "0.3.0-dev.9", notice: "installed"});
f.tick();
assert.equal(f.requests.length, 0);
assert.equal(f.choices[0].complete, true);
f.choices[0].done("done");
assert.equal(f.requests.length, 1);
f.reply(f.requests[0], f.state({installed: true, revision: "e".repeat(32)}));
assert.equal(f.requests[1].body, token + "|" + "e".repeat(32) + "|dismiss|-|-|-");

// Mazda navigation can cancel completion without selecting either action.
f = fixture(null, false, {version: "0.3.0-dev.9", notice: "installed"});
f.tick();
f.choices[0].done("cancel");
assert.equal(f.requests.length, 0);
assert.equal(f.messages.length, 0);

// Full hardware verification can exceed four seconds. One shared twelve-second
// read budget permits a slow answer, including after a briefly unavailable worker.
f = fixture(null, false, {version: "0.3.0-dev.9", notice: "-"});
f.tick();
refreshed = undefined;
f.store.refresh(ok => { refreshed = ok; });
f.advance(5000);
assert.equal(f.requests[0].aborted, undefined);
f.reply(f.requests[0], f.state({installed: true}));
assert.equal(refreshed, true);

f = fixture(null, false, {version: "0.3.0-dev.9", notice: "-"});
f.tick();
refreshed = undefined;
f.store.refresh(ok => { refreshed = ok; });
f.advance(3000);
f.reply(f.requests[0], null);
f.advance(500); // Retry gets only the remainder, not another complete allowance.
assert.equal(f.requests.length, 2);
f.advance(8500);
assert.equal(f.requests[1].aborted, true);
assert.equal(refreshed, null);
f.advance(1000);
assert.equal(f.requests.length, 2);
assert.ok(f.requests.every(request => request.body.includes("|status|")));

// A worker deferred until Home can refuse connections for over four seconds.
// Fast failures must use the shared boot budget, rather than an earlier retry cap.
f = fixture(null, false, {version: "0.3.0-dev.10", notice: "-"});
f.tick();
refreshed = undefined;
f.store.refresh(ok => { refreshed = ok; });
for (let attempt = 0; attempt < 10; attempt++) {
    assert.equal(f.requests.length, attempt + 1);
    f.reply(f.requests[attempt], null);
    f.advance(500);
    assert.equal(refreshed, undefined);
}
f.reply(f.requests[10], f.state({installed: true}));
assert.equal(refreshed, true);

// Repeated immediate failures still stop at twelve seconds without a new XHR.
f = fixture(null, false, {version: "0.3.0-dev.10", notice: "-"});
f.tick();
refreshed = undefined;
f.store.refresh(ok => { refreshed = ok; });
for (let attempt = 0; attempt < 24; attempt++) {
    assert.equal(f.requests.length, attempt + 1);
    f.reply(f.requests[attempt], null);
    f.advance(500);
}
assert.equal(refreshed, null);
f.advance(1000);
assert.equal(f.requests.length, 24);

// USB client dependencies stay within their own verified session.
f = fixture(null, true);
f.ctx.OpenConnect.start(token, true);
assert.deepEqual(f.loads, ["file:///tmp/open-connect/sessions/session-test/dialog.js",
    "file:///tmp/open-connect/sessions/session-test/settings.js"]);

// Catalog data survives transport and supplies the expected bit to writes.
f = fixture(); f.ctx.OpenConnect.start(token, false);
const serviceRows = [{id: "android-auto", label: "Android Auto", saved: 1, current: null,
    enable: "Load after restart.", disable: "Stop after restart."}];
f.reply(f.requests[0], f.state({installed: true, services: serviceRows})); f.tick();
assert.equal(f.store.read().services[0].current, null);
f.store.write("android-auto", 1, 0, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|android-auto|1|0");
