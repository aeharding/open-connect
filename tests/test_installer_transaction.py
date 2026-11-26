"""Interrupt the maintained transaction code around real file publications."""

import fcntl
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
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
# SPDX-License-Identifier: AGPL-3.0-or-later
# Readable scalar choices for physical-adapter fixtures. Invoke the actual
# seven-argument writer with one canonical preferences payload; never installed.
fixture_snapshot() (
    local prefs= package=$2 dependencies=${7:--}
    if test "$dependencies" = /dev/null; then dependencies=-; fi
    if test "$package" != -; then
        prefs=$(printf 'OC2\nbase=%s\nmetadata=%s\nnvram=%s\npackage=%s\nservice.android-auto=1\nservice.pandora=%s\ntouch=%s\nwarning=%s\nwireless=%s' \
            "${10:-0}" "$6" "$5" "$package" "${9:-1}" "$3" "$4" "${11:-0}")
    fi
    snapshot_create "$1" "$package" "$5" "$6" "$dependencies" "${8:--}" "$prefs"
)

uuid() { openssl rand -hex 16; }
root_mode() { printf 'ro,noatime\n'; }
cleanup_mount_guard() { test "$CUT" != mount; }
startup_staging_guard() { test "$CUT" != staging; }
dependency_path() { test "$1" = relevant && printf '%s\n' "$D-relevant"; }
dependencies_capture() { printf '%s  relevant\n' "$(sha "$D-relevant")"; }
nvram_read() { cat "$D-nvram"; }
nvram_change() {
    printf '%s|%s\n' "$1" "$2" >> "$D-nvram-calls"
    test "$(cat "$D-nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D-nvram"
    test ! -e "$D-nvram-commit-fails" || return 1
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
    R_BASE=$(state_capture - - "")
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
service-off)
    snapshot_read "$R_CURRENT"
    prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" service.pandora 0 "$S_SCHEMA")
    after=$(snapshot_create "$AUTOSTART" "$S_PACKAGE" "$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$prefs")
    transaction_prepare set "$R_CURRENT" "$after";;
install)
    printf 'installed\n' > "$D/installed"
    package=$(cat "$D/package-id")
    mkdir -p "$D/composed/$package"
    cp "$D/installed" "$D/composed/$package/autostart"
    service_choice=1; base_choice=0; wireless_choice=0
    after=$(fixture_snapshot "$D/installed" "$package" 1 1 disable "755:$(id -u):$(id -g)" "$D/snapshots/$R_CURRENT/dependencies" - "$service_choice" "$base_choice" "$wireless_choice")
    transaction_prepare install "$R_CURRENT" "$after";;
uninstall)
    targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
    before=$R_CURRENT
    after=$(fixture_snapshot "$D/snapshots/$R_BASE/autostart" - 0 0 absent "755:$(id -u):$(id -g)" "$D/snapshots/$before/dependencies")
    transaction_prepare uninstall "$before" "$after";;
legacy-current)
    snapshot_read "$R_CURRENT"
    R_CURRENT=$(state_capture "$S_PACKAGE" "$D/snapshots/$R_CURRENT" "$S_PREFS")
    R_NOTICE=undone
    record_write
    exit;;
