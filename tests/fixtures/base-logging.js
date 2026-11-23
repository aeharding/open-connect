// Replay synchronous logger startup. Settings may be an authored fixture or
// a private original; the constructor is a stand-in and no OEM source is stored.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const context = {};
let constructorRan = false;
for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    const src = /src="([^"]+)"/.exec(match[1]);
    if (src && src[1] === "common/js/logDefaults.js") {
        vm.runInNewContext(fs.readFileSync(process.argv[3], "utf8"), context);
    } else if (src && src[1] === "framework/js/Log.js") {
        vm.runInNewContext("var log = {level: logDefaults.__global__};", context);
        constructorRan = true;
        break;
    } else if (!src) {
        vm.runInNewContext(match[2], context);
    }
}
assert.ok(constructorRan);
assert.equal(context.log.level, process.argv[4] || "warn", "the Base policy must precede Log construction");
assert.ok(!html.includes("feature/log-defaults.js"));
