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
        phone = ROOT / "runs/issue132-loading-ux/rootfs/jci/gui/apps/phone/js/phoneApp.js"
        subprocess.run(
            ["node", ROOT / "tests/fixtures/carplay.js", ASSETS, stock, CI17]
            + ([phone] if phone.is_file() else []),
            check=True,
            timeout=15,
        )


class PageBudgets(unittest.TestCase):
    def test_each_authored_inode_fits_its_allocated_pages(self):
        caps = {
            "carplay.js": 4096,
            "settings.js": 28672,
            "runtime.js": 16384,
            "maintenance.js": 20480,
            "dialog.js": 8192,
            "preferences.awk": 8192,
            "loader.js": 4096,
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
