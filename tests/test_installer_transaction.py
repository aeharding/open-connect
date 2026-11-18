"""Interrupt the maintained transaction code around real file publications."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DRIVER = r"""
set -eu
umask 077
D=$1; P=$2; SOURCE=$3; ACTION=$4; CUT=${5:-none}
AUTOSTART=$D/target
. "$SOURCE/state.sh"
. "$SOURCE/transaction.sh"
uuid() { openssl rand -hex 16; }
dependency_path() { test "$1" = relevant && printf '%s\n' "$D/relevant"; }
dependencies_capture() { printf '%s  relevant\n' "$(sha "$D/relevant")"; }
nvram_read() { cat "$D/nvram"; }
nvram_change() {
    test "$(cat "$D/nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D/nvram"
    test "$CUT" != nvram || kill -KILL $$
}
startup_publish() {
    test "$(sha "$AUTOSTART")" = "$3" && test "$(stat -c '%a:%u:%g' "$AUTOSTART")" = "$4" || return 1
    cp "$1" "$AUTOSTART.next"; metadata "$2"
    chown "$S_UID:$S_GID" "$AUTOSTART.next"; chmod "$S_MODE" "$AUTOSTART.next"
    mv "$AUTOSTART.next" "$AUTOSTART"
    test "$CUT" != startup || kill -KILL $$
}
if test "$ACTION" = init; then
    printf 'stock\n' > "$AUTOSTART"; chmod 755 "$AUTOSTART"
    printf 'absent\n' > "$D/nvram"
    printf 'dependency\n' > "$D/relevant"
    R_BASE=$(state_capture - 0 0)
    R_BACKEND=$(printf '%064d' 0); R_CURRENT=$R_BASE; R_PHASE=removed
    R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
    record_write
    exit
fi
record_read
if ! settled; then transaction_reconcile; exit; fi
case "$ACTION" in
install)
    printf 'installed\n' > "$D/installed"
    package=$(printf '%064d' 1)
    after=$(snapshot_create "$D/installed" "$package" 1 1 disable "755:$(id -u):$(id -g)" "$D/snapshots/$R_CURRENT/dependencies")
    transaction_prepare install "$R_CURRENT" "$after";;
uninstall)
    snapshot_read "$R_CURRENT"
    before=$(state_capture "$S_PACKAGE" "$S_TOUCH" "$S_WARNING")
    after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - 0 0 absent "755:$(id -u):$(id -g)" "$D/snapshots/$before/dependencies")
    transaction_prepare uninstall "$before" "$after";;
undo) undo_prepare;;
*) exit 64;;
esac
test "$CUT" != prepared || kill -KILL $$
transaction_reconcile
"""


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerTransaction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.tools = self.root / "tools"
        self.tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.tools / "flush"],
            check=True,
        )
        self.driver = self.root / "driver.sh"
        self.driver.write_text(DRIVER)

    def create(self, name):
        data = self.root / name
        data.mkdir(mode=0o700)
        (data / "snapshots").mkdir(mode=0o700)
        self.run_ok(data, "init")
        return data

    def run_command(self, data, action, cut="none"):
        return subprocess.run(
            ["sh", self.driver, data, self.tools, ROOT / "cmu/installer", action, cut],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )

    def run_ok(self, *args):
        result = self.run_command(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_interrupted_install_and_uninstall_complete_from_each_target_boundary(self):
        for action in ("install", "uninstall"):
            for cut in ("prepared", "startup", "nvram"):
                with self.subTest(action=action, cut=cut):
                    data = self.create(action + cut)
                    if action == "uninstall":
                        self.run_ok(data, "install")
                    self.assertNotEqual(self.run_command(data, action, cut).returncode, 0)
                    self.assertEqual((data / "record").read_text().split("|")[1], action)
                    self.run_ok(data, action)
                    self.assertEqual(
                        (data / "target").read_text(),
                        "installed\n" if action == "install" else "stock\n",
                    )
                    self.assertEqual(
                        (data / "nvram").read_text(),
                        "disable\n" if action == "install" else "absent\n",
                    )

    def test_interrupted_transaction_preserves_later_unknown_edit(self):
        data = self.create("later-edit")
        self.assertNotEqual(self.run_command(data, "install", "startup").returncode, 0)
        (data / "target").write_text("someone else's later change\n")
        before = (data / "record").read_bytes()
        result = self.run_command(data, "install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup_changed", result.stderr)
        self.assertEqual((data / "target").read_text(), "someone else's later change\n")
        self.assertEqual((data / "nvram").read_text(), "absent\n")
        self.assertEqual((data / "record").read_bytes(), before)

    def test_conflicting_uninstall_can_undo_exact_as_found_bytes_and_mode(self):
        data = self.create("conflict")
        self.run_ok(data, "install")
        (data / "target").write_text("unknown modified startup\n")
        (data / "target").chmod(0o750)
        (data / "relevant").write_text("modified dependency\n")
        (data / "nvram").write_text("enable\n")
        self.run_ok(data, "uninstall")
        self.assertEqual((data / "target").read_text(), "stock\n")
        self.assertEqual((data / "nvram").read_text(), "absent\n")
        self.run_ok(data, "undo")
        self.assertEqual((data / "target").read_text(), "unknown modified startup\n")
        self.assertEqual((data / "target").stat().st_mode & 0o777, 0o750)
        self.assertEqual((data / "nvram").read_text(), "enable\n")
        self.assertEqual((data / "relevant").read_text(), "modified dependency\n")

    def test_undo_refuses_later_target_or_retained_dependency_changes_without_writes(self):
        for target in ("target", "nvram", "relevant"):
            with self.subTest(target=target):
                data = self.create("undo-" + target)
                self.run_ok(data, "install")
                self.run_ok(data, "uninstall")
                (data / target).write_text("later edit\n")
                before = {p.name: p.read_bytes() for p in data.iterdir() if p.is_file()}
                result = self.run_command(data, "undo")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(
                    {p.name: p.read_bytes() for p in data.iterdir() if p.is_file()}, before
                )
