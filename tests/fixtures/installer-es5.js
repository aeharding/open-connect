const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const acorn = require("acorn");

function parse(source) {
    const ast = acorn.parse(source, {ecmaVersion: 5, sourceType: "script", locations: true});
    function visit(node, parent, grandparent) {
        // Acorn also accepts legacy block declarations in its ES5 mode. The
        // CMU's strict parser permits declarations only in a source/function body.
        if (node.type === "FunctionDeclaration" && parent.type !== "Program" &&
                !(parent.type === "BlockStatement" && grandparent &&
                    /^(FunctionDeclaration|FunctionExpression)$/.test(grandparent.type) &&
                    grandparent.body === parent)) {
            throw new SyntaxError("Function declaration in statement context at line " + node.loc.start.line);
        }
        for (const value of Object.values(node)) {
            for (const child of Array.isArray(value) ? value : [value]) {
                if (child && typeof child.type === "string") { visit(child, node, parent); }
            }
        }
    }
    visit(ast, null, null);
    return ast;
}

// Modern Node accepts this; strict ES5 (including the CMU's Opera) rejects it.
assert.throws(() => parse('"use strict"; if (true) { function show() {} }'), SyntaxError);
parse('"use strict"; if (true) { var show = function () {}; }');
parse('"use strict"; function outer() { function inner() {} }');
assert.throws(() => parse("const value = 1;"), SyntaxError);

const folder = process.argv[2];
for (const name of fs.readdirSync(folder).filter(name => name.endsWith(".js"))) {
    const source = fs.readFileSync(path.join(folder, name), "utf8");
    try { parse(source); }
    catch (error) { throw new Error(name + ": " + error.message, {cause: error}); }
}
console.log("Installer JavaScript parses as ES5");
