import shlex
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from open_connect import usb

ROOT = Path(__file__).resolve().parents[1]


class UsbPreview(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_ui_lifetime_and_duplicate_session(self):
        subprocess.run(
            [
                "node",
                str(ROOT / "tests/fixtures/usb-preview.js"),
                str(ROOT / "cmu/installer/usb-preview.js"),
            ],
            check=True,
        )

    def test_trigger_only_selects_our_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, body in [
                ("sda1/run.sh", "echo WRONG"),
                ("sdb1/open-connect/run.sh", "echo OPEN_CONNECT"),
                ("sdc1/open-connect/run.sh", "echo DUPLICATE"),
            ]:
                target = root / "tmp/mnt" / name
                target.parent.mkdir(parents=True)
                target.write_text(body + "\n")
            # Map the CMU's root directory into this fixture; do not change HOME.
            command = usb.TRIGGER[2:-4].replace("S=${HOME%root}", "S=/")
            command = command.replace("P=${S}tmp", "P=" + shlex.quote(temp) + "${S}tmp")
            result = subprocess.run(
                ["sh", "-c", command],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "OPEN_CONNECT\n")

    def test_archive_has_literal_trigger_and_checked_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "build"
            archive = usb.build(output)
            with zipfile.ZipFile(archive) as z:
                self.assertIn(usb.TRIGGER, z.namelist())
                self.assertEqual(z.read(usb.TRIGGER), b"")
                self.assertIn("open-connect/KENATIA-LICENSE", z.namelist())
                self.assertFalse(any(".." in Path(n).parts for n in z.namelist()))
                launcher = z.read("open-connect/run.sh")
                self.assertNotIn(b"@CHECKS@", launcher)
                self.assertEqual(launcher.count(b"openssl dgst -sha256"), 3)
                self.assertIn(b"JCI_SW_VER_PATCH=", launcher)
                self.assertIn(b"JCI_SW_FLAVOR=", launcher)
                for name in ("run.sh", "session.sh"):
                    subprocess.run(["sh", "-n"], input=z.read("open-connect/" + name), check=True)
            with self.assertRaises(FileExistsError):
                usb.build(output)
