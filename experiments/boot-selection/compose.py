"""Build one concrete FW55 service/logging/native/JS composition experiment."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import prototype

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_oc_composed_loader", HERE.parent / "optional-loader/build.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
INDEX_SHA = "b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420"
COMMON_SHA = "0f3bf19fa890332ef2196531eebed3ce6e166cf805cc1edc1e53f98a873effbf"


def replace_once(data, old, new):
    if data.count(old) != 1:
        raise ValueError("expected one exact composition anchor")
    return data.replace(old, new)


def config(original, directory):
    if hashlib.sha256(original).hexdigest() != prototype.CONFIG_SHA:
        raise ValueError("unsupported service configuration")
    if any(d.get("value") == "blm_ira_stitcher" for d in ET.fromstring(original).iter("dependency")):
        raise ValueError("Stitcher has a declared consumer")
    replacements = [
        (b'name="blm_ira_stitcher" path="/jci/ira/svcjciblm_ira_stitcher.so" autorun="yes"',
         b'name="blm_ira_stitcher" path="/jci/ira/svcjciblm_ira_stitcher.so" autorun="no"'),
        (b'name="jciMMUI" path="/jci/mmui/svcjcimmui.so"',
         ('name="jciMMUI" path="' + directory + '/mmui.so"').encode()),
        (b'args="-u /jci/gui/index.html"', ('args="-u ' + directory + '/index.html"').encode()),
    ]
    selected = original
    for old, new in replacements:
        selected = replace_once(selected, old, new)
    ET.fromstring(selected)
    return selected


def index(original, directory):
    if hashlib.sha256(original).hexdigest() != INDEX_SHA:
        raise ValueError("unsupported GUI index")
    selected = replace_once(original, b"<head>", b'<head>\n        <base href="file:///jci/gui/" />')
    return replace_once(selected, b"    </body>",
                        ('        <script src="file://' + directory + '/probe.js" type="text/javascript"></script>\n    </body>').encode())


def build(original, sm_config, flush, plugin, gui_index, common, directory, output, clang=None, linker=None):
    if not re.fullmatch(r"/tmp/mnt/data_persist/oc-boot-[0-9a-f]{32}", directory):
        raise ValueError("fresh owned generation path required")
    if common.name != "libjcicommon.so" or hashlib.sha256(common.read_bytes()).hexdigest() != COMMON_SHA:
        raise ValueError("unsupported native logging library")
    # Validate all OEM inputs before making any generated payload.
    selected_config = config(sm_config, directory)
    selected_index = index(gui_index, directory)
    if hashlib.sha256(plugin).hexdigest() != loader.BASE_SHA:
        raise ValueError("unsupported MMUI plugin")
    if hashlib.sha256(original).hexdigest() != prototype.AUTOSTART_SHA:
        raise ValueError("unsupported autostart")
    output = loader.elf.private_output(output)
    scratch = output.with_name(output.name + "-compiler")
    scratch.mkdir(parents=True, exist_ok=False)
    clang = loader.elf.tool("clang", clang)
    linker = linker or shutil.which("ld.lld")
    if not linker:
        mac = Path("/opt/homebrew/opt/lld/bin/ld.lld")
        linker = str(mac) if mac.is_file() else None
    if not linker:
        raise ValueError("ld.lld is required")
    commands = []
    nonce = directory.rsplit("-", 1)[1]
    try:
        obj = loader.compile_stub(clang, scratch / "loader.o", directory + "/bootstrap.so")
        selected_plugin, relocs = loader.patch(plugin, obj)
        command = [
            clang, "--target=armv7-none-eabi", "-march=armv7-a", "-marm",
            "-mfloat-abi=hard", "-mfpu=vfpv3", "-Os", "-fPIC", "-ffreestanding",
            "-fno-stack-protector", "-fno-unwind-tables", "-fvisibility=hidden",
            '-DOC_GENERATION="' + nonce + '"', "-Wall", "-Wextra", "-Werror",
            "-c", str(HERE / "generation-probe.c"), "-o", str(scratch / "probe.o"),
        ]
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True)
        command = [str(linker), "-shared", "-z", "defs", "--build-id=none",
                   "-soname", "oc-generation.so", str(scratch / "probe.o"),
                   "-L" + str(common.parent), "-ljcicommon", "-o", str(scratch / "bootstrap.so")]
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True)
        js = ('/* Open Connect generation probe; no callbacks or heartbeat changes. */\n'
              'log.jciLogger.JCILog("framework ERROR oc_generation.js[1] OCGEN_JS|' + nonce + '|entered");\n').encode()
        dependencies = {"mmui.so": selected_plugin, "bootstrap.so": (scratch / "bootstrap.so").read_bytes(),
                        "index.html": selected_index, "probe.js": js}
        plan = prototype.build(original, sm_config, flush, directory, output,
                               generation_config=selected_config, dependencies=dependencies, log_level="Warn")
        plan.update(scope="one service/logging/native/JS generation; baseline on next boot",
                    markers={"native": "/tmp/oc-generation-" + nonce + ".native", "js": "OCGEN_JS|" + nonce + "|entered"},
                    expected={"stitcher_autorun": False, "native_log_level": "Warn",
                              "baseline_native_log_level": "Info"},
                    compiler_commands=commands, loader_relocations=relocs,
                    source_inputs={"index_sha256": INDEX_SHA, "plugin_sha256": loader.BASE_SHA,
                                   "common_sha256": COMMON_SHA})
        for p in (Path(__file__), HERE / "generation-probe.c", loader.SOURCE, Path(loader.__file__)):
            plan["source_pins"][str(p.relative_to(HERE.parents[1]))] = hashlib.sha256(p.read_bytes()).hexdigest()
        (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        return plan
    except subprocess.CalledProcessError as error:
        (scratch / "failure.stdout").write_bytes(error.stdout or b"")
        (scratch / "failure.stderr").write_bytes(error.stderr or b"")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "config", "flush", "plugin", "index", "common", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--clang")
    parser.add_argument("--linker")
    a = parser.parse_args()
    result = build(a.original.read_bytes(), a.config.read_bytes(), a.flush.read_bytes(),
                   a.plugin.read_bytes(), a.index.read_bytes(), a.common, a.directory,
                   a.output, a.clang, a.linker)
    print(json.dumps(result, indent=2))
