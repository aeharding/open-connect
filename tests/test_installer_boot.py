"""Run the actual selector with real records and simulated physical adapters."""

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
        (self.root / "acc").write_text("1\n")
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
        (self.source / "firmware.sh").write_text(r"""
firmware_guard() { :; }
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
""")
        (self.source / "service.sh").write_text(
            "printf '%s\\n' " + shlex.quote(str(self.runtime)) + "\n"
        )
        script = (ASSETS / "boot.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/usr/bin/autostart": str(self.root / "data-target"),
            "/proc/sys/kernel/random/boot_id": str(self.root / "boot-id"),
            "/sys/class/gpio/ACC_Sense/value": str(self.root / "acc"),
        }.items():
            script = script.replace(old, new)
        (self.source / "boot.sh").write_text(script)
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
            "system-app.js",
            "sm-normal-on.conf",
            "sm-wcp-on.conf",
            "index-on.html",
            "index-off.html",
        ):
            (composed / name).write_text("synthetic feature @TOKEN@\n")
        for profile in ("normal", "wcp"):
            for setting in ("on", "off"):
                (composed / f"sm-{profile}-{setting}.conf").write_text(f"{profile} {setting}\n")
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        self.shell(r"""
printf 'stock\n' > "$D/stock"; chmod 755 "$D/stock"
R_BASE=$(snapshot_create "$D/stock" - 0 0 absent "755:$(id -u):$(id -g)")
printf 'installed\n' > "$D-target"; chmod 755 "$D-target"
cp "$D-target" "$D/composed/$R_BACKEND/autostart"
printf 'disable\n' > "$D-nvram"
R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 1 disable "755:$(id -u):$(id -g)")
R_PHASE=active; R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=3; R_OFF=-; R_BOOT=-; R_NOTICE=installed
record_write
""")

    def shell(self, script):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; R_BACKEND=$3; . "$P/state.sh"\n' + script,
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

    def boot(self, number):
        boot_id = "00000000-0000-0000-0000-" + f"{number:012x}"
        (self.root / "boot-id").write_text(boot_id + "\n")
        shutil.rmtree(self.runtime / "feature", ignore_errors=True)
        (self.runtime / "selected").unlink(missing_ok=True)
        return subprocess.run(
            ["sh", self.package / "boot.sh"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def record(self):
        return (self.data / "record").read_text().strip().split("|")

    def test_both_board_configurations_follow_selected_warning_preference(self):
        for warning, number in ((1, 1), (0, 2)):
            with self.subTest(warning=warning):
                self.shell(
                    'record_read; snapshot_read "$R_CURRENT"; '
                    'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 '
                    + str(warning)
                    + ' disable "$S_META"); record_write'
                )
                result = self.boot(number)
                self.assertEqual(result.returncode, 0, result.stderr)
                setting = "on" if warning else "off"
                for profile, name in (("normal", "sm.conf"), ("wcp", "sm_WCP.conf")):
                    self.assertEqual(
                        (self.runtime / "feature" / name).read_text(), f"{profile} {setting}\n"
                    )

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
        config = (self.data / "snapshots" / self.record()[5] / "config").read_text().split("|")
        self.assertEqual(config[1:4], ["1", "1", "absent"])
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
