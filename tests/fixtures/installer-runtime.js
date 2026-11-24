const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const token = "a".repeat(32), revision = "b".repeat(32);
function fixture(previous, loadingUSB, boot, port) {
    const requests = [], intervals = [], timeouts = [], choices = [], messages = [], loads = [], progress = [];
    let eligible = true;
    const fw = {_browserShown: true, getAppInstance() { return app; }};
    const app = {}, nodes = {}, scripts = [], scriptEvents = [];
    const head = {appendChild(node) {
        node.parentNode = head; scripts.push(node); loads.push(node.src);
        scriptEvents.push(() => {
            if (node.src.endsWith("runtime.js")) vm.runInNewContext(source, ctx);
            node.onload();
        });
    }, removeChild(node) {
        const index=scripts.indexOf(node); assert.notEqual(index,-1);
        scripts.splice(index,1);node.parentNode=null;
    }};
    if (loadingUSB) { nodes["oc-usb-loader"] = {ocToken: token,
        src: "file:///tmp/open-connect/sessions/session-test/loader.js", ocPort: port}; }
    let store, now = 0;
    const ctx = {
        OpenConnect: previous,
        document: {querySelector(selector) {
            if (selector === "head") return head;
            const match = selector.match(/open-connect-(token|version|notice)/);
            return boot && match ? {getAttribute() { return match[1] === "token" ? (boot.token || token) : boot[match[1]]; }} : null;
        }, getElementById(id) { return nodes[id] || scripts.find(n=>n.id===id); },
            createElement(tag) { assert.equal(tag,"script"); return {}; }},
        framework: fw,
        utility: {loadScript(url, attrs, done) {
            const node = ctx.document.createElement("script");
            Object.assign(node,attrs,{src:url,type:"text/javascript",onload:done});
            head.appendChild(node);
        }},
        setTimeout(fn, ms) { const timer = {fn, ms, at: now + ms, active: true}; timeouts.push(timer); return timer; },
        clearTimeout(timer) { if (timer) { timer.active = false; } },
        setInterval(fn) { intervals.push(fn); return fn; }, clearInterval() {},
        Date: {now() { return now; }},
        XMLHttpRequest: function () {
            this.open = (method, url) => { this.method = method; this.url = url; };
            this.setRequestHeader = (name, value) => { this.type = value; };
            this.send = body => {
                const op=body.split("|")[2];
                if(op==="install" || op==="uninstall") assert.ok(progress.some(v=>!v.closed), "shield acquired before POST");
                this.body = body; requests.push(this);
            };
            this.abort = () => { this.aborted = true; };
        },
        OpenConnectInstaller: {
            choose(fw, installed, done, version, retained, installedVersion) {
                choices.push({installed, retained, done, version, installedVersion}); return () => {};
            },
            message(fw, title, text, buttons, done) { messages.push({title, text, buttons, done}); return () => {}; },
            complete(fw, version, done) { if (!eligible) return false;
                choices.push({complete: true, version, done}); return () => {}; },
            progress(fw, action, warning, suspended) {
                if (!eligible) return false;
                const v = {action, warning, suspended, closed: false,
                    close() { this.closed = true; suspended(); },
                    update(a,w) { this.action=a; this.warning=w; if(!eligible) { this.close(); return false; } return true; }};
                progress.push(v); return v;
            }
        },
        OpenConnectSettings: {attach(fw, app, value) { store = value; return () => {}; }}
    };
    function flushScripts() { while(scriptEvents.length) scriptEvents.shift()(); }
    ctx.window = ctx;
    vm.runInNewContext(fs.readFileSync(require("node:path").join(require("node:path").dirname(process.argv[2]), "settings.js"), "utf8"), ctx);
    ctx.OpenConnectSettings.attach = (fw, app, value) => { store=value; return () => {}; };
    vm.runInNewContext(source, ctx);
    flushScripts();
    function reply(request, value) {
        request.status = value === null || value === undefined ? 0 : 200;
        request.responseText = value === null || value === undefined ? "" : JSON.stringify(value);
        request.readyState = 4;
        request.onreadystatechange();
    }
    function state(extra = {}) {
        return {ok: true, revision, installed: false, retained: false, conflict: false,
            restart: false, pending: false, touch: 0, warning: 0, notice: "-", version: "0.2.0-dev.1", ...extra};
    }
    return {ctx, nodes, scripts, requests, choices, messages, loads, reply, state, progress,
        start(value, usb) { ctx.OpenConnect.start(value,usb); flushScripts(); },
        eligible(value) { eligible=value; },
        openSettings() {
            const pages=[], parent={removeChild(n){n.parentNode=null;}};
            const host={divElt:{style:{display:""},parentNode:parent},list2Ctrl:{},handleControllerEvent(){}};
            Object.assign(fw,{getCurrentApp:()=>"syssettings",getCurrCtxtId:()=>"SystemTab",_frameworkState:1,_FWK_STATE_IDLE:1,
                _currTmpltInstance:host,common:{getCommonTransitionData(){}},multicontroller:{getMode:()=>"controllerActive"},
                sendEventToMmui(){},instantiateTemplate(app,parent,type,props){
                    const ctrl=props.List2Ctrl;ctrl.updateItems=()=>{};
                    const page={list2Ctrl:ctrl,divElt:{parentNode:parent},cleanUp(){},handleControllerEvent(){}};
                    pages.push(page);return page;
                }});
            const close=ctx.OpenConnectSettings.open(fw,store);
            assert.equal(typeof close,"function");
            function pick(index) {const c=pages.at(-1).list2Ctrl;c.selectCallback(c,c.dataList.items[index].appData);}
            pick(0); // Touch radio page.
            return {pick,close,pages};
        },
        insert(legacy = false) {
            nodes["oc-usb-loader"] = {ocToken: token, src: "file:///tmp/oc/loader.js",
                parentNode: {removeChild(n) { if(nodes["oc-usb-loader"] === n) delete nodes["oc-usb-loader"]; }}};
            const path=require("node:path");
            const file=legacy ? path.join(__dirname,"legacy-usb-loader.js") : path.join(path.dirname(process.argv[2]),"loader.js");
            vm.runInNewContext(fs.readFileSync(file,"utf8"),ctx);
            flushScripts();
        },
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
f.start(token, true);
assert.equal(f.requests[0].body, token + "|-|status|-|-|-");
f.reply(f.requests[0], f.state());
f.tick();
assert.equal(f.choices.length, 1);
f.choices[0].done("install");
const install = f.requests[1];
assert.equal(install.method, "POST");
assert.equal(install.url, "http://127.0.0.1:15555/control");
assert.equal(install.type, "text/plain");
assert.equal(install.body, token + "|" + revision + "|install|-|-|-");
f.ctx.OpenConnect.cancelUSB(token); // Removing USB cannot abort an in-flight mutation.
f.reply(install, f.state({installed: true, restart: true, revision: "c".repeat(32)}));
assert.equal(f.requests[2].body, token + "|" + "c".repeat(32) + "|restart|-|-|-");
f.reply(install, f.state({installed: true, restart: true})); // Duplicate readyState event.
assert.equal(f.requests.length, 3);

// Maintenance must distinguish the installed package from the staged client.
f = fixture();
f.start(token, true);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.4", installedVersion: "0.3.0-dev.3"}));
f.tick();
assert.equal(f.choices[0].installedVersion, "0.3.0-dev.3");
assert.equal(f.choices[0].version, "0.3.0-dev.4");
assert.equal(f.store.version, "0.3.0-dev.3");
// Cancelling a newer maintenance client does not expose services unsupported by
// the installed selector. Existing choices still use the same request contract.
f = fixture();
f.start(token, true);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.6",
    installedVersion: "0.3.0-dev.5"}));
