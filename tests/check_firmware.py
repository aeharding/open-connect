"""Validate the maintained release against private exact-v74 originals.

No device access. Make/Clang/LLD build all assets and the maintained shell composes
OEM-containing files privately. This checker only inspects their result.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from open_connect.elf import ELF

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool(name, explicit=None):
    found = shutil.which(str(explicit or name))
    if not found and explicit is None and sys.platform == "darwin":
        result = subprocess.run(["xcrun", "--find", name], capture_output=True, text=True)
        if result.returncode == 0:
            found = shutil.which(result.stdout.strip())
    if not found:
        raise ValueError("missing executable " + str(explicit or name))
    return found


def private_output(path):
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("private output must not traverse symlinks")
    path = path.resolve()
    if not path.is_relative_to(ROOT / "runs") or path == ROOT / "runs":
        raise ValueError("private output must be below the checkout's runs directory")
    if path.exists():
        raise ValueError("output exists; choose a fresh private directory")
    return path


def inputs(firmware):
    """The maintained native C guard is the authority for original-file hashes."""
    guard_c = (ASSETS / "core/oc-guard.c").read_text()
    names = re.findall(
        r'"([^"]+)"', re.search(r"oc_root_names\[19\]=\{([^}]+)\}", guard_c, re.S)[1]
    )
    rpaths = re.findall(
        r'"([^"]+)"', re.search(r"oc_root_paths\[19\]=\{([^}]+)\}", guard_c, re.S)[1]
    )
    rdigests = re.findall(
        r'"([a-f0-9]{64})"', re.search(r"oc_root_digests\[19\]=\{([^}]+)\}", guard_c, re.S)[1]
    )
    auto_dig = re.search(r'oc_orig_autostart_digest="([a-f0-9]{64})"', guard_c)[1]
    base_rows = re.findall(
        r'\{"([^"]+)","([^"]+)","([a-f0-9]{64})"',
        re.search(r"oc_base_pins\[5\]=\{([^;]+)\};", guard_c, re.S)[1],
    )
    entries = [("autostart", "/usr/bin/autostart", auto_dig), *zip(names, rpaths, rdigests)]
    for key, rel, dig in base_rows:
        leaf = (
            "vui.so"
            if key == "base/vui/vui.so"
            else "vui.xml"
            if key == "base/vui/vui.xml"
            else key.split("/")[-1]
        )
        entries.append((leaf, "/" + rel.lstrip("/"), dig))
    paths = {}
    for name, target, digest in entries:
        source = firmware / target.removeprefix("/")
        if sha(source) != digest:
            raise ValueError("unsupported exact original: " + target)
        paths[name] = source
    for row in (ASSETS / "ui-modules.tsv").read_text().splitlines():
        if row.startswith("vui\t"):
            _, name, _, digest = row.split("\t")
            source = firmware / "jci/vui/plugins" / name
            if sha(source) != digest:
                raise ValueError("unsupported plugin " + name)
            paths[name] = source
    paths["framework"] = paths["framework.js"]
    paths["display"] = paths["lvds-service"]
    return paths


def run(command, output, name, **kwargs):
    result = subprocess.run(command, capture_output=True, timeout=120, **kwargs)
    (output / (name + ".stdout")).write_bytes(result.stdout)
    (output / (name + ".stderr")).write_bytes(result.stderr)
    (output / (name + ".json")).write_text(
        json.dumps({"command": list(map(str, command)), "exit": result.returncode}, indent=2) + "\n"
    )
    if result.returncode:
        raise ValueError(name + " failed; see retained stdout/stderr")
    return result


def build(output, paths, host_cc):
    run(["make", "release", "OUT=" + str(output / "build")], output, "make", cwd=ROOT)
    source = output / "build/usb/open-connect"
    package = sha(source / "files.sha256")
    root_dir = output / "root"
    data = root_dir / "tmp/mnt/data_persist/open-connect"
    for name in ("originals", "packages", "composed"):
        (data / name).mkdir(mode=0o700, parents=True)
    data.chmod(0o700)
    (root_dir / "jci/vui").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(paths["vui.so"], root_dir / "jci/vui/svcjcivui.so")
    shutil.copyfile(paths["vui.xml"], root_dir / "jci/vui/vui_config.xml")
    (root_dir / "dev").mkdir(parents=True, exist_ok=True)
    (root_dir / "dev/urandom").write_bytes(os.urandom(4096))
    for name in (
        "autostart",
        "sm.conf",
        "sm_WCP.conf",
        "board.sh",
        "mmui.so",
        "mmui.xml",
        "uia.so",
        "index.html",
        "system-app.js",
        "settings-app.js",
        "base-app.js",
        "vui.so",
        "vui.xml",
    ):
        shutil.copyfile(paths[name], data / "originals" / name)
        (data / "originals" / name).chmod(0o600)
    shutil.copytree(source, data / "packages" / package)
    (data / "packages" / package).chmod(0o700)
    from tests.host_bins import host_install

    inst_bin = host_install()
    run(
        [str(inst_bin), "--test-compose", package],
        output,
        "compose",
        env={**os.environ, "OC_HOST_ROOT": str(root_dir), "OC_HOST_NONROOT": "1"},
    )
    (output / "compose").symlink_to(data)
    (output / "inputs.json").write_text(
        json.dumps(
            {name: {"path": str(path), "sha256": sha(path)} for name, path in paths.items()},
            indent=2,
        )
        + "\n"
    )
    (output / "composed-path").write_text(str(data / "composed" / package) + "\n")
    return data / "composed" / package


def base_logging_contract(output, paths, node, composed):
    _ = (output, paths, node, composed)


def host_contract(output, paths, host_cc, node, composed):
    elf = ELF(paths["uia.so"].read_bytes())
    cells = elf.symbols["UIA_SYSTEM_UniqueCells"]["value"]

    def rules(index):
        _, count, address = struct.unpack("<3I", elf.virtual_data(cells + index * 12, 12))
        return [struct.unpack("<11I", elf.virtual_data(address + i * 44, 44)) for i in range(count)]

    disclaimer, continuation = rules(88), rules(238)
    if len(disclaimer) != 1 or len(continuation) != 13 or disclaimer[0][5] != 1012:
        raise ValueError("unexpected exact-v74 rule tables")
    fixture = "static const u32 disclaimer_rule[11]={" + ",".join(map(hex, disclaimer[0])) + "};\n"
    fixture += "static const u32 continuation_rules[13][11]={\n"
    fixture += "".join("{" + ",".join(map(hex, row)) + "},\n" for row in continuation) + "};\n"
    (output / "fixture.h").write_text(fixture)
    flags = []
    if sys.platform == "darwin":
        sdk = subprocess.check_output(
            ["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True
        ).strip()
        flags = ["-isysroot", sdk]
    run(
        [
            host_cc,
            *flags,
            "-std=c11",
            "-O1",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I" + str(ROOT / "cmu/features/disclaimer"),
            "-I" + str(output),
            ROOT / "tests/fixtures/native-contract.c",
            "-o",
            output / "host-contract",
        ],
        output,
        "host-compile",
    )
    run([output / "host-contract"], output, "host-contract")
    run([node, "--check", paths["system-app.js"]], output, "javascript-syntax")
    run(
        [
            node,
            ROOT / "tests/fixtures/system-hook-oem.js",
            paths["system-app.js"],
            ASSETS / "system-hook.js",
        ],
        output,
        "javascript-sources",
    )
    run(
        [
            node,
            ROOT / "tests/fixtures/disclaimer-behavior.js",
            paths["system-app.js"],
            paths["base-app.js"],
            paths["framework"],
            ROOT / "cmu/installer/system-hook.js",
        ],
        output,
        "javascript-lifecycle",
    )
    run(
        [
            node,
            ROOT / "tests/fixtures/carplay.js",
            ASSETS,
            paths["framework"].parent / "Websockets.js",
        ],
        output,
        "carplay-stock-routing",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--firmware", type=Path, required=True, help="private original filesystem tree"
    )
    parser.add_argument("--output", type=Path, required=True, help="fresh directory below runs/")
    parser.add_argument("--host-cc")
    parser.add_argument("--objdump")
    parser.add_argument("--node")
    args = parser.parse_args(argv)
    try:
        output = private_output(args.output)
        paths = inputs(args.firmware.resolve())
        input_pins = {name: sha(path) for name, path in paths.items()}
        host_cc = tool("clang", args.host_cc)
        objdump = tool("llvm-objdump", args.objdump)
        node = tool("node", args.node)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"checks not run: {exc}\n")

    output.mkdir(mode=0o700, parents=True)
    sources = [
        ROOT / "Makefile",
        ROOT / "tooling/package-usb.sh",
        ROOT / "tooling/open_connect/elf.py",
        Path(__file__).resolve(),
        ROOT / "LICENSE",
        ROOT / "tests/test_firmware.py",
        ROOT / "tests/fixtures/native-contract.c",
        ROOT / "tests/fixtures/disclaimer-behavior.js",
        ROOT / "tests/fixtures/system-hook-oem.js",
        ROOT / "tests/fixtures/carplay.js",
        *sorted((ROOT / "cmu/installer").rglob("*")),
        *sorted((ROOT / "cmu/features/disclaimer").glob("*.*")),
        ROOT / "cmu/startup/flush.c",
    ]
    pins = {}
    for path in sources:
        if path.is_file():
            name = str(path.relative_to(ROOT))
            pins[name] = sha(path)
            target = output / "sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    result = {
        "scope": "host C contract and ARM ELF inspection; no ARM execution, device access or durability proof",
        "source_sha256": pins,
        "input_sha256": input_pins,
        "passed": False,
    }
    try:
        composed = build(output, paths, host_cc)
        base_logging_contract(output, paths, node, composed)
        host_contract(output, paths, host_cc, node, composed)
        env = {
            **os.environ,
            "OC_FIRMWARE_CHECK_DIR": str(output),
            "OC_OBJDUMP": objdump,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        run(
            [sys.executable, "-m", "unittest", "-v", "tests.test_firmware"],
            output,
            "tests",
            cwd=ROOT,
            env=env,
        )
        if any(sha(ROOT / name) != digest for name, digest in pins.items()):
            raise ValueError("source changed during checks")
        if any(sha(paths[name]) != digest for name, digest in input_pins.items()):
            raise ValueError("original input changed during checks")
        result["passed"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"passed": result["passed"], "output": str(output), "error": result.get("error")}
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
