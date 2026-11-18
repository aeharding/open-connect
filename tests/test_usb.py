"""Check the real Make/shell build and the staged USB entry, without a CMU."""

import hashlib
import os
import shlex
import shutil
import struct
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
TRIGGER = next((ASSETS / "usb-root").glob("*.up")).name
STATIC = ("run.sh", "session.sh", "loader.js", "dialog.js", "usb-preview.js")
PAYLOAD = (*STATIC[1:], "receiver")


class UsbBuild(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_ui_lifetime_and_cancel_during_loading(self):
        for name in ("usb-preview", "usb-loader"):
            subprocess.run(
                [
                    "node",
                    str(ROOT / f"tests/fixtures/{name}.js"),
                    str(ASSETS / ("loader.js" if name == "usb-loader" else "usb-preview.js")),
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
            command = TRIGGER[2:-4].replace("S=${HOME%root}", "S=/")
            command = command.replace("P=${S}tmp", "P=" + shlex.quote(temp) + "${S}tmp")
            result = subprocess.run(["sh", "-c", command], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "OPEN_CONNECT\n")

    def test_release_is_static_files_and_standard_native_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "build"
            command = ["make", "release", "OUT=" + str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("python", result.stdout.lower())
            with zipfile.ZipFile(output / "open-connect-usb-preview.zip") as z:
                expected = {TRIGGER, "jci-autoupdate"} | {
                    "open-connect/" + f
                    for f in (*STATIC, "receiver", "payload.sha256", "LICENSE", "KENATIA-LICENSE")
                }
                self.assertEqual({n for n in z.namelist() if not n.endswith("/")}, expected)
                self.assertEqual(z.read(TRIGGER), b"")
                for name in STATIC:
                    self.assertEqual(z.read("open-connect/" + name), (ASSETS / name).read_bytes())
                for name in ("run.sh", "session.sh"):
                    subprocess.run(["sh", "-n"], input=z.read("open-connect/" + name), check=True)
                rows = [
                    line.split()
                    for line in z.read("open-connect/payload.sha256").decode().splitlines()
                ]
                self.assertEqual({name for _, name in rows}, set(PAYLOAD))
                self.assertEqual(len(rows), len(PAYLOAD))
                for digest, name in rows:
                    self.assertEqual(
                        hashlib.sha256(z.read("open-connect/" + name)).hexdigest(), digest
                    )
            self.assertEqual(
                struct.unpack("<II", (output / "sizes.bin").read_bytes()),
                (0x48C00 + len((output / "native.bin").read_bytes()),) * 2,
            )
            self.assertLessEqual(len((output / "native.bin").read_bytes()), 1024)
            self.assertEqual(len((output / "branch.bin").read_bytes()), 4)
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("fresh OUT", again.stderr)

    def test_staging_checks_manifest_before_executing_payload(self):
        # Rewrite physical paths only; exercise the actual staging/hash loop with
        # real local files. No firmware bytes, mount commands or device access.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            package = root / "tmp/mnt/sda1/open-connect"
            package.mkdir(parents=True)
            (root / "version").write_text(
                'JCI_SW_VER="MAZ_CMU-150_55.00.750"\nJCI_SW_VER_PATCH="B"\nJCI_SW_FLAVOR="cmu150_NA"\n'
            )
            (root / "original").write_bytes(b"fixture")
            digest = hashlib.md5(b"fixture").hexdigest()
            script = (ASSETS / "run.sh").read_text()
            replacements = {
                "PATH=/sbin:/bin:/usr/sbin:/usr/bin": "PATH=" + shlex.quote(os.environ["PATH"]),
                '"$(id -u)" = 0': f'"$(id -u)" = {os.getuid()}',
                "/jci/version.ini": str(root / "version"),
                "/jci/gui/index.html": str(root / "original"),
                "/jci/gui/framework/js/GuiFramework.js": str(root / "original"),
                "0ad187b787e242953a9a7612f55bfcfb": digest,
                "e90530cdb9b05922bdcaade8757ea1f9": digest,
                "/tmp/mnt/sd": str(root / "tmp/mnt/sd"),
                "/tmp/open-connect-usb.lock": str(root / "lock"),
                "/tmp/oc-usb-XXXXXX": str(root / "staged-XXXXXX"),
                "token=$(tr -d '-' < /proc/sys/kernel/random/uuid).$(cat /proc/sys/kernel/random/boot_id)": "token=fixture",
            }
            for old, new in replacements.items():
                self.assertIn(old, script)
                script = script.replace(old, new)
            (package / "run.sh").write_text(script)
            marker = root / "executed"
            for name in PAYLOAD:
                (package / name).write_text("fixture\n")
            (package / "session.sh").write_text(
                "printf '%s' executed > " + shlex.quote(str(marker)) + "\n"
            )
            manifest = "".join(
                hashlib.sha256((package / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in PAYLOAD
            )
            for broken in (
                manifest.replace("  receiver", "  ../../elsewhere"),
                manifest.replace("  receiver", "  loader.js"),
                manifest.replace(manifest.split()[0], "f" * 64),
            ):
                (package / "payload.sha256").write_text(broken)
                result = subprocess.run(
                    ["sh", str(package / "run.sh")], capture_output=True, timeout=5
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())
                self.assertFalse((root / "lock").exists())
                self.assertEqual(list(root.glob("staged-*")), [])
            (package / "payload.sha256").write_text(manifest)
            result = subprocess.run(["sh", str(package / "run.sh")], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            for _ in range(30):
                if marker.exists():
                    break
                time.sleep(0.05)
            self.assertEqual(marker.read_text(), "executed")