f.tick(); f.choices[0].done("cancel");
assert.equal(f.store.read().pandora, undefined);
f.store.write("touch", 0, 1, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|touch|0|1");
f = fixture();
f.start(token, false);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.6",
    installedVersion: "0.3.0-dev.6", pandora: 0}));
f.tick();
assert.equal(f.store.read().pandora, 0);
assert.equal(f.store.read().base, undefined);
f = fixture();
f.start(token, false);
f.reply(f.requests[0], f.state({installed: true, version: "0.3.0-dev.7",
    installedVersion: "0.3.0-dev.7", pandora: 1, base: 0}));
f.tick();
assert.equal(f.store.read().base, 0);
f.store.write("base", 0, 1, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|base|0|1");
f = fixture();
f.start(token, true);
f.reply(f.requests[0], f.state({installed: true, installedVersion: "-"}));
f.tick();
assert.equal(f.choices[0].installedVersion, "-");
assert.equal(f.store.version, undefined);

// A complete access-preserving reinstall can exceed the former one-minute cap.
f = fixture();
f.start(token, true);
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
f.start(token, true);
f.reply(f.requests[0], f.state());
f.tick(); f.choices[0].done("install");
const lostInstall = f.requests[1];
f.advance(185000);
assert.equal(lostInstall.aborted, true);
assert.equal(f.requests.filter(r => r.body.includes("|install|")).length, 1);
assert.equal(f.requests.at(-1).body, token + "|-|status|-|-|-");

f = fixture();
f.start(token, false);
f.reply(f.requests[0], f.state({installed: true}));
f.tick();
let saved;
f.store.write("touch", 0, 1, value => { saved = value; });
assert.equal(f.requests[1].body, token + "|" + revision + "|set|touch|0|1");
f.reply(f.requests[1], null);
assert.equal(f.requests[2].body, token + "|-|status|-|-|-");
f.reply(f.requests[2], f.state({installed: true, touch: 1, revision: "c".repeat(32)}));
assert.equal(saved.touch, 1);
assert.equal(f.requests.filter(r => r.body.includes("|set|")).length, 1);

f = fixture();
f.start(token, true);
f.reply(f.requests[0], f.state({pending: true})); f.tick();
assert.equal(f.requests[1].body, token + "|" + revision + "|recover|-|-|-");
f.tick();
assert.equal(f.choices.length, 0); // Internal recovery, no misleading fresh-install choice.
f.reply(f.requests[1], {ok: false, error: "state_changed"});
f.reply(f.requests[2], f.state()); f.tick();
assert.ok(f.messages.some(m => /Check your settings/.test(m.text)));
assert.equal(f.requests.filter(r => r.body.includes("|recover|")).length, 1);

f = fixture();
f.start(token, true);
f.reply(f.requests[0], null);
f.tick();
assert.equal(f.messages.length, 1); // Connection errors remain visible without cached state.

f = fixture();
f.start(token, true);
f.reply(f.requests[0], {ok: false, error: "busy"});
assert.equal(f.messages.length, 0);
f.retry();
assert.equal(f.requests[1].body, token + "|-|status|-|-|-");
f.reply(f.requests[1], f.state({installed: true, notice: "installed"}));
f.tick();
assert.equal(f.choices[0].complete, undefined); // Missing authenticated page proof: maintenance only.
f.ctx.OpenConnect.dispose();

// Loading, cancellation and failed status must leave the installed client alive.
let disposed = 0;
const previous = {dispose() { disposed++; }};
f = fixture(previous, true);
f.ctx.OpenConnect.cancelUSB(token); // Script evaluated, loader onload has not run.
assert.equal(f.ctx.OpenConnect, previous);
assert.equal(disposed, 0);
f = fixture(previous);
assert.equal(disposed, 0);
f.start(token, true);
f.ctx.OpenConnect.cancelUSB(token);
assert.equal(f.ctx.OpenConnect, previous);
f.reply(f.requests[0], f.state({installed: true}));
assert.equal(disposed, 0); // Late response cannot take over after cancellation.
f = fixture(previous);
f.start(token, true);
f.reply(f.requests[0], null);
assert.equal(f.ctx.OpenConnect, previous);
assert.equal(disposed, 0);
f = fixture(previous);
f.start(token, false);
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

// Superseded status responses must not overwrite current state before the intent fence.
f = fixture(); f.start(token, false);
f.reply(f.requests[0], f.state({installed: true})); f.tick();
f.ctx.OpenConnect.reopenUSB(token);
f.ctx.OpenConnect.cancelUSB(token);
f.reply(f.requests[1], f.state({installed: true, revision: "d".repeat(32), installedVersion: "9.0"}));
assert.equal(f.store.version, "0.2.0-dev.1");
f.tick(); assert.equal(f.choices.length, 0);
f.ctx.OpenConnect.reopenUSB(token);
f.reply(f.requests[2], f.state({pending: true})); f.tick();
assert.match(f.requests[3].body, /\|recover\|/);

f = fixture();
f.start(token, true);
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
f.start(token, false);
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
f.start(token, false);
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

// Cold Base-on listener startup and verification can exceed twelve seconds.
// Begin one bounded completion-proof window only when the browser is shown.
f = fixture(null, false, {version: "0.3.0-dev.17", notice: "installed"});
f.ctx.framework._browserShown = false;
f.tick(); f.advance(20000); f.tick();
assert.equal(f.requests.length, 0);
f.ctx.framework._browserShown = true;
f.tick(); f.advance(20000);
assert.equal(f.requests[0].aborted, undefined);
f.reply(f.requests[0], f.state({installed: true, installedVersion: "0.3.0-dev.17",
    notice: "installed", completionReady: true}));
f.tick(); assert.equal(f.choices[0].complete, true);

// Refusals/backoff share that same 35s deadline; they cannot replenish it.
f = fixture(null, false, {version: "0.3.0-dev.17", notice: "installed"});
f.tick(); f.advance(34000); f.reply(f.requests[0], null);
f.advance(500); assert.equal(f.requests.length, 2);
f.advance(499); f.reply(f.requests[1], {ok: false, error: "busy"});
f.advance(1); f.tick();
assert.equal(f.requests.length, 2); assert.equal(f.choices.length, 0);
f.advance(60000); f.tick();
assert.equal(f.requests.length, 2); assert.equal(f.choices.length, 0);

// Completion requires fresh post-commit boot proof, including through USB entry.
for (const usb of [false, true]) {
    f = fixture(null, usb, {version: "0.3.0-dev.17", notice: "installed"});
    if (usb) f.start(token, true);
    f.tick();
    assert.equal(f.choices.length, 0);
    f.reply(f.requests[0], f.state({installed: true, installedVersion: "0.3.0-dev.17", notice: "installed", completionReady: true}));
    f.tick();
    assert.equal(f.choices[0].complete, true);
    assert.equal(f.choices[0].version, "0.3.0-dev.17");
    f.choices[0].done("done");
    assert.match(f.requests[1].body, /\|dismiss\|/);
}
for (const extra of [{completionReady: false}, {completionReady: "true"}, {installedVersion: "-"},
    {installedVersion: undefined}, {installedVersion: "0.3.0-dev.16"}, {restart: true}, {conflict: true}]) {
    f = fixture(null, true, {version: "0.3.0-dev.17", notice: "installed"});
    f.start(token, true);
    f.reply(f.requests[0], f.state({installed: true, installedVersion: "0.3.0-dev.17", notice: "installed", completionReady: true, ...extra}));
    f.tick(); assert.equal(f.choices.some(c => c.complete), false);
}
for (const boot of [null, {version: "0.3.0-dev.17", notice: "-"},
    {version: "0.3.0-dev.17", notice: "installed", token: "d".repeat(32)},
    {version: "0.3.0-dev.16", notice: "installed"}]) {
    f = fixture(null, true, boot); f.start(token, true);
    f.reply(f.requests[0], f.state({installed: true, installedVersion: "0.3.0-dev.17", notice: "installed", completionReady: true}));
    f.tick(); assert.equal(f.choices.some(c => c.complete), false);
}

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

// A last-millisecond refusal or busy answer cannot push backoff past the budget.
for (const answer of [null, {ok: false, error: "busy"}]) {
    f = fixture(null, false, {version: "0.3.0-dev.11", notice: "-"});
    f.tick();
    refreshed = undefined;
    f.store.refresh(ok => { refreshed = ok; });
    f.advance(11999);
    f.reply(f.requests[0], answer);
    assert.equal(refreshed, undefined);
    f.advance(1);
    assert.equal(refreshed, null);
    f.advance(500);
    assert.equal(f.requests.length, 1);
}

// USB client dependencies stay within their own verified session.
f = fixture(null, true);
f.start(token, true);
assert.deepEqual(f.loads, ["file:///tmp/open-connect/sessions/session-test/dialog.js",
    "file:///tmp/open-connect/sessions/session-test/settings.js"]);

// Catalog data survives transport and supplies the expected bit to writes.
f = fixture(); f.start(token, false);
const serviceRows = [{id: "android-auto", label: "Android Auto", saved: 1, current: null,
    enable: "Load after restart.", disable: "Stop after restart."}];
f.reply(f.requests[0], f.state({installed: true, services: serviceRows})); f.tick();
assert.equal(f.store.read().services[0].current, null);
f.store.write("android-auto", 1, 0, () => {});
assert.equal(f.requests.at(-1).body, token + "|" + revision + "|set|android-auto|1|0");

// A same-boot USB upgrade retains a live dev.12 endpoint, including cancellation.
f = fixture(previous, true, null, 35555);
f.start(token, true);
assert.equal(f.requests[0].url, "http://127.0.0.1:35555/control");
f.ctx.OpenConnect.cancelUSB(token);
assert.equal(f.ctx.OpenConnect, previous);

// Acquire synchronously before any mutation; failed acquisition is unsent.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.eligible(false); f.choices[0].done("install");
assert.equal(f.requests.length,1); assert.equal(f.ctx.OpenConnect.protected(),true);
f.tick(); assert.equal(f.requests.length,1);
f.eligible(true); f.tick(); assert.equal(f.requests.length,2);
assert.equal(f.progress.length,1); assert.equal(f.progress[0].action,"Installing Open Connect");
assert.equal(f.progress[0].closed,false);
const protectedClient=f.ctx.OpenConnect, loaded=f.loads.length;
for (const legacy of [true,false]) {
    f.insert(legacy); assert.equal(f.ctx.OpenConnect,protectedClient); assert.equal(f.loads.length,loaded);
}
f.reply(f.requests[1],f.state({installed:true,installedVersion:"0.2.0-dev.1",restart:false}));
assert.match(f.requests[2].body,/\|restart\|/); // Same-snapshot reinstall still promises a restart.
assert.equal(f.progress.length,1); assert.equal(f.progress[0].action,"Restarting Mazda Connect");
f.reply(f.requests[2],f.state({installed:true}));
f.insert(true); assert.equal(f.ctx.OpenConnect,protectedClient); assert.equal(f.loads.length,loaded);
f.ctx.OpenConnect.cancelUSB(token); assert.equal(f.ctx.OpenConnect.protected(),true);
assert.equal(f.ctx.OpenConnect.dispose(),false);
f.advance(12000); f.tick();
assert.equal(f.progress[0].closed,true); assert.match(f.messages.at(-1).title,/Unable to confirm/);
f.messages.at(-1).done("done"); assert.equal(f.ctx.OpenConnect.protected(),true);
assert.equal(f.store.pending(true),false);
assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,1);
assert.equal(f.requests.filter(r=>r.body.includes("|install|")).length,1);

