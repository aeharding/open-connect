"""Composition boundaries; explicit private inputs enable the real OEM checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

import feature
import test_selector


class FeatureTests(unittest.TestCase):
    D = "/tmp/mnt/data_persist/oc-boot-" + "a" * 32

    def test_unknown_inputs_and_directory_refused(self):
        with self.assertRaises(ValueError):
            feature.mmui_plugin(b"unknown", self.D)
        with self.assertRaises(ValueError):
            feature.mmui_config(b"<config/>", self.D)
        with self.assertRaises(ValueError):
            feature.index(b"<html/>", self.D)
        for path in (self.D + "/../other", self.D + "\n", "/tmp/test", self.D.upper()):
            with self.assertRaises(ValueError):
                feature.route_script(path)

    def test_delegate_preserves_arguments_receiver_return_and_other_urls(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js required")
        code = """
const assert=require('node:assert/strict'),vm=require('node:vm');
const calls=[], result={};const utility={loadScript:function(...args){calls.push([this,args]);return result}};
const c={utility};vm.runInNewContext(process.argv[1],c);
const attrs={},callback=()=>{},receiver={};
assert.equal(utility.loadScript.call(receiver,'apps/system/js/systemApp.js',attrs,callback),result);
assert.equal(calls[0][0],receiver);
assert.equal(calls[0][1][0],process.argv[2]);assert.equal(calls[0][1][1],attrs);assert.equal(calls[0][1][2],callback);
for(const url of ['apps/fmradio/js/fmradioApp.js','apps/system/js/systemAppDict_en_US.js',
 'file:///jci/gui/apps/system/js/systemApp.js','apps/system/js/systemApp.js?x']){
 utility.loadScript(url);assert.equal(calls.at(-1)[1][0],url);
}
"""
        subprocess.run([node, "-e", code, feature.route_script(self.D),
                        "file://" + self.D + "/system-app.js"], check=True, timeout=10)

    def test_every_dependency_checked_before_consumption_then_baseline(self):
        fixture = test_selector.SelectorTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        dependencies = {n: ("exact " + n).encode() for n in
                        ("mmui.so", "mmui.xml", feature.NATIVE_FILE, "system-app.js", "index.html")}
        for name, content in dependencies.items():
            p = fixture.d / name
            p.write_bytes(content)
            p.chmod(0o600)
        fixture.install_selector(dependencies)
        armed = (fixture.d / "armed").read_bytes()
        for name, content in dependencies.items():
            with self.subTest(name=name):
                p = fixture.d / name
                p.write_bytes(content + b"x")
                fixture.baseline()
                self.assertEqual((fixture.d / "armed").read_bytes(), armed)
                self.assertFalse((fixture.d / "spent").exists())
                p.write_bytes(content)
        self.assertIn("OCBOOT|trial|consumed-before-services", fixture.run_parent())
        self.assertEqual((fixture.d / "spent").read_bytes(), armed)
        fixture.baseline()


@unittest.skipUnless(os.environ.get("OC_FEATURE_INPUTS"), "explicit private OEM inputs required")
class PrivateFeatureTests(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads(Path(os.environ["OC_FEATURE_INPUTS"]).read_text())
        self.d = FeatureTests.D

    def read(self, key):
        return Path(self.inputs[key]).read_bytes()

    def test_actual_plugin_xml_and_index(self):
        original = self.read("plugin")
        changed = feature.mmui_plugin(original, self.d)
        self.assertEqual(len(changed), len(original))
        image = feature.loader.elf.ELF(changed)
        pointer = struct.unpack_from("<I", changed, 0x31FC)[0]
        for base in (0, 0x2B000000, 0x70000000):
            self.assertEqual((base + 0x2A70 + pointer) & 0xFFFFFFFF, base + 0x3F38)
        length = struct.unpack_from("<I", changed, 0x2A6C)[0] & 255
        self.assertEqual(changed[0x3F38:0x3F38+length], (self.d + "/mmui.xml").encode() + b"\0")
        self.assertEqual(struct.unpack_from("<I", changed, image.h[5] + 16)[0], 0x3F38 + length)
        old = feature.ET.fromstring(self.read("mmui_xml"))
        new = feature.ET.fromstring(feature.mmui_config(self.read("mmui_xml"), self.d))
        a, b = list(old.iter()), list(new.iter())
        self.assertEqual(len(a), len(b))
        differences = [(x.attrib, y.attrib) for x, y in zip(a,b) if x.attrib != y.attrib]
        self.assertEqual(len(differences), 1)
        self.assertEqual(differences[0][0]["uiaid"], "1")
        parent, generation = self.d.rsplit("/", 1)
        expected = dict(differences[0][0], libpath=parent, lib=generation + "/" + feature.NATIVE_FILE)
        self.assertEqual(differences[0][1], expected)
        selected = feature.index(self.read("index"), self.d).decode()
        self.assertLess(selected.index("utility.loadScript ="), selected.index("var baseApp"))
        self.assertLess(selected.index("utility.loadScript ="), selected.index("var framework"))
        self.assertEqual(selected.count('<base href="file:///jci/gui/" />'), 1)

    def test_actual_loader_field_limits_and_join(self):
        original = self.read("plugin")
        # The original ARM parser copies 49 bytes for BOTH XML path fields.
        self.assertEqual(struct.unpack_from("<I", original, 0x33AC)[0], 0xE3A02031)
        self.assertEqual(struct.unpack_from("<I", original, 0x3484)[0], 0xE3A02031)
        for literal, add, name in ((0x36C0, 0x3378, b"libpath"),
                                   (0x36D4, 0x3450, b"lib")):
            ptr = (struct.unpack_from("<I", original, literal)[0] + add + 8) & 0xFFFFFFFF
            self.assertEqual(original[ptr:ptr+len(name)+1], name + b"\0")
        separator = (struct.unpack_from("<I", original, 0x2944)[0] + 0x20A8 + 8) & 0xFFFFFFFF
        self.assertEqual(original[separator:separator+2], b"/\0")
        xml = feature.ET.fromstring(feature.mmui_config(self.read("mmui_xml"), self.d))
        row, = (x for x in xml.iter() if x.get("name") == "system")
        path, lib = row.get("libpath").encode(), row.get("lib").encode()
        self.assertLessEqual(len(path), 49)
        self.assertLessEqual(len(lib), 49)
        loaded = path[:49] + b"/" + lib[:49]
        self.assertEqual(loaded, (self.d + "/" + feature.NATIVE_FILE).encode())
        self.assertLess(len(loaded), 512)
        # Preserve the real first-trial failure as a regression, not an accepted path.
        broken = (self.d + "/").encode()[:49] + b"/libjciuiasystem.so"
        self.assertNotEqual(broken, (self.d + "/libjciuiasystem.so").encode())

    def test_real_oem_utility_and_framework_dispatch(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js required")
        self.assertEqual(hashlib.sha256(self.read("utility")).hexdigest(),
                         "eff9e63497fbd0f90d5dc9e2d9403c93fc6171cc71f70319462686a423fea791")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "index.html"
            p.write_bytes(feature.index(self.read("index"), self.d))
            subprocess.run([node, str(feature.HERE / "test_feature.js"), self.inputs["utility"],
                            self.inputs["framework"], str(p), "file://" + self.d + "/system-app.js"],
                           check=True, timeout=10)

    def test_checked_pair_refuses_changed_candidate(self):
        pair = Path(self.inputs["pair"])
        data, _, _ = feature.checked_pair(pair)
        self.assertEqual(len(data[feature.NATIVE_FILE]), 454142)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "pair"
            shutil.copytree(pair, copy)
            p = copy / "js/candidate.js"
            p.write_bytes(p.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "candidate changed"):
                feature.checked_pair(copy)


if __name__ == "__main__":
    unittest.main()
