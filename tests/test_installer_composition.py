"""Composition must stop at a failed native write, even in an OR-list caller."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


class InstallerComposition(unittest.TestCase):
    def test_supported_mod_backups_remain_bound_to_the_first_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            originals = root / "originals"
            originals.mkdir(mode=0o700)
            (root / "snapshots").mkdir(mode=0o700)
            board = root / "board.sh"
            startup = root / "autostart"
            startup.write_bytes(b"synthetic startup\n")
            board.write_bytes(b"synthetic mod A\n")
            mod_a = hashlib.sha256(board.read_bytes()).hexdigest()
            mod_b = hashlib.sha256(b"synthetic mod B\n").hexdigest()
            stock = hashlib.sha256(b"synthetic stock board\n").hexdigest()
            # Only replace the private source hashes with ordinary test files.
            # Copy, hashing, source guards and snapshot verification stay real.
            firmware = root / "firmware.sh"
            firmware.write_text(
                (ASSETS / "firmware.sh")
                .read_text()
                .replace("f9f52effa73fa63810aa9bcb76a54835e150c3779dd1a2c649e9c6571ff1ffb1", mod_a)
                .replace("7f2b8747ee5f85015ce6bc8c128239c7d0bc06cbf6bfdbbcbb1be7bf43e13121", mod_b)
            )
            tools = root / "tools"
            tools.mkdir()
            for name in ("stat", "readlink"):
                if shutil.which("g" + name):
                    (tools / name).symlink_to(shutil.which("g" + name))
            driver = r"""
set -eu
D=$1; STOCK=$4; . "$2/state.sh"; . "$3"
flush() { :; }
original_files() {
    printf '%s autostart %s\n' "$(sha "$D/autostart")" "$D/autostart"
    printf '%s board.sh %s\n' "$STOCK" "$D/board.sh"
}
firmware_dependencies() { original_files; }
supported_dependencies
rmdir "$D/originals"
originals_save
test "$(sha "$D/originals/board.sh")" = "$(sha "$D/board.sh")"
dependencies_capture - > "$D/dependencies"
R_BASE=$(snapshot_create "$D/autostart" - 0 0 absent "700:$(id -u):$(id -g)" "$D/dependencies")
originals_verify
# Even a second recognized mod cannot replace the saved original after capture.
printf 'synthetic mod B\n' > "$D/originals/board.sh"
if originals_verify; then exit 1; fi
cp "$D/board.sh" "$D/originals/board.sh"
originals_verify
# The recognized digest belongs only to its named firmware component.
if supported_original "$4" sm.conf "$(sha "$D/board.sh")"; then exit 1; fi
printf 'unknown later edit\n' > "$D/board.sh"
if supported_dependencies; then exit 1; fi
originals_verify
"""
            result = subprocess.run(
                ["sh", "-c", driver, "test", root, ASSETS, firmware, stock],
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(board.read_bytes(), b"unknown later edit\n")
            self.assertEqual((originals / "board.sh").read_bytes(), b"synthetic mod A\n")

    def test_wcp_dependency_resolves_without_accepting_unknown_paths(self):
        driver = (
            'set -eu; . "$1/state.sh"; . "$1/firmware.sh"\n'
            "dependency_path root/sm_WCP.conf\n"
            "for name in root/not_known.conf root/../sm_WCP.conf root//sm_WCP.conf; do\n"
            '    if dependency_path "$name"; then exit 1; fi\n'
            "done\n"
        )
        result = subprocess.run(
            ["sh", "-c", driver, "test", ASSETS], capture_output=True, text=True, check=True
        )
        self.assertEqual(result.stdout, "/jci/sm/sm_WCP.conf\n")

    def test_each_failed_patch_write_refuses_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name in ("originals", "packages", "composed", "tools"):
                (root / name).mkdir(mode=0o700)
            for name in ("uia.so", "mmui.so"):
                (root / "originals" / name).write_bytes(b"synthetic original\n")
            package = "a" * 64
            (root / "packages" / package).mkdir()
            for name in (
                "native",
                "branch",
                "sizes",
                "layout",
                "mmui-path",
                "mmui-sizes",
                "mmui-length",
                "mmui-pointer",
                "mmui-count-pointer",
            ):
                (root / "packages" / package / (name + ".bin")).write_bytes(b"patch")
            shutil.copyfile(
                ROOT / "cmu/features/disclaimer/layout.txt",
                root / "packages" / package / "layout.txt",
            )
            for command in ("dd", "head", "tail"):
                wrapper = root / "tools" / command
                wrapper.write_text(
                    "#!/bin/sh\nset -eu\n"
                    'n=$(cat "$COUNT"); n=$((n+1)); echo "$n" > "$COUNT"\n'
                    'if test "$n" = "$FAIL_AT"; then exit 42; fi\n'
                    + "exec "
                    + shlex.quote(shutil.which(command))
                    + ' "$@"\n'
                )
                wrapper.chmod(0o700)
            backend = (ASSETS / "backend.sh").read_text().splitlines()
            error_handler = next(line for line in backend if line.startswith("fail()"))
            invocation = next(
                line for line in backend if line.lstrip().startswith('compose "$package"')
            )
            driver = (
                'set -eu\numask 077\nD=$1; . "$2/state.sh"; . "$2/firmware.sh"\n'
                # Synthetic fixtures enter immediately after input verification;
                # every composition write and its real caller context are intact.
                "verify_manifest() { :; }; originals_verify() { :; }\n"
                + error_handler
                + "\npackage=$3\n"
                + invocation
                + "\n"
            )
            # Prefix/gap/tail, payload/branch/sizes, every ELF layout word,
            # and all six MMUI writes must fail closed in the backend caller.
            for fail_at in range(1, 30):
                with self.subTest(write=fail_at):
                    (root / "count").write_text("0\n")
                    result = subprocess.run(
                        ["sh", "-c", driver, "test", root, ASSETS, package],
                        env={
                            **os.environ,
                            "PATH": str(root / "tools") + os.pathsep + os.environ["PATH"],
                            "COUNT": str(root / "count"),
                            "FAIL_AT": str(fail_at),
                        },
                        text=True,
                        capture_output=True,
                        timeout=10,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        json.loads(result.stdout), {"ok": False, "error": "composition_failed"}
                    )
                    self.assertEqual((root / "count").read_text().strip(), str(fail_at))
                    self.assertFalse((root / "composed" / package).exists())

    def test_manager_is_captured_and_resolved_as_a_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            manager = root / "manager.so"
            manager.write_bytes(b"synthetic manager\n")
            firmware = root / "firmware.sh"
            firmware.write_text(
                (ASSETS / "firmware.sh")
                .read_text()
                .replace("/jci/lib/libjciuiamgr.so", str(manager))
            )
            driver = (
                'set -eu\n. "$1/state.sh"; . "$2"\n'
                "original_files() { :; }\ndependencies_capture -\ndependency_path root/manager.so\n"
            )
            result = subprocess.run(
                ["sh", "-c", driver, "test", ASSETS, firmware],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                result.stdout.splitlines(),
                [
                    hashlib.sha256(manager.read_bytes()).hexdigest() + "  root/manager.so",
                    str(manager),
                ],
            )