f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.eligible(false); f.choices[0].done("install"); f.ctx.OpenConnect.cancelUSB(token);
f.eligible(true); f.tick(); assert.equal(f.requests.filter(r=>r.body.includes("|install|")).length,0);
assert.equal(f.ctx.__ocUSBLoading,undefined);

// Settings removal survives purge and old-media arrivals with no USB wording.
f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
f.store.uninstall(); const removing=f.progress[0];
assert.equal(removing.action,"Removing Open Connect"); assert.doesNotMatch(removing.warning,/USB/);
const removingClient=f.ctx.OpenConnect, beforeLoads=f.loads.length;
f.insert(true); assert.equal(f.loads.length,beforeLoads); assert.equal(f.ctx.OpenConnect,removingClient);
f.reply(f.requests[1],f.state({revision:"-",installedVersion:"-"}));
assert.equal(f.requests[2].body,token+"|-|restart|-|-|-");
assert.doesNotMatch(removing.warning,/USB/);
f.insert(true); assert.equal(f.ctx.OpenConnect,removingClient);
f.reply(f.requests[2],null); f.reply(f.requests[3],f.state({revision:"-",installedVersion:"-"}));
f.advance(12000); f.tick(); assert.doesNotMatch(f.messages.at(-1).text,/USB/);
assert.equal(f.requests.filter(r=>r.body.includes("|uninstall|")).length,1);
assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,1);

