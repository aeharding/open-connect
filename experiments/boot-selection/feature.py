"""Select the existing paired feature through copied OEM launch configurations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import prototype
from compose import INDEX_SHA, loader, replace_once

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "cmu/adapters/fw55/system-app-path.js"
NATIVE_FILE = "uia.so"
MMUI_XML_SHA = "c94446b8c6e5bde79607514d3eb41036a3f56914d2d3f418605110bc250be0d0"


def directory_guard(directory):
    if not re.fullmatch(r"/tmp/mnt/data_persist/oc-boot-[0-9a-f]{32}", directory):
        raise ValueError("fresh owned generation path required")


def mmui_plugin(original, directory):
    """Only redirect the existing XML filename copy; no new executable code."""
    directory_guard(directory)
    if len(original) != 22952 or hashlib.sha256(original).hexdigest() != loader.BASE_SHA:
        raise ValueError("unsupported exact MMUI plugin")
    image = loader.elf.ELF(original)
    phoff = image.h[5]
    if struct.unpack_from("<8I", original, phoff) != (1, 0, 0, 0, 0x3F38, 0x3F38, 5, 0x8000):
        raise ValueError("unexpected plugin RX segment")
    if original[0x3F38:0x4000] != bytes(0xC8):
        raise ValueError("occupied plugin padding")
    # ldr r1,[pc,...]; add r1,pc,r1 at 0x2a68; memcpy length at 0x2a6c.
    if struct.unpack_from("<3I", original, 0x2A64) != (0xE59F1790, 0xE08F1001, 0xE3A0201A):
        raise ValueError("unexpected config copy instructions")
    old_path = (struct.unpack_from("<I", original, 0x31FC)[0] + 0x2A70) & 0xFFFFFFFF
    if original[old_path:old_path + 26] != b"/jci/mmui/mmui_config.xml\0":
        raise ValueError("unexpected config filename")
    path = (directory + "/mmui.xml").encode("ascii") + b"\0"
    if len(path) > 0xC8 or len(path) > 255:
        raise ValueError("config path exceeds padding or ARM immediate")
    candidate = bytearray(original)
    candidate[0x3F38:0x3F38 + len(path)] = path
    struct.pack_into("<I", candidate, 0x31FC, 0x3F38 - 0x2A70)
    struct.pack_into("<I", candidate, 0x2A6C, 0xE3A02000 | len(path))
    for offset in (16, 20):
        struct.pack_into("<I", candidate, phoff + offset, 0x3F38 + len(path))
    allowed = set(range(0x3F38, 0x3F38 + len(path)))
    for offset in (0x31FC, 0x2A6C, phoff + 16, phoff + 20):
        allowed.update(range(offset, offset + 4))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(original, candidate))):
        raise ValueError("unexpected plugin change")
    return bytes(candidate)


def mmui_config(original, directory):
    directory_guard(directory)
    if hashlib.sha256(original).hexdigest() != MMUI_XML_SHA:
        raise ValueError("unsupported exact MMUI configuration")
    old = b'name="system" libpath="/jci/mmui/uia/" lib="libjciuiasystem.so"'
    # OEM ReadConfigEntry copies both libpath and lib into 50-byte fields.
    # ProcessEntry joins them with '/'; a relative subpath in lib fits unchanged.
    parent, generation = directory.rsplit("/", 1)
    library = generation + "/" + NATIVE_FILE
    if max(len(parent.encode()), len(library.encode())) > 49:
        raise ValueError("MMUI library path exceeds OEM field")
    new = ('name="system" libpath="' + parent + '" lib="' + library + '"').encode()
    changed = replace_once(original, old, new)
    ET.fromstring(changed)
    return changed


def route_script(directory):
    directory_guard(directory)
    return ROUTE.read_text().replace("@SYSTEM_APP@", json.dumps("file://" + directory + "/system-app.js"))


def index(original, directory):
    directory_guard(directory)
    if hashlib.sha256(original).hexdigest() != INDEX_SHA:
        raise ValueError("unsupported exact GUI index")
    selected = replace_once(original, b"<head>", b'<head>\n        <base href="file:///jci/gui/" />')
    anchor = b"var utility = new Utility();"
    return replace_once(selected, anchor, anchor + b"\n" + route_script(directory).encode())


def checked_pair(pair):
    result = json.loads((pair / "result.json").read_text())
    native = json.loads((pair / "native/candidate/profile.json").read_text())
    manifest = json.loads((pair / "native/manifest.json").read_text())
    if result.get("status") != "PASS" or manifest.get("returncode") != 0:
        raise ValueError("paired feature checks did not pass")
    pins = dict(result["source_sha256"], **manifest["source_sha256"])
    for name, expected in pins.items():
        if not re.fullmatch(r"experiments/(intro-handoff|disclaimer-native)/[a-z_.]+", name):
            raise ValueError("unexpected feature source")
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("checked feature source changed: " + name)
    data = {}
    for name, relative, expected in (
        (NATIVE_FILE, "native/candidate/candidate.bin", native["candidate"]),
        ("system-app.js", "js/candidate.js", result["js_profile"]["candidate"]),
    ):
        content = (pair / relative).read_bytes()
        if prototype.fingerprint(content) != expected:
            raise ValueError("checked feature candidate changed: " + name)
        data[name] = content
    return data, pins, native["manager_dependency"]


def build(original, config, flush, plugin, mmui_xml, gui_index, pair, directory, output):
    directory_guard(directory)
    output = loader.elf.private_output(output)
    selected_plugin = mmui_plugin(plugin, directory)
    selected_xml = mmui_config(mmui_xml, directory)
    selected_index = index(gui_index, directory)
    if hashlib.sha256(config).hexdigest() != prototype.CONFIG_SHA:
        raise ValueError("unsupported service configuration")
    selected_config = replace_once(config,
        b'name="jciMMUI" path="/jci/mmui/svcjcimmui.so"',
        ('name="jciMMUI" path="' + directory + '/mmui.so"').encode())
    selected_config = replace_once(selected_config, b'args="-u /jci/gui/index.html"',
        ('args="-u ' + directory + '/index.html"').encode())
    ET.fromstring(selected_config)
    dependencies, pins, manager = checked_pair(pair)
    nonce = directory.rsplit("-", 1)[1]
    marker = "OCFEATURE_JS|" + nonce + "|loaded"
    dependencies["system-app.js"] += (
        '\nlog.jciLogger.JCILog("framework ERROR oc_feature.js[1] ' + marker + '");\n').encode()
    dependencies.update({"mmui.so": selected_plugin, "mmui.xml": selected_xml, "index.html": selected_index})
    plan = prototype.build(original, config, flush, directory, output,
                           generation_config=selected_config, dependencies=dependencies)
    plan.update(scope="one boot of the existing native/JS feature, then existing baseline",
                feature_pair=str(pair.resolve()), manager_dependency=manager,
                js_marker=marker, dependencies=sorted(dependencies), root_feature_writes=False,
                limits=["one-shot experiment; no automatic ACC renewal",
                        "selected-file checks do not prove both processes initialized successfully",
                        "baseline is existing bench software, not factory original"])
    plan["source_pins"].update(pins)
    for p in (Path(__file__), ROUTE):
        plan["source_pins"][str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "config", "flush", "plugin", "mmui-xml", "index", "pair", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    try:
        plan = build(args.original.read_bytes(), args.config.read_bytes(), args.flush.read_bytes(),
                     args.plugin.read_bytes(), args.mmui_xml.read_bytes(), args.index.read_bytes(),
                     args.pair, args.directory, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, "feature generation not built: " + str(error) + "\n")
    print(json.dumps(plan, indent=2))
