"""Exercise the on-device transaction in fresh shells with a temporary NVRAM model."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from open_connect.paths import ROOT


class TouchInstallation(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.key = self.base / "keys/lvds_speed_restriction"
        self.key.parent.mkdir()
        self.commit = self.base / "commit"
        self.commit.write_text("untouched")
        self.volume = self.base / "persist"
        self.volume.mkdir(mode=0o755)
        self.volume.chmod(0o755)
        self.receipt = self.volume / ".open-connect-touch-original-v1"
        self.script = self.base / "setting.sh"
        version = self.base / "version"
        version.write_text(
            'JCI_SW_VER="MAZ_CMU-150_55.00.750"\nJCI_SW_VER_PATCH="B"\nJCI_SW_FLAVOR="cmu150_NA"\n'
        )
        mounts = self.base / "mounts"
        mounts.write_text(f"/dev/mmcblk0p2 {self.volume} relfs rw,noatime 0 0\n")
        source = (ROOT / "cmu/features/touch/setting.sh").read_text()
        owners = f"{os.getuid()}:{os.getgid()}"
        # Redirect physical reads and model the two write-only kernel commands.
        # The receipt, lock, shell, commit and fsync operations run on real files.
        replacements = {
            "/sys/class/nvram/nv-config": str(self.base),
            "/tmp/mnt/data_persist": str(self.volume),
            "/proc/mounts": str(mounts),
            "/tmp/oc-lvds-setting.lock": str(self.base / "lock"),
            "/jci/version.ini": str(version),
            "/jci/lvds/lvds_service": str(version),
            "6bb6b50fb459f3a152b6528efbf5a95c": hashlib.md5(version.read_bytes()).hexdigest(),
            "0:0:755": owners + ":755",
            "0:0:600:1": owners + ":600:1",
            "stat -c": (shutil.which("gstat") or "stat") + " -c",
            """printf '%s=%s\\n' "$key" "$3" > "$store/add" """.strip(): '''printf '%s\\n' "$3" > "$store/keys/$key"''',
            """printf '%s\\n' "$key" > "$store/remove" """.strip(): '''rm "$store/keys/$key"''',
        }
        for old, new in replacements.items():
            self.assertIn(old, source)
            source = source.replace(old, new)
        self.script.write_text(source)
        self.flush = self.base / "flush-arm"
        subprocess.run(
            ["cc", "-DOC_HOST", str(ROOT / "cmu/startup/flush.c"), "-o", str(self.flush)],
            check=True,
        )

    def invoke(self, action, expected=0):
        result = subprocess.run(["sh", self.script, action], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.strip()

    def test_install_and_uninstall_in_separate_processes(self):
        for original in ("absent", "enable", "disable"):
            with self.subTest(original=original):
                if original == "absent":
                    self.key.unlink(missing_ok=True)
                else:
                    self.key.write_text(original + "\n")
                self.assertEqual(self.invoke("install"), "disable")
                self.assertEqual(self.invoke("install"), "disable")
                self.assertEqual(self.receipt.read_bytes(), (original + "\n").encode())
                self.assertEqual(self.invoke("uninstall"), original)
                self.assertEqual(self.invoke("read"), original)
                self.assertFalse(self.receipt.exists())
                self.commit.write_text("untouched")
                self.assertEqual(self.invoke("uninstall"), "unmanaged")
                self.assertEqual(self.commit.read_text(), "untouched")

    def test_unconfirmed_restore_keeps_original_for_retry(self):
        self.key.write_text("enable\n")
        self.invoke("install")
        self.commit.unlink()
        self.commit.mkdir()
        result = subprocess.run(["sh", self.script, "uninstall"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.receipt.read_bytes(), b"enable\n")
        self.commit.rmdir()
        self.commit.write_text("uncommitted")
        self.assertEqual(self.invoke("uninstall"), "enable")
        self.assertEqual(self.commit.read_text(), "\n")

    def test_invalid_receipt_and_conflicting_value_preserved(self):
        self.invoke("install")
        self.key.write_text("enable\n")
        self.commit.write_text("untouched")
        self.invoke("uninstall", 73)
        self.assertEqual(self.receipt.read_bytes(), b"absent\n")
        self.receipt.write_bytes(b"enable\0")
        self.invoke("install", 73)
        self.assertEqual(self.receipt.read_bytes(), b"enable\0")
        self.assertEqual(self.key.read_bytes(), b"enable\n")
        self.assertEqual(self.commit.read_text(), "untouched")
