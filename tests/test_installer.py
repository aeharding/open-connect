import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerControls(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_installer_javascript_es5_syntax(self):
        subprocess.run(
            ["node", ROOT / "tests/fixtures/installer-es5.js", ROOT / "cmu/installer"],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_oem_dialog_choice_lifecycle(self):
        subprocess.run(
            [
                "node",
                str(ROOT / "tests/fixtures/installer-dialog.js"),
                str(ROOT / "cmu/installer/dialog.js"),
            ],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_oem_settings_pages(self):
        subprocess.run(
            [
                "node",
                str(ROOT / "tests/fixtures/installer-settings.js"),
                str(ROOT / "cmu/installer/dialog.js"),
                str(ROOT / "cmu/installer/settings.js"),
            ],
            check=True,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_settings_transitions_cache_and_apply(self):
        subprocess.run(
            [
                "node",
                ROOT / "tests/fixtures/installer-settings-ux.js",
                ROOT / "cmu/installer/dialog.js",
                ROOT / "cmu/installer/settings.js",
            ],
            check=True,
        )
