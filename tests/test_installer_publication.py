"""Interrupt the actual startup publisher using ordinary files and mount adapters."""

import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerPublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bin = self.root / "bin"
        self.tools = self.root / "tools"
        self.bin.mkdir()
        self.tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.tools / "flush"],
            check=True,
        )
        self.target = self.bin / "autostart"
        self.source = self.root / "planned"
        self.source.write_text("verified complete startup integration\nsecond line\n")
        self.stage = self.bin / (".open-connect-" + "b" * 32)
        self.mount = self.root / "mount"
        firmware = (ROOT / "cmu/installer/firmware.sh").read_text()
        self.firmware = self.root / "firmware.sh"
        self.firmware.write_text(firmware.replace("/usr/bin", str(self.bin)))
        self.driver = self.root / "driver.sh"
        self.driver.write_text(r"""
set -eu
umask 077
CUT=$1; P=$2; SOURCE=$3; FIRMWARE=$4; AUTOSTART=$5; PLAN=$6; MOUNT=$7
R_REV=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
. "$SOURCE/state.sh"
. "$FIRMWARE"
root_mode() { cat "$MOUNT"; }
remount() { printf '%s,noatime\n' "$1" > "$MOUNT"; }
flush() {
    "$P/flush" "$1" "$2" || fail flush_failed
    case "$CUT:$2" in
        flush:*/.open-connect-*) fail injected_flush_failure;;
        staged:*/.open-connect-*) sh -c 'kill -KILL "$PPID"' ;;
    esac
}
cat() {
    if test "$CUT:$1" = "partial:$PLAN"; then
        head -c 11 "$1"; sh -c 'kill -KILL "$PPID"'
    else command cat "$@"; fi
}
# The target BusyBox cp replaces an existing destination inode. A future
# regression to cp must not pass just because the host cp preserves it.
cp() { command rm -f "$2" && command cp "$@"; }
mv() {
    command mv "$@" || return
    test "$CUT" != renamed || sh -c 'kill -KILL "$PPID"' 
}
if test "$CUT" = guard; then startup_staging_guard; exit; fi
startup_publish "$PLAN" "755:$(id -u):$(id -g)" "$(sha "$AUTOSTART")" "$(stat -c '%a:%u:%g' "$AUTOSTART")"
""")
        self.reset()

    def reset(self):
        self.target.write_text("stock startup\n")
        self.target.chmod(0o755)
        self.mount.write_text("ro,noatime\n")

    def run_publish(self, cut="none", shell=None):
        return subprocess.run(
            (shell or ["sh"])
            + [
                self.driver,
                cut,
                self.tools,
                ROOT / "cmu/installer",
                self.firmware,
                self.target,
                self.source,
                self.mount,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )

    def fail_durability(self):
        real = self.tools / "flush-real"
        (self.tools / "flush").rename(real)
        (self.tools / "flush").write_text(
            '#!/bin/sh\nif test "$1" = h; then exec '
            + shlex.quote(str(real))
            + ' "$@"; fi\nexit 1\n'
        )
        (self.tools / "flush").chmod(0o700)

    @unittest.skipUnless(shutil.which("busybox"), "BusyBox required for ash trap regression")
    def test_ash_exit_trap_keeps_inputs_after_function_locals_unwind(self):
        for cut in ("none", "flush", "cleanup-flush"):
            with self.subTest(cut=cut):
                self.reset()
                if cut == "cleanup-flush":
                    self.fail_durability()
                result = self.run_publish(cut, [shutil.which("busybox"), "ash"])
                if cut == "none":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.target.read_text(), "stock startup\n")
                self.assertFalse(self.stage.exists())
                self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_handled_flush_failure_removes_owned_stage_and_restores_read_only(self):
        result = self.run_publish("flush")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.target.read_text(), "stock startup\n")
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_interrupted_copy_flush_and_rename_reuse_the_recorded_stage(self):
        for cut in ("partial", "staged", "renamed"):
            with self.subTest(cut=cut):
                self.reset()
                self.assertNotEqual(self.run_publish(cut).returncode, 0)
                if cut != "renamed":
                    self.assertTrue(self.stage.is_file())
                result = self.run_publish()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
                self.assertEqual(list(self.bin.glob(".open-connect-*")), [])
                self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_changed_stage_is_preserved_without_overwriting_target(self):
        self.stage.write_text("someone else's edit\n")
        result = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup_stage_changed", result.stderr)
        self.assertEqual(self.stage.read_text(), "someone else's edit\n")
        self.assertEqual(self.target.read_text(), "stock startup\n")
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_cleanup_flush_failure_still_restores_read_only(self):
        self.fail_durability()
        result = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("flush_failed", result.stderr)
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_unknown_legacy_stage_blocks_complete_removal(self):
        unknown = self.bin / ".open-connect-Ab12Cd"
        unknown.write_text("unverified bytes\n")
        self.assertNotEqual(self.run_publish("guard").returncode, 0)
        self.assertEqual(unknown.read_text(), "unverified bytes\n")
