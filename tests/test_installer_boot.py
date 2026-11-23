"""Run the actual selector with real records and simulated physical adapters."""

import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerBoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.runtime = self.root / "runtime"
        self.tools = self.root / "tools"
        self.source = self.root / "source"
        for path in (self.data, self.runtime, self.tools, self.source):
            path.mkdir(mode=0o700)
        for name in ("packages", "composed", "snapshots"):
            (self.data / name).mkdir(mode=0o700)
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        # Lock contention is covered separately; this fixture is one process.
        (self.tools / "flock").write_text("#!/bin/sh\nexit 0\n")
        (self.tools / "flock").chmod(0o700)
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.source / "flush"],
            check=True,
        )
        shutil.copyfile(self.source / "flush", self.runtime / "flush")
        (self.runtime / "flush").chmod(0o700)
        (self.runtime / "lock").touch()
        (self.runtime / "token").write_text("a" * 32 + "\n")
        (self.runtime / "ignition.sh").write_text("exit 0\n")
        (self.source / "ignition.sh").write_text("exit 0\n")
        for name in ("runtime.js", "dialog.js", "settings.js", "VERSION"):
            shutil.copyfile(ASSETS / name, self.source / name)
        (self.root / "acc").write_text("1\n")
        (self.root / "uptime").write_text("1.00 0.00\n")
        (self.root / "mounts").write_text(
            "rootfs / rootfs rw 0 0\n"
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
        )
        state = (
            (ASSETS / "state.sh")
            .read_text()
            .replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
        )
        (self.source / "state.sh").write_text(state)
        shutil.copyfile(ASSETS / "transaction.sh", self.source / "transaction.sh")
        shutil.copyfile(ASSETS / "access.sh", self.source / "access.sh")
        for name in (
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "wireless-device.awk",
            "wireless.sh",
            "defer-gap2.sh",
            "base-logging.js",
            "system-hook.js",
            "ui-profile.awk",
            "ui-modules.tsv",
            "defer-nav.sh",
        ):
            shutil.copyfile(ASSETS / name, self.source / name)
        self.manager = self.root / "manager.so"
        self.manager.write_bytes(b"synthetic pinned manager library\n")
        self.wcp_original = self.root / "sm_WCP.conf"
        self.wcp_original.write_bytes(b"synthetic pinned WCP service profile\n")
        self.log_original = b"synthetic original logging settings\n"
        self.log_library = b"synthetic exact common library\n"
        (self.root / "physical-log-settings").write_bytes(self.log_original)
        (self.root / "common-library").write_bytes(self.log_library)
        firmware = (ASSETS / "firmware.sh").read_text()
        # Use every real v74 dependency name/path mapping with synthetic bytes.
        # Keeping only manager.so here concealed sm_WCP.conf's valid underscore.
        oem_map = subprocess.check_output(
            ["sh", "-c", '. "$1"; firmware_dependencies', "fixture", ASSETS / "firmware.sh"],
            text=True,
        )
        (self.root / "oem").mkdir()
        self.oem_adapters = {}
        for row in oem_map.splitlines():
            digest, name, target = row.split()
            if name == "autostart":
                continue
            if name == "manager.so":
                fake = self.manager
            elif name == "sm_WCP.conf":
                fake = self.wcp_original
            else:
                fake = self.root / "oem" / name
                fake.write_bytes(("synthetic OEM dependency " + name + "\n").encode())
            self.oem_adapters[target] = str(fake)
            firmware = firmware.replace(target, str(fake))
        ui_map = subprocess.check_output(
            ["sh", "-c", '. "$1"; base_ui_files', "fixture", ASSETS / "firmware.sh"],
            text=True,
        )
        for row in ui_map.splitlines():
            digest, name, target = row.split()
            fake = self.root / "oem" / name
            fake.write_bytes(b'var logDefaults = {"__global__": "info"};\n')
            firmware = firmware.replace(target, str(fake)).replace(
                digest, hashlib.sha256(fake.read_bytes()).hexdigest()
            )
        for old, new in {
            "/jci/lib/libjciuiamgr.so": str(self.manager),
            "/jci/sm/sm_WCP.conf": str(self.wcp_original),
            "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29": hashlib.sha256(
                self.manager.read_bytes()
            ).hexdigest(),
            "/config/common/log/settings.txt": str(self.root / "physical-log-settings"),
            "/jci/lib/libjcicommon.so": str(self.root / "common-library"),
            "/tmp/common": str(self.root / "common"),
            "/sys/devices/virtual/block/ffx01": str(self.root / "flash"),
            "8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0": hashlib.sha256(
                self.log_original
            ).hexdigest(),
            "637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d": hashlib.sha256(
                self.log_library
            ).hexdigest(),
        }.items():
            firmware = firmware.replace(old, new)
        (self.root / "flash/queue").mkdir(parents=True)
        (self.root / "flash/dev").write_text("253:16\n")
        queue = self.root / "flash/queue/read_ahead_kb"
        queue.write_text("128\n")
        queue.chmod(0o644)
        (self.source / "firmware.sh").write_text(
            firmware
            + r"""
firmware_guard() { :; }
boot_mount_guard() { test ! -e "$D-overmount"; }
native_guard() { :; }
root_mode() { printf 'ro,noatime\n'; }
cleanup_mount_guard() { :; }
startup_staging_guard() { :; }
nvram_read() { cat "$D-nvram"; }
nvram_change() {
    test "$(cat "$D-nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D-nvram"
}
startup_publish() {
    test "$(sha "$AUTOSTART")" = "$3" || return 1
    cp "$1" "$AUTOSTART.next" && metadata "$2" &&
        chmod "$S_MODE" "$AUTOSTART.next" && mv "$AUTOSTART.next" "$AUTOSTART"
}
"""
        )
        # Authored native-UI inputs; no OEM payload is checked into the tests.
        originals = self.data / "originals"
        originals.mkdir(mode=0o700)
        shutil.copyfile(ROOT / "tests/fixtures/ui-profile.xml", originals / "mmui.xml")
        vui_root = self.root / "vui"
        (vui_root / "plugins").mkdir(parents=True)
        module_rows = []
        for line in (self.source / "ui-modules.tsv").read_text().splitlines():
            if line.startswith("vui\t"):
                kind, name, group, _ = line.split("\t")
                payload = ("authored plugin " + name + "\n").encode()
                (vui_root / "plugins" / name).write_bytes(payload)
                line = "\t".join((kind, name, group, hashlib.sha256(payload).hexdigest()))
            module_rows.append(line)
        (self.source / "ui-modules.tsv").write_text("\n".join(module_rows) + "\n")
        text = (
            (self.source / "firmware.sh")
            .read_text()
            .replace("/jci/vui/plugins/", str(vui_root / "plugins") + "/")
            .replace(
                "ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0",
                hashlib.sha256((originals / "mmui.xml").read_bytes()).hexdigest(),
            )
        )
        text += '\nvui_source_files() { :; }\nvui_stock_device() { stat -c %d "$D"; }\n'
        (self.source / "firmware.sh").write_text(text)
        with (self.source / "firmware.sh").open("a") as stream:
            stream.write(r"""
boot_ui_stage() {
    cp "$D/composed/$package/mmui.so" "$work/mmui.so"
    cp "$D/snapshots/$R_CURRENT/mmui.xml" "$work/mmui.xml"
    if test "$warning" = 1; then ln -s "$D/composed/$package/uia.so" "$work/uia.so"; fi
    if test "$base" = 1; then
        cp "$D/composed/$package/vui.so" "$D/composed/$package/vui.xml" "$work/"
        mkdir "$work/vui-plugins"
        ln -s feature/vui-plugins "$work/.vui-link"
        while read -r name; do ln -s "/jci/vui/plugins/$name" "$work/vui-plugins/$name"; done < "$D/snapshots/$R_CURRENT/vui-plugins.list"
    fi
}
""")
        (self.source / "service.sh").write_text(
            "service_files() { runtime=" + shlex.quote(str(self.runtime)) + "; }\n"
            'service_listen() { : > "$R/listen-attempted"; test ! -e "$R/port-blocked"; }\n'
        )
        script = (ASSETS / "boot.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/usr/bin/autostart": str(self.root / "data-target"),
            "/proc/sys/kernel/random/boot_id": str(self.root / "boot-id"),
            "/proc/uptime": str(self.root / "uptime"),
            "/usr/bin/open-connect-boot-select": str(self.root / "root-selector"),
            "/sys/class/gpio/ACC_Sense/value": str(self.root / "acc"),
            "../../mnt/data_persist/open-connect/composed/": str(self.data / "composed") + "/",
            'test "$(id -u)" = 0': 'test "$(id -u)" = ' + str(os.getuid()),
            "700:0:0": f"700:{os.getuid()}:{os.getgid()}",
        }.items():
            script = script.replace(old, new)
        (self.source / "boot.sh").write_text(script)
        backend = (ASSETS / "backend.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/usr/bin/autostart": str(self.root / "data-target"),
        }.items():
            backend = backend.replace(old, new)
        (self.source / "backend.sh").write_text(backend)
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(self.source.iterdir())
        )
        (self.source / "files.sha256").write_text(manifest)
        self.package_id = hashlib.sha256(manifest.encode()).hexdigest()
        self.package = self.data / "packages" / self.package_id
        shutil.copytree(self.source, self.package)
        composed = self.data / "composed" / self.package_id
        composed.mkdir(mode=0o700)
        for name in (
            "uia.so",
            "mmui.so",
            "mmui.xml",
            "vui.so",
            "vui.xml",
            "sm-normal-on.conf",
            "sm-wcp-on.conf",
            "index-on.html",
            "index-off.html",
        ):
            (composed / name).write_text("synthetic feature @TOKEN@\n")
        for name in ("index-on.html", "index-off.html"):
            (composed / name).write_text(
                '<script src="common/js/logDefaults.js"></script>\n'
                '<script src="framework/js/Log.js"></script>\nframework.init();\nsynthetic feature @TOKEN@\n'
            )
        self.write_profiles()
        self.composed_manifest()
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        self.shell(r"""
printf 'stock\n' > "$D/stock"; chmod 755 "$D/stock"
R_BASE=$(fixture_snapshot "$D/stock" - 0 0 absent "755:$(id -u):$(id -g)")
printf 'installed\n' > "$D-target"; chmod 755 "$D-target"
cp "$D-target" "$D/composed/$R_BACKEND/autostart"
(cd "$D/composed/$R_BACKEND"; for f in *; do test "$f" = files.sha256 || printf '%s  %s\n' "$(sha "$f")" "$f"; done) > "$D/composed/$R_BACKEND/files.sha256"
printf 'disable\n' > "$D-nvram"
R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 1 disable "755:$(id -u):$(id -g)")
R_PHASE=active; R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=3; R_OFF=-; R_BOOT=-; R_NOTICE=installed
record_write
""")
        self.populated_dependencies()

    def composed_manifest(self, package=None):
        folder = self.data / "composed" / (package or self.package_id)
        (folder / "files.sha256").write_text(
            "".join(
                hashlib.sha256(f.read_bytes()).hexdigest() + "  " + f.name + "\n"
                for f in sorted(folder.iterdir())
                if f.name != "files.sha256"
            )
        )

    def shell(self, script):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; R_BACKEND=$3; . "$P/state.sh"; . "$P/firmware.sh"\n'
                + (ROOT / "tests/fixtures/installer-snapshots.sh").read_text()
                + script,
                "test",
                self.data,
                self.package,
                self.package_id,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def boot(self, number, *, preserve_log=False, stderr_fd=None, shell_args=None):
        boot_id = "00000000-0000-0000-0000-" + f"{number:012x}"
        (self.root / "boot-id").write_text(boot_id + "\n")
        shutil.rmtree(self.runtime / "feature", ignore_errors=True)
        (self.runtime / "selected").unlink(missing_ok=True)
        for name in ("v.xml", "vui-hold.so", "vui-plugins"):
            (self.runtime / name).unlink(missing_ok=True)
        if not preserve_log:
            shutil.rmtree(self.root / "common", ignore_errors=True)
        return subprocess.run(
            [*(shell_args or ["sh"]), self.package / "boot.sh"],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if stderr_fd is None else stderr_fd,
            text=True,
            timeout=10,
        )

    def populated_dependencies(self, change=""):
        self.composed_manifest()
        self.shell(
            '. "$P/firmware.sh"; record_read; snapshot_read "$R_CURRENT"; '
            'deps=$(mktemp "$D/.deps-XXXXXX"); dependencies_capture "$R_BACKEND" > "$deps"; '
            + change
            + 'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" "$S_TOUCH" "$S_WARNING" '
            '"$S_NVRAM" "$S_META" "$deps" - "$S_PANDORA" "$S_BASE" "$S_WIRELESS"); '
            'rm "$deps"; record_write'
        )

    def hook(self, oem="", after=""):
        hook = (
            (ASSETS / "startup-hook.sh").read_text()
            + oem
            + (ASSETS / "startup-join.sh").read_text()
            + after
        )
        # Bash supplies read -n/-t for these host adapter cases. The actual
        # target BusyBox controller is also exercised on Linux separately.
        hook = hook.replace("/bin/busybox timeout", "timeout").replace("/bin/busybox sh", "sh")
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/proc/uptime": str(self.root / "uptime"),
            "/proc/self/mounts": str(self.root / "mounts"),
            "/usr/bin/open-connect-boot-select": str(self.root / "root-selector"),
            'test "$(id -u)" = 0': 'test "$(id -u)" = ' + str(os.getuid()),
            "700:0:0": f"700:{os.getuid()}:{os.getgid()}",
        }.items():
            hook = hook.replace(old, new)
        timeout = shutil.which("gtimeout") or shutil.which("timeout")
        self.assertIsNotNone(timeout)
        shim = self.tools / "timeout"
        shim.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$2" >> '
            + shlex.quote(str(self.root / "timeout-allowances"))
            + "\n"
            'if test "$1" = -t; then shift; fi\nexec ' + shlex.quote(timeout) + ' "$@"\n'
        )
        shim.chmod(0o700)
        return subprocess.run(
            [
                "bash",
                "-c",
                "SMCFG_NORMALMODE=stock; " + hook + '\nprintf "CONFIG|%s\\n" "$SMCFG_NORMALMODE"',
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_embedded_hook_selects_only_after_complete_source_verification(self):
        self.populated_dependencies()
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        result = self.hook()
        self.assertIn(
            "CONFIG|" + str(self.runtime / "feature/sm.conf"), result.stdout, result.stderr
        )
        self.assertTrue((self.runtime / "selected").exists())
        self.assertIn("package_verified|", (self.runtime / "startup-times").read_text())

    def test_gate_retains_worker_pid_across_oem_jobs_and_joins_before_selection(self):
        helper = self.root / "root-selector"
        complete = self.root / "worker-complete"
        helper.write_text(
            "#!/bin/sh\nprintf G\nexec 1>&-\n/bin/sleep 0.15\n"
            ": > " + shlex.quote(str(complete)) + "\nexit 0\n"
        )
        helper.chmod(0o700)
        result = self.hook(
            oem="\n" + ": &\n" * 8 + "/bin/sleep 0.02\n",
            after="\ntest -f " + shlex.quote(str(complete)) + " || exit 31\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG|" + str(self.runtime / "feature/sm.conf"), result.stdout)

    def test_gate_malformed_frame_never_selects_features(self):
        helper = self.root / "root-selector"
        helper.write_text("#!/bin/sh\nprintf X\nexit 0\n")
        helper.chmod(0o700)
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG|stock", result.stdout)

    def test_gate_does_not_read_again_after_join_exhausts_shared_deadline(self):
        helper = self.root / "root-selector"
        helper.write_text(
            "#!/bin/sh\nprintf '26.00 0.00\\n' > "
            + shlex.quote(str(self.root / "uptime"))
            + "\nexit 0\n"
        )
        helper.chmod(0o700)
        began = time.monotonic()
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG|stock", result.stdout)
        self.assertLess(time.monotonic() - began, 1.8)

    def test_gate_accepts_delayed_valid_frame_before_shared_deadline(self):
        helper = self.root / "root-selector"
        helper.write_text("#!/bin/sh\nsleep 1.1\nprintf G\nexit 0\n")
        helper.chmod(0o700)
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG|" + str(self.runtime / "feature/sm.conf"), result.stdout)

    def test_pending_recovery_and_observer_do_not_require_a_listener(self):
        for fixture in ("usb", "blocked-port"):
            with self.subTest(fixture=fixture):
                self.populated_dependencies()
                self.shell(
                    '. "$P/transaction.sh"; . "$P/firmware.sh"; AUTOSTART=$D-target; '
                    'record_read; transaction_prepare set "$R_CURRENT" "$R_CURRENT"'
                )
                if fixture == "usb":
                    (self.runtime / "runtime").symlink_to(self.runtime, target_is_directory=True)
                    (self.runtime / "listener").write_text("owned USB session\n")
                else:
                    (self.runtime / "port-blocked").touch()
                (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
                result = self.hook()
                self.assertIn(
                    "CONFIG|" + str(self.runtime / "feature/sm.conf"), result.stdout, result.stderr
                )
                self.assertEqual(self.record()[1], "active")
                self.assertEqual(self.record()[9], "2")
                self.assertTrue((self.runtime / "ignition/ignition.sh").is_file())
                self.assertFalse((self.runtime / "listen-attempted").exists())
                if fixture == "usb":
                    self.assertEqual((self.runtime / "listener").read_text(), "owned USB session\n")
                    (self.runtime / "runtime").unlink()
                for name in ("selected", "startup-times"):
                    (self.runtime / name).unlink(missing_ok=True)
                shutil.rmtree(self.runtime / "feature")
                shutil.rmtree(self.runtime / "ignition")

    def test_shell_entry_refuses_overmount_before_any_budget_write(self):
        self.populated_dependencies()
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        (self.root / "data-overmount").touch()
        before = (self.data / "record").read_bytes()
        result = self.hook()
        self.assertIn("CONFIG|stock", result.stdout)
        self.assertIn("invalid_boot_mounts", result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_native_handoff_uses_only_the_remaining_deadline(self):
        self.populated_dependencies()
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        helper = self.root / "root-selector"
        helper.write_text(
            '#!/bin/sh\nprintf J\nprintf "20.00 0.00\\n" > '
            + shlex.quote(str(self.root / "uptime"))
            + "\nexit 95\n"
        )
        helper.chmod(0o700)
        result = self.hook()
        self.assertIn(
            "CONFIG|" + str(self.runtime / "feature/sm.conf"), result.stdout, result.stderr
        )
        self.assertEqual((self.root / "timeout-allowances").read_text().splitlines(), ["25", "6"])

    def test_embedded_hook_refuses_corrupt_or_unlisted_package_before_execution(self):
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        original = (self.package / "boot.sh").read_bytes()
        (self.package / "boot.sh").write_bytes(original + b"\nfalse\n")
        result = self.hook()
        self.assertIn("CONFIG|stock", result.stdout)
        self.assertFalse((self.runtime / "selected").exists())
        (self.package / "boot.sh").write_bytes(original)
        (self.package / "undeclared").write_text("unlisted\n")
        result = self.hook()
        self.assertIn("CONFIG|stock", result.stdout)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual(self.record()[9], "3")

    def test_standalone_entry_checks_service_bytes_before_loading_them(self):
        marker = self.root / "unverified-service-ran"
        with (self.package / "service.sh").open("a") as f:
            f.write("\ntouch " + shlex.quote(str(marker)) + "\n")
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("damaged_package", result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(self.record()[9], "3")

    def test_populated_fast_path_keeps_budget_and_original_dependency_guards(self):
        self.populated_dependencies()
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()[9], "2")
        phases = (self.runtime / "startup-times").read_text()
        self.assertLess(phases.index("targets_dependencies|"), phases.index("session_ready|"))
        self.wcp_original.write_bytes(b"foreign WCP profile\n")
        result = self.boot(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual(self.record()[9], "2")

    def test_active_matching_snapshot_cannot_omit_all_dependencies(self):
        self.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 1 disable '
            '"$S_META" /dev/null - 1 0 0); record_write'
        )
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual(self.record()[9], "3")

    def test_preparation_refuses_authenticated_extra_composed_member(self):
        folder = self.data / "composed" / self.package_id
        before = (self.data / "record").read_bytes()
        (folder / "foreign").write_text("not a composition output\n")
        with self.assertRaises(subprocess.CalledProcessError):
            self.populated_dependencies()
        self.assertEqual((self.data / "record").read_bytes(), before)
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.runtime / "selected").exists())

    def test_new_plugin_pin_failure_refuses_before_prepare_and_keeps_removal_available(self):
        before = (self.data / "record").read_bytes()
        nvram = (self.root / "data-nvram").read_bytes()
        plugin = self.root / "vui/plugins/vui_plugin_common.so"
        plugin.write_bytes(b"foreign plugin\n")
        with self.assertRaises(subprocess.CalledProcessError):
            self.select_base(1)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertEqual((self.root / "data-nvram").read_bytes(), nvram)
        result = self.shell(
            '. "$P/transaction.sh"; AUTOSTART=$D-target; record_read; targets_match "$R_CURRENT"; dependencies_match "$R_CURRENT"; uninstall_owned "$R_CURRENT"'
        )
        self.assertEqual(result.returncode, 0)

    def test_damaged_saved_xml_set_refuses_without_blocking_uninstall(self):
        client = self.runtime / "client"
        shutil.copytree(self.package, client)
        (self.runtime / "runtime").symlink_to(client)
        current = self.record()[5]
        record = (self.data / "record").read_bytes()
        nvram = (self.root / "data-nvram").read_bytes()
        source = self.data / "originals/mmui.xml"
        source.write_bytes(source.read_bytes().replace(b"</MmuiLoadConfiguration>", b""))
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "set", "warning", "1", "0"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "plan_failed"})
        self.assertEqual((self.data / "record").read_bytes(), record)
        self.assertEqual((self.root / "data-nvram").read_bytes(), nvram)
        removed = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertFalse(self.data.exists())

    def test_foreign_device_plugin_refuses_set_before_prepare_and_keeps_uninstall(self):
        client = self.runtime / "client"
        shutil.copytree(self.package, client)
        (self.runtime / "runtime").symlink_to(client)
        current = self.record()[5]
        record = (self.data / "record").read_bytes()
        nvram = (self.root / "data-nvram").read_bytes()
        # Only the device response changes; canonical path and pinned bytes do
        # not. The target-owned renderer reaches this through its real PATH.
        tool = self.tools / "stat"
        real = str(tool.resolve()) if tool.exists() else shutil.which("stat")
        tool.unlink(missing_ok=True)
        plugin = str(self.root / "vui/plugins/vui_plugin_common.so")
        tool.write_text(
            '#!/bin/sh\nif test "$1:$2:$3" = '
            + shlex.quote("-c:%d:" + plugin)
            + '; then printf "999999\\n"; else exec '
            + shlex.quote(real)
            + ' "$@"; fi\n'
        )
        tool.chmod(0o700)
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "set", "base", "0", "1"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "plan_failed"})
        self.assertEqual((self.data / "record").read_bytes(), record)
        self.assertEqual((self.root / "data-nvram").read_bytes(), nvram)
        removed = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertFalse(self.data.exists())

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_rendered_base_off_aa_off_preserves_both_oem_callbacks(self):
        for base in (0, 1):
            for warning in (0, 1):
                result = self.shell(
                    'record_read; snapshot_read "$R_CURRENT"; prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" service.android-auto 0 "$S_SCHEMA"); '
                    + f'prefs=$(preferences_change "$prefs" "$S_PACKAGE" base {base} OC2); prefs=$(preferences_change "$prefs" "$S_PACKAGE" warning {warning} OC2); '
                    + 'snapshot_create "$D-target" "$S_PACKAGE" "$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - "$prefs"'
                )
                index = self.data / "snapshots" / result.stdout.strip() / "index.html"
                subprocess.run(
                    ["node", ROOT / "tests/fixtures/system-hook-rendered.js", index, str(base)],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )

    def test_shell_alias_failure_boundaries_remove_owned_names_and_preserve_foreign(self):
        for mode in ("metadata", "before", "after", "foreign"):
            for alias in ("v.xml", "vui-hold.so", "vui-plugins"):
                with self.subTest(mode=mode, alias=alias):
                    root = self.root / f"alias-{mode}-{alias}"
                    feature = root / "feature"
                    feature.mkdir(parents=True)
                    (feature / "vui.xml").write_text("config\n")
                    (feature / "vui.so").write_bytes(b"ELF fixture\n")
                    (feature / ".vui-link").symlink_to("feature/vui-plugins")
                    runtime = root / "tools"
                    runtime.mkdir()
                    helper = runtime / "flush"
                    helper.write_text(
                        '#!/bin/sh\nif test "$1:$3" = "l:$OC_ALIAS_ROOT/$OC_ALIAS_NAME"; then\n'
                        ' case "$OC_ALIAS_MODE" in before) exit 1;; foreign) printf "foreign\\n" > "$3"; exit 1;; after) '
                        + shlex.quote(str(self.source / "flush"))
                        + ' "$@"; exit 1;; esac\nfi\nexec '
                        + shlex.quote(str(self.source / "flush"))
                        + ' "$@"\n'
                    )
                    helper.chmod(0o700)
                    script = r"""
. "${1%/*}/state.sh"
. "$1"
R=$2; runtime=$3; base=1
stat() {
    if test "$OC_ALIAS_MODE" = metadata && test "$3" = "$R/$OC_ALIAS_NAME" && test ! -e "$R/fault-used"; then
        : > "$R/fault-used"; return 1
    fi
    command stat "$@"
}
boot_ui_prepare || exit 67
if boot_ui_publish; then exit 55; fi
boot_ui_unwind
"""
                    result = subprocess.run(
                        ["sh", "-c", script, "alias-check", ASSETS / "boot.sh", root, runtime],
                        capture_output=True,
                        text=True,
                        env={
                            **self.env,
                            "OC_ALIAS_ROOT": str(root),
                            "OC_ALIAS_NAME": alias,
                            "OC_ALIAS_MODE": mode,
                        },
                        timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for name in ("v.xml", "vui-hold.so", "vui-plugins"):
                        if mode == "foreign" and name == alias:
                            self.assertEqual((root / name).read_bytes(), b"foreign\n")
                        else:
                            self.assertFalse(os.path.lexists(root / name))

    def test_shell_post_link_metadata_failure_rolls_back_after_one_debit(self):
        self.select_base(1)
        script = (
            (self.package / "boot.sh")
            .read_text()
            .replace(
                "    boot_load\n",
                r"""
    boot_load
    stat() {
        if test "$3" = "$R/vui-hold.so" && test ! -e "$R/metadata-fault"; then
            : > "$R/metadata-fault"; return 1
        fi
        command stat "$@"
    }
""",
            )
        )
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        result = subprocess.run(
            [
                "sh",
                "-c",
                script.replace('case "${0##*/}" in boot.sh) boot_main;; esac', "boot_select"),
                "injected",
            ],
            env={**self.env, "P": str(self.package)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("selection_commit_failed", result.stderr)
        self.assertEqual(self.record()[9], "2")
        self.assertTrue((self.runtime / "metadata-fault").exists())
        for name in ("selected", "v.xml", "vui-hold.so", "vui-plugins"):
            self.assertFalse(os.path.lexists(self.runtime / name))

    def test_forced_shell_copy_failure_consumes_one_attempt_without_alias_publication(self):
        self.select_base(1)
        # Inject a runtime staging refusal after verified boot_load; package
        # bytes and their manifest stay unchanged.
        script = (self.package / "boot.sh").read_text()
        script = script.replace(
            "    boot_load\n", "    boot_load\n    boot_ui_stage() { return 1; }\n"
        )
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        result = subprocess.run(
            [
                "sh",
                "-c",
                script.replace('case "${0##*/}" in boot.sh) boot_main;; esac', "boot_select"),
                "injected",
            ],
            env={**self.env, "P": str(self.package)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record()[9], "2")
        for name in ("selected", "v.xml", "vui-hold.so", "vui-plugins"):
            self.assertFalse(os.path.lexists(self.runtime / name))

    def test_fast_path_refuses_unlisted_composed_file_and_directory(self):
        folder = self.data / "composed" / self.package_id
        for directory in (False, True):
            path = folder / ("foreign-directory" if directory else ".unlisted")
            if directory:
                path.mkdir()
            else:
                path.write_text("not listed\n")
            before = (self.data / "record").read_bytes()
            result = self.boot(1)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.data / "record").read_bytes(), before)
            if directory:
                path.rmdir()
            else:
                path.unlink()

    def test_preparation_refuses_noncanonical_composed_manifest_before_state_change(self):
        manifest = self.data / "composed" / self.package_id / "files.sha256"
        original = manifest.read_bytes()
        record = (self.data / "record").read_bytes()
        nvram = (self.root / "data-nvram").read_bytes()
        for changed in (
            original + b"0" * 64 + b"  foreign",
            original[:-1],
            original[:-1] + b"\0",
            original.replace(b"  ", b" ", 1),
            original.replace(b"  ", b"\t", 1),
            b" " + original,
            original + b"\0",
        ):
            with self.subTest(manifest=changed):
                manifest.write_bytes(changed)
                with self.assertRaises(subprocess.CalledProcessError):
                    self.shell(
                        'record_read; snapshot_read "$R_CURRENT"; '
                        'fixture_snapshot "$D-target" "$R_BACKEND" "$S_TOUCH" "$S_WARNING" '
                        '"$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - '
                        '"$S_PANDORA" "$S_BASE" "$S_WIRELESS"'
                    )
                self.assertEqual((self.data / "record").read_bytes(), record)
                self.assertEqual((self.root / "data-nvram").read_bytes(), nvram)
                self.assertFalse((self.runtime / "selected").exists())
        manifest.write_bytes(original)

    def test_closed_diagnostic_pipe_keeps_shell_selection(self):
        self.select_base(1)
        (self.root / "flash/queue/read_ahead_kb").unlink()
        shells = [["sh"]]
        busybox = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
        if busybox:
            shells.append([busybox, "ash"])
        for number, shell in enumerate(shells, 1):
            with self.subTest(shell=shell):
                read_fd, write_fd = os.pipe()
                os.close(read_fd)
                try:
                    result = self.boot(number, stderr_fd=write_fd, shell_args=shell)
                finally:
                    os.close(write_fd)
                self.assertEqual(result.returncode, 0)
                self.assertTrue((self.runtime / "selected").is_file())
                self.assertEqual(self.record()[9], str(3 - number))

    def test_full_diagnostic_pipe_keeps_shell_selection(self):
        self.select_base(1)
        (self.root / "flash/queue/read_ahead_kb").unlink()
        shells = [["sh"]]
        busybox = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
        if busybox:
            shells.append([busybox, "ash"])
        for number, shell in enumerate(shells, 1):
            with self.subTest(shell=shell):
                read_fd, write_fd = os.pipe()
                try:
                    os.set_blocking(write_fd, False)
                    with self.assertRaises(BlockingIOError):
                        while True:
                            os.write(write_fd, b"x" * 4096)
                    os.set_blocking(write_fd, True)
                    result = self.boot(number, stderr_fd=write_fd, shell_args=shell)
                finally:
                    os.close(read_fd)
                    os.close(write_fd)
                self.assertEqual(result.returncode, 0)
                self.assertTrue((self.runtime / "selected").is_file())
                self.assertEqual(self.record()[9], str(3 - number))
                self.assertIn(
                    "base_read_ahead_unavailable|", (self.runtime / "startup-times").read_text()
                )

    def test_set_refuses_unlisted_composed_entry_before_record_or_nvram_change(self):
        client = self.runtime / "client"
        shutil.copytree(self.package, client)
        (self.runtime / "runtime").symlink_to(client)
        current = self.record()[5]
        record = (self.data / "record").read_bytes()
        nvram = (self.root / "data-nvram").read_bytes()
        folder = self.data / "composed" / self.package_id
        foreign = folder / ".unlisted"
        foreign.write_text("not a composed member\n")
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "set", "touch", "1", "0"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "plan_failed"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.data / "record").read_bytes(), record)
        self.assertEqual((self.root / "data-nvram").read_bytes(), nvram)
        # Unlisted files were never part of the authenticated installed state.
        # Refusing a Set must not prevent removing that installation.
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.data.exists())
        self.assertEqual((self.root / "data-target").read_text(), "stock\n")
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")

    def test_fast_path_keeps_compiled_native_pin_when_snapshot_matches_foreign_bytes(self):
        self.manager.write_bytes(b"foreign manager adopted by snapshot\n")
        self.populated_dependencies()
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual(self.record()[9], "3")

    def test_fast_path_refuses_missing_and_duplicate_package_dependencies(self):
        for change in (
            'sed \'/package-.*\\/boot.sh$/d\' "$deps" > "$deps.next"; mv "$deps.next" "$deps"; ',
            'grep \'package-.*\\/boot.sh$\' "$deps" >> "$deps.copy"; cat "$deps.copy" >> "$deps"; ',
            'sed \'/composed-.*\\/uia.so$/d\' "$deps" > "$deps.next"; mv "$deps.next" "$deps"; ',
            'sed \'/root\\/sm.conf$/d\' "$deps" > "$deps.next"; mv "$deps.next" "$deps"; ',
        ):
            self.populated_dependencies(change)
            result = self.boot(1)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.runtime / "selected").exists())
            self.assertEqual(self.record()[9], "3")

    def test_standalone_refuses_each_corrupt_library_without_sourcing_it(self):
        marker = self.root / "unverified-library"
        for name in ("state.sh", "firmware.sh", "access.sh", "transaction.sh"):
            path = self.package / name
            original = path.read_bytes()
            path.write_bytes(original + ("\ntouch " + shlex.quote(str(marker)) + "\n").encode())
            result = self.boot(1)
            self.assertNotEqual(result.returncode, 0, name)
            self.assertFalse(marker.exists(), name)
            self.assertEqual(self.record()[9], "3")
            path.write_bytes(original)

    def test_hook_and_standalone_refuse_dangling_or_special_operation_lock(self):
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        lock = self.runtime / "lock"
        outside = self.root / "must-not-create"
        for special in (False, True):
            lock.unlink()
            if special:
                os.mkfifo(lock)
            else:
                lock.symlink_to(outside)
            result = self.hook()
            self.assertIn("CONFIG|stock", result.stdout)
            self.assertNotEqual(self.boot(1).returncode, 0)
            self.assertFalse(outside.exists())
            self.assertEqual(self.record()[9], "3")

    def test_diagnostic_special_path_cannot_block_or_fail_selection(self):
        receipt = self.runtime / "startup-times"
        os.mkfifo(receipt)
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.runtime / "selected").exists())
        self.assertTrue(receipt.is_fifo())

    def test_parent_only_term_during_base_preparation_cannot_publish_after_stock(self):
        self.select_base(1)
        (self.root / "boot-id").write_text("00000000-0000-0000-0000-000000000001\n")
        marker = self.root / "base-preparing"
        chmod = self.tools / "chmod"
        chmod.write_text(
            '#!/bin/sh\ncase "$*" in *".open-connect-log-"*) '
            + "printf ready > "
            + shlex.quote(str(marker))
            + "; sleep 0.4;; esac\n"
            + shutil.which("chmod")
            + ' "$@"\n'
        )
        chmod.chmod(0o700)
        process = subprocess.Popen(
            ["sh", self.package / "boot.sh"],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists())
        process.send_signal(signal.SIGTERM)
        out, err = process.communicate(timeout=5)
        self.assertNotEqual(process.returncode, 0, (out, err))
        time.sleep(0.5)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertFalse((self.root / "common/log/settings.txt").exists())

    def test_selected_directory_or_symlink_cannot_report_success_or_retain_base(self):
        for number, symlink in enumerate((False, True), 1):
            self.select_base(1)
            (self.root / "boot-id").write_text("00000000-0000-0000-0000-" + f"{number:012x}\n")
            shutil.rmtree(self.runtime / "feature", ignore_errors=True)
            shutil.rmtree(self.root / "common", ignore_errors=True)
            selected = self.runtime / "selected"
            if selected.exists():
                shutil.rmtree(selected)
            foreign = self.root / ("foreign-" + str(number))
            foreign.mkdir()
            if symlink:
                selected.symlink_to(foreign, target_is_directory=True)
            else:
                selected.mkdir()
            result = subprocess.run(
                ["sh", self.package / "boot.sh"],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertTrue(selected.is_dir())
            self.assertEqual(list(selected.iterdir()), [])
            self.assertFalse((self.root / "common/log/settings.txt").exists())

    def record(self):
        return (self.data / "record").read_text().strip().split("|")

    def test_both_board_configurations_follow_selected_warning_preference(self):
        for warning, number in ((1, 1), (0, 2)):
            with self.subTest(warning=warning):
                self.shell(
                    'record_read; snapshot_read "$R_CURRENT"; '
                    'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 '
                    + str(warning)
                    + ' disable "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT"); record_write'
                )
                result = self.boot(number)
                self.assertEqual(result.returncode, 0, result.stderr)
                for profile, name in (("normal", "sm.conf"), ("wcp", "sm_WCP.conf")):
                    selected = (
                        self.data
                        / "snapshots"
                        / self.record()[5]
                        / ("sm-normal.conf" if profile == "normal" else "sm-wcp.conf")
                    )
                    self.assertEqual(
                        (self.runtime / "feature" / name).read_bytes(), selected.read_bytes()
                    )

    def write_profiles(self):
        for profile in ("normal", "wcp"):
            args = {
                "jciMMUI": "mouse=filtered-mouse0, keyboard=filtered-keyboard0, display=filtered-touchscreen0",
                "start_network": "UCP",
                "bds": "-interface dbus",
            }
            if profile == "wcp":
                args["jciMMUI"] += ", wcp"
                args["start_network"] = ""
                args["bds"] += " -wcp"
            lines = ["<services>"]
            for name in (
                "stage_1",
                "stage_3",
                "stage_wifi",
                "stage_gap2",
                "jciVBS",
                "system_mazda_my14",
                "aap_service",
                "jciAAPA",
                "jciDAB",
                "jcitv",
                "blm_ira_stitcher",
                "irsstitcher_server",
                "jciMMUI",
                "jciVUI",
                "jcinavi",
                "start_network",
                "bds",
                "jciUSBMGR",
                "jciCARPLAY",
                "jciBCA",
                "blm_nms_svc",
                "devicemanager",
                "blm_ira_pandora",
                "jciLDS",
                "stage_vr",
                "stage_ir",
                "jcidvd",
                "jciSXMS",
                "jciXMMGR",
                "jcixm",
                "jcixmad",
                "jciXMDATA",
                "blm_ira_aha",
                "offboard_service",
                "irs_server",
            ):
                attr = f'name="{name}" autorun="yes" reset_board="yes" retry_count="0"'
                if name in ("jcixm", "jcixmad", "jciXMDATA"):
                    attr = attr.replace('autorun="yes"', 'autorun="no"')
                if name in args:
                    attr += f' args="{args[name]}"'
                elif (
                    name in ("jciUSBMGR", "jciCARPLAY", "jciBCA", "blm_nms_svc")
                    and profile == "wcp"
                ):
                    attr += ' args="wcp"'
                elif name == "jciLDS":
                    attr += ' args="actual-gps-provider"'
                if name == "jciVUI":
                    attr += ' path="/jci/vui/svcjcivui.so"'
                if name == "jciMMUI":
                    attr += ' path="/jci/mmui/svcjcimmui.so"'
                lines += ["<service " + attr + ">"]
                parents = {
                    "bds": ("stage_3", "settings", "dmserver"),
                    "stage_wifi": ("stage_3", "blm_ira_aha"),
                    "stage_gap2": ("stage_3", "blm_ira_aha"),
                    "stage_vr": ("existing", "blm_ira_aha"),
                }.get(name, ("existing",))
                lines += [f'<dependency type="service" value="{parent}"/>' for parent in parents]
                lines += ["</service>"]
            lines += ["</services>"]
            for setting in ("on", "off"):
                path = self.data / "composed" / self.package_id / f"sm-{profile}-{setting}.conf"
                text = "\n".join(lines) + "\n"
                if setting == "on":
                    text = text.replace(
                        'path="/jci/mmui/svcjcimmui.so"', 'path="/tmp/open-connect/feature/mmui.so"'
                    )
                path.write_text(text)

    def select_wireless(self, value, *, base=0):
        self.write_profiles()
        self.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 1 disable "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - 1 '
            + str(base)
            + " "
            + str(value)
            + "); record_write"
        )
        self.populated_dependencies()

    def test_wireless_boot_composes_both_profiles_and_preserves_native_services(self):
        self.select_wireless(1)
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        feature = self.runtime / "feature"
        for name in ("wireless.sh", "wireless-device.awk"):
            self.assertEqual((feature / name).read_bytes(), (ASSETS / name).read_bytes())
        self.assertEqual((feature / "boot-id").read_bytes(), (self.root / "boot-id").read_bytes())
        self.assertEqual((feature / "wireless-applied").read_text(), "0\n")
        for name in ("sm.conf", "sm_WCP.conf"):
            services = {s.attrib["name"]: s for s in ET.parse(feature / name).iter("service")}
            self.assertEqual(services["jciLDS"].attrib["args"], "actual-gps-provider")
            self.assertEqual(services["jciCARPLAY"].attrib["args"], "wcp")
            self.assertEqual(services["jciCARPLAY"].attrib["reset_board"], "yes")
            self.assertEqual(services["jciCARPLAY"].attrib["retry_count"], "0")
            helper = services["open_connect_wireless"]
            self.assertEqual(
                helper.attrib["args"], "timeout -t 15 sh /tmp/open-connect/feature/wireless.sh"
            )
            self.assertEqual(helper.attrib["reset_board"], "no")
            dependencies = [d.attrib["value"] for d in services["devicemanager"]]
            self.assertEqual(dependencies, ["open_connect_wireless", "existing"])

    def test_wireless_remains_absent_when_disabled_or_startup_budget_is_exhausted(self):
        self.select_wireless(0)
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.runtime / "feature/wireless.sh").exists())
        self.assertNotIn("open_connect_wireless", (self.runtime / "feature/sm.conf").read_text())
        self.select_wireless(1)
        self.shell("record_read; R_BUDGET=0; record_write")
        result = self.boot(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.runtime / "selected").exists())

    def test_foreign_wireless_service_argument_refuses_before_other_ram_effects(self):
        self.select_wireless(1, base=1)
        path = self.data / "composed" / self.package_id / "sm-normal-on.conf"
        path.write_text(
            path.read_text().replace('name="jciUSBMGR"', 'name="jciUSBMGR" args="foreign"')
        )
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.root / "common/log/settings.txt").exists())

    def select_base(self, value):
        self.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 1 disable "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - 1 '
            + str(value)
            + "); record_write"
        )

    def test_logging_is_boot_only_and_disabled_again_on_fallback(self):
        target = self.root / "common/log/settings.txt"
        for enabled, number in ((1, 1), (0, 2), (1, 3)):
            self.select_base(enabled)
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            if enabled:
                self.assertEqual(target.read_bytes(), b"COMMON_LOG_LEVEL=Warn\n")
                self.assertEqual(target.stat().st_nlink, 1)
                self.assertEqual(list(target.parent.glob(".open-connect-*")), [])
            else:
                self.assertFalse((self.root / "common").exists())
            self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)
        result = self.boot(4)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)

    def test_logging_conflict_preserves_other_provider_and_refuses_selected_marker(self):
        self.select_base(1)
        target = self.root / "common/log/settings.txt"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"another provider\n")
        result = self.boot(1, preserve_log=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b"another provider\n")
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)

    def test_service_policy_selects_both_ram_profiles_and_survives_fallback(self):
        composed = self.data / "composed" / self.package_id
        originals = {
            profile: (composed / f"sm-{profile}-on.conf").read_bytes()
            for profile in ("normal", "wcp")
        }
        for enabled, number in ((0, 1), (1, 2), (0, 3)):
            self.shell(
                'record_read; snapshot_read "$R_CURRENT"; '
                'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 1 disable "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - '
                + str(enabled)
                + "); record_write"
            )
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("sm.conf", "sm_WCP.conf"):
                jobs = {
                    node.get("name"): node
                    for node in ET.parse(self.runtime / "feature" / name).iter("service")
                }
                self.assertEqual(jobs["blm_ira_pandora"].get("autorun"), "yes" if enabled else "no")
                self.assertEqual(jobs["jciAAPA"].get("autorun"), "yes")
            for profile in ("normal", "wcp"):
                self.assertEqual(
                    (composed / f"sm-{profile}-on.conf").read_bytes(), originals[profile]
                )
        self.assertNotEqual(self.boot(4).returncode, 0)
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        config = (self.data / "snapshots" / self.record()[5] / "config").read_text()
        self.assertIn("service.pandora=0\n", config)

    def test_budget_nvram_apply_preserves_android_auto_off(self):
        self.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" service.android-auto 0 "$S_SCHEMA"); '
            'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" "$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" - "$prefs"); record_write'
        )
        self.assertEqual(self.boot(1).returncode, 0)
        jobs = {
            node.get("name"): node
            for node in ET.parse(self.runtime / "feature/sm.conf").iter("service")
        }
        self.assertEqual(jobs["jciAAPA"].get("autorun"), "no")
        self.assertEqual(jobs["blm_ira_pandora"].get("autorun"), "yes")
        self.shell("record_read; R_BUDGET=0; record_write")
        self.assertNotEqual(self.boot(2).returncode, 0)
        config = (self.data / "snapshots" / self.record()[5] / "config").read_text()
        self.assertIn("nvram=absent\n", config)
        self.assertIn("service.android-auto=0\n", config)
        self.assertIn("service.pandora=1\n", config)

    def test_reset_budget_is_finite_and_fallback_restores_nvram_without_losing_preferences(self):
        for number in range(1, 4):
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.record()[9], str(3 - number))
            self.assertTrue((self.runtime / "selected").exists())
        result = self.boot(4)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        self.assertEqual(self.record()[9], "0")
        config = (self.data / "snapshots" / self.record()[5] / "config").read_text()
        for line in ("touch=1\n", "warning=1\n", "nvram=absent\n", "service.android-auto=1\n"):
            self.assertIn(line, config)
        self.assertNotEqual(self.boot(5).returncode, 0)
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")

    def test_only_off_then_new_kernel_and_on_renews_attempts(self):
        self.assertEqual(self.boot(1).returncode, 0)
        self.shell("record_read; R_OFF=$R_BOOT; record_write")
        # The same kernel cannot consume or renew another attempt.
        self.assertNotEqual(self.boot(1).returncode, 0)
        self.assertEqual(self.record()[9], "2")
        (self.root / "acc").write_text("0\n")
        self.assertEqual(self.boot(2).returncode, 0)
        self.assertEqual(self.record()[9], "1")
        self.shell("record_read; R_OFF=$R_BOOT; record_write")
        (self.root / "acc").write_text("1\n")
        (self.root / "uptime").write_text("1.00 0.00\n")
        self.assertEqual(self.boot(3).returncode, 0)
        self.assertEqual(self.record()[9], "2")

    def test_ignition_requires_sustained_off_and_clears_quick_resume_evidence(self):
        self.assertEqual(self.boot(1).returncode, 0)
        boot = self.record()[11]
        script = (ASSETS / "ignition.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/proc/sys/kernel/random/boot_id": str(self.root / "boot-id"),
            "/proc/uptime": str(self.root / "uptime"),
            "/sys/class/gpio/ACC_Sense/value": str(self.root / "acc"),
        }.items():
            script = script.replace(old, new)
        (self.package / "ignition.sh").write_text(script)
        (self.root / "sequence").write_text("0\n1\n0\n0\n0\n1\nend\n")
        (self.root / "step").write_text("0\n")
        # Advance physical samples instead of waiting; capture the real record
        # after each observation, including a short OFF and same-kernel resume.
        (self.tools / "sleep").write_text(
            "#!/bin/sh\nset -eu\nR=" + shlex.quote(str(self.root)) + "\n"
            'cut -d "|" -f 11 "$R/data/record" >> "$R/observed"\n'
            'n=$(cat "$R/step"); n=$((n+1)); echo "$n" > "$R/step"\n'
            'next=$(sed -n "${n}p" "$R/sequence")\n'
            'if test "$next" = end; then echo changed > "$R/boot-id"; '
            'else printf "%s\\n" "$next" > "$R/acc"; fi\n'
        )
        (self.tools / "sleep").chmod(0o700)
        subprocess.run(
            ["sh", self.package / "ignition.sh", boot],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(
            (self.root / "observed").read_text().splitlines(), ["-", "-", "-", "-", "-", boot, "-"]
        )
        self.assertEqual(self.record()[9:11], ["2", "-"])

    def test_boot_finishes_interrupted_uninstall_from_ram_and_starts_stock(self):
        self.shell(r"""
. "$P/firmware.sh"
. "$P/transaction.sh"
AUTOSTART=$D-target
record_read
transaction_prepare uninstall "$R_CURRENT" "$R_BASE"
""")
        result = self.boot(1)
        # The hook uses Mazda's original configuration on a nonzero exit.
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.data.exists())
        self.assertEqual((self.root / "data-target").read_text(), "stock\n")
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        self.assertFalse((self.runtime / "selected").exists())
