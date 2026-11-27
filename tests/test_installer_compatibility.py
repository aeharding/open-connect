"""Verify active dev.9 snapshots are explicitly refused while stock baselines remain readable."""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
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
        core_srcs = [p for p in sorted((ASSETS / "core").glob("*.c")) if p.name != "oc-api.c"]
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-D_GNU_SOURCE",
                "-std=c11",
                "-O2",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                ASSETS / "boot-select.c",
                *core_srcs,
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
        # Dev.9 still owns the historical composed System member. The current
        # package uses the OEM URL and a page hook instead; keep fixtures distinct.
        (f.data / "composed" / self.old_id / "system-app.js").write_text("old System fixture\n")
        f.composed_manifest(self.old_id)
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

    def test_active_dev9_snapshots_are_explicitly_refused_without_mutating_state(self):
        before = (self.fixture.data / "record").read_bytes()
        result = self.run_shell(
            r"""
record_read
snapshot_read "$R_CURRENT"
""",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.fixture.data / "record").read_bytes(), before)
        # snapshot_package also refuses 8-field active dev.9 configs.
        pkg_dev9 = self.run_shell('record_read; snapshot_package "$R_CURRENT"', check=False)
        self.assertNotEqual(pkg_dev9.returncode, 0)
        # 5-field stock baseline (R_BASE) remains readable by snapshot_read and snapshot_package.
        stock = self.run_shell(
            r"""
record_read
test "$(snapshot_package "$R_BASE")" = -
snapshot_read "$R_BASE"
test "$S_SCHEMA:$S_PACKAGE" = "stock:-"
"""
        )
        self.assertEqual(stock.returncode, 0, stock.stderr)

    def test_legacy_dev9_package_snapshot_create_and_seal_are_refused(self):
        before = (self.fixture.data / "record").read_bytes()
        create = self.run_shell(
            r"""
record_read
snapshot_create "$AUTOSTART" "$R_BACKEND" disable "755:$(id -u):$(id -g)" "$D/snapshots/$R_CURRENT/dependencies" - ""
""",
            check=False,
        )
        self.assertNotEqual(create.returncode, 0)
        self.assertIn("unsupported_snapshot_package", create.stderr)
        seal = self.run_shell(
            r"""
record_read
boot_snapshot_seal "$R_CURRENT"
""",
            check=False,
        )
        self.assertNotEqual(seal.returncode, 0)
        self.assertEqual((self.fixture.data / "record").read_bytes(), before)