// An unchanged same-version state after a lost reply is never commit evidence.
f=fixture(); f.start(token,true);
f.reply(f.requests[0],f.state({installed:true,installedVersion:"0.2.0-dev.1"})); f.tick();
f.choices[0].done("install"); f.reply(f.requests[1],null);
f.reply(f.requests[2],f.state({installed:true,installedVersion:"0.2.0-dev.1",notice:"installed",completionReady:true})); f.tick();
assert.match(f.messages.at(-1).title,/Unable to confirm/);
assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
assert.equal(f.ctx.OpenConnect.protected(),true);

// One shared twelve-second budget, including restart. Never replay the mutation.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.choices[0].done("install"); f.reply(f.requests[1],null);
f.advance(11000); f.reply(f.requests[2],f.state({installed:true,installedVersion:"0.2.0-dev.1",
    revision:"e".repeat(32),notice:"installed"}));
assert.match(f.requests[3].body,/\|restart\|/);
f.advance(1000); f.tick(); assert.match(f.messages.at(-1).title,/Unable to confirm/);
assert.equal(f.requests[3].aborted,true); f.advance(20000); assert.equal(f.requests.length,4);

// Safe refusal releases ownership; insertion can then load a maintenance client.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.choices[0].done("install"); f.reply(f.requests[1],{ok:false,error:"state_changed"});
f.reply(f.requests[2],f.state()); f.tick(); assert.match(f.messages.at(-1).title,/Unable to finish/);
assert.equal(f.ctx.__ocUSBLoading,undefined);
const idleClient=f.ctx.OpenConnect;
f.insert(true); assert.notEqual(f.ctx.OpenConnect,idleClient); assert.match(f.requests.at(-1).body,/\|status\|/);

