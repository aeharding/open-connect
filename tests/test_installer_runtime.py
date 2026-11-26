"""Check the authored browser client against its actual POST contract."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerRuntime(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_native_usb_receiver_preserves_settings_and_generation(self):
        subprocess.run(
            ["node", ROOT / "tests/fixtures/usb-receiver.js", ROOT / "cmu/installer"],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_page_owned_system_hook(self):
        subprocess.run(
            ["node", ROOT / "tests/fixtures/system-hook.js", ROOT / "cmu/installer/system-hook.js"],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_installed_settings_remains_independent(self):
        subprocess.run(
            [
                "node",
                ROOT / "tests/fixtures/installed-runtime.js",
                ROOT / "cmu/installer",
            ],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_maintenance_recovery_and_unknown_acknowledgements(self):
        subprocess.run(
            [
                "node",
                ROOT / "tests/fixtures/maintenance-runtime.js",
                ROOT / "cmu/installer",
            ],
            check=True,
        )
