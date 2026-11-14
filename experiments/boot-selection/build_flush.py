#!/usr/bin/env python3
"""Build the small Linux ARM EABI helper into a caller-selected local directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).with_name("flush.c")


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    clang = os.environ.get("CC") or shutil.which("clang")
    linker = os.environ.get("OC_LLD") or shutil.which("ld.lld")
    if not linker:
        mac_linker = Path("/opt/homebrew/opt/lld/bin/ld.lld")
        if mac_linker.is_file():
            linker = str(mac_linker)
    if not clang or not linker:
        raise RuntimeError("clang and ld.lld are required; set CC / OC_LLD if needed")
    target = output / "flush-arm"
    command = [
        clang, "--target=armv7-linux-gnueabi", "-marm", "-mfloat-abi=soft",
        "-Os", "-ffreestanding", "-fno-stack-protector", "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables", "-nostdlib", "-static",
        "-Wall", "-Wextra", "-Werror", "--ld-path=" + linker,
        "-Wl,-e,_start,--build-id=none,-z,max-page-size=4096,--strip-all",
        str(SOURCE.resolve()), "-o", str(target.resolve()),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    (output / "stdout.txt").write_text(result.stdout)
    (output / "stderr.txt").write_text(result.stderr)
    result.check_returncode()
    data = target.read_bytes()
    if data[:7] != b"\x7fELF\x01\x01\x01" or int.from_bytes(data[18:20], "little") != 40:
        raise RuntimeError("expected a little-endian ELF32 ARM executable")
    record = dict(command=command, source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
