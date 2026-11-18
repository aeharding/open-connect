"""Composition must stop at a failed native write, even in an OR-list caller."""

import hashlib
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
                "mmui-path",
                "mmui-sizes",
                "mmui-length",
                "mmui-pointer",
            ):
                (root / "packages" / package / (name + ".bin")).write_bytes(b"patch")
            wrapper = root / "tools/dd"
            wrapper.write_text(
                "#!/bin/sh\nset -eu\n"
                'n=$(cat "$COUNT"); n=$((n+1)); echo "$n" > "$COUNT"\n'
                'if test "$n" = "$FAIL_AT"; then exit 42; fi\n'
                + "exec "
                + shlex.quote(shutil.which("dd"))
                + ' "$@"\n'
            )
            wrapper.chmod(0o700)
            driver = (
                'set -eu\numask 077\nD=$1; . "$2/state.sh"; . "$2/firmware.sh"\n'
                # Synthetic fixtures enter immediately after input verification;
                # every composition write and its real caller context are intact.
                "verify_manifest() { :; }; originals_verify() { :; }\n"
                'compose "$3" || fail composition_failed\n'
            )
            for fail_at in range(1, 8):
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
                    self.assertIn("compose_patch_failed", result.stderr)
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
