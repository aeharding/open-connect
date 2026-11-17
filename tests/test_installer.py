import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerControls(unittest.TestCase):
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

    def test_setting_compares_before_write_and_preserves_unknowns(self):
        # Ordinary files model reads, conflicts and commits to an existing key.
        # Only the actual target implements the kernel add/remove attributes.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            keys = base / "keys"
            keys.mkdir()
            key = keys / "lvds_speed_restriction"
            commit = base / "commit"
            commit.write_text("untouched")
            version = base / "version"
            version.write_text(
                'JCI_SW_VER="MAZ_CMU-150_55.00.750"\nJCI_SW_VER_PATCH="B"\nJCI_SW_FLAVOR="cmu150_NA"\n'
            )
            script = (ROOT / "cmu/features/touch/setting.sh").read_text()
            for old, new in [
                ("/sys/class/nvram/nv-config", str(base)),
                ("/jci/version.ini", str(version)),
                ("/jci/lvds/lvds_service", str(version)),
                ("6bb6b50fb459f3a152b6528efbf5a95c", hashlib.md5(version.read_bytes()).hexdigest()),
                ("/tmp/oc-lvds-setting.lock", str(base / "lock")),
            ]:
                self.assertIn(old, script)
                script = script.replace(old, new)

            # BSD md5sum can label stdin differently; on the CMU it labels it '-'.
            def run(*args):
                return subprocess.run(
                    ["/bin/sh", "-c", script, "touch", *args], capture_output=True, text=True
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
