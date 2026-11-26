"""Feed real backend metadata to the USB popup without reshaping its reply."""

import shutil
import subprocess
import unittest

from tests import test_installer_transaction as transaction


@unittest.skipUnless(shutil.which("clang") and shutil.which("node"), "Clang and Node.js required")
class USBMetadataContract(unittest.TestCase):
    def fixture(self):
        fixture = transaction.InstallerTransaction()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def check_popup(self, fixture, data, expected):
        fixture.backend_fixture(data)
        runtime = fixture.root / "runtime"
        (runtime / "runtime").unlink()
        (runtime / "usb-runtime").symlink_to(fixture.tools)
        result, metadata = fixture.api("status", argument="settings")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("conflict", metadata)
        reply = subprocess.run(
            [
                "node",
                transaction.ROOT / "tests/fixtures/usb-metadata.js",
                transaction.ROOT / "cmu/installer",
                expected,
            ],
            input=result.stdout,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(reply.returncode, 0, reply.stdout + reply.stderr)

    def test_fresh_usb_chooser_accepts_actual_metadata(self):
        fixture = self.fixture()
        self.check_popup(fixture, fixture.root / "absent", "fresh")

    def test_pending_usb_recovery_accepts_actual_metadata(self):
        fixture = self.fixture()
        data = fixture.create("pending")
        fixture.run_ok(data, "install")
        cut = fixture.run_command(data, "uninstall", "prepared")
        self.assertNotEqual(cut.returncode, 0)
        self.assertEqual((data / "record").read_text().split("|")[1], "uninstall")
        self.check_popup(fixture, data, "pending")
