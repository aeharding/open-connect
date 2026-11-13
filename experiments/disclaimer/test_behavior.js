// Independent host harness. Loads private OEM originals, never redistributes them.
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');

function load(path) {
    let now = 1000, id = 0;
    const timers = new Map(), events = [], registrations = [];
    const context = {
        log: {addSrcFile() {}, debug() {}},
        framework: {
            sendEventToMmui(app, event) { events.push([app, event]); },
            registerAppLoaded(...args) { registrations.push(args); }
        },
        Date: {now() { return now; }},
        setTimeout(fn, delay) { const handle = ++id; timers.set(handle, {fn, delay}); return handle; },
        clearTimeout(handle) { timers.delete(handle); },
        setInterval() { throw new Error('unexpected interval creation'); },
        clearInterval() { throw new Error('unexpected interval removal'); }
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path, 'utf8'), context, {timeout: 1000, filename: 'private-OEM.js'});
    assert.deepEqual(registrations, [['system', null, true]]);
    const app = Object.create(context.systemApp.prototype);
    app.uiaId = 'system';
    app._currentContext = {ctxtId: 'Disclaimer'};
    // Minimal state fixture corresponding to captured OEM appInit; no UI/native MMUI model.
    app._disclaimerTime = {reset: true, remaining: 0, whenStarted: 0, timeoutId: null};
    return {
        app, timers, events,
        advance(ms) { now += ms; },
        next() { assert.equal(timers.size, 1); return [...timers.entries()][0]; },
        fire() {
            const [handle, timer] = this.next();
            timers.delete(handle); now += timer.delay; timer.fn();
        }
    };
}

const [original, candidate] = process.argv.slice(2);
assert(original && candidate, 'need private original/candidate paths');
const before = load(original), after = load(candidate);
before.app._displayedDisclaimer(); after.app._displayedDisclaimer();
assert.equal(before.next()[1].delay, 3500);
assert.equal(after.next()[1].delay, 0);
assert.deepEqual(after.events, [['system', 'DisposeIntroVideo']]);
after.fire();
assert.deepEqual(after.events, [['system', 'DisposeIntroVideo'], ['system', 'Timeout']]);
assert.equal(after.next()[1].delay, 3500); // no repeated zero-delay event storm
before.fire();
assert.deepEqual(before.events, after.events);
after.fire(); assert.equal(after.next()[1].delay, 3500);
assert.equal(after.events.filter(row => row[1] === 'Timeout').length, 2);
assert(!after.events.some(row => row[1] === 'Global.Yes'));

// Manual acceptance still clears the retry and sends the OEM common event.
after.app._selectCallbackDisclaimer(null, 'Global.Yes', null);
assert.equal(after.timers.size, 0);
assert.equal(after.app._disclaimerTime.reset, true);
assert.deepEqual(after.events.at(-1), ['common', 'Global.Yes']);

// Overlay/interrupt hides the disclaimer: cancel timer, account elapsed, resume OEM path.
const covered = load(candidate);
covered.app._displayedDisclaimer(); covered.advance(5);
covered.app._currentContext = {ctxtId: 'SystemWarning'};
covered.app._noLongerDisplayedDisclaimer();
assert.equal(covered.timers.size, 0);
assert.equal(covered.app._disclaimerTime.timeoutId, null);
assert.equal(covered.app._disclaimerTime.remaining, -5);
assert(!covered.events.some(row => row[1] === 'Timeout'));
covered.app._currentContext = {ctxtId: 'Disclaimer'};
covered.app._displayedDisclaimer();
assert.deepEqual(covered.events.at(-1), ['system', 'Timeout']);

// Timer races with a context change: keep the existing context guard and retry.
const raced = load(candidate);
raced.app._displayedDisclaimer(); raced.app._currentContext = {ctxtId: 'SystemWarning'};
raced.fire();
assert(!raced.events.some(row => row[1] === 'Timeout'));
assert.equal(raced.next()[1].delay, 3500);
raced.app._noLongerDisplayedDisclaimer(); assert.equal(raced.timers.size, 0);

// A later normal/quick-start display resets its initial timer, still via OEM callback.
const again = load(candidate);
again.app._disclaimerTime.remaining = 999;
again.app._displayedDisclaimer(); assert.equal(again.next()[1].delay, 0);
again.app._noLongerDisplayedDisclaimer();
again.app._disclaimerTime.reset = true;
again.app._displayedDisclaimer(); assert.equal(again.next()[1].delay, 0);

for (const name of ['_selectCallbackDisclaimer', '_disclaimerTimedout', '_noLongerDisplayedDisclaimer']) {
    assert.equal(before.app[name].toString(), after.app[name].toString(), name + ' must be unchanged');
}
console.log(JSON.stringify({
    result: 'PASS', initial_original_ms: 3500, initial_candidate_ms: 0,
    retry_ms: 3500, manual_agree: 'unchanged', context_guard: 'unchanged',
    pause_and_teardown: 'unchanged', quick_start_reset: 'modeled',
    limitation: 'Requested delays/events in Node VM; no actual Opera rendering/MMUI/startup or heartbeat runtime claim'
}, null, 2));
