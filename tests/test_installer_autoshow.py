"""Exercise page-owned autoshow without devices or extracted firmware."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
CI17 = ROOT / "runs/loading-ux-20261124/ci-ad10c3a/extracted/open-connect"


@unittest.skipUnless(shutil.which("node"), "Node.js required")
class CarPlayAutoshow(unittest.TestCase):
    def test_connection_and_owner_lifecycles(self):
        subprocess.run(
            ["node", ROOT / "tests/fixtures/carplay.js", ROOT / "cmu/installer"],
            check=True,
            timeout=15,
        )

    @unittest.skipUnless(CI17.is_dir(), "private archived CI17 bundle required")
    def test_archived_browser_handoff(self):
        stock = ROOT / "runs/wave-c-20261123/firmware/jci/gui/framework/js/Websockets.js"
        if not stock.is_file():
            self.skipTest("private exact-v74 Websockets required")
        subprocess.run(
            ["node", ROOT / "tests/fixtures/carplay.js", ASSETS, stock, CI17],
            check=True,
            timeout=15,
        )


class PageBudgets(unittest.TestCase):
    def test_each_authored_inode_fits_its_allocated_pages(self):
        caps = {
            "carplay.js": 4096,
            "settings.js": 28672,
            "runtime.js": 16384,
            "dialog.js": 8192,
            "preferences.awk": 8192,
            "loader.js": 4096,
            "backend.sh": 20480,
            "state.sh": 20480,
            "firmware.sh": 45056,
            "transaction.sh": 16384,
            "service.sh": 16384,
        }
        for name, cap in caps.items():
            with self.subTest(name=name):
                self.assertLessEqual((ASSETS / name).stat().st_size, cap)
        # Each USB/session copy pays for its own observer with one Settings page.
        self.assertEqual(caps["settings.js"] + caps["carplay.js"], 32768)


@unittest.skipUnless(
    CI17.is_dir() and shutil.which("clang"), "private archived CI17 bundle and Clang required"
)
class ArchivedMaintenance(unittest.TestCase):
    def test_upgrade_defaults_and_old_writer_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"

            def write(package, data=None):
                catalog = package / "services.tsv"
                args = [
                    "awk",
                    "-v",
                    "operation=write",
                    "-v",
                    "catalog=" + str(catalog),
                    "-v",
                    "catalog_bytes=" + str(catalog.stat().st_size),
                    "-v",
                    "package_id=" + "a" * 64,
                    "-v",
                    "metadata_value=755:0:0",
                    "-v",
                    "nvram_value=disable",
                ]
                if data is not None:
                    config.write_bytes(data)
                    args += ["-v", "input=" + str(config), "-v", "input_bytes=" + str(len(data))]
                return subprocess.run(
                    [*args, "-f", package / "preferences.awk"], capture_output=True, timeout=5
                )

            old = write(CI17)
            self.assertEqual(old.returncode, 0, old.stderr)
            upgraded = write(ASSETS, old.stdout)
            self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
            self.assertIn(b"carplay-autoshow=0\n", upgraded.stdout)
            refused = write(CI17, upgraded.stdout)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(refused.stdout, b"")

    def test_actual_ci17_decoder_and_direct_uninstall_accept_new_snapshot(self):
        from tests.test_installer_boot import InstallerBoot

        f = InstallerBoot("test_shell_autoshow_copy_follows_selected_snapshot_and_absent_defaults")
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" carplay-autoshow 1 OC2); '
            'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" "$S_NVRAM" "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" - "$prefs"); record_write'
        )
        current = f.record()[5]
        decoded = f.shell(
            '. "' + str(CI17 / "state.sh") + '"; '
            'config_decode "$D/snapshots/' + current + '/config"; '
            'test "$S_PACKAGE" = "$R_BACKEND"'
        )
        self.assertEqual(decoded.returncode, 0, decoded.stderr)
        client = f.runtime / "old-ci17"
        shutil.copytree(CI17, client)
        # Actual archived control/state/transaction code; only physical firmware
        # boundaries and ARM flush are replaced by the shared local-file adapter.
        shutil.copyfile(f.package / "firmware.sh", client / "firmware.sh")
        shutil.copyfile(f.source / "flush", client / "flush")
        for script in client.glob("*.sh"):
            text = (
                script.read_text()
                .replace(
                    "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                    "uuid() { openssl rand -hex 16; }",
                )
                .replace("/tmp/mnt/data_persist/open-connect", str(f.data))
                .replace("/tmp/open-connect", str(f.runtime))
                .replace("/usr/bin/autostart", str(f.root / "data-target"))
            )
            script.write_text(text)
        (client / "flush").chmod(0o700)
        (f.runtime / "runtime").symlink_to(client)
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", current, "uninstall", "-", "-", "-"],
            env=f.env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(f.data.exists())
        self.assertEqual((f.root / "data-target").read_text(), "stock\n")