// Starting a write fences an earlier status before it can alter store.version.
f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
let staleRefresh;
f.store.refresh(v=>staleRefresh=v); f.store.write("touch",0,1,()=>{});
f.reply(f.requests[1],f.state({installed:true,installedVersion:"9.0",revision:"d".repeat(32)}));
assert.equal(staleRefresh,undefined); assert.equal(f.store.version,"0.2.0-dev.1");
f.reply(f.requests[2],f.state({installed:true,touch:1,revision:"e".repeat(32)}));

// The claim precedes the debounce, remains through all acknowledgements, and
// refuses a callback belonging to a client superseded by a legacy loader.
for (const delay of [0,249]) {
    f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
    const client=f.ctx.OpenConnect; assert.equal(f.store.pending(true),true); f.advance(delay);
    f.insert(true); assert.equal(f.ctx.OpenConnect,client);
    let ack=0;
    f.store.write("touch",0,1,()=>{ack++;f.store.pending(false);});
    f.insert(true); assert.equal(f.ctx.OpenConnect,client);
    f.reply(f.requests[1],f.state({installed:true,touch:1}));
    assert.equal(ack,1); assert.equal(f.ctx.__ocUSBLoading,undefined);
    const oldStore=f.store;
    f.insert(true); assert.notEqual(f.ctx.OpenConnect,client);
    assert.equal(f.ctx.__ocUSBLoading,undefined); // Legacy loader has finished; replacement is reading.
    assert.equal(oldStore.pending(true),false); assert.equal(f.ctx.__ocUSBLoading,undefined);
}

// Actual USB loader path on a later authenticated boot, not a boot-only shortcut.
f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"});
f.insert();
f.reply(f.requests[0],f.state({installed:true,installedVersion:"0.3.0-dev.17",notice:"installed",completionReady:true}));
f.tick(); assert.equal(f.choices[0].complete,true);

assert.equal(require("node:crypto").createHash("sha256").update(fs.readFileSync(require("node:path").join(__dirname,"legacy-usb-loader.js"))).digest("hex"),
    "7fcf62d625b9139e12c052bf10cbdf545f9ce06f99e6c12c1851609982c8e877");

