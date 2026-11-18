"""Check the real Make/shell build and the staged USB entry, without a CMU."""

import hashlib
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
TRIGGER = next((ASSETS / "usb-root").glob("*.up")).name
STATIC = (
    "run.sh",
    "session.sh",
    "service.sh",
    "loader.js",
    "runtime.js",
    "dialog.js",
    "settings.js",
    "backend.sh",
    "state.sh",
    "transaction.sh",
    "firmware.sh",
    "boot.sh",
    "startup-hook.sh",
    "ignition.sh",
    "intro.js",
    "system-route.js",
    "VERSION",
    "KENATIA-LICENSE",
)
COMPILED = (
    "api",
    "flush",
    "native.bin",
    "branch.bin",
    "sizes.bin",
    "mmui-path.bin",
    "mmui-sizes.bin",
    "mmui-length.bin",
    "mmui-pointer.bin",
)
PAYLOAD = (*STATIC, *COMPILED, "touch.sh", "LICENSE")


class UsbBuild(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_ui_lifetime_and_cancel_during_loading(self):
        for name in ("usb-loader",):
            subprocess.run(
                [
                    "node",
                    str(ROOT / f"tests/fixtures/{name}.js"),
                    str(ASSETS / "loader.js"),
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
            version = (ASSETS / "VERSION").read_text().strip()
            with zipfile.ZipFile(output / f"open-connect-{version}-usb.zip") as z:
                expected = {TRIGGER, "jci-autoupdate"} | {
                    "open-connect/" + f for f in (*PAYLOAD, "files.sha256")
                }
                self.assertEqual({n for n in z.namelist() if not n.endswith("/")}, expected)
                self.assertEqual(z.read(TRIGGER), b"")
                for name in STATIC:
                    self.assertEqual(z.read("open-connect/" + name), (ASSETS / name).read_bytes())
                for name in (n for n in PAYLOAD if n.endswith(".sh")):
                    subprocess.run(["sh", "-n"], input=z.read("open-connect/" + name), check=True)
                rows = [
                    line.split()
                    for line in z.read("open-connect/files.sha256").decode().splitlines()
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
            tools = root / "tools"
            tools.mkdir()
            if shutil.which("gstat"):
                (tools / "stat").symlink_to(shutil.which("gstat"))
            if not shutil.which("flock"):
                (tools / "flock").write_text(
                    f"#!{sys.executable}\nimport fcntl,sys\n"
                    "fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                )
                (tools / "flock").chmod(0o700)
            script = (ASSETS / "run.sh").read_text()
            replacements = {
                "PATH=/sbin:/bin:/usr/sbin:/usr/bin": "PATH="
                + shlex.quote(str(tools) + os.pathsep + os.environ["PATH"]),
                '"$(id -u)" = 0': f'"$(id -u)" = {os.getuid()}',
                "/jci/version.ini": str(root / "version"),
                "/tmp/mnt/sd": str(root / "tmp/mnt/sd"),
                "/tmp/open-connect-usb.lock": str(root / "lock"),
                "/tmp/oc-usb-XXXXXX": str(root / "staged-XXXXXX"),
            }
            for old, new in replacements.items():
                self.assertIn(old, script)
                script = script.replace(old, new)
            (package / "run.sh").write_text(script)
            marker = root / "executed"
            payload = ("loader.js", "session.sh", "api", "flush")
            for name in payload:
                (package / name).write_text("fixture\n")
            (package / "session.sh").write_text(
                "printf '%s' executed > " + shlex.quote(str(marker)) + "\n"
            )
            manifest = "".join(
                hashlib.sha256((package / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in payload
            )
            for broken in (
                manifest.replace("  api", "  ../../elsewhere"),
                manifest.replace("  api", "  loader.js"),
                manifest.replace(manifest.split()[0], "f" * 64),
            ):
                (package / "files.sha256").write_text(broken)
                result = subprocess.run(
                    ["sh", str(package / "run.sh")], capture_output=True, timeout=5
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())
                self.assertEqual(list(root.glob("staged-*")), [])
            (package / "files.sha256").write_text(manifest)
            result = subprocess.run(["sh", str(package / "run.sh")], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            for _ in range(30):
                if marker.exists():
                    break
                time.sleep(0.05)
            self.assertEqual(marker.read_text(), "executed")
