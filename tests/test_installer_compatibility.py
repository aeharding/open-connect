"""Maintain the one actual predecessor using its verified writer and renderer."""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
OLD = ROOT / "tests/fixtures/dev9"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class PredecessorMaintenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.program = Path(cls.build.name) / "boot-select"
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-D_GNU_SOURCE",
                "-O2",
                ASSETS / "boot-select.c",
                "-o",
                cls.program,
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        from tests.test_installer_boot import InstallerBoot

        self.fixture = f = InstallerBoot(
            "test_populated_fast_path_keeps_budget_and_original_dependency_guards"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        package = f.data / "packages/.old"
        package.mkdir(mode=0o700)
        for name in (
            "state.sh",
            "firmware.sh",
            "access.sh",
            "transaction.sh",
            "wireless-sm.awk",
            "VERSION",
        ):
            shutil.copyfile(OLD / name, package / name)
        shutil.copyfile(f.source / "flush", package / "flush")
        (package / "flush").chmod(0o700)
        shutil.copyfile(self.program, package / "boot-select")
        (package / "boot-select").chmod(0o700)
        firmware = (package / "firmware.sh").read_text()
        for source, target in f.oem_adapters.items():
            firmware = firmware.replace(source, target)
        version = f.root / "version.ini"
        version.write_text("synthetic exact identity\n")
        for source, target in {
            "/jci/version.ini": str(version),
            "/config/common/log/settings.txt": str(f.root / "physical-log-settings"),
            "/jci/lib/libjcicommon.so": str(f.root / "common-library"),
            "/tmp/common": str(f.root / "common"),
            "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29": hashlib.sha256(
                f.manager.read_bytes()
            ).hexdigest(),
        }.items():
            firmware = firmware.replace(source, target)
        current_fw = (f.source / "firmware.sh").read_text()
        firmware += current_fw[current_fw.rindex("\nfirmware_guard()") :]
        (package / "firmware.sh").write_text(firmware)
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(package.iterdir())
        )
        (package / "files.sha256").write_text(manifest)
        self.old_id = hashlib.sha256(manifest.encode()).hexdigest()
        self.old_package = package.with_name(self.old_id)
        package.rename(self.old_package)
        shutil.copytree(f.data / "composed" / f.package_id, f.data / "composed" / self.old_id)
        # The actual dev.9 writer constructs both baseline and active policy.
        self.run_shell(r"""
P=$OLD
. "$P/state.sh"; . "$P/firmware.sh"; . "$P/access.sh"; . "$P/transaction.sh"
uuid() { openssl rand -hex 16; }
R_BACKEND=${OLD##*/}
R_BASE=$(snapshot_create "$D/stock" - 0 0 absent "755:$(id -u):$(id -g)")
deps=$(mktemp "$D/.old-deps-XXXXXX"); dependencies_capture "$R_BACKEND" > "$deps"
R_CURRENT=$(snapshot_create "$AUTOSTART" "$R_BACKEND" 1 1 disable "755:$(id -u):$(id -g)" "$deps" - 1 0 0)
rm "$deps"
R_PHASE=active; R_BEFORE=-; R_AFTER=-; R_BUDGET=3; R_OFF=-; R_BOOT=-; R_NOTICE=-
record_write
R_CURRENT=$(boot_snapshot_seal "$R_CURRENT"); record_write
""")
        self.baseline = f.record()[4]
        self.assertEqual(
            len((f.data / "snapshots" / self.baseline / "config").read_text().strip().split("|")), 5
        )

    def run_shell(self, script, check=True):
        f = self.fixture
        result = subprocess.run(
            [
                "sh",
                "-c",
                "set -eu; umask 077; D=$1; P=$2; OLD=$3; AUTOSTART=$D-target; "
                '. "$P/state.sh"; . "$P/firmware.sh"; . "$P/access.sh"; . "$P/transaction.sh";\n'
                + script,
                "maintenance",
                f.data,
                f.package,
                self.old_package,
            ],
            env=f.env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_new_media_set_and_pending_recovery_keep_dev9_serializer_and_renderer(self):
        result = self.run_shell(
            r"""
record_read; snapshot_read "$R_CURRENT"
prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" service.pandora 0 "$S_SCHEMA")
after=$(snapshot_create "$AUTOSTART" "$S_PACKAGE" "$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$prefs")
transaction_prepare set "$R_CURRENT" "$after"
exit 9
""",
            check=False,
        )
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(self.fixture.record()[1], "set")
        self.run_shell("record_read; transaction_reconcile")
        f = self.fixture
        self.assertEqual(f.record()[4], self.baseline)
        snapshot = f.data / "snapshots" / f.record()[5]
        fields = (snapshot / "config").read_text().strip().split("|")
        self.assertEqual(len(fields), 8)
        self.assertEqual(fields[0], self.old_id)
        self.assertEqual(fields[5], "0")
        for name in ("sm-normal.conf", "sm-wcp.conf"):
            jobs = {node.get("name"): node for node in ET.parse(snapshot / name).iter("service")}
            self.assertEqual(jobs["blm_ira_pandora"].get("autorun"), "no")
            self.assertEqual(jobs["jciAAPA"].get("autorun"), "yes")
        self.assertTrue((snapshot / "boot.plan").is_file())

    def test_pending_upgrade_has_old_current_and_first_canonical_after(self):
        result = self.run_shell(
            r"""
record_read; snapshot_read "$R_CURRENT"; prefs=$S_PREFS
before=$R_CURRENT; R_BACKEND=${P##*/}
deps=$(mktemp "$D/.new-deps-XXXXXX"); dependencies_capture "$R_BACKEND" > "$deps"
after=$(snapshot_create "$AUTOSTART" "$R_BACKEND" "$S_NVRAM" "$S_META" "$deps" - "$prefs")
rm "$deps"
transaction_prepare install "$before" "$after"
exit 9
""",
            check=False,
        )
        self.assertEqual(result.returncode, 9, result.stderr)
        f = self.fixture
        record = f.record()
        self.assertEqual(record[3], f.package_id)
        self.assertTrue(
            (f.data / "snapshots" / record[7] / "config").read_text().startswith("OC2\n")
        )
        self.assertEqual(
            len((f.data / "snapshots" / record[5] / "config").read_text().strip().split("|")), 8
        )
        self.run_shell("record_read; transaction_reconcile")
        self.assertEqual(f.record()[4], self.baseline)
        self.assertEqual(f.record()[1], "active")
        config = (f.data / "snapshots" / f.record()[5] / "config").read_text()
        self.assertIn("service.android-auto=1\n", config)
        self.assertIn("service.pandora=1\n", config)