*) exit 64;;
esac
test "$CUT" != prepared || kill -KILL $$
transaction_reconcile
"""


def fixture_package(data, tools, selector=None):
    package = data / "packages/.new"
    package.mkdir(parents=True, mode=0o700)
    for name in ("state.sh", "preferences.awk", "services.tsv", "sm-profile.awk"):
        shutil.copyfile(ROOT / "cmu/installer" / name, package / name)
    shutil.copyfile(tools / "flush", package / "flush")
    (package / "flush").chmod(0o700)
    (package / "VERSION").write_text("0.3.0-dev.10-fixture\n")
    (package / "firmware.sh").write_text(
        "boot_render_profiles() {\n"
        ' config_decode "$2" || return 1\n'
        ' for name in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do printf "%s\\n" "$S_SERVICES" > "$1/$name"; done\n'
        "}\n"
    )
    if selector is not None:
        (package / "boot-select").write_bytes(selector)
        (package / "boot-select").chmod(0o700)
    manifest = "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
        for p in sorted(package.iterdir())
    )
    (package / "files.sha256").write_text(manifest)
    identity = hashlib.sha256(manifest.encode()).hexdigest()
    package.rename(package.with_name(identity))
    (data / "package-id").write_text(identity + "\n")
    return identity


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
        fixture_package(data, self.tools)
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

    def test_snapshot_writer_requires_every_named_program_in_verified_manifest(self):
        data = self.create("writer-members")
        original = data / "packages" / (data / "package-id").read_text().strip()
        record = (data / "record").read_bytes()
        snapshots = set((data / "snapshots").iterdir())
        for omitted in (
            "state.sh",
            "firmware.sh",
            "flush",
            "VERSION",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
        ):
            with self.subTest(omitted=omitted):
                package = data / "packages/.missing"
                shutil.copytree(original, package)
                manifest = "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(package.iterdir())
                    if p.name not in (omitted, "files.sha256")
                )
                (package / "files.sha256").write_text(manifest)
                identity = hashlib.sha256(manifest.encode()).hexdigest()
                package.rename(package.with_name(identity))
                result = subprocess.run(
                    [
                        "sh",
                        "-c",
                        'set -eu; umask 077; D=$1; P=$2; . "$3"; '
                        'after=$(snapshot_create "$D-target" "$4" disable '
                        '"755:$(id -u):$(id -g)" - - "") || exit 1',
                        "writer",
                        data,
                        self.tools,
                        ROOT / "cmu/installer/state.sh",
                        identity,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid_snapshot_package", result.stderr)
                self.assertEqual((data / "record").read_bytes(), record)
                self.assertEqual(set((data / "snapshots").iterdir()), snapshots)

    def backend_fixture(self, data):
        runtime = self.root / "runtime"
        runtime.mkdir(mode=0o700)
        (runtime / "lock").touch()
        (runtime / "runtime").symlink_to(self.tools)
        for name in (
            "state.sh",
            "transaction.sh",
            "service.sh",
            "access.sh",
            "VERSION",
            "preferences.awk",
            "services.tsv",
        ):
            shutil.copyfile(ROOT / "cmu/installer" / name, self.tools / name)
        state = (
            (self.tools / "state.sh")
            .read_text()
            .replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
        )
        state = state.replace("/tmp/open-connect", str(runtime))
        (self.tools / "state.sh").write_text(state)
        uptime = self.root / "uptime"
        uptime.write_text("100.00 0.00\n")
        service = self.tools / "service.sh"
        service.write_text(
            service.read_text()
            .replace("/tmp/open-connect", str(runtime))
            .replace("/proc/uptime", str(uptime))
        )
        # Use the real backend and state/transaction code; replace only physical
        # firmware, NVRAM, mount, root-publication and reboot adapters.
        adapters = DRIVER[DRIVER.index("root_mode()") : DRIVER.index('if test "$ACTION" = init;')]
        (self.tools / "firmware.sh").write_text(
            'CUT=none\nfirmware_guard() { :; }\nfactory_wireless() { test -f "$D-factory-wireless"; }\n'
            'native_log_inputs_verify() { test ! -e "$D-base-changed"; }\n' + adapters
        )
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
        (self.tools / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(self.tools.iterdir())
                if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
            )
        )

    def api(self, operation, revision="-", argument="-", expected="-", desired="-"):
        result = subprocess.run(
            [
                "sh",
                self.tools / "backend.sh",
                "api",
                revision,
                operation,
                argument,
                expected,
                desired,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        return result, json.loads(result.stdout)

    def test_service_preference_survives_other_settings_and_stale_requests(self):
        data = self.create("service-setting")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        self.assertFalse((self.tools / "sm-profile.awk").exists())
        self.assertEqual(status["pandora"], 1)
        old_targets = self.target(data, "target").read_bytes()
        result, status = self.api("set", status["revision"], "pandora", "1", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(status["pandora"], 0)
        self.assertTrue(status["restart"])
        self.assertEqual(self.target(data, "target").read_bytes(), old_targets)
        result, status = self.api("set", status["revision"], "warning", "1", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(status["pandora"], 0)
        record = (data / "record").read_bytes()
        result, error = self.api("set", status["revision"], "pandora", "1", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "stale_setting")
        self.assertEqual((data / "record").read_bytes(), record)
        result, status = self.api("uninstall", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertEqual(self.target(data, "target").read_text(), "stock\n")

    def test_pandora_only_change_never_invokes_failing_nvram_adapter(self):
        data = self.create("pandora-no-nvram")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        calls = self.target(data, "nvram-calls")
        calls.unlink()
        self.target(data, "nvram-commit-fails").touch()
        _, before = self.api("status")
        result, status = self.api("set", before["revision"], "pandora", "1", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((status["pandora"], status["touch"]), (0, 1))
        self.assertFalse(status["pending"])
        self.assertFalse(calls.exists())
        self.assertEqual(self.target(data, "nvram").read_text(), "disable\n")
        for revision in (before["revision"], status["revision"]):
            self.assertIn("nvram=disable\n", (data / "snapshots" / revision / "config").read_text())
        record = (data / "record").read_text().split("|")
        self.assertEqual(
            (record[1], record[5], record[6:8]), ("active", status["revision"], ["-", "-"])
        )
        _, fresh = self.api("status")
        self.assertEqual((fresh["pandora"], fresh["pending"]), (0, False))
        self.assertFalse(calls.exists())

    def test_interrupted_touch_change_recommits_when_actual_already_matches_after(self):
        data = self.create("touch-nvram-recommit")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        calls = self.target(data, "nvram-calls")
        calls.unlink()
        failing = self.target(data, "nvram-commit-fails")
        failing.touch()
        _, before = self.api("status")
        result, error = self.api("set", before["revision"], "touch", "1", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "nvram_commit_failed")
        self.assertEqual(self.target(data, "nvram").read_text(), "absent\n")
        self.assertEqual(calls.read_text().splitlines(), ["disable|absent"])
        record = (data / "record").read_bytes()
        fields = record.decode().split("|")
        self.assertEqual(
            (fields[1], fields[5], fields[6]), ("set", before["revision"], before["revision"])
        )
        for revision, value in ((fields[6], "disable"), (fields[7], "absent")):
            self.assertIn(
                f"nvram={value}\n", (data / "snapshots" / revision / "config").read_text()
            )
        _, pending = self.api("status")
        self.assertTrue(pending["pending"])
        result, error = self.api("recover", pending["revision"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "nvram_commit_failed")
        self.assertEqual(calls.read_text().splitlines(), ["disable|absent", "absent|absent"])
        self.assertEqual((data / "record").read_bytes(), record)
        failing.unlink()
        result, recovered = self.api("recover", pending["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((recovered["touch"], recovered["pending"]), (0, False))
        self.assertEqual(recovered["revision"], fields[7])
        self.assertEqual(
            calls.read_text().splitlines(), ["disable|absent", "absent|absent", "absent|absent"]
        )

    def test_pending_pandora_change_refuses_nvram_drift_then_recovers_without_writing(self):
        data = self.create("pandora-nvram-drift")
        self.run_ok(data, "install")
        self.assertNotEqual(self.run_command(data, "service-off", "prepared").returncode, 0)
        record = (data / "record").read_bytes()
        self.backend_fixture(data)
        calls = self.target(data, "nvram-calls")
        calls.unlink()
        self.target(data, "nvram-commit-fails").touch()
        self.target(data, "nvram").write_text("enable\n")
        _, pending = self.api("status")
        result, error = self.api("recover", pending["revision"])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "nvram_changed")
        self.assertEqual((data / "record").read_bytes(), record)
        self.assertEqual(self.target(data, "nvram").read_text(), "enable\n")
        self.assertFalse(calls.exists())
        self.target(data, "nvram").write_text("disable\n")
        result, recovered = self.api("recover", pending["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((recovered["pandora"], recovered["pending"]), (0, False))
        self.assertFalse(calls.exists())

    def test_wireless_choice_applied_status_and_other_choices_survive_until_uninstall(self):
        data = self.create("wireless-setting")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        self.assertEqual((status["wireless"], status["wirelessCurrent"]), (0, 0))
        self.assertFalse(status["wirelessFactory"])
        for key, before, after in (
            ("wireless", "0", "1"),
            ("pandora", "1", "0"),
            ("base", "0", "1"),
            ("warning", "1", "0"),
        ):
            result, status = self.api("set", status["revision"], key, before, after)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((status["wireless"], status["pandora"], status["base"]), (1, 0, 1))
        self.assertEqual(status["wirelessCurrent"], 0)
        config = data / "snapshots" / status["revision"] / "config"
        self.assertTrue(config.read_text().startswith("OC2\n"))
        runtime = self.root / "runtime"
        (runtime / "selected").write_text(status["revision"] + "\n")
        feature = runtime / "feature"
        feature.mkdir(mode=0o700)
        (feature / "wireless-applied").write_text("1\n")
        _, status = self.api("status")
        self.assertEqual(status["wirelessCurrent"], 1)
        self.assertFalse(status["wirelessFactory"])
        self.assertFalse(status["restart"])
        result, status = self.api("set", status["revision"], "wireless", "1", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((status["wireless"], status["wirelessCurrent"]), (0, 1))
        self.assertTrue(status["restart"])
        result, _ = self.api("uninstall", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertEqual(self.target(data, "target").read_text(), "stock\n")

    def test_factory_wireless_status_does_not_change_the_saved_override(self):
        data = self.create("factory-wireless")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        record = (data / "record").read_bytes()
        flag = self.root / "factory-wireless-factory-wireless"
        flag.touch()
        result, status = self.api("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(status["wirelessFactory"])
        self.assertEqual((status["wireless"], status["wirelessCurrent"]), (0, 0))
        self.assertEqual((data / "record").read_bytes(), record)
        flag.unlink()
        _, status = self.api("status")
        self.assertFalse(status["wirelessFactory"])

    def test_base_setting_preserves_service_and_other_choices_through_uninstall(self):
        data = self.create("base-setting")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        self.assertEqual(status["base"], 0)
        result, status = self.api("set", status["revision"], "pandora", "1", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        result, status = self.api("set", status["revision"], "base", "0", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((status["base"], status["pandora"]), (1, 0))
        result, status = self.api("set", status["revision"], "warning", "1", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((status["base"], status["pandora"]), (1, 0))
        self.assertIn("base=1\n", (data / "snapshots" / status["revision"] / "config").read_text())
        record = (data / "record").read_bytes()
        result, error = self.api("set", status["revision"], "base", "0", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "stale_setting")
        self.assertEqual((data / "record").read_bytes(), record)
        result, _ = self.api("uninstall", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertEqual(self.target(data, "target").read_text(), "stock\n")

    def test_rejected_base_inputs_leave_active_record_and_uninstall_usable(self):
        data = self.create("base-prerequisite")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        before = (data / "record").read_bytes()
        self.target(data, "base-changed").touch()
        result, error = self.api("set", status["revision"], "base", "0", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "base_inputs_changed")
        self.assertEqual((data / "record").read_bytes(), before)
        result, _ = self.api("uninstall", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())

    def test_uninstall_preserves_current_identity_and_five_field_stock_after_preparation(self):
        data = self.create("five-field-removal")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        current = status["revision"]
        original_flush = self.tools / "flush-real"
        (self.tools / "flush").rename(original_flush)
        armed = self.root / "interrupt-once"
        armed.touch()
        (self.tools / "flush").write_text(
            "#!/bin/sh\nset -eu\n"
            + shlex.quote(str(original_flush))
            + ' "$@"\n'
            + 'if test "$1" = d && test "$2" = '
            + shlex.quote(str(data))
            + " && test -f "
            + shlex.quote(str(armed))
            + ' && test "$(cut -d \'|\' -f 2 "$2/record")" = uninstall; then\n'
            + "rm "
            + shlex.quote(str(armed))
            + '; kill -KILL "$PPID"\nfi\n'
        )
        (self.tools / "flush").chmod(0o700)
        result = subprocess.run(
            ["sh", self.tools / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            capture_output=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        self.assertNotEqual(result.returncode, 0)
        fields = (data / "record").read_text().split("|")
        self.assertEqual(fields[1], "uninstall")
        self.assertEqual(fields[5], current)
        self.assertEqual(fields[6], current)
        self.assertEqual(
            len((data / "snapshots" / fields[7] / "config").read_text().strip().split("|")), 5
        )
        _, status = self.api("status")
        self.assertTrue(status["pending"])
        result, _ = self.api("recover", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data.exists())
        self.assertEqual(self.target(data, "target").read_text(), "stock\n")

    def test_interrupted_service_selection_keeps_conflicts_and_recovers_preference(self):
        data = self.create("service-recovery")
        self.run_ok(data, "install")
        self.assertNotEqual(self.run_command(data, "service-off", "prepared").returncode, 0)
        record = (data / "record").read_bytes()
        target = self.target(data, "target").read_bytes()
        dependency = self.target(data, "relevant")
        original = dependency.read_bytes()
        dependency.write_bytes(b"external edit\n")
        refused = self.run_command(data, "service-off")
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual((data / "record").read_bytes(), record)
        self.assertEqual(dependency.read_bytes(), b"external edit\n")
        dependency.write_bytes(original)
        self.run_ok(data, "service-off")
        current = (data / "record").read_text().split("|")[5]
        self.assertIn("service.pandora=0\n", (data / "snapshots" / current / "config").read_text())
        self.assertEqual(self.target(data, "target").read_bytes(), target)

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

    def test_status_distinguishes_installed_and_maintenance_versions(self):
        data = self.create("versions")
        package = data / "packages" / (data / "package-id").read_text().strip()
        self.run_ok(data, "install")
        self.backend_fixture(data)
        source_version = (self.tools / "VERSION").read_text().strip()
        self.assertNotEqual(source_version, "0.3.0-dev.10-fixture")
        result, state = self.api("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["version"], source_version)
        self.assertEqual(state["installedVersion"], "0.3.0-dev.10-fixture")
        (package / "VERSION").unlink()
        result, state = self.api("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["installedVersion"], "-")

    def test_settings_status_reads_each_distinct_snapshot_once(self):
        data = self.create("status-reads")
        self.run_ok(data, "install")
        applied = (data / "record").read_text().split("|")[5]
        self.run_ok(data, "service-off")
        current = (data / "record").read_text().split("|")[5]
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        state_file = self.tools / "state.sh"
        state_file.write_text(
            state_file.read_text().replace(
                'snapshot_read() { snapshot_verify "$1" && snapshot_decode "$1"; }',
                'snapshot_read() { printf "%s\\n" "$1" >> "$D/reads"; '
                'snapshot_verify "$1" && snapshot_decode "$1"; }',
            )
        )
        for selected in (current, applied):
            with self.subTest(selected=selected):
                (runtime / "selected").write_text(selected + "\n")
                (runtime / "access-selected").write_text(selected + "\n")
                (data / "reads").write_text("")
                result, status = self.api("status", argument="settings")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (data / "reads").read_text().splitlines(),
                    [current] if selected == current else [current, applied],
                )
                pandora = next(row for row in status["services"] if row["id"] == "pandora")
                self.assertEqual(pandora["saved"], 0)
                self.assertEqual(pandora["current"], int(selected == applied))
                self.assertEqual(status["restart"], selected != current)

    def test_settings_read_skips_flash_audit_but_usb_and_mutations_refuse_edits(self):
        data = self.create("status-guards")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        revision = (data / "record").read_text().split("|")[5]
        for target in ("target", "relevant"):
            with self.subTest(target=target):
                path = self.target(data, target)
                original = path.read_bytes()
                path.write_bytes(b"external edit\n")
                record = (data / "record").read_bytes()
                result, fast = self.api("status", argument="settings")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(fast["conflict"])
                self.assertFalse(fast["completionReady"])
                _, strict = self.api("status")
                self.assertTrue(strict["conflict"])
                for operation, args in (
                    ("set", ("warning", "1", "0")),
                    ("import", ()),
                    ("install", ()),
                    ("uninstall", ()),
                    ("restart", ()),
                ):
                    result, answer = self.api(operation, revision, *args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(answer["error"], "state_changed")
                    self.assertEqual((data / "record").read_bytes(), record)
                    self.assertEqual(path.read_bytes(), b"external edit\n")
                path.write_bytes(original)

    def test_fast_status_cannot_authorize_conflicted_completion(self):
        data = self.create("completion-conflict")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        record = (data / "record").read_text().split("|")
        record[11] = "12345678-1234-1234-1234-123456789abc"
        record[12] = "installed\n"
        (data / "record").write_text("|".join(record))
        kernel = self.root / "kernel"
        kernel.write_text(record[11] + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace("/proc/sys/kernel/random/boot_id", str(kernel))
        )
        (self.root / "runtime/selected").write_text(record[5] + "\n")
        for argument in ("completion",):
            result, ready = self.api("status", argument=argument)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(ready["completionReady"])
            for target in ("target", "relevant"):
                path = self.target(data, target)
                original = path.read_bytes()
                path.write_bytes(b"changed after boot\n")
                result, answer = self.api("status", argument=argument)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(answer["conflict"])
                self.assertFalse(answer["completionReady"])
                path.write_bytes(original)
        package = data / "packages" / (data / "package-id").read_text().strip()
        for name in ("VERSION", "services.tsv", "preferences.awk"):
            path = package / name
            original = path.read_bytes()
            path.write_bytes(original + b"edited\n")
            result, answer = self.api("status", argument="completion")
            self.assertFalse(answer.get("completionReady", False))
            if name == "VERSION":
                self.assertTrue(answer["conflict"] or answer["installedVersion"] == "-")
            else:
                self.assertNotEqual(result.returncode, 0)
            path.write_bytes(original)

    def test_completion_requires_selection_and_recorded_current_boot(self):
        data = self.create("completion")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        kernel = self.root / "kernel-boot"
        boot = "12345678-1234-1234-1234-123456789abc"
        kernel.write_text(boot + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace("/proc/sys/kernel/random/boot_id", str(kernel))
        )
        record = (data / "record").read_text().split("|")
        record[11] = boot
        record[12] = "installed\n"
        selected = runtime / "selected"
        selected.write_text(record[5] + "\n")
        (data / "record").write_text("|".join(record))
        for variant in (
            "ready",
            "previous-boot",
            "unselected",
            "no-notice",
            "invalid-kernel",
            "same-boot-commit",
        ):
            with self.subTest(variant=variant):
                current = record.copy()
                current[11] = "-" if variant == "same-boot-commit" else boot
                current[12] = "-\n" if variant == "no-notice" else "installed\n"
                (data / "record").write_text("|".join(current))
                kernel.write_text(
                    (
                        "87654321-1234-1234-1234-123456789abc"
                        if variant == "previous-boot"
                        else "invalid"
                        if variant == "invalid-kernel"
                        else boot
                    )
                    + "\n"
                )
                selected.write_text(("0" * 64 if variant == "unselected" else record[5]) + "\n")
                before = (data / "record").read_bytes()
                result, status = self.api("status", argument="completion")
                if variant == "unselected":
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(status["error"], "invalid_selected_snapshot")
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(status["completionReady"], variant == "ready")
                self.assertEqual((data / "record").read_bytes(), before)

    def test_completion_uses_volatile_identity_when_kernel_uuid_repeats(self):
        data = self.create("repeated-completion")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        kernel = self.root / "kernel-boot"
        raw = "f7a1f4aa-1234-1234-1234-123456789abc"
        kernel.write_text(raw + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace("/proc/sys/kernel/random/boot_id", str(kernel))
        )
        fields = (data / "record").read_text().split("|")
        fields[12] = "installed\n"
        (runtime / "selected").write_text(fields[5] + "\n")
        marker = runtime / "boot-id"
        first = "12345678-1234-1234-1234-123456789abc"
        second = "87654321-1234-1234-1234-123456789abc"
        for token, recorded, ready in (
            (first, first, True),
            (second, first, False),  # New kernel; installation was not selected.
            (second, second, True),
            (second, raw, False),  # Repeated raw UUID must never rescue a mismatch.
            (None, raw, True),  # New USB serving a live dev.19 installation.
            (None, second, False),
            ("invalid", raw, False),
            (raw + "\n", raw, False),
        ):
            with self.subTest(token=token, recorded=recorded):
                marker.unlink(missing_ok=True)
                if token is not None:
                    marker.symlink_to(token)
                fields[11] = recorded
                (data / "record").write_text("|".join(fields))
                before = (data / "record").read_bytes()
                result, status = self.api("status", argument="completion")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(status["completionReady"], ready)
                self.assertEqual((data / "record").read_bytes(), before)
        marker.unlink()
        marker.write_text(raw + "\n")  # A regular file is not a legacy absence.
        fields[11] = raw
        (data / "record").write_text("|".join(fields))
        result, status = self.api("status", argument="completion")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(status["completionReady"])
        self.assertEqual(kernel.read_text(), raw + "\n")

    def test_fast_completion_audit_uses_volatile_identity_with_repeated_kernel_uuid(self):
        data = self.create("fast-repeated-completion")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        raw = "f7a1f4aa-1234-1234-1234-123456789abc"
        kernel = self.root / "kernel-boot"
        kernel.write_text(raw + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace("/proc/sys/kernel/random/boot_id", str(kernel))
        )
        fields = (data / "record").read_text().split("|")
        fields[12] = "installed\n"
        (runtime / "selected").write_text(fields[5] + "\n")
        marker = runtime / "boot-id"
        for token in (
            "12345678-1234-1234-1234-123456789abc",
            "87654321-1234-1234-1234-123456789abc",
        ):
            with self.subTest(volatile_boot=token):
                marker.unlink(missing_ok=True)
                marker.symlink_to(token)
                fields[11] = token
                (data / "record").write_text("|".join(fields))
                before = (data / "record").read_bytes()
                result, ready = self.api("status", argument="completion")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(ready["completionReady"])
                self.assertFalse(ready["conflict"])
                for target in ("target", "relevant"):
                    with self.subTest(changed=target):
                        path = self.target(data, target)
                        original = path.read_bytes()
                        path.write_bytes(b"external edit after selected boot\n")
                        try:
                            result, refused = self.api("status", argument="completion")
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertTrue(refused["conflict"])
                            self.assertFalse(refused["completionReady"])
                            self.assertEqual(
                                path.read_bytes(), b"external edit after selected boot\n"
                            )
                            self.assertEqual((data / "record").read_bytes(), before)
                        finally:
                            path.write_bytes(original)
                self.assertEqual(os.readlink(marker), token)
                self.assertEqual(kernel.read_text(), raw + "\n")

    def test_completion_identity_failure_cannot_bypass_audit_on_a_second_read(self):
        data = self.create("single-completion-proof")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        fields = (data / "record").read_text().split("|")
        fields[11] = "12345678-1234-1234-1234-123456789abc"
        fields[12] = "installed\n"
        (data / "record").write_text("|".join(fields))
        (self.root / "runtime/selected").write_text(fields[5] + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace(
                "completion_boot_id() {",
                "completion_boot_id() {\n"
                ' local reads; IFS= read -r reads < "$D/identity-reads"\n'
                ' reads=$((reads+1)); printf "%s\\n" "$reads" > "$D/identity-reads"\n'
                ' printf "%s\\n" "$R_BOOT"\n'
                ' test "$reads" -gt 1; return $?\n',
            )
        )
        for argument in ("completion",):
            with self.subTest(argument=argument):
                (data / "identity-reads").write_text("0\n")
                before = (data / "record").read_bytes()
                result, denied = self.api("status", argument=argument)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(denied["completionReady"])
                self.assertEqual((data / "identity-reads").read_text(), "1\n")
                _, ready = self.api("status", argument=argument)
                self.assertTrue(ready["completionReady"])
                self.assertEqual((data / "identity-reads").read_text(), "2\n")
                dependency = self.target(data, "relevant")
                original = dependency.read_bytes()
                dependency.write_bytes(b"external edit\n")
                try:
                    _, refused = self.api("status", argument=argument)
                    self.assertTrue(refused["conflict"])
                    self.assertFalse(refused["completionReady"])
                finally:
                    dependency.write_bytes(original)
                self.assertEqual((data / "record").read_bytes(), before)

    def test_status_refuses_an_unreadable_authority_fingerprint(self):
        data = self.create("authority-read-failure")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        module = self.tools / "state.sh"
        module.write_text(
            module.read_text().replace("sha() {", "raw_sha() {", 1)
            + '\nsha() { test "$1" != "$D/record" || return 1; raw_sha "$@"; }\n'
        )
        result, answer = self.api("status")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(answer["error"], "state_changed")
        self.assertNotIn("installed", answer)

    def test_status_refuses_malformed_authority_digests_on_either_sample(self):
        data = self.create("authority-shape")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        module = self.tools / "state.sh"
        original = module.read_text().replace("sha() {", "raw_sha() {", 1)
        for value in ("", "a" * 63, "g" * 64, "A" * 64):
            for sample in (1, 2):
                with self.subTest(value=value, sample=sample):
                    counter = self.root / "hash-count"
                    counter.write_text("0\n")
                    module.write_text(
                        original
                        + '\nsha() { if test "$1" = "$D/record"; then '
                        + f"n=$(cat {shlex.quote(str(counter))}); n=$((n+1)); "
                        + f'printf "%s\\n" "$n" > {shlex.quote(str(counter))}; '
                        + f'if test "$n" = {sample}; then printf "%s\\n" '
                        + shlex.quote(value)
                        + '; return 0; fi; fi; raw_sha "$@"; }\n'
                    )
                    result, answer = self.api("status")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(answer, {"ok": False, "error": "state_changed"})

    def test_installed_settings_keep_selected_program_catalog_and_refuse_new_package_writes(self):
        data = self.create("selected-package")
        self.run_ok(data, "install")
        selected = (data / "record").read_text().split("|")[5]
        old_package = (data / "package-id").read_text().strip()
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        (runtime / "selected").write_text(selected + "\n")
        result, before = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result, saved = self.api("set", before["revision"], "warning", "1", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(saved["warning"], 0)
        _, same_package = self.api("status", argument="settings")
        self.assertEqual(same_package["warning"], 0)

        successor = data / "packages/.successor"
        shutil.copytree(data / "packages" / old_package, successor)
        (successor / "VERSION").write_text("0.3.0-successor\n")
        catalog = successor / "services.tsv"
        catalog.write_text(catalog.read_text().replace("Pandora", "Successor Pandora"))
        marker = self.root / "successor-interpreter-ran"
        interpreter = successor / "preferences.awk"
        interpreter.write_text(f'BEGIN {{ system("touch {marker}") }}\n' + interpreter.read_text())
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(successor.iterdir())
            if p.name != "files.sha256"
        )
        (successor / "files.sha256").write_text(manifest)
        package = hashlib.sha256(manifest.encode()).hexdigest()
        successor.rename(successor.with_name(package))
        (data / "package-id").write_text(package + "\n")
        self.run_ok(data, "install")
        fields = (data / "record").read_text().split("|")
        fields[3] = package
        (data / "record").write_text("|".join(fields))
        marker.unlink()
        for argument in ("settings", "-"):
            result, view = self.api("status", argument=argument)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(view["revision"], fields[5])
            self.assertTrue(view["restart"])
            self.assertEqual(view["installedVersion"], before["installedVersion"])
            self.assertEqual(view["warning"], 1)
            self.assertIn("Pandora", [row["label"] for row in view["services"]])
            self.assertNotIn("Successor Pandora", [row["label"] for row in view["services"]])
            self.assertFalse(marker.exists())
        expected = (data / "record").read_bytes()
        for operation, args in (("set", ("warning", "1", "0")), ("import", ())):
            result, answer = self.api(operation, fields[5], *args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(answer["error"], "restart_required")
            self.assertEqual((data / "record").read_bytes(), expected)
            self.assertFalse(marker.exists())
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        result, view = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(view["installedVersion"], "0.3.0-successor")
        self.assertFalse(marker.exists())

    def test_usb_metadata_never_runs_catalog_probe_or_flash_audit(self):
        data = self.create("usb-metadata")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        with (self.tools / "firmware.sh").open("a") as target:
            target.write("\nfactory_wireless() { exit 99; }\n")
        with (self.tools / "state.sh").open("a") as target:
            target.write("\nsnapshot_decode() { exit 98; }\n")
        self.target(data, "relevant").write_text("physical conflict\n")
        result, metadata = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(metadata["installedVersion"], "0.3.0-dev.10-fixture")
        self.assertTrue(metadata["installed"])
        self.assertFalse(metadata["completionReady"])
        self.assertNotIn("services", metadata)
        package = data / "packages" / (data / "package-id").read_text().strip()
        version = (package / "VERSION").read_bytes()
        (package / "VERSION").write_text("unverified-version\n")
        result, error = self.api("status", argument="settings")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "invalid_version")
        (package / "VERSION").write_bytes(version)
        config = data / "snapshots" / metadata["revision"] / "config"
        original = config.read_bytes()
        config.write_bytes(original + b"unknown=1\n")
        result, error = self.api("status", argument="settings")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "invalid_snapshot")
        config.write_bytes(original)
        (data / "record").unlink()
        result, error = self.api("status", argument="settings")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "invalid_record")
        shutil.rmtree(data)
        data.mkdir(mode=0o700)
        result, empty = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(empty["pending"])
        self.assertFalse(empty["installed"])

    def test_installed_dismiss_acknowledges_verified_record_without_audit(self):
        data = self.create("dismiss-no-audit")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        fields = (data / "record").read_text().split("|")
        fields[12] = "installed\n"
        (data / "record").write_text("|".join(fields))
        with (self.tools / "transaction.sh").open("a") as target:
            target.write("\ntargets_match_loaded() { exit 99; }\n")
        result, answer = self.api("dismiss", fields[5])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(answer, {"ok": True})
        self.assertEqual((data / "record").read_text().split("|")[12], "-\n")
        self.assertTrue((self.tools / "closed").exists())
        result, status = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(status["notice"], "-")

    def real_flock(self):
        flock = self.tools / "flock"
        flock.write_text(
            f"#!{sys.executable}\nimport fcntl,sys\n"
            "flags=fcntl.LOCK_UN if '-u' in sys.argv else "
            "(fcntl.LOCK_SH if '-s' in sys.argv else fcntl.LOCK_EX)\n"
            "if '-n' in sys.argv: flags|=fcntl.LOCK_NB\n"
            "try: fcntl.flock(int(sys.argv[-1]),flags)\n"
            "except OSError: sys.exit(1)\n"
        )
        flock.chmod(0o700)

    def delayed_status(self, name):
        data = self.create(name)
        self.run_ok(data, "install")
        self.backend_fixture(data)
        self.real_flock()
        transaction = self.tools / "transaction.sh"
        transaction.write_text(
            transaction.read_text().replace(
                "targets_match_loaded() {",
                "targets_match_loaded() {\n"
                ' if test "${operation:-}" = status && test "${argument:-}" != settings; then\n'
                '  printf ready > "$D-audit-started"; local count=0\n'
                '  while test ! -f "$D-audit-go"; do\n'
                '   count=$((count+1)); test "$count" -lt 2000 || return 1; sleep 0.01\n'
                "  done\n"
                " fi",
                1,
            )
        )
        process = subprocess.Popen(
            ["sh", self.tools / "backend.sh", "api", "-", "status", "-", "-", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        gate = self.target(data, "audit-go")

        def cleanup():
            gate.touch()
            try:
                process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.communicate(timeout=3)

        self.addCleanup(cleanup)
        deadline = time.monotonic() + 5
        while not self.target(data, "audit-started").exists():
            self.assertIsNone(process.poll(), "audit exited before the barrier")
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        return data, process, gate

    def test_restart_response_keeps_writer_excluded_until_bounded_reboot_handoff(self):
        data = self.create("restart-writer-lock")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        self.real_flock()
        backend = self.tools / "backend.sh"
        reboot = self.root / "reboot.py"
        # The host adapter enforces the same finite timeout as BusyBox on target.
        timeout = self.root / "timeout.py"
        timeout.write_text(
            "import subprocess,sys\n"
            "assert sys.argv[1:3] == ['timeout', '-t']\n"
            "assert sys.argv[3] == '10'\n"
            "try: sys.exit(subprocess.run(sys.argv[4:], timeout=0.2).returncode)\n"
            "except subprocess.TimeoutExpired: sys.exit(124)\n"
        )
        source = backend.read_text()
        start = self.root / "delay-started"
        gate = self.root / "reboot-go"
        delay = (
            f"touch {shlex.quote(str(start))}; n=0; "
            f"while test ! -f {shlex.quote(str(gate))}; do "
            'n=$((n+1)); test "$n" -lt 500 || exit 1; sleep 0.01; done'
        )
        source = source.replace("sleep 2;", delay + ";")
        source = source.replace(
            "/bin/busybox", shlex.quote(sys.executable) + " " + shlex.quote(str(timeout))
        )
        source = source.replace(
            "printf restarted > " + shlex.quote(str(self.root / "restarted")),
            shlex.quote(sys.executable) + " " + shlex.quote(str(reboot)),
        )
        backend.write_text(source)
        fields = (data / "record").read_text().split("|")
        expected = (data / "record").read_bytes()
        for behavior in ("return", "fail", "hang"):
            with self.subTest(behavior=behavior):
                start.unlink(missing_ok=True)
                gate.unlink(missing_ok=True)
                reboot.write_text(
                    "import sys,time\n"
                    + ("time.sleep(5)\n" if behavior == "hang" else "")
                    + ("sys.exit(1)\n" if behavior == "fail" else "")
                )
                result, answer = self.api("restart", fields[5])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(answer["ok"])
                try:
                    deadline = time.monotonic() + 2
                    while not start.exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(0.01)
                    # A complete second backend write must fail before prepare.
                    result, answer = self.api("uninstall", fields[5])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(answer["error"], "busy")
                    self.assertEqual((data / "record").read_bytes(), expected)
                finally:
                    gate.touch()
                deadline = time.monotonic() + 3
                with (self.root / "runtime/lock").open("r+") as lock:
                    while True:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            self.assertLess(time.monotonic(), deadline)
                            time.sleep(0.01)

    def test_failed_usb_writer_allows_removal_and_replacement_recovery(self):
        data = self.create("usb-failed-writer")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        fields = (data / "record").read_text().split("|")
        failure = self.target(data, "nvram-commit-fails")
        failure.touch()
        result, answer = self.api("uninstall", fields[5])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(answer["error"], "nvram_commit_failed")
        self.assertEqual((data / "record").read_text().split("|")[1], "uninstall")
        self.assertFalse(os.path.lexists(self.tools / "admitted"))
        self.api("dismiss", argument="usb")
        # Exercise the actual stop and replacement branches. Only the native
        # listener and its Linux /proc retirement adapter are replaced on host.
        service = self.tools / "service.sh"
        with service.open("a") as target:
            target.write(
                "\nstop_listener() { :; }\n"
                'service_listen() { service_config "$2"; ln -sfn "$1" "$service_runtime"; }\n'
            )
        usb = (ROOT / "cmu/installer/usb-service.sh").read_text()
        usb = usb.replace("/tmp/open-connect", str(runtime))
        usb = usb.replace("/tmp/mnt/data_persist/open-connect", str(data))
        usb = usb.replace("retire) retire;;", "retire) exit 0;;")
        (self.tools / "usb-service.sh").write_text(usb)
        sessions = runtime / "sessions"
        sessions.mkdir(mode=0o700)
        old = sessions / "session-old"
        self.tools.rename(old)
        self.tools = old
        (runtime / "usb-runtime").unlink()
        (runtime / "usb-runtime").symlink_to(old)
        env = {**os.environ, "PATH": str(old) + os.pathsep + os.environ["PATH"]}
        stopped = subprocess.run(
            ["sh", old / "usb-service.sh", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertFalse((runtime / "usb-runtime").exists())
        replacement = self.root / "replacement"
        shutil.copytree(old, replacement)
        (replacement / "closed").unlink()
        (replacement / "api").write_text("#!/bin/sh\nexit 0\n")
        (replacement / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(replacement.iterdir())
                if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
            )
        )
        started = subprocess.run(
            ["sh", replacement / "usb-service.sh"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.tools = Path(started.stdout.strip())
        _, pending = self.api("status", argument="settings")
        self.assertTrue(pending["pending"])
        self.assertFalse(pending["completionReady"])
        failure.unlink()
        result, recovered = self.api("recover", pending["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(data.exists())
        self.assertFalse(recovered["pending"])
        self.assertTrue(recovered["restart"])
        self.assertTrue((self.tools / "admitted").is_symlink())

    def test_successful_usb_removal_retains_bounded_readback_and_restart(self):
        data = self.create("usb-success-retention")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        runtime = self.root / "runtime"
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        revision = (data / "record").read_text().split("|")[5]
        result, _ = self.api("uninstall", revision)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(data.exists())
        admitted = self.tools / "admitted"
        lease = os.readlink(admitted)
        self.assertEqual(lease, "OCUSB1|22000|-")
        self.api("dismiss", argument="usb")
        result, readback = self.api("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(readback["installed"])
        self.assertFalse(readback["pending"])
        for malformed in (lease + "\n", lease + "|extra", "OCUSB1|999999|-", "", "OCUSB1|22000|a"):
            admitted.unlink()
            if malformed:
                admitted.symlink_to(malformed)
            else:
                admitted.touch()  # Legacy empty markers have no authority.
            result, error = self.api("restart")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(error["error"], "session_closed")
        admitted.unlink()
        admitted.symlink_to(lease)
        (self.root / "uptime").write_text("220.00 0.00\n")
        result, error = self.api("restart")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(error["error"], "session_closed")
        (self.root / "uptime").write_text("219.99 0.00\n")
        result, answer = self.api("restart")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(answer["ok"])

    def test_usb_writer_outlives_expired_lease_and_refreshes_it_at_success(self):
        data = self.create("usb-writer-expired-lease")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        self.real_flock()
        runtime = self.root / "runtime"
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        current = (data / "record").read_text().split("|")[5]
        (self.tools / "admitted").symlink_to(f"OCUSB1|10001|{current}")
        adapter = self.tools / "firmware.sh"
        adapter.write_text(
            adapter.read_text().replace(
                "nvram_change() {",
                "nvram_change() {\n"
                ' printf ready > "$D-writer-started"; local count=0\n'
                ' while test ! -f "$D-writer-go"; do\n'
                '  count=$((count+1)); test "$count" -lt 1000 || return 1; sleep 0.01\n'
                " done\n",
            )
        )
        writer = subprocess.Popen(
            ["sh", self.tools / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        gate = self.target(data, "writer-go")
        try:
            deadline = time.monotonic() + 5
            while not self.target(data, "writer-started").exists():
                self.assertIsNone(writer.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            (self.root / "uptime").write_text("1000.00 0.00\n")
            self.assertFalse(os.path.lexists(self.tools / "admitted"))
            prepared = (data / "record").read_bytes()
            self.assertEqual(prepared.decode().split("|")[1], "uninstall")
            result, error = self.api("recover", prepared.decode().split("|")[2])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(error["error"], "busy")
            self.assertEqual((data / "record").read_bytes(), prepared)
        finally:
            gate.touch()
            out, err = writer.communicate(timeout=10)
        self.assertEqual(writer.returncode, 0, out + err)
        self.assertTrue(json.loads(out)["ok"])
        self.assertEqual(os.readlink(self.tools / "admitted"), "OCUSB1|112000|-")

    def test_slow_audit_allows_an_unchanged_exclusive_settings_reader(self):
        _, process, gate = self.delayed_status("concurrent-read")
        backend = self.tools / "backend.sh"
        source = backend.read_text()
        lock = (
            'if test "$operation:$argument" = status:settings; then flock -n -s 9 || fail busy\n'
            "else flock -n -x 9 || fail busy; fi"
        )
        self.assertIn(lock, source)
        # The old installed reader takes an exclusive lock. Merely changing the
        # new audit to a shared lock would still block this exact behavior.
        legacy = source.replace(lock, "flock -n -x 9 || fail busy")
        result = subprocess.run(
            ["sh", "-c", legacy, str(backend), "api", "-", "status", "settings", "-", "-"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["installed"])
        self.assertIsNone(process.poll())
        self.assertFalse(gate.exists())
        gate.touch()
        out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, out + err)

    def test_audit_discards_a_changed_authoritative_record(self):
        data, process, gate = self.delayed_status("changed-audit-record")
        with (self.root / "runtime/lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record = data / "record"
            fields = record.read_text().split("|")
            fields[2] = "f" * 32
            pending = data / "record-test-new"
            pending.write_text("|".join(fields))
            pending.chmod(0o600)
            pending.replace(record)
        expected = record.read_bytes()
        gate.touch()
        out, _ = process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(json.loads(out)["error"], "busy")
        self.assertEqual(record.read_bytes(), expected)

    def test_audit_discards_a_retired_runtime(self):
        _, process, gate = self.delayed_status("retired-audit-runtime")
        pointer = self.root / "runtime/runtime"
        with (self.root / "runtime/lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pointer.unlink()
            pointer.symlink_to(self.root / "successor")
        gate.touch()
        out, _ = process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(json.loads(out)["error"], "session_replaced")

    def test_usb_cancel_closes_only_its_own_session(self):
        data = self.create("usb-cancel-notice")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        pointer = self.root / "runtime/runtime"
        pointer.unlink()
        (self.root / "runtime/usb-runtime").symlink_to(self.tools)
        expected = (data / "record").read_bytes()
        result, answer = self.api("dismiss", argument="usb")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(answer, {"ok": True})
        self.assertTrue((self.tools / "closed").exists())
        self.assertEqual((data / "record").read_bytes(), expected)
        self.assertFalse(os.path.lexists(self.tools / "admitted"))
        result, answer = self.api("install", (data / "record").read_text().split("|")[5])
        self.assertEqual(answer["error"], "session_closed")
        self.assertEqual((data / "record").read_bytes(), expected)

    def test_definite_prewrite_refusal_releases_its_volatile_admission(self):
        data = self.create("usb-refused-admission")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        (self.root / "runtime/runtime").unlink()
        (self.root / "runtime/usb-runtime").symlink_to(self.tools)
        expected = (data / "record").read_bytes()
        result, answer = self.api("install", "f" * 64)
        self.assertEqual(answer["error"], "stale_state")
        self.assertFalse(os.path.lexists(self.tools / "admitted"))
        self.assertEqual((data / "record").read_bytes(), expected)

    def test_selection_markers_require_the_complete_canonical_file(self):
        data = self.create("selection-markers")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        resources = data / "access-fixture"
        resources.mkdir(mode=0o700)
        (resources / "runlogin").write_text("synthetic login\n")
        (resources / "sshd.conf").write_text("synthetic sshd\n")
        (resources / "access").write_text(
            f"1|0|-|755:{os.getuid()}:{os.getgid()}|644:{os.getuid()}:{os.getgid()}|-\n"
        )
        subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; D=$1; P=$2; . "$P/state.sh"; . "$P/firmware.sh"; '
                'record_read; snapshot_read "$R_CURRENT"; '
                'R_CURRENT=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$S_PACKAGE" '
                '"$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$3" "$S_PREFS"); '
                "record_write",
                "access-snapshot",
                data,
                self.tools,
                resources,
            ],
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        current = (data / "record").read_text().split("|")[5]
        runtime = self.root / "runtime"
        for name in ("selected", "access-selected"):
            (runtime / name).write_text(current + "\n")
        _, valid = self.api("status", argument="settings")
        self.assertEqual(valid["uartCurrent"], 1)
        self.assertFalse(valid["restart"])
        invalid = (
            current + "\nextra\n",
            current + "\n\n",
            current,
            current + "0\n",
            current.upper() + "\n",
            "",
            "g" * 64 + "\n",
        )
        for name in ("selected", "access-selected"):
            marker = runtime / name
            for content in invalid:
                with self.subTest(marker=name, content=content):
                    marker.write_text(content)
                    result, status = self.api("status", argument="settings")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if name == "selected":
                        self.assertTrue(status["restart"])
                        self.assertTrue(all(r["current"] is None for r in status["services"]))
                    else:
                        self.assertEqual(status["uart"], 1)
                        self.assertEqual(status["uartCurrent"], 0)
            marker.write_text(current + "\n")

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