// Unknown legacy installed-version fields cannot establish a version transition.
for (const old of [undefined,"-"]) {
    f=fixture(); f.start(token,true);
    f.reply(f.requests[0],f.state({installed:true,installedVersion:old})); f.tick();
    f.choices[0].done("install"); f.reply(f.requests[1],null);
    f.reply(f.requests[2],f.state({installed:true,installedVersion:"0.2.0-dev.1",notice:"installed",revision:"c".repeat(32)})); f.tick();
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
    assert.match(f.messages.at(-1).title,/Unable to confirm/);
}

// End-to-end preferences queue + runtime + actual unmodified legacy loader.
for(const at of [0,249]) {
    f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
    const client=f.ctx.OpenConnect, page=f.openSettings(); page.pick(1);
    assert.equal(f.ctx.OpenConnect.protected(),true);
    f.advance(at); f.insert(true); page.close();
    assert.equal(f.ctx.OpenConnect,client);
    assert.equal(f.requests.filter(r=>r.body.includes("|set|")).length,0);
    f.advance(250-at);
    assert.equal(f.requests.filter(r=>r.body.includes("|set|")).length,1);
    f.insert(true); assert.equal(f.ctx.OpenConnect,client);
    f.reply(f.requests.at(-1),f.state({installed:true,touch:1}));
    assert.equal(f.ctx.__ocUSBLoading,undefined);
    assert.equal(f.ctx.OpenConnect.protected(),false);
}
f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
const supersededPage=f.openSettings(), oldClient=f.ctx.OpenConnect;
f.insert(true); assert.notEqual(f.ctx.OpenConnect,oldClient);
assert.equal(f.ctx.__ocUSBLoading,undefined);
supersededPage.pick(1); f.advance(250);
assert.equal(f.requests.filter(r=>r.body.includes("|set|")).length,0);
assert.equal(f.ctx.__ocUSBLoading,undefined);
supersededPage.close();

// Definite pre-write refusals cannot become lost-ack success, even when fresh
// state shows an independently installed target or a different revision.
for (const error of ["busy", "incomplete_maintenance_bundle", "unsupported_original", "stale_state", "state_changed", "future_refusal"])
for (const scenario of ["unchanged", "changed", "installed"]) {
    const installed=scenario==="installed";
    f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
    f.choices[0].done("install"); f.reply(f.requests[1],{ok:false,error});
    const fresh=f.state({installed,revision:scenario==="unchanged"?revision:"d".repeat(32),
        installedVersion:installed?"0.2.0-dev.1":"-",notice:installed?"installed":"-"});
    f.reply(f.requests[2],fresh); f.tick();
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
    assert.equal(f.ctx.OpenConnect.protected(),false);
    assert.equal(f.ctx.__ocUSBLoading,undefined);
    assert.match(f.messages.at(-1).title,/Unable to finish/);
    assert.doesNotMatch(f.messages.at(-1).text,/restart/i);
    assert.equal(f.ctx.OpenConnect.reopenUSB(token),true);
    f.reply(f.requests.at(-1),fresh); f.tick();
    assert.equal(f.choices.length,2); assert.equal(f.choices.at(-1).installed,installed);
    f.choices.at(-1).done("install");
    assert.equal(f.requests.filter(r=>r.body.includes("|install|")).length,2); // New explicit decision is permitted.
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
}
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.choices[0].done("install"); f.reply(f.requests[1],{ok:false,error:"stale_state"});
f.advance(12000); f.tick(); // Even cached settled state cannot replace a fresh journal check.
assert.equal(f.ctx.OpenConnect.protected(),true);
assert.ok(f.ctx.__ocUSBLoading);
assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);

// Revalidate proof at view acquisition, not only when completion was queued.
for(const invalid of [{completionReady:false,restart:true},{notice:"-"},{installedVersion:"0.3.0-dev.16"}]) {
    f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"}); f.tick();
    f.reply(f.requests[0],f.state({installed:true,notice:"installed",completionReady:true,installedVersion:"0.3.0-dev.17"}));
    f.eligible(false); f.tick(); assert.equal(f.choices.length,0);
    f.store.refresh(()=>{});
    f.reply(f.requests.at(-1),f.state({installed:true,notice:"installed",completionReady:true,installedVersion:"0.3.0-dev.17",...invalid}));
    f.eligible(true); f.tick(); f.tick();
    assert.equal(f.choices.length,0);
    assert.equal(f.requests.filter(r=>r.body.includes("|dismiss|")).length,0);
}
for(const action of ["done","settings"]) {
    f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"}); f.tick();
    f.reply(f.requests[0],f.state({installed:true,notice:"installed",completionReady:true,installedVersion:"0.3.0-dev.17"}));
    f.tick(); assert.equal(f.choices[0].complete,true);
    f.store.refresh(()=>{});
    f.reply(f.requests.at(-1),f.state({installed:true,notice:"installed",completionReady:false,restart:true,installedVersion:"0.3.0-dev.17"}));
    f.choices[0].done(action);
    assert.equal(f.requests.filter(r=>r.body.includes("|dismiss|")).length,0);
}

