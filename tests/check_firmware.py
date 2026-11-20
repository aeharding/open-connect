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
    """The maintained target guard is the authority for original-file hashes."""
    rows = subprocess.check_output(
        ["sh", "-c", '. "$1"; firmware_dependencies', "check", ASSETS / "firmware.sh"],
        text=True,
    )
    paths = {}
    for line in rows.splitlines():
        digest, name, target = line.split()
        source = firmware / target.removeprefix("/")
        if sha(source) != digest:
            raise ValueError("unsupported exact original: " + target)
        paths[name] = source
    guard = (ASSETS / "firmware.sh").read_text()
    for name, target in (
        ("framework", "/jci/gui/framework/js/GuiFramework.js"),
        ("display", "/jci/lvds/lvds_service"),
    ):
        pattern = r"md5sum < " + re.escape(target) + r"""\)" = '([a-f0-9]{32})  -'"""
        expected = re.findall(pattern, guard)
        source = firmware / target.removeprefix("/")
        if len(expected) != 1 or hashlib.md5(source.read_bytes()).hexdigest() != expected[0]:
            raise ValueError("unsupported exact original: " + target)
        paths[name] = source
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


def build(output, paths):
    run(["make", "release", "OUT=" + str(output / "build")], output, "make", cwd=ROOT)
    source = output / "build/usb/open-connect"
    package = sha(source / "files.sha256")
    data = output / "compose"
    for name in ("originals", "packages", "composed", "tools"):
        (data / name).mkdir(mode=0o700, parents=True)
    # The manager is a dependency, not an original needed for composition.
    for name, path in paths.items():
        if name not in ("manager.so", "framework", "display"):
            shutil.copyfile(path, data / "originals" / name)
            (data / "originals" / name).chmod(0o600)
    shutil.copytree(source, data / "packages" / package)
    for name in ("stat", "readlink"):
        if shutil.which("g" + name):
            (data / "tools" / name).symlink_to(shutil.which("g" + name))
    env = {**os.environ, "PATH": str(data / "tools") + os.pathsep + os.environ["PATH"]}
    run(
        [
            "sh",
            "-c",
            'set -eu; D=$1; P=$2; . "$3/state.sh"; . "$3/firmware.sh"; '
            'flush() { :; }; compose "$4"',
            "check",
            data,
            source,
            ASSETS,
            package,
        ],
        output,
        "compose",
        env=env,
    )
    (output / "inputs.json").write_text(
        json.dumps(
            {name: {"path": str(path), "sha256": sha(path)} for name, path in paths.items()},
            indent=2,
        )
        + "\n"
    )
    (output / "composed-path").write_text(str(data / "composed" / package) + "\n")
    return data / "composed" / package


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
    run([node, "--check", composed / "system-app.js"], output, "javascript-syntax")
    run(
        [
            node,
            ROOT / "tests/fixtures/disclaimer-behavior.js",
            composed / "system-app.js",
            paths["base-app.js"],
        ],
        output,
        "javascript-lifecycle",
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
        *sorted((ROOT / "cmu/installer").rglob("*")),
        *sorted((ROOT / "cmu/features/disclaimer").glob("*.*")),
        ROOT / "cmu/features/touch/setting.sh",
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
        composed = build(output, paths)
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
