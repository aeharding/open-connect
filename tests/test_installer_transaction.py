"""Interrupt the maintained transaction code around real file publications."""

import json
import os
import shlex
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
AUTOSTART=$D-target
. "$SOURCE/state.sh"
. "$SOURCE/transaction.sh"
uuid() { openssl rand -hex 16; }
root_mode() { printf 'ro,noatime\n'; }
cleanup_mount_guard() { test "$CUT" != mount; }
startup_staging_guard() { test "$CUT" != staging; }
dependency_path() { test "$1" = relevant && printf '%s\n' "$D-relevant"; }
dependencies_capture() { printf '%s  relevant\n' "$(sha "$D-relevant")"; }
nvram_read() { cat "$D-nvram"; }
nvram_change() {
    test "$(cat "$D-nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D-nvram"
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
    printf 'absent\n' > "$D-nvram"
    printf 'dependency\n' > "$D-relevant"
    R_BASE=$(state_capture - 0 0)
    R_BACKEND=$(printf '%064d' 0); R_CURRENT=$R_BASE; R_PHASE=removed
    R_BEFORE=-; R_AFTER=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
    record_write
    exit
fi
if test "$ACTION" = cleanup; then
    # Kill at actual durable-record and unlink boundaries, including after the
    # snapshots are gone and after the last record is unlinked.
    flush() {
        "$P/flush" "$1" "$2" || fail flush_failed
        if test "$CUT:$1:$2" = "purge:d:$D" && test -f "$D/record" &&
            test "$(cut -d '|' -f 2 "$D/record")" = purge; then kill -KILL $$; fi
    }
    rm() {
        command rm "$@" || return
        case "$CUT:$*" in
            entry:*-rf*) kill -KILL $$;;
            snapshots:*"$D/snapshots") kill -KILL $$;;
            record:"$D/record") kill -KILL $$;;
        esac
    }
    uninstall_cleanup
    exit
fi
record_read
if ! settled; then transaction_reconcile; exit; fi
case "$ACTION" in
install)
    printf 'installed\n' > "$D/installed"
    package=$(printf '%064d' 1)
    mkdir -p "$D/composed/$package"
    cp "$D/installed" "$D/composed/$package/autostart"
    after=$(snapshot_create "$D/installed" "$package" 1 1 disable "755:$(id -u):$(id -g)" "$D/snapshots/$R_CURRENT/dependencies")
    transaction_prepare install "$R_CURRENT" "$after";;
uninstall)
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    snapshot_read "$R_CURRENT"
    before=$(state_capture "$S_PACKAGE" "$S_TOUCH" "$S_WARNING")
    after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - 0 0 absent "755:$(id -u):$(id -g)" "$D/snapshots/$before/dependencies")
    transaction_prepare uninstall "$before" "$after";;
