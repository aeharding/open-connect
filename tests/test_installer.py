import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
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
                str(ROOT / "cmu/installer/settings.js"),
                str(ROOT / "cmu/installer/dialog.js"),
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

    def test_setting_compares_before_write_and_preserves_unknowns(self):
        # Ordinary files model reads, conflicts and commits to an existing key.
        # Only the actual target implements the kernel add/remove attributes.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            tools = base / "tools"
            tools.mkdir()
            if not shutil.which("flock"):
                (tools / "flock").write_text(
                    f"#!{sys.executable}\nimport fcntl,sys\n"
                    "fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                )
                (tools / "flock").chmod(0o700)
            keys = base / "keys"
            keys.mkdir()
            key = keys / "lvds_speed_restriction"
            commit = base / "commit"
            commit.write_text("untouched")
            version = base / "version"
            version.write_text(
                'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
            )
            script = (ROOT / "cmu/features/touch/setting.sh").read_text()
            for old, new in [
                ("/sys/class/nvram/nv-config", str(base)),
                ("/jci/version.ini", str(version)),
                ("/jci/lvds/lvds_service", str(version)),
                ("1d3e74362d4a97814a9f0fb316ff583f", hashlib.md5(version.read_bytes()).hexdigest()),
                ("/tmp/oc-lvds-setting.lock", str(base / "lock")),
            ]:
                self.assertIn(old, script)
                script = script.replace(old, new)

            # BSD md5sum can label stdin differently; on the CMU it labels it '-'.
            def run(*args):
                return subprocess.run(
                    ["/bin/sh", "-c", script, "touch", *args],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                )

            self.assertEqual(run("read").stdout, "absent\n")
            key.write_text("absent\n")
            self.assertNotEqual(run("read").returncode, 0)
            key.write_text("enable\n")
            self.assertEqual(run("change", "absent", "disable").returncode, 73)
            self.assertEqual(commit.read_text(), "untouched")
            self.assertEqual(run("change", "enable", "disable").stdout, "disable\n")
            self.assertEqual(key.read_text(), "disable\n")
            self.assertEqual(commit.read_text(), "\n")
            commit.unlink()
            commit.mkdir()
            self.assertNotEqual(run("change", "disable", "enable").returncode, 0)
            self.assertEqual(key.read_text(), "enable\n")
            commit.rmdir()
            commit.write_text("uncommitted")
            self.assertEqual(run("read").stdout, "enable\n")
            self.assertEqual(commit.read_text(), "uncommitted")
            self.assertEqual(run("change", "enable", "enable").returncode, 0)
            self.assertEqual(commit.read_text(), "\n")
            key.write_text("unexpected\n")
            self.assertNotEqual(run("change", "disable", "absent").returncode, 0)
            self.assertEqual(key.read_text(), "unexpected\n")