// Document-order lookup returns the first generation for duplicate IDs. Failed
// handoff removes only the appended generation; repeated success leaves no modules.
f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
const originalClient=f.ctx.OpenConnect, originalModules=f.scripts.slice();
assert.equal(originalModules.length,2);
originalModules.forEach((node,index)=>node.id="oc-runtime-"+["dialog","settings"][index]);
f.insert(); assert.equal(f.scripts.length,4);
assert.equal(f.ctx.document.getElementById("oc-runtime-dialog"),originalModules[0]);
const replacementModules=f.scripts.filter(n=>!originalModules.includes(n));
f.reply(f.requests.at(-1),null);
assert.equal(f.ctx.OpenConnect,originalClient);
assert.deepEqual(f.scripts,originalModules);
assert.ok(originalModules.every(n=>n.parentNode));
assert.ok(replacementModules.every(n=>!n.parentNode));
for(let i=0;i<8;i++) {
    const prior=f.ctx.OpenConnect, priorModules=f.scripts.slice();
    f.insert(); assert.equal(f.scripts.length,4);
    f.reply(f.requests.at(-1),f.state({installed:true})); f.tick();
    assert.notEqual(f.ctx.OpenConnect,prior);
    assert.equal(f.scripts.length,2);
    assert.ok(priorModules.every(n=>!n.parentNode));
}
f.ctx.OpenConnect.dispose(); assert.equal(f.scripts.length,0);

// USB removal cannot cancel an accepted Settings-origin operation while its
// progress view is waiting for an eligible native host.
f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
f.eligible(false); f.store.uninstall();
assert.equal(f.requests.filter(r=>r.body.includes("|uninstall|")).length,0);
f.ctx.OpenConnect.cancelUSB(token);
f.ctx.__ocUSBLoading.cancel();
assert.equal(f.ctx.OpenConnect.protected(),true);
f.eligible(true); f.tick(); f.tick();
assert.equal(f.requests.filter(r=>r.body.includes("|uninstall|")).length,1);
assert.equal(f.progress[0].action,"Removing Open Connect");
assert.doesNotMatch(f.progress[0].warning,/USB/);

// A still-pending authoritative journal is not a free maintenance state. A
// refusal during recovery must not cause tick to resubmit the same recovery.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state({pending:true})); f.tick();
f.reply(f.requests[1],{ok:false,error:"state_changed"});
f.reply(f.requests[2],f.state({pending:true}));
f.tick(); f.tick();
assert.equal(f.requests.filter(r=>r.body.includes("|recover|")).length,1);
assert.equal(f.ctx.OpenConnect.protected(),true);

// The last verified pending state survives missing or malformed reconciliation
// replies. Repeated ticks/timeouts must not replay an already refused recovery.
for (const response of [null, {ok:false,error:"invalid_record"}, {ok:true,pending:false}]) {
    f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state({pending:true})); f.tick();
    f.reply(f.requests[1],{ok:false,error:"state_changed"});
    if(response) f.reply(f.requests[2],response);
    else f.advance(12000);
    for(let i=0;i<3;i++) { f.tick(); f.advance(12000); }
    assert.equal(f.requests.filter(r=>r.body.includes("|recover|")).length,1);
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
    assert.equal(f.ctx.OpenConnect.protected(),true);
    assert.ok(f.ctx.__ocUSBLoading);
}
// A genuinely verified settled status can release the refusal guard.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state({pending:true})); f.tick();
f.reply(f.requests[1],{ok:false,error:"busy"});
f.reply(f.requests[2],f.state({pending:false})); f.tick();
assert.equal(f.ctx.OpenConnect.protected(),false);
assert.equal(f.ctx.__ocUSBLoading,undefined);
assert.equal(f.requests.filter(r=>r.body.includes("|recover|")).length,1);

// Non-null malformed acknowledgements are not missing acknowledgements. Fresh
// desired state cannot turn them into permission to infer this install committed.
for(const answer of [false,0,"",{ok:true},{error:"busy"},{ok:"false",error:"busy"}]) {
    f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
    f.choices[0].done("install"); f.reply(f.requests[1],answer);
    f.reply(f.requests[2],f.state({installed:true,installedVersion:"0.2.0-dev.1",notice:"installed",revision:"c".repeat(32)}));
    f.tick();
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
    assert.equal(f.ctx.OpenConnect.protected(),true);
}
// Explicit refusal is also distinct from an inferred Set/import success.
for(const op of ["set","import"]) {
    f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
    let result="unanswered";
    if(op==="set") f.store.write("touch",0,1,answer=>result=answer);
    else f.store.importKey(answer=>result=answer);
    f.reply(f.requests[1],{ok:false,error:"busy"});
    f.reply(f.requests[2],f.state({installed:true,touch:1,key:"c".repeat(64),revision:"d".repeat(32)}));
    assert.equal(result,null); assert.equal(f.ctx.OpenConnect.protected(),false);
}
// A refused restart is not resent after reconciliation or its watchdog.
f=fixture(); f.start(token,true); f.reply(f.requests[0],f.state()); f.tick();
f.choices[0].done("install"); f.reply(f.requests[1],f.state({installed:true,restart:true}));
f.reply(f.requests[2],{ok:false,error:"busy"});
f.reply(f.requests[3],f.state({installed:true,restart:true})); f.advance(12000); f.tick();
assert.equal(f.ctx.OpenConnect.protected(),false);
assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,1);