legacy-current)
    snapshot_read "$R_CURRENT"
    R_CURRENT=$(state_capture "$S_PACKAGE" "$S_TOUCH" "$S_WARNING")
    R_NOTICE=undone
    record_write
    exit;;
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

    def target(self, data, name):
        return data.with_name(data.name + "-" + name)

    def backend_fixture(self, data):
        runtime = self.root / "runtime"
        runtime.mkdir(mode=0o700)
        (runtime / "lock").touch()
        (runtime / "runtime").symlink_to(self.tools)
        for name in ("state.sh", "transaction.sh", "access.sh", "VERSION"):
            shutil.copyfile(ROOT / "cmu/installer" / name, self.tools / name)
        state = (
            (self.tools / "state.sh")
            .read_text()
            .replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
        )
        (self.tools / "state.sh").write_text(state)
        # Use the real backend and state/transaction code; replace only physical
        # firmware, NVRAM, mount, root-publication and reboot adapters.
        adapters = DRIVER[DRIVER.index("root_mode()") : DRIVER.index('if test "$ACTION" = init;')]
        (self.tools / "firmware.sh").write_text("CUT=none\nfirmware_guard() { :; }\n" + adapters)
        (self.tools / "flock").write_text("#!/bin/sh\nexit 0\n")
        (self.tools / "flock").chmod(0o700)
        script = (ROOT / "cmu/installer/backend.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(data),
            "/tmp/open-connect": str(runtime),
            "/usr/bin/autostart": str(self.target(data, "target")),
            "/sbin/reboot": "printf restarted > " + shlex.quote(str(self.root / "restarted")),
        }.items():
            script = script.replace(old, new)
        (self.tools / "backend.sh").write_text(script)

    def api(self, operation, revision="-"):
        result = subprocess.run(
            ["sh", self.tools / "backend.sh", "api", revision, operation, "-", "-", "-"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        return result, json.loads(result.stdout)

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
                        self.target(data, "target").read_text(),
                        "installed\n" if action == "install" else "stock\n",
                    )
                    self.assertEqual(
                        self.target(data, "nvram").read_text(),
                        "disable\n" if action == "install" else "absent\n",
                    )

    def test_interrupted_transaction_preserves_later_unknown_edit(self):
        data = self.create("later-edit")
        self.assertNotEqual(self.run_command(data, "install", "startup").returncode, 0)
        self.target(data, "target").write_text("someone else's later change\n")
        before = (data / "record").read_bytes()
        result = self.run_command(data, "install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup_changed", result.stderr)
        self.assertEqual(self.target(data, "target").read_text(), "someone else's later change\n")
        self.assertEqual(self.target(data, "nvram").read_text(), "absent\n")
        self.assertEqual((data / "record").read_bytes(), before)

    def test_uninstall_refuses_conflicting_changes_without_writes(self):
        for target in ("target", "nvram", "relevant"):
            with self.subTest(target=target):
                data = self.create("conflict-" + target)
                self.run_ok(data, "install")
                self.target(data, target).write_text("later edit\n")
                before = (data / "record").read_bytes()
                result = self.run_command(data, "uninstall")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("state_changed", result.stderr)
                self.assertEqual((data / "record").read_bytes(), before)
                self.assertEqual(self.target(data, target).read_text(), "later edit\n")

    def test_cleanup_resumes_after_each_durable_boundary_and_removes_everything(self):
        for cut in ("purge", "entry", "snapshots", "record"):
            with self.subTest(cut=cut):
                data = self.create("cleanup-" + cut)
                self.run_ok(data, "install")
                self.run_ok(data, "uninstall")
                (data / ".temporary").write_text("interrupted staging\n")
                (data / "outside-link").symlink_to(self.target(data, "relevant"))
                self.assertNotEqual(self.run_command(data, "cleanup", cut).returncode, 0)
                if cut == "record":
                    self.assertEqual(list(data.iterdir()), [])
                else:
                    self.assertEqual((data / "record").read_text().split("|")[1], "purge")
                self.run_ok(data, "cleanup")
                self.assertFalse(data.exists())
                self.assertEqual(self.target(data, "target").read_text(), "stock\n")
                self.assertEqual(self.target(data, "nvram").read_text(), "absent\n")
                self.assertEqual(self.target(data, "relevant").read_text(), "dependency\n")

    def test_cleanup_requires_verified_restoration(self):
        data = self.create("unverified")
        self.run_ok(data, "install")
        before = (data / "record").read_bytes()
        result = self.run_command(data, "cleanup")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not_removed", result.stderr)
        self.assertEqual((data / "record").read_bytes(), before)
        self.run_ok(data, "uninstall")
        self.target(data, "target").write_text("later edit\n")
        result = self.run_command(data, "cleanup")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("state_changed", result.stderr)
        self.assertTrue((data / "snapshots").is_dir())

    def test_missing_record_never_authorizes_deleting_nonempty_state(self):
        data = self.create("missing-record")
        (data / "record").unlink()
        result = self.run_command(data, "cleanup")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((data / "snapshots").is_dir())

    def test_cleanup_refuses_a_mounted_subtree(self):
        data = self.create("mounted")
        self.run_ok(data, "install")
        self.run_ok(data, "uninstall")
        before = (data / "record").read_bytes()
        result = self.run_command(data, "cleanup", "mount")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cleanup_mount_present", result.stderr)
        self.assertEqual((data / "record").read_bytes(), before)

    def test_cleanup_refuses_unknown_startup_staging_before_discarding_backups(self):
        data = self.create("staging")
        self.run_ok(data, "install")
        self.run_ok(data, "uninstall")
        result = self.run_command(data, "cleanup", "staging")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup_stage_changed", result.stderr)
        self.assertEqual((data / "record").read_text().split("|")[1], "removed")
        self.assertTrue((data / "snapshots").is_dir())

    def test_backend_uninstall_removes_state_and_can_request_restart_without_a_record(self):
        data = self.create("backend")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, state = self.api("status")
        self.assertTrue(state["installed"])
        result, removed = self.api("uninstall", state["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertFalse(removed["installed"])
        self.assertFalse(removed["retained"])
        self.assertTrue(removed["restart"])
        self.assertEqual(removed["revision"], "-")
        self.assertEqual(self.target(data, "target").read_text(), "stock\n")
        self.assertEqual(self.target(data, "nvram").read_text(), "absent\n")
        result, reply = self.api("restart")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(reply["ok"])

    def test_backend_reinstall_refuses_later_target_or_dependency_edits(self):
        data = self.create("reinstall-conflict")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        revision = (data / "record").read_text().split("|")[5]
        for name in ("target", "nvram", "relevant"):
            with self.subTest(changed=name):
                path = self.target(data, name)
                original = path.read_bytes()
                path.write_bytes(b"later external edit\n")
                before = {
                    str(p): (p.read_bytes(), p.stat().st_mode)
                    for p in data.rglob("*")
                    if p.is_file()
                }
                result, answer = self.api("install", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(answer, {"ok": False, "error": "state_changed"})
                self.assertEqual(path.read_bytes(), b"later external edit\n")
                self.assertEqual(
                    {
                        str(p): (p.read_bytes(), p.stat().st_mode)
                        for p in data.rglob("*")
                        if p.is_file()
                    },
                    before,
                )
                path.write_bytes(original)

    def test_backend_recovers_after_snapshots_or_record_have_been_deleted(self):
        for cut in ("snapshots", "record"):
            with self.subTest(cut=cut):
                data = self.create("backend-" + cut)
                self.run_ok(data, "install")
                self.run_ok(data, "uninstall")
                self.assertNotEqual(self.run_command(data, "cleanup", cut).returncode, 0)
                self.backend_fixture(data)
                result, state = self.api("status")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(state["pending"])
                result, reply = self.api("recover", state["revision"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(data.exists())
                self.assertTrue(reply["restart"])
                shutil.rmtree(self.root / "runtime")

    def test_backend_cleans_legacy_removed_state_without_offering_undo(self):
        data = self.create("legacy")
        self.run_ok(data, "install")
        checkpoint = (data / "record").read_text().split("|")[5]
        self.run_ok(data, "uninstall")
        fields = (data / "record").read_text().split("|")
        fields[8] = checkpoint  # v0.2.0-dev.1 retained an Undo checkpoint here.
        (data / "record").write_text("|".join(fields))
        self.backend_fixture(data)
        _, state = self.api("status")
        self.assertFalse(state["installed"])
        self.assertTrue(state["retained"])
        self.assertFalse(state["undo"])
        result, reply = self.api("uninstall", state["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertTrue(reply["restart"])

    def test_legacy_adopted_nvram_edit_is_refused_but_baseline_fallback_is_allowed(self):
        for value, allowed in (("enable", False), ("absent", True)):
            with self.subTest(value=value):
                data = self.create("legacy-nvram-" + value)
                self.run_ok(data, "install")
                # Model a value adopted by v0.2.0-dev.1 Undo. Its current record
                # matches the device, so targets_match alone cannot catch it.
                self.target(data, "nvram").write_text(value + "\n")
                self.run_ok(data, "legacy-current")
                self.backend_fixture(data)
                _, state = self.api("status")
                before = (data / "record").read_bytes()
                result, reply = self.api("uninstall", state["revision"])
                if allowed:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(data.exists())
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(reply["error"], "state_changed")
                    self.assertEqual((data / "record").read_bytes(), before)
                    self.assertEqual(self.target(data, "nvram").read_text(), "enable\n")
                shutil.rmtree(self.root / "runtime")

    def test_pending_legacy_uninstall_refuses_adopted_edits_even_after_restoration(self):
        for edit in ("nvram", "startup", "mode"):
            for restored in (False, True):
                with self.subTest(edit=edit, restored=restored):
                    data = self.create(f"legacy-pending-{edit}-{restored}")
                    self.run_ok(data, "install")
                    if edit == "nvram":
                        self.target(data, "nvram").write_text("enable\n")
                    elif edit == "startup":
                        self.target(data, "target").write_text("external startup\n")
                    else:
                        self.target(data, "target").chmod(0o700)
                    self.run_ok(data, "legacy-current")
                    # Legacy preparation accepts its adopted current snapshot.
                    # Stop before the new reconciliation ownership check runs.
                    self.assertNotEqual(
                        self.run_command(data, "uninstall", "prepared").returncode, 0
                    )
                    if restored:
                        self.target(data, "target").write_text("stock\n")
                        self.target(data, "target").chmod(0o755)
                        self.target(data, "nvram").write_text("absent\n")
                    before = (data / "record").read_bytes()
                    startup = self.target(data, "target").read_bytes()
                    mode = self.target(data, "target").stat().st_mode
                    nvram = self.target(data, "nvram").read_bytes()
                    self.backend_fixture(data)
                    _, state = self.api("status")
                    self.assertTrue(state["pending"])
                    result, reply = self.api("recover", state["revision"])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(reply["error"], "state_changed")
                    self.assertEqual((data / "record").read_bytes(), before)
                    self.assertEqual(self.target(data, "target").read_bytes(), startup)
                    self.assertEqual(self.target(data, "target").stat().st_mode, mode)
                    self.assertEqual(self.target(data, "nvram").read_bytes(), nvram)
                    shutil.rmtree(self.root / "runtime")
