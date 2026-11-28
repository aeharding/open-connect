"""Feed real native api USB metadata to the USB popup without reshaping its reply."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.host_bins import host_api

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang") and shutil.which("node"), "Clang and Node.js required")
class USBMetadataContract(unittest.TestCase):
    def check_popup(self, expected):
        api_bin = host_api()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram = root / "tmp/open-connect"
            data = root / "tmp/mnt/data_persist/open-connect"
            sess = ram / "sessions/session-usb001"
            for d in (ram, sess, root / "tmp/mnt/data_persist", root / "proc/self", root / "dev"):
                d.mkdir(parents=True, exist_ok=True)
            for d in (ram, ram / "sessions", sess):
                d.chmod(0o700)
            (ram / "lock").write_bytes(b"")
            (ram / "lock").chmod(0o600)
            (ram / "usb-runtime").symlink_to(sess)
            (sess / "VERSION").write_bytes((ASSETS / "VERSION").read_bytes())
            (sess / "VERSION").chmod(0o600)
            if expected == "pending":
                data.mkdir(parents=True, mode=0o700)
                pkg = "a" * 64
                snap = "b" * 64
                base = "c" * 64
                (data / "record").write_text(
                    f"OC1|uninstall|{'1' * 32}|{pkg}|{base}|{snap}|{snap}|{base}|-|3|-|-|-\n"
                )
                (data / "record").chmod(0o600)
            env = {
                **os.environ,
                "OC_HOST_ROOT": str(root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(root / "no-wireless"),
            }
            result = subprocess.run(
                [str(api_bin), "--handle", str(sess), "-", "status", "settings", "-", "-"],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metadata = json.loads(result.stdout)
            self.assertNotIn("conflict", metadata)
            reply = subprocess.run(
                [
                    "node",
                    ROOT / "tests/fixtures/usb-metadata.js",
                    ASSETS,
                    expected,
                ],
                input=result.stdout,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(reply.returncode, 0, reply.stdout + reply.stderr)

    def test_fresh_usb_chooser_accepts_actual_metadata(self):
        self.check_popup("fresh")

    def test_pending_usb_recovery_accepts_actual_metadata(self):
        self.check_popup("pending")
