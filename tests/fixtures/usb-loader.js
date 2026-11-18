const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const session = fs.readFileSync(require("node:path").join(require("node:path").dirname(process.argv[2]), "session.sh"), "utf8");
const cleanup = session.match(/navigate "javascript:([^"\n]+)" \|\| :/)[1].replaceAll("$token", "token");
function fixture(start = true) {
    const nodes = {}, pending = [], calls = [], window = {};
    const parent = {removeChild(n) { delete nodes[n.id]; n.parentNode = null; }};
    nodes["oc-usb-loader"] = {id: "oc-usb-loader", ocToken: "token", ocPort: 20001,
        src: "file://localhost/tmp/oc-usb-abc/loader.js", parentNode: parent};
    const ctx = {window, document: {getElementById(id) { return nodes[id]; }},
        utility: {loadScript(url, attrs, loaded) {
            nodes[attrs.id] = {...attrs, parentNode: parent};
            pending.push({url, loaded});
        }}, OpenConnectPreview(...args) { calls.push(args); }};
    const run = () => vm.runInNewContext(source, ctx);
    if (start) run();
    return {window, nodes, pending, calls, run, cleanup() { vm.runInNewContext(cleanup, ctx); }};
}
let f = fixture();
f.run();
assert.equal(f.pending.length, 1);
assert.equal(f.pending[0].url, "file://localhost/tmp/oc-usb-abc/dialog.js");
f.pending[0].loaded();
assert.equal(f.pending[1].url, "file://localhost/tmp/oc-usb-abc/usb-preview.js");
assert.equal(f.calls.length, 0);
f.pending[1].loaded();
assert.deepEqual(f.calls, [["token", 20001]]);
assert.deepEqual(Object.keys(f.nodes), []);
assert.equal(f.window.__ocUSBLoading, undefined);
for (const stage of [0, 1]) {
    f = fixture();
    if (stage) f.pending[0].loaded();
    f.cleanup();
    f.pending[stage].loaded(); // Late callbacks after removal cannot open a dialog.
    assert.deepEqual(f.calls, []);
    assert.deepEqual(Object.keys(f.nodes), []);
    assert.equal(f.window.__ocUSBLoading, undefined);
}
// The entry element can exist before the browser has executed its script.
f = fixture(false);
f.cleanup();
f.run(); // A delayed script execution after cleanup must not restart loading.
assert.deepEqual(Object.keys(f.nodes), []);
assert.deepEqual(f.pending, []);
assert.deepEqual(f.calls, []);
// A stale session cannot remove a later session's entry element.
f = fixture(false);
f.nodes["oc-usb-loader"].ocToken = "later-token";
f.cleanup();
assert.equal(f.nodes["oc-usb-loader"].ocToken, "later-token");
