const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
function session(available) {
    let interval, deadline, callback, opened = 0, closed = 0;
    const requests = [], events = [], window = {framework: {_browserShown: true}};
    const ctx = {
        window, token: "session-token", port: 39877, Image: function () { requests.push(this); },
        setInterval(f) { interval = f; return 1; }, clearInterval() { interval = null; },
        setTimeout(f) { deadline = f; return 2; }, clearTimeout() { deadline = null; },
        log: {jciLogger: {JCILog(s) { events.push(s); }}},
        OpenConnectInstaller: {preview(fw, done) {
            if (!available) { return false; }
            opened++; callback = done;
            return function () { closed++; done("cancel"); };
        }}
    };
    function run() { vm.runInNewContext("(function(){" + source + "}())", ctx); }
    run();
    return {window, requests, events, run,
        tick() { interval(); }, expire() { deadline(); },
        choose() { callback("cancel"); }, counts() { return [opened, closed]; },
        timers() { return [interval, deadline]; }};
}
let s = session(true);
s.tick();
assert.deepEqual(s.counts(), [1,0]);
const state = s.window.__ocUSB;
s.run(); // Duplicate execution does not replace the active session.
assert.equal(s.window.__ocUSB, state);
s.choose();
state.cancel(); // Late duplicate callbacks cannot send a second acknowledgement.
assert.deepEqual(s.counts(), [1,1]);
assert.equal(s.window.__ocUSB, undefined);
assert.equal(s.requests.length, 1);
assert.equal(s.requests[0].src, "http://127.0.0.1:39877/session-token");
assert.deepEqual(s.timers(), [null,null]);
s.run(); s.tick(); s.window.__ocUSB.cancel();
assert.deepEqual(s.counts(), [2,2]); // Reinsertion can open a new dialog.
s = session(true); s.tick(); s.expire();
assert.deepEqual(s.counts(), [1,1]);
assert.match(s.events.at(-1), /expired$/);
s = session(false);
for (let i=0;i<81;i++) { s.tick(); }
assert.deepEqual(s.counts(), [0,0]);
assert.match(s.events.at(-1), /busy$/);
assert.deepEqual(s.timers(), [null,null]);