// Through the actual USB loader, invalidated queued completion must fall through
// to the verified maintenance chooser. A displayed completion consumes the entry.
for(const invalid of [{notice:"-",completionReady:false},{restart:true,completionReady:false}]) {
    f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"}); f.insert();
    const proof={installed:true,version:"0.3.0-dev.17",installedVersion:"0.3.0-dev.17",notice:"installed",completionReady:true};
    f.reply(f.requests[0],f.state(proof)); f.eligible(false); f.tick();
    assert.equal(f.choices.length,0);
    f.store.refresh(()=>{}); f.reply(f.requests.at(-1),f.state({...proof,...invalid}));
    f.eligible(true); f.tick(); f.tick(); f.tick();
    assert.equal(f.choices.length,1); assert.equal(f.choices[0].complete,undefined);
    assert.equal(f.choices[0].installed,true); assert.equal(f.choices[0].version,"0.3.0-dev.17");
}
f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"}); f.insert();
f.reply(f.requests[0],f.state({installed:true,installedVersion:"0.3.0-dev.17",notice:"installed",completionReady:true}));
f.tick(); assert.equal(f.choices[0].complete,true);
f.choices[0].done("cancel"); f.tick(); f.tick();
assert.equal(f.choices.length,1);

// A post-prepare failure may leave a durable uninstall journal even though the
// last successful status was settled. Only fresh valid settled status can free
// that owner. Replay the real backend's nvram_commit_failed response, and an
// unclassified failure, without allowing old USB media to replace the client.
for(const origin of ["usb","settings"]) for(const error of ["nvram_commit_failed","future_failure"])
for(const followup of ["timeout","invalid_record","malformed","pending"]) {
    f=fixture(); f.start(token,origin==="usb");
    f.reply(f.requests[0],f.state({installed:true,touch:1,warning:1,pending:false})); f.tick();
    if(origin==="usb") f.choices[0].done("uninstall");
    else f.store.uninstall();
    const owner=f.ctx.OpenConnect, marker=f.ctx.__ocUSBLoading, count=f.loads.length;
    f.reply(f.requests[1],{ok:false,error});
    if(followup==="timeout") f.advance(12000);
    else f.reply(f.requests[2],followup==="invalid_record" ? {ok:false,error:"invalid_record"} :
        followup==="malformed" ? {ok:true,pending:false} : f.state({installed:true,pending:true,revision:"d".repeat(32)}));
    f.tick();
    assert.equal(f.ctx.OpenConnect.protected(),true);
    assert.equal(f.ctx.__ocUSBLoading,marker);
    f.insert(true);
    assert.equal(f.ctx.OpenConnect,owner);
    assert.equal(f.ctx.__ocUSBLoading,marker);
    assert.equal(f.loads.length,count);
    assert.equal(owner.dispose(),false);
    f.advance(24000); f.tick(); f.tick();
    assert.equal(f.requests.filter(r=>r.body.includes("|uninstall|")).length,1);
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
    assert.equal(f.requests.filter(r=>r.body.includes("|recover|")).length,0);
}
// If reconciliation genuinely verifies settled state, the refusal may release
// its owner, but still cannot infer success or restart from that state.
for(const installed of [true,false]) {
    f=fixture(); f.start(token,false); f.reply(f.requests[0],f.state({installed:true})); f.tick();
    f.store.uninstall(); f.reply(f.requests[1],{ok:false,error:"nvram_commit_failed"});
    f.reply(f.requests[2],f.state({installed,pending:false,revision:installed?"d".repeat(32):"-"})); f.tick();
    assert.equal(f.ctx.OpenConnect.protected(),false);
    assert.equal(f.ctx.__ocUSBLoading,undefined);
    assert.equal(f.requests.filter(r=>r.body.includes("|restart|")).length,0);
}
// A superseding USB cancellation cannot strand or renew the boot reservation.
f=fixture(null,false,{version:"0.3.0-dev.17",notice:"installed"});
assert.equal(f.ctx.OpenConnect.autoshowState(),1);
f.tick();
f.ctx.OpenConnect.cancelUSB(token); // generation invalidates pending proof callback.
f.advance(35000);
assert.equal(f.ctx.OpenConnect.autoshowState(),0,'absolute proof deadline survives cancellation');
