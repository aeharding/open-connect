"""Interrupt the maintained transaction code around real file publications."""

import atexit
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HOST_API_CACHE = None


def compile_host_api():
    """Compile host api once per test process under ASan+UBSan."""
    global _HOST_API_CACHE
    if _HOST_API_CACHE is not None and _HOST_API_CACHE.is_file():
        return _HOST_API_CACHE
    cache_dir = Path(tempfile.mkdtemp(prefix="oc-host-api-"))
    atexit.register(shutil.rmtree, cache_dir, True)
    binary = cache_dir / "api"
    core = ROOT / "cmu/installer/core"
    srcs = [
        ROOT / "cmu/installer/api.c",
        core / "oc-hash.c",
        core / "oc-io.c",
        core / "oc-manifest.c",
        core / "oc-record.c",
        core / "oc-config.c",
        core / "oc-guard.c",
        core / "oc-api.c",
    ]
    subprocess.run(
        [
            "clang",
            "-DOC_HOST",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            *(str(s) for s in srcs),
            "-o",
            str(binary),
        ],
        check=True,
    )
    binary.chmod(0o700)
    _HOST_API_CACHE = binary
    return binary


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
startup_staging_retire() { :; }
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
    printf '%s\n' "${OC_TEST_NVRAM:-absent}" > "$D-nvram"
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
    R_BACKEND=$package
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
        self.host_tools = self.root / "host-tools"
        self.host_tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
            (self.host_tools / "stat").symlink_to(shutil.which("gstat"))
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.tools / "flush"],
            check=True,
        )
        shutil.copyfile(compile_host_api(), self.tools / "api")
        (self.tools / "api").chmod(0o700)
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
            env={
                **os.environ,
                "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
                "OC_TEST_NVRAM": getattr(self, "base_nvram", "absent"),
            },
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
        self._backend_data = data
        runtime = self.root / "runtime"
        runtime.mkdir(mode=0o700)
        (runtime / "lock").touch()
        (runtime / "runtime").symlink_to(self.tools)
        if (data / "record").exists():
            fields = (data / "record").read_text().split("|")
            if fields[1] not in ("removed", "purge"):
                (runtime / "selected").write_text(fields[5] + "\n")
        for name in (
            "state.sh",
            "transaction.sh",
            "service.sh",
            "usb-service.sh",
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
        usb = self.tools / "usb-service.sh"
        usb.write_text(usb.read_text().replace("/tmp/open-connect", str(runtime)))
        # Use the real backend and state/transaction code; replace only physical
        # firmware, NVRAM, mount, root-publication and reboot adapters.
        adapters = DRIVER[DRIVER.index("root_mode()") : DRIVER.index('if test "$ACTION" = init;')]
        fw_src = (ROOT / "cmu/installer/firmware.sh").read_text()
        manifest_exact_fn = fw_src[
            fw_src.index("manifest_exact() {") : fw_src.index("composed_members_verify() {")
        ]
        (self.tools / "firmware.sh").write_text(
            'CUT=none\nfirmware_guard() { :; }\nfactory_wireless() { test -f "$D-factory-wireless"; }\n'
            'native_log_inputs_verify() { test ! -e "$D-base-changed"; }\n'
            'touch_inputs_verify() { test ! -e "$D-touch-changed"; }\n'
            + manifest_exact_fn
            + adapters
        )
        (self.tools / "flock").write_text("#!/bin/sh\nexit 0\n")
        (self.tools / "flock").chmod(0o700)
        # Runtime staging gives non-product fixtures mode 0600. Retain the
        # host lock adapter outside that packet, including real_flock rewrites.
        (self.host_tools / "flock").unlink(missing_ok=True)
        os.link(self.tools / "flock", self.host_tools / "flock")
        script = (ROOT / "cmu/installer/backend.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(data),
            "/tmp/open-connect": str(runtime),
            "/usr/bin/autostart": str(self.target(data, "target")),
            "/sbin/reboot": "printf restarted > " + shlex.quote(str(self.root / "restarted")),
        }.items():
            script = script.replace(old, new)
        (self.tools / "backend.sh").write_text(script)
        backend_manifest = None
        if (data / "record").exists():
            rec_fields = (data / "record").read_text().split("|")
            candidate = data / "packages" / rec_fields[3] / "files.sha256"
            if rec_fields[1] == "active" and candidate.is_file():
                backend_manifest = candidate
        if backend_manifest is not None:
            shutil.copyfile(backend_manifest, self.tools / "files.sha256")
        else:
            (self.tools / "files.sha256").write_text(
                "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(self.tools.iterdir())
                    if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
                )
            )

    def host_api_env(self, data=None, *, host_tools=None):
        data_dir = (
            data if data is not None else getattr(self, "_backend_data", self.root / "absent")
        )
        return {
            **os.environ,
            "PATH": os.pathsep.join(
                str(path)
                for path in (host_tools, self.tools, self.host_tools, os.environ["PATH"])
                if path
            ),
            "OC_HOST_DATA": str(data_dir),
            "OC_HOST_RAM": str(self.root / "runtime"),
            "OC_HOST_SKIP_FW_GUARD": "1",
            "OC_HOST_WIRELESS_FILE": f"{data_dir}-factory-wireless",
        }

    def api(
        self, operation, revision="-", argument="-", expected="-", desired="-", *, host_tools=None
    ):
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
            # Keep host adapters available after staging a replacement runtime.
            env=self.host_api_env(host_tools=host_tools),
        )
        return result, json.loads(result.stdout)

    def test_all_six_touch_transitions_for_each_baseline_nvram(self):
        for baseline in ("absent", "enable", "disable"):
            with self.subTest(baseline=baseline):
                self.base_nvram = baseline
                data = self.create("touch-" + baseline)
                self.run_ok(data, "install")
                self.backend_fixture(data)
                _, status = self.api("status")
                for before, after in zip((1, 0, 2, 1, 2, 0), (0, 2, 1, 2, 0, 1), strict=True):
                    calls = self.target(data, "nvram-calls")
                    calls.write_text("")
                    old_value = "disable" if before == 1 else baseline
                    wanted = "disable" if after == 1 else baseline
                    result, status = self.api(
                        "set", status["revision"], "touch", str(before), str(after)
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(status["touch"], after)
                    self.assertEqual(
                        calls.read_text(),
                        "" if old_value == wanted else old_value + "|" + wanted + "\n",
                    )
                    self.assertEqual(self.target(data, "nvram").read_text(), wanted + "\n")
                result, _ = self.api("uninstall", status["revision"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.target(data, "nvram").read_text(), baseline + "\n")
                shutil.rmtree(self.root / "runtime")

    def test_selectorless_oc2_fallback_refuses_extra_package_file(self):
        data = self.create("selectorless-extra")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        package_id = (data / "package-id").read_text().strip()
        package_dir = data / "packages" / package_id
        _, status = self.api("status")
        rev = status["revision"]
        record_before = (data / "record").read_bytes()
        # Clean control: no-op touch 1->1 succeeds.
        res_noop_clean, out_noop_clean = self.api("set", rev, "touch", "1", "1")
        self.assertEqual(
            res_noop_clean.returncode, 0, res_noop_clean.stdout + res_noop_clean.stderr
        )
        self.assertTrue(out_noop_clean["ok"])
        self.assertEqual((data / "record").read_bytes(), record_before)
        self.assertEqual(self.target(data, "nvram").read_text(), "disable\n")
        # Extra ordinary file in selector-less OC2 package refuses both no-op and touch 1->0
        # with state_changed, preserving byte-identical OC1 and unchanged NVRAM.
        extra = package_dir / "stray-file"
        extra.write_text("stray\n")
        for desired in ("1", "0"):
            with self.subTest(extra_desired=desired):
                res, out = self.api("set", rev, "touch", "1", desired)
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(out["error"], "state_changed")
                self.assertEqual((data / "record").read_bytes(), record_before)
                self.assertEqual(self.target(data, "nvram").read_text(), "disable\n")
        extra.unlink()
        # Clean control: changing touch 1->0 succeeds and clears NVRAM.
        res_clean, out_clean = self.api("set", rev, "touch", "1", "0")
        self.assertEqual(res_clean.returncode, 0, res_clean.stdout + res_clean.stderr)
        self.assertTrue(out_clean["ok"])
        self.assertEqual(out_clean["touch"], 0)
        self.assertEqual(self.target(data, "nvram").read_text(), "absent\n")

    def test_touch_pin_refusal_before_prepare_leaves_exit_and_uninstall_usable(self):
        data = self.create("touch-pin-refusal")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, status = self.api("status")
        before = (data / "record").read_bytes()
        self.target(data, "touch-changed").touch()
        result, error = self.api("set", status["revision"], "touch", "1", "2")
        self.assertEqual(error["error"], "touch_inputs_changed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((data / "record").read_bytes(), before)
        self.target(data, "touch-changed").unlink()
        result, status = self.api("set", status["revision"], "touch", "1", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.target(data, "touch-changed").touch()
        result, status = self.api("set", status["revision"], "touch", "2", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        result, _ = self.api("uninstall", status["revision"])
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_operation_replies_do_not_repeat_their_physical_verification(self):
        data = self.create("operation-audits")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        backend = self.tools / "backend.sh"
        backend.write_text(backend.read_text().replace("set -eu\n", "set -eux\n", 1))

        def counted(operation, *args, passes, dep_passes=None):
            if dep_passes is None:
                dep_passes = passes
            result, answer = self.api(operation, *args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for function, expected in (
                ("targets_match_loaded", passes),
                ("dependencies_match", dep_passes),
            ):
                self.assertEqual(
                    len(re.findall(r"^\++ " + function + r" ", result.stderr, re.M)),
                    expected,
                    (operation, function),
                )
            return answer

        before = counted("status", passes=1)
        counted("status", "-", "settings", passes=0)
        saved = counted("set", before["revision"], "pandora", "1", "0", passes=2, dep_passes=2)
        row = next(row for row in saved["services"] if row["id"] == "pandora")
        self.assertEqual((row["saved"], row["current"]), (0, 1))
        self.assertTrue(saved["restart"])
        self.assertEqual(saved, counted("status", passes=1))
        second = counted("set", saved["revision"], "warning", "1", "0", passes=2, dep_passes=2)
        self.assertEqual((second["pandora"], second["warning"]), (0, 0))
        self.assertNotEqual(second["revision"], saved["revision"])
        # A no-op is already validated by admission, with no new transaction.
        record = (data / "record").read_bytes()
        counted("set", second["revision"], "warning", "0", "0", passes=1)
        self.assertEqual((data / "record").read_bytes(), record)
        ack = counted("restart", second["revision"], passes=1)
        self.assertEqual(ack, {"ok": True, "restarting": True})
        self.assertEqual((data / "record").read_bytes(), record)

    def test_settings_status_replaces_only_scalar_openssl_calls_with_verified_flush(self):
        data = self.create("scalar-settings")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        # Exercise the maintained factory-board guard too, with a host script
        # standing in for the pinned OEM script and its successful return code.
        board = self.root / "get_board_type.sh"
        board.write_text("#!/bin/sh\nexit 2\n")
        factory = (ROOT / "cmu/installer/firmware.sh").read_text()
        factory = factory[
            factory.index("factory_wireless() (") : factory.index("originals_verify()")
        ]
        factory = factory.replace("/jci/scripts/get_board_type.sh", str(board)).replace(
            "2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da",
            hashlib.sha256(board.read_bytes()).hexdigest(),
        )
        firmware = self.tools / "firmware.sh"
        firmware.write_text(firmware.read_text() + "\n" + factory)
        calls = self.root / "digest-calls"
        openssl = shlex.quote(shutil.which("openssl"))
        real_flush = self.root / "flush-real"
        (self.tools / "flush").rename(real_flush)
        for name, program in (("openssl", openssl), ("flush", shlex.quote(str(real_flush)))):
            path = self.tools / name
            path.write_text(
                "#!/bin/sh\n"
                + f"printf '%s|%s\\n' {name} \"$*\" >> {shlex.quote(str(calls))}\n"
                + f'exec {program} "$@"\n'
            )
            path.chmod(0o700)
        module = self.tools / "state.sh"
        candidate = module.read_text()
        scalar = 'sha() { "$P/flush" h "$1"; }\nsha_many() { "$P/flush" H "$@"; }'
        self.assertIn(scalar, candidate)
        module.write_text(
            candidate.replace(
                scalar,
                'sha() { local value; value=$(openssl dgst -sha256 < "$1") || return; '
                'printf "%s\\n" "${value##* }"; }\n'
                'sha_many() { openssl dgst -sha256 -r "$@"; }',
                1,
            )
        )
        before_record = (data / "record").read_bytes()
        result, answer = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(answer["ok"])
        self.assertTrue(answer["installed"])
        self.assertEqual((data / "record").read_bytes(), before_record)
        # Native api handles status:settings in-process with zero openssl or flush subprocesses.
        self.assertFalse(calls.exists())

    def test_one_line_and_metadata_boundary_regressions(self):
        data = self.create("one-line-bounds")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        record_path = data / "record"
        good_record = record_path.read_bytes()
        for label, bad in (
            ("missing-nl", good_record[:-1]),
            ("second-line", good_record + b"\n"),
            ("trailing-pipe", good_record[:-1] + b"|\n"),
            ("embedded-nul", good_record[:-1] + b"\x00\n"),
        ):
            with self.subTest(record=label):
                record_path.write_bytes(bad)
                res, ans = self.api("status", argument="settings")
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(ans["error"], "invalid_record")
        record_path.write_bytes(good_record)
        # Verify metadata fast path (< 10 digits) and 10-digit uint32 boundary.
        script = (
            f'set -eu; D="{data}"; P="{self.tools}"; . "$P/state.sh"\n'
            'metadata "755:0:0"\n'
            'metadata "755:1000:999999999"\n'
            'metadata "755:4294967295:4294967295"\n'
            'if metadata "755:4294967296:0"; then exit 11; fi\n'
            'if metadata "755:0:4294967296"; then exit 12; fi\n'
            'if metadata "755:10000000000:0"; then exit 13; fi\n'
        )
        res = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        # Embedded NUL in a snapshot manifest selector name must fail snapshot_read.
        snap_id = good_record.decode().split("|")[5]
        src_snap = data / "snapshots" / snap_id
        nul_snap = data / "snapshots" / "nul-selector-work"
        shutil.copytree(src_snap, nul_snap)
        nul_snap.chmod(0o700)
        sel = nul_snap / "selector"
        if not sel.exists():
            sel.write_bytes(b"-\n")
            sel.chmod(0o600)
        raw_mf = (nul_snap / "files.sha256").read_bytes()
        lines = [ln for ln in raw_mf.splitlines(keepends=True) if not ln.endswith(b"  selector\n")]
        sel_hex = hashlib.sha256(sel.read_bytes()).hexdigest().encode()
        nul_mf = b"".join(lines) + sel_hex + b"  sel\x00ector\n"
        (nul_snap / "files.sha256").write_bytes(nul_mf)
        nul_id = hashlib.sha256(nul_mf).hexdigest()
        nul_target = data / "snapshots" / nul_id
        nul_snap.rename(nul_target)
        res = subprocess.run(
            [
                "sh",
                "-c",
                f'set -eu; D="{data}"; P="{self.tools}"; . "$P/state.sh"; '
                f'if snapshot_read "{nul_id}"; then exit 21; fi',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        shutil.rmtree(nul_target)

    def test_save_final_verification_failure_requires_fresh_reconciliation(self):
        data = self.create("save-final-conflict")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        _, before = self.api("status")
        firmware = self.tools / "firmware.sh"
        # Change a dependency after admission/preparation, while publishing the
        # new target, so only the command's final verification can reject it.
        firmware.write_text(
            firmware.read_text().replace(
                'mv "$AUTOSTART.next" "$AUTOSTART"',
                'mv "$AUTOSTART.next" "$AUTOSTART"\nprintf changed > "$D-relevant"',
            )
        )
        result, answer = self.api("set", before["revision"], "pandora", "1", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(answer, {"ok": False, "error": "final_verification_failed"})
        self.assertEqual((data / "record").read_text().split("|")[1], "set")
        _, fresh = self.api("status")
        self.assertTrue(fresh["pending"])
        self.assertTrue(fresh["conflict"])
        # A fresh full read must observe subsequent physical changes, rather
        # than inheriting the failed write's admission or any displayed model.
        self.target(data, "relevant").write_text("dependency\n")
        _, fresh = self.api("status")
        self.assertTrue(fresh["pending"])
        self.assertFalse(fresh["conflict"])

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
                '  snapshot_verify "$1" && snapshot_decode "$1" || return 1',
                '  printf "%s\\n" "$1" >> "$D/reads"\n'
                '  snapshot_verify "$1" && snapshot_decode "$1" || return 1',
            )
        )
        for selected in (current, applied):
            with self.subTest(selected=selected):
                (runtime / "selected").write_text(selected + "\n")
                (runtime / "access-selected").write_text(selected + "\n")
                (data / "reads").write_text("")
                result, status = self.api("status", argument="settings")
                self.assertEqual(result.returncode, 0, result.stderr)
                # Native api resolves both current and selected snapshots in-process without shell state.sh.
                self.assertEqual((data / "reads").read_text().splitlines(), [])
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
                saved_manifest = (self.tools / "files.sha256").read_bytes()
                for operation, args in (
                    ("set", ("warning", "1", "0")),
                    ("import", ()),
                    ("install", ()),
                    ("uninstall", ()),
                    ("restart", ()),
                ):
                    if operation == "install":
                        (self.tools / "files.sha256").write_text(
                            "".join(
                                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                                for p in sorted(self.tools.iterdir())
                                if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
                            )
                        )
                    else:
                        (self.tools / "files.sha256").write_bytes(saved_manifest)
                    result, answer = self.api(operation, revision, *args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(answer["error"], "state_changed")
                    self.assertEqual((data / "record").read_bytes(), record)
                    self.assertEqual(path.read_bytes(), b"external edit\n")
                (self.tools / "files.sha256").write_bytes(saved_manifest)
                path.write_bytes(original)

    def completion_fixture(self, name):
        data = self.create(name)
        self.run_ok(data, "install")
        self.backend_fixture(data)
        fields = (data / "record").read_text().strip().split("|")
        boot = "12345678-1234-1234-1234-123456789abc"
        fields[3] = (data / "package-id").read_text().strip()
        fields[11:13] = [boot, "installed"]
        (data / "record").write_text("|".join(fields) + "\n")
        runtime = self.root / "runtime"
        (runtime / "boot-id").symlink_to(boot)
        # service_stage already authenticates this installed endpoint. Its
        # manifest identifies the selected package, not the maintenance media.
        shutil.copyfile(data / "packages" / fields[3] / "files.sha256", self.tools / "files.sha256")
        return data, runtime, fields

    def test_completion_keeps_environment_guards_without_rehashing_boot_inputs(self):
        data, runtime, fields = self.completion_fixture("completion-guard")
        version, mounts = self.root / "version.ini", self.root / "mounts"
        framework, display, calls = (
            self.root / name for name in ("framework", "display", "md5-calls")
        )
        (self.root / "mnt/persist").mkdir(parents=True)
        version.write_text(
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
        )
        mounts.write_text(
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            f"/dev/mmcblk0p2 {self.root}/mnt/persist relfs rw 0 0\n"
        )
        source = (ROOT / "cmu/installer/firmware.sh").read_text()
        guard = source[
            source.index("firmware_guard() {") : source.index("native_dependency_guard()")
        ]
        # Run the real guard. Only host UID, physical paths and input digests
        # are synthetic; no OEM files or physical devices are involved.
        guard = guard.replace('test "$(id -u)" = 0', f'test "$(id -u)" = {os.getuid()}')
        paths = {
            "/jci/version.ini": version,
            "/proc/mounts": mounts,
            "/proc/self/mounts": mounts,
            "/jci/gui/framework/js/GuiFramework.js": framework,
            "/jci/lvds/lvds_service": display,
            "/tmp/open-connect": runtime,
            "/tmp/mnt/data_persist": self.root / "mnt/persist",
            "/tmp/mnt": self.root / "mnt",
            "/tmp": self.root,
        }
        guard = re.sub(
            "|".join(re.escape(path) for path in sorted(paths, key=len, reverse=True)),
            lambda match: str(paths[match[0]]),
            guard,
        )
        module = self.tools / "firmware.sh"
        adapter = (
            f"\nmd5sum() {{ printf call >> {shlex.quote(str(calls))}; "
            'local value; IFS= read -r value; case "$value" in '
            'framework) printf "0228bd6330c544eb500dacd7b00a9e79  -\\n";; '
            'display) printf "1d3e74362d4a97814a9f0fb316ff583f  -\\n";; '
            "*) return 1;; esac; }\n"
        )
        original = module.read_text() + "\n" + guard + adapter
        module.write_text(original)
        # Missing physical input files prove that neither completion nor its
        # readback accidentally executes the old upfront hash checks.
        for _ in range(2):
            result, proof = self.api("status", argument="completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(proof["completionReady"])
        self.assertFalse(calls.exists())
        framework.write_text("framework\n")
        display.write_text("display\n")
        for operation in (
            "status",
            "set",
            "install",
            "import",
            "uninstall",
            "restart",
            "recover",
        ):
            calls.unlink(missing_ok=True)
            self.api(operation, "f" * 64)
            self.assertEqual(calls.read_text(), "callcall", operation)

        # Verify shell firmware_guard directly for usb:status:completion and all 5 environment guards.
        def run_shell_guard(tag):
            return subprocess.run(
                [
                    "sh",
                    "-c",
                    'set -eu; P=$1; . "$P/state.sh"; . "$P/firmware.sh"; '
                    'fail() { printf \'{"ok":false,"error":"%s"}\\n\' "$1"; exit 1; }; '
                    'firmware_guard "$2"',
                    "guard",
                    self.tools,
                    tag,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=self.host_api_env(data),
            )

        calls.unlink(missing_ok=True)
        self.assertEqual(run_shell_guard("settings:status:completion").returncode, 0)
        self.assertFalse(calls.exists())
        self.assertEqual(run_shell_guard("usb:status:completion").returncode, 0)
        self.assertEqual(calls.read_text(), "callcall")
        for fact, error in (
            ("root", "root_required"),
            ("version", "unsupported_firmware"),
            ("mount", "persistence_unavailable"),
            ("root-mount", "invalid_boot_mounts"),
            ("path", "invalid_persistence_path"),
        ):
            with self.subTest(fact=fact):
                saved_version, saved_mounts = version.read_text(), mounts.read_text()
                if fact == "root":
                    module.write_text(
                        original.replace(
                            f"= {os.getuid()} || fail root_required",
                            f"= {os.getuid() + 1} || fail root_required",
                        )
                    )
                elif fact == "version":
                    version.write_text('JCI_SW_VER="unsupported"\n')
                elif fact == "mount":
                    mounts.write_text(saved_mounts.replace("relfs rw", "relfs ro"))
                elif fact == "root-mount":
                    mounts.write_text(saved_mounts.replace("relfs ro,noatime", "relfs rw"))
                else:
                    (self.root / "mnt/persist").rmdir()
                result = run_shell_guard("settings:status:completion")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["error"], error)
                module.write_text(original)
                version.write_text(saved_version)
                mounts.write_text(saved_mounts)
                if fact == "path":
                    (self.root / "mnt/persist").mkdir()

    def test_completion_is_a_narrow_fresh_selected_boot_proof(self):
        data, runtime, fields = self.completion_fixture("narrow-completion")
        for module, functions in (
            ("state.sh", ("snapshot_decode",)),
            ("transaction.sh", ("targets_match_loaded", "dependencies_match")),
            ("access.sh", ("access_login_check",)),
            ("firmware.sh", ("factory_wireless",)),
        ):
            with (self.tools / module).open("a") as stream:
                for function in functions:
                    stream.write("\n" + function + "() { exit 99; }\n")
        before = (data / "record").read_bytes()
        result, proof = self.api("status", argument="completion")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            proof,
            dict(
                ok=True,
                revision=fields[5],
                package=fields[3],
                boot=fields[11],
                installedVersion="0.3.0-dev.10-fixture",
                notice="installed",
                completionReady=True,
            ),
        )
        self.assertEqual((data / "record").read_bytes(), before)
        # A read-only proof is of selection, not a second physical-state audit.
        self.target(data, "target").write_text("external edit after selected boot\n")
        self.target(data, "relevant").write_text("external dependency edit\n")
        _, fresh = self.api("status", argument="completion")
        self.assertEqual(fresh, proof)
        # ACC may rotate OC1's write nonce without changing the selected boot.
        fields[2] = "f" * 32
        (data / "record").write_text("|".join(fields) + "\n")
        result, answer = self.api("dismiss", proof["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(answer, {"ok": True})
        self.assertTrue((self.tools / "closed").exists())
        _, cleared = self.api("status", argument="completion")
        self.assertEqual(cleared, {**proof, "notice": "-", "completionReady": False})
        before = (data / "record").read_bytes()
        _, refused = self.api("dismiss", proof["revision"])
        self.assertEqual(refused["error"], "stale_state")
        self.assertEqual((data / "record").read_bytes(), before)
        self.assertEqual((runtime / "selected").read_text(), fields[5] + "\n")

    def test_completion_and_ack_refuse_incomplete_or_mismatched_authority(self):
        cases = (
            "no-selected",
            "malformed-selected",
            "unselected",
            "no-boot",
            "bad-boot",
            "regular-boot",
            "previous-boot",
            "same-boot-commit",
            "pending",
            "removed",
            "config",
            "version",
            "manifest",
            "package",
            "old-endpoint",
            "replaced",
            "usb",
        )
        for case in cases:
            with self.subTest(case=case):
                shutil.rmtree(self.root / "runtime", ignore_errors=True)
                data, runtime, fields = self.completion_fixture("completion-" + case)
                selected, marker = runtime / "selected", runtime / "boot-id"
                if case == "no-selected":
                    selected.unlink()
                elif case == "malformed-selected":
                    selected.write_text(fields[5] + "\nextra\n")
                elif case == "unselected":
                    selected.write_text("0" * 64 + "\n")
                elif case == "no-boot":
                    marker.unlink()
                elif case in ("bad-boot", "regular-boot", "previous-boot"):
                    marker.unlink()
                    if case == "regular-boot":
                        marker.write_text(fields[11] + "\n")
                    else:
                        marker.symlink_to(
                            "invalid"
                            if case == "bad-boot"
                            else "87654321-1234-1234-1234-123456789abc"
                        )
                elif case == "same-boot-commit":
                    fields[11] = "-"
                elif case == "pending":
                    fields[1], fields[6], fields[7] = "set", fields[5], fields[5]
                elif case == "removed":
                    fields[1] = "removed"
                elif case == "config":
                    (data / "snapshots" / fields[5] / "config").write_text("invalid config\n")
                elif case == "version":
                    (data / "packages" / fields[3] / "VERSION").write_text("0.3.0-forged\n")
                elif case == "package":
                    fields[3] = "f" * 64
                elif case == "manifest":
                    (self.tools / "files.sha256").write_text("invalid identity\n")
                elif case == "old-endpoint":
                    (self.tools / "files.sha256").write_text("0" * 64 + "  VERSION\n")
                elif case in ("replaced", "usb"):
                    (runtime / "runtime").unlink()
                    (runtime / ("usb-runtime" if case == "usb" else "runtime")).symlink_to(
                        self.tools if case == "usb" else self.root / "successor"
                    )
                (data / "record").write_text("|".join(fields) + "\n")
                before = (data / "record").read_bytes()
                for operation, args in (("status", ("-", "completion")), ("dismiss", (fields[5],))):
                    result, error = self.api(operation, *args)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertFalse(error.get("completionReady", False))
                    if case == "pending":
                        self.assertEqual(error["error"], "operation_pending")
                    self.assertEqual((data / "record").read_bytes(), before)
                self.assertFalse((self.tools / "closed").exists())

    def test_completion_uses_only_the_volatile_boot_identity(self):
        data, runtime, fields = self.completion_fixture("repeated-completion")
        kernel = self.root / "kernel-boot"
        kernel.write_text(fields[11] + "\n")
        backend = self.tools / "backend.sh"
        backend.write_text(
            backend.read_text().replace("/proc/sys/kernel/random/boot_id", str(kernel))
        )
        marker = runtime / "boot-id"
        for current, recorded, ready in (
            (fields[11], fields[11], True),
            ("87654321-1234-1234-1234-123456789abc", fields[11], False),
            ("87654321-1234-1234-1234-123456789abc", "87654321-1234-1234-1234-123456789abc", True),
            (None, fields[11], False),  # Repeated raw UUID cannot replace selection evidence.
        ):
            with self.subTest(current=current, recorded=recorded):
                marker.unlink(missing_ok=True)
                if current:
                    marker.symlink_to(current)
                fields[11] = recorded
                (data / "record").write_text("|".join(fields) + "\n")
                result, proof = self.api("status", argument="completion")
                self.assertEqual(result.returncode == 0, ready, result.stdout + result.stderr)
                self.assertEqual(proof.get("completionReady", False), ready)

    def test_real_package_writer_gives_reinstalls_distinct_capabilities(self):
        data = self.create("install-generations")
        source = data / "packages" / (data / "package-id").read_text().strip()
        script = (
            'set -eu; D=$1; P=$2; . "$3/state.sh"; . "$3/firmware.sh"; '
            "uuid() { openssl rand -hex 16; }; package_save; package_save"
        )
        result = subprocess.run(
            ["sh", "-c", script, "packages", data, source, ROOT / "cmu/installer"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        first, second = result.stdout.splitlines()
        self.assertNotEqual(first, second)
        self.assertNotIn(source.name, (first, second))
        for identity in (first, second):
            folder = data / "packages" / identity
            self.assertEqual(
                hashlib.sha256((folder / "files.sha256").read_bytes()).hexdigest(), identity
            )
            self.assertTrue((folder / "INSTANCE").is_file())
        # Even repeated randomness cannot publish the same generation twice.
        collision = (
            script[: script.index("uuid()")]
            + 'repeat_instance=$D/packages/$4/INSTANCE; uuid() { cat "$repeat_instance"; }; package_save'
        )
        result = subprocess.run(
            ["sh", "-c", collision, "packages", data, source, ROOT / "cmu/installer", first],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("package_collision", result.stderr)

    def test_pending_recovery_still_audits_physical_targets_and_dependencies(self):
        for target, error in (("target", "startup_changed"), ("relevant", "dependencies_changed")):
            with self.subTest(target=target):
                shutil.rmtree(self.root / "runtime", ignore_errors=True)
                data = self.create("recover-audit-" + target)
                self.run_ok(data, "install")
                self.assertNotEqual(self.run_command(data, "service-off", "prepared").returncode, 0)
                self.backend_fixture(data)
                record = (data / "record").read_bytes()
                revision = record.decode().split("|")[2]
                path = self.target(data, target)
                path.write_text("external edit while recovery was pending\n")
                result, answer = self.api("recover", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(answer["error"], error)
                self.assertEqual((data / "record").read_bytes(), record)
                self.assertEqual(path.read_text(), "external edit while recovery was pending\n")

    def test_completion_ack_cannot_clear_a_new_install_before_its_boot(self):
        data, runtime, fields = self.completion_fixture("stale-completion-ack")
        _, proof = self.api("status", argument="completion")
        # Even a synthetic reinstall reusing identical fixture bytes cannot be
        # acknowledged on this boot: all non-apply commits clear R_BOOT.
        self.run_ok(data, "install")
        before = (data / "record").read_bytes()
        _, refused = self.api("dismiss", proof["revision"])
        self.assertEqual(refused["error"], "completion_unavailable")
        self.assertEqual((data / "record").read_bytes(), before)
        self.assertEqual((data / "record").read_text().split("|")[12], "installed\n")
        self.assertFalse((self.tools / "closed").exists())

    def test_old_ack_refuses_a_valid_successor_selected_boot(self):
        data, runtime, fields = self.completion_fixture("successor-completion-ack")
        _, old = self.api("status", argument="completion")
        source = data / "packages" / fields[3]
        result = subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; D=$1; P=$2; . "$3/state.sh"; . "$3/firmware.sh"; '
                "uuid() { openssl rand -hex 16; }; package_save",
                "reinstall",
                data,
                source,
                ROOT / "cmu/installer",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        successor = result.stdout.strip()
        (data / "package-id").write_text(successor + "\n")
        self.run_ok(data, "install")
        fields = (data / "record").read_text().strip().split("|")
        fields[3] = successor
        fields[11] = "87654321-1234-1234-1234-123456789abc"
        (data / "record").write_text("|".join(fields) + "\n")
        (runtime / "boot-id").unlink()
        (runtime / "boot-id").symlink_to(fields[11])
        (runtime / "selected").write_text(fields[5] + "\n")
        shutil.copyfile(data / "packages" / successor / "files.sha256", self.tools / "files.sha256")
        _, fresh = self.api("status", argument="completion")
        self.assertTrue(fresh["completionReady"])
        self.assertNotEqual(fresh["revision"], old["revision"])
        before = (data / "record").read_bytes()
        _, refused = self.api("dismiss", old["revision"])
        self.assertEqual(refused["error"], "stale_state")
        self.assertEqual((data / "record").read_bytes(), before)
        self.assertFalse((self.tools / "closed").exists())

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

        # Missing or malformed volatile evidence must never select B's program.
        def saved_files():
            return {
                str(p.relative_to(data)): (p.read_bytes(), p.stat().st_mode, p.stat().st_ctime_ns)
                for p in data.rglob("*")
                if p.is_file()
            }

        unchanged = saved_files()
        selected_file = runtime / "selected"
        for content in (None, selected + "\n\n", selected + "\nextra\n"):
            selected_file.unlink(missing_ok=True)
            if content is not None:
                selected_file.write_text(content)
            for operation, args in (("status", ("settings",)), ("set", ("warning", "1", "0"))):
                result, answer = self.api(operation, fields[5], *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(answer["error"], "invalid_selected_snapshot")
                self.assertEqual((data / "record").read_bytes(), expected)
                self.assertEqual(saved_files(), unchanged)
                self.assertFalse(marker.exists())
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(self.tools)
        result, view = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(view["installedVersion"], "0.3.0-successor")
        self.assertFalse(marker.exists())

    def legacy_endpoint(self, data, pinned=False, version="0.3.0-dev.22"):
        """Actual main/dev.22 backend, with only host physical paths adapted."""
        runtime = self.root / "runtime"
        target = runtime / "sessions/session-legacy"
        target.parent.mkdir(mode=0o700)
        shutil.copytree(self.tools, target)
        target.chmod(0o700)
        old = (ROOT / "tests/fixtures/dev22/backend.sh").read_text()
        self.assertEqual(
            hashlib.sha256(old.encode()).hexdigest(),
            "518809f76ea2bfe6cbe33387ee1646c607c00dde7e798c22702510285bf89485",
        )
        if pinned:
            old = (ROOT / "cmu/installer/backend.sh").read_text()
        old = (
            old.replace("/tmp/open-connect", str(runtime))
            .replace("/tmp/mnt/data_persist/open-connect", str(data))
            .replace("/usr/bin/autostart", str(self.target(data, "target")))
        )
        (target / "backend.sh").write_text(old)
        package = data / "packages" / (data / "package-id").read_text().strip()
        source = package.with_name(".legacy")
        shutil.copytree(package, source)
        (source / "backend.sh").write_text(old)
        (source / "VERSION").write_text(version + "\n")
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(source.iterdir())
            if p.name != "files.sha256"
        )
        (source / "files.sha256").write_text(manifest)
        package_id = hashlib.sha256(manifest.encode()).hexdigest()
        source.rename(source.with_name(package_id))
        (data / "package-id").write_text(package_id + "\n")
        self.run_ok(data, "install")
        fields = (data / "record").read_text().split("|")
        fields[3] = package_id
        (data / "record").write_text("|".join(fields))
        (runtime / "selected").write_text(fields[5] + "\n")
        shutil.copyfile(data / "packages" / package_id / "files.sha256", target / "files.sha256")
        pointer = runtime / "runtime"
        pointer.unlink()
        pointer.symlink_to(target)
        (runtime / "usb-runtime").symlink_to(self.tools)
        (runtime / "listener").write_text("123 456 " + str(target) + "\n")
        # Source/socket ownership is tested on Linux separately. This fixture
        # keeps the real pre-OC1 gate and real inherited writer flock.
        with (self.tools / "service.sh").open("a") as stream:
            stream.write('\nservice_owns_listener() { test "$1:$2:$3:$4" = ')
            stream.write(shlex.quote("123:456:" + str(target) + ":15555") + "; }\n")
        helper = self.tools / "usb-service.sh"
        helper.write_text(
            helper.read_text().replace(
                "518809f76ea2bfe6cbe33387ee1646c607c00dde7e798c22702510285bf89485",
                hashlib.sha256(old.encode()).hexdigest(),
            )
        )
        self.real_flock()
        return target, fields[5]

    def legacy_api(self, target, revision, operation="status", *args):
        result = subprocess.run(
            [
                "sh",
                target / "backend.sh",
                "api",
                revision,
                operation,
                *(args or ("settings", "-", "-")),
            ],
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result, json.loads(result.stdout)

    def test_legacy22_endpoint_is_fenced_before_prepare_and_refuses_successor(self):
        data = self.create("legacy-fence")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, revision = self.legacy_endpoint(data)
        result, changed = self.legacy_api(target, revision, "set", "warning", "1", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(changed["warning"], 0)
        revision = changed["revision"]
        runtime = self.root / "runtime"
        pointer = runtime / "runtime"
        record = (data / "record").read_bytes()
        # Normal preflight failure leaves the exact old publication in place.
        self.target(data, "relevant").write_text("external edit\n")
        _, error = self.api("uninstall", revision)
        self.assertEqual(error["error"], "state_changed")
        self.assertEqual(pointer.readlink(), target)
        self.assertEqual((data / "record").read_bytes(), record)
        self.target(data, "relevant").write_text("dependency\n")
        # Witness withdrawal after staging and immediately before publication.
        transaction = self.tools / "transaction.sh"
        transaction.write_text(
            transaction.read_text().replace(
                "    if ! record_publish; then",
                '    absent "' + str(pointer) + '" || fail fence_missing; '
                "if ! record_publish; then",
            )
        )
        self.target(data, "nvram-commit-fails").touch()
        result, _ = self.api("uninstall", revision)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.lexists(pointer))
        self.assertTrue((runtime / "listener").is_file())
        self.assertTrue((target / "backend.sh").is_file())
        expected = (data / "record").read_bytes()
        # Both actual old22 entry points fail before interpreting pending OC1.
        for operation, args in (("status", ("settings", "-", "-")), ("set", ("warning", "1", "0"))):
            reply = subprocess.run(
                ["sh", target / "backend.sh", "api", revision, operation, *args],
                env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(reply.returncode, 0)
            self.assertEqual(json.loads(reply.stdout)["error"], "session_replaced")
            self.assertEqual((data / "record").read_bytes(), expected)

    def test_verified_pinned_endpoint_stays_public_during_usb_change(self):
        data = self.create("pinned-public")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, revision = self.legacy_endpoint(data, pinned=True, version="0.3.0-dev.23")
        result, reply = self.api("uninstall", revision)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(reply["restart"])
        self.assertEqual((self.root / "runtime/runtime").readlink(), target)

    def test_unknown_legacy_contract_refuses_before_prepare(self):
        data = self.create("unknown-legacy")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, revision = self.legacy_endpoint(data, version="0.3.0-dev.21")
        record = (data / "record").read_bytes()
        result, reply = self.api("uninstall", revision)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(reply["error"], "unsupported_legacy_runtime")
        self.assertEqual((data / "record").read_bytes(), record)
        self.assertEqual(list(data.glob("record.*")), [])
        self.assertEqual((self.root / "runtime/runtime").readlink(), target)

    def test_legacy_recovery_checks_physical_state_before_withdrawal(self):
        data = self.create("legacy-recovery")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, _ = self.legacy_endpoint(data)
        self.assertNotEqual(self.run_command(data, "uninstall", "prepared").returncode, 0)
        revision = (data / "record").read_text().split("|")[2]
        pointer = self.root / "runtime/runtime"
        record = (data / "record").read_bytes()
        self.target(data, "nvram").write_text("enable\n")
        result, reply = self.api("recover", revision)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(reply["error"], "nvram_changed")
        self.assertEqual((data / "record").read_bytes(), record)
        self.assertEqual(pointer.readlink(), target)
        self.target(data, "nvram").write_text("disable\n")
        result, reply = self.api("recover", revision)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(reply["restart"])
        self.assertFalse(os.path.lexists(pointer))
        self.assertFalse(data.exists())
        self.assertTrue((target / "backend.sh").is_file())

    def test_changed_legacy_endpoint_refuses_before_prepare(self):
        data = self.create("changed-legacy")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, revision = self.legacy_endpoint(data)
        with (target / "backend.sh").open("a") as stream:
            stream.write("# unknown endpoint revision\n")
        record = (data / "record").read_bytes()
        result, reply = self.api("uninstall", revision)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(reply["error"], "invalid_legacy_source")
        self.assertEqual((data / "record").read_bytes(), record)
        self.assertEqual(list(data.glob("record.*")), [])
        self.assertEqual((self.root / "runtime/runtime").readlink(), target)

    def test_failed_withdrawal_restores_only_unchanged_authority(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                data = self.create("withdraw-" + str(changed))
                self.run_ok(data, "install")
                self.backend_fixture(data)
                target, revision = self.legacy_endpoint(data)
                runtime = self.root / "runtime"
                pointer = runtime / "runtime"
                record = (data / "record").read_bytes()
                with (self.tools / "firmware.sh").open("a") as stream:
                    stream.write(
                        '\nrm() { if test "$1" = '
                        + shlex.quote(str(pointer))
                        + '; then command rm "$@" || return; '
                    )
                    if changed:
                        stream.write(
                            "printf changed > " + shlex.quote(str(runtime / "boot-id")) + "; "
                        )
                    stream.write('return 1; fi; command rm "$@"; }\n')
                result, reply = self.api("uninstall", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(reply["error"], "legacy_fence_failed")
                self.assertEqual((data / "record").read_bytes(), record)
                self.assertEqual(list(data.glob("record.*")), [])
                self.assertEqual(os.path.lexists(pointer), not changed)
                if not changed:
                    self.assertEqual(pointer.readlink(), target)
                shutil.rmtree(runtime)

    def test_legacy_record_staging_failures_leave_old_endpoint_public(self):
        cuts = {
            "create": (
                'mktemp() { if test "$1" = "$D/record.XXXXXX"; then cut_record; return 1; fi; command mktemp "$@"; }',
                "record_create_failed",
            ),
            "write": (
                'printf() { case "$1" in OC1\\|*) cut_record; return 1;; esac; command printf "$@"; }',
                "record_write_failed",
            ),
            "mode": (
                'chmod() { case "${2:-}" in "$D"/record.*) cut_record; return 1;; esac; command chmod "$@"; }',
                "record_mode_failed",
            ),
            "flush": (
                'flush() { case "$2" in "$D"/record.*) cut_record; fail flush_failed;; esac; "$P/flush" "$@" || fail flush_failed; }',
                "flush_failed",
            ),
        }
        for cut, (injection, error) in cuts.items():
            with self.subTest(cut=cut):
                shutil.rmtree(self.root / "runtime", ignore_errors=True)
                data = self.create("record-stage-" + cut)
                self.run_ok(data, "install")
                self.backend_fixture(data)
                target, revision = self.legacy_endpoint(data)
                runtime = self.root / "runtime"
                pointer = runtime / "runtime"
                watched = [
                    data / "record",
                    runtime / "listener",
                    runtime / "selected",
                    target / "backend.sh",
                    self.target(data, "target"),
                    self.target(data, "nvram"),
                ]
                before = {p: (p.stat().st_ino, p.stat().st_mode, p.read_bytes()) for p in watched}
                reached = self.root / ("reached-" + cut)
                # Exercise the exact existing backend resource-trap bodies too.
                cleanup_traps = [
                    line.strip()
                    for line in (self.tools / "backend.sh").read_text().splitlines()
                    if line.strip().startswith("trap '")
                ]
                resources = self.root / ("resource-" + cut)
                resources.mkdir()
                backend = self.tools / "backend.sh"
                backend.write_text(
                    backend.read_text().replace(
                        '  transaction_prepare uninstall "$before" "$after"',
                        "  access_work="
                        + shlex.quote(str(resources))
                        + "; resources=$access_work\n"
                        + "  "
                        + cleanup_traps[list(cuts).index(cut) % len(cleanup_traps)]
                        + "\n"
                        + '  transaction_prepare uninstall "$before" "$after"',
                    )
                )
                with (self.tools / "firmware.sh").open("a") as stream:
                    stream.write(
                        '\ncut_record() { test "$(readlink '
                        + shlex.quote(str(pointer))
                        + ')" = '
                        + shlex.quote(str(target))
                        + " || fail pointer_withdrawn; "
                        + 'test "$(sh '
                        + shlex.quote(str(target / "backend.sh"))
                        + " api "
                        + shlex.quote(revision)
                        + ' status settings - - || :)" = '
                        + shlex.quote('{"ok":false,"error":"busy"}')
                        + " || fail writer_lock_missing; "
                        + "command printf reached > "
                        + shlex.quote(str(reached))
                        + "; }\n"
                        + injection
                        + "\n"
                    )
                result, reply = self.api("uninstall", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(reply["error"], error)
                self.assertTrue(reached.exists())
                self.assertEqual(pointer.readlink(), target)
                self.assertEqual(list(data.glob("record.*")), [])
                self.assertFalse(resources.exists())
                self.assertEqual(
                    {p: (p.stat().st_ino, p.stat().st_mode, p.read_bytes()) for p in watched},
                    before,
                )
                result, reply = self.legacy_api(target, revision)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(reply["installedVersion"], "0.3.0-dev.22")
                shutil.rmtree(runtime)

    def test_failed_legacy_record_rename_restores_only_definite_unchanged_authority(self):
        for cut in (
            "unchanged",
            "record",
            "selected",
            "access-selected",
            "boot-id",
            "listener",
            "ownership",
            "replacement",
            "published",
            "missing-candidate",
            "directory-flush",
        ):
            with self.subTest(cut=cut):
                shutil.rmtree(self.root / "runtime", ignore_errors=True)
                data = self.create("record-rename-" + cut)
                self.run_ok(data, "install")
                self.backend_fixture(data)
                target, revision = self.legacy_endpoint(data)
                runtime = self.root / "runtime"
                pointer = runtime / "runtime"
                record = (data / "record").read_bytes()
                reached = self.root / ("rename-reached-" + cut)
                lost = self.root / ("listener-lost-" + cut)
                with (self.tools / "service.sh").open("a") as stream:
                    stream.write(
                        "\nservice_owns_listener() { test ! -e "
                        + shlex.quote(str(lost))
                        + ' && test "$1:$2:$3:$4" = '
                        + shlex.quote("123:456:" + str(target) + ":15555")
                        + "; }\n"
                    )
                mutations = {
                    "unchanged": ":",
                    "record": 'printf changed >> "$D/record"',
                    "selected": "printf '%064d\\n' 1 > " + shlex.quote(str(runtime / "selected")),
                    "access-selected": "printf '%064d\\n' 1 > "
                    + shlex.quote(str(runtime / "access-selected")),
                    "boot-id": "ln -s 12345678-1234-1234-1234-123456789abc "
                    + shlex.quote(str(runtime / "boot-id")),
                    "listener": "printf changed >> " + shlex.quote(str(runtime / "listener")),
                    "ownership": "touch " + shlex.quote(str(lost)),
                    "replacement": "ln -s "
                    + shlex.quote(str(self.tools))
                    + " "
                    + shlex.quote(str(pointer)),
                    "published": 'command mv "$@" || return',
                    "missing-candidate": 'command rm "$2" || return',
                    "directory-flush": 'command mv "$@" || return; return 0',
                }
                with (self.tools / "firmware.sh").open("a") as stream:
                    stream.write(
                        '\nmv() { if test "$3" = "$D/record"; then '
                        "absent " + shlex.quote(str(pointer)) + " || fail fence_missing; "
                        'test -f "$2" || fail candidate_missing; '
                        "command printf reached > "
                        + shlex.quote(str(reached))
                        + "; "
                        + mutations[cut]
                        + '; return 1; fi; command mv "$@"; }\n'
                    )
                    if cut == "directory-flush":
                        stream.write(
                            'flush() { if test "$1:$2" = "d:$D"; then fail flush_failed; fi; '
                            '"$P/flush" "$@" || fail flush_failed; }\n'
                        )
                result, reply = self.api("uninstall", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(
                    reply["error"],
                    "flush_failed" if cut == "directory-flush" else "record_rename_failed",
                )
                self.assertTrue(reached.exists())
                self.assertEqual(list(data.glob("record.*")), [])
                if cut == "unchanged":
                    self.assertEqual(pointer.readlink(), target)
                    result, reply = self.legacy_api(target, revision)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(reply["installedVersion"], "0.3.0-dev.22")
                elif cut == "replacement":
                    self.assertEqual(pointer.readlink(), self.tools)
                else:
                    self.assertFalse(os.path.lexists(pointer))
                    result, reply = self.legacy_api(target, revision)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(reply["error"], "session_replaced")
                if cut in ("published", "directory-flush"):
                    self.assertEqual((data / "record").read_text().split("|")[1], "uninstall")
                elif cut != "record":
                    self.assertEqual((data / "record").read_bytes(), record)

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
            env=self.host_api_env(),
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
        # Staging gives only api/flush executable modes, and omits the host stat
        # symlink. Keep the host stat/flock adapters outside that CMU packet.
        result, pending = self.api("status", argument="settings", host_tools=old)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(pending["pending"])
        self.assertFalse(pending["completionReady"])
        failure.unlink()
        result, recovered = self.api("recover", pending["revision"], host_tools=old)
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
            env=self.host_api_env(),
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
        data, process, gate = self.delayed_status("concurrent-read")
        # Both an exclusive lock holder (simulating a legacy installed reader) and
        # native api's shared status:settings reader succeed while full status drops
        # the lock during its unlocked physical audit.
        with (self.root / "runtime/lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock, fcntl.LOCK_UN)
        result, answer = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(answer["installed"])
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
                    if name == "selected":
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(status["error"], "invalid_selected_snapshot")
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(status["uart"], 1)
                        self.assertEqual(status["uartCurrent"], 0)
            marker.write_text(current + "\n")

    def test_backend_reinstall_refuses_later_target_or_dependency_edits(self):
        data = self.create("reinstall-conflict")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        (self.tools / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(self.tools.iterdir())
                if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
            )
        )
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

    def test_usb_recovers_partial_purge_with_live_pinned_endpoint(self):
        data = self.create("pinned-partial-purge")
        self.run_ok(data, "install")
        self.backend_fixture(data)
        target, _ = self.legacy_endpoint(data, pinned=True, version="0.3.0-dev.23")
        pointer = self.root / "runtime/runtime"
        self.run_ok(data, "uninstall")
        self.assertNotEqual(self.run_command(data, "cleanup", "snapshots").returncode, 0)
        self.assertFalse((data / "snapshots").exists())
        self.assertEqual((data / "record").read_text().split("|")[1], "purge")
        result, pending = self.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(pending["pending"])
        record = (data / "record").read_bytes()
        env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        refused = subprocess.run(
            ["sh", target / "backend.sh", "api", pending["revision"], "set", "warning", "1", "0"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(json.loads(refused.stdout)["error"], "operation_pending")
        self.assertEqual((data / "record").read_bytes(), record)
        result, recovered = self.api("recover", pending["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(data.exists())
        self.assertFalse(recovered["pending"])
        self.assertTrue(recovered["restart"])
        self.assertEqual(pointer.readlink(), target)
        self.assertTrue((target / "backend.sh").is_file())
        # The surviving installed endpoint cannot create settings after purge.
        refused = subprocess.run(
            ["sh", target / "backend.sh", "api", "-", "set", "warning", "1", "0"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(json.loads(refused.stdout)["error"], "not_installed")
        self.assertFalse(data.exists())

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
