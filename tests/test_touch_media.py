"""Tagged dev.23 scripts against real snapshots, with host physical adapters."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from tests import test_installer_transaction as transactions

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = os.environ.get("OC_TEST_DEV23_USB")


@unittest.skipUnless(
    ARCHIVE and Path(ARCHIVE).is_file(), "set OC_TEST_DEV23_USB to the tagged dev.23 USB archive"
)
class TouchOldMedia(unittest.TestCase):
    def setUp(self):
        self.fixture = transactions.InstallerTransaction()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.data = f.create("old-media")
        f.run_ok(self.data, "install")
        f.backend_fixture(self.data)
        for folder in ("packages", "composed"):
            (self.data / folder).chmod(0o700)
        self.media = f.root / "media"
        self.media.mkdir(mode=0o700)
        self.assertEqual(
            hashlib.sha256(Path(ARCHIVE).read_bytes()).hexdigest(),
            "df2f6922d9927b5bc762c71fc6d944d3317998e4c7cf7b4aa6da2a988c67d6b7",
        )
        with zipfile.ZipFile(ARCHIVE) as archive:
            manifest = archive.read("open-connect/files.sha256").decode()
            for row in manifest.splitlines():
                digest, name = row.split()
                content = archive.read("open-connect/" + name)
                self.assertEqual(hashlib.sha256(content).hexdigest(), digest)
                (self.media / name).write_bytes(content)
        # Only physical OS adapters and target binaries are replaced. The actual
        # archived backend/state/preferences/transaction execute unchanged apart
        # from temporary path and random-source substitution.
        shutil.copyfile(f.tools / "flush", self.media / "flush")
        (self.media / "flush").chmod(0o700)
        runtime = f.root / "runtime"
        login = f.root / "runlogin"
        login.write_text("host original login\n")
        login.chmod(0o755)
        for name in (
            "backend.sh",
            "state.sh",
            "transaction.sh",
            "service.sh",
            "usb-service.sh",
            "access.sh",
        ):
            path = self.media / name
            text = (
                path.read_text()
                .replace("/tmp/open-connect", str(runtime))
                .replace("/tmp/mnt/data_persist/open-connect", str(self.data))
                .replace("/usr/bin/autostart", str(f.target(self.data, "target")))
                .replace("/usr/bin/runlogin", str(login))
                .replace("/usr/bin/.open-connect-runlogin-", str(f.root / ".runlogin-"))
                .replace("/proc/uptime", str(f.root / "uptime"))
            )
            text = text.replace(
                "b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8",
                hashlib.sha256(login.read_bytes()).hexdigest(),
            )
            text = text.replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
            path.write_text(text)
        firmware = (
            (self.media / "firmware.sh").read_text() + "\n" + (f.tools / "firmware.sh").read_text()
        )
        firmware += """
stock_dependencies() { :; }
originals_save() { :; }
compose() {
    mkdir -p "$D/composed/$1"
    cp "$AUTOSTART" "$D/composed/$1/autostart"
}
boot_render_profiles() {
    config_decode "$2" || return 1
    for name in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do
        printf 'host profile\n' > "$1/$name"
    done
}
boot_snapshot_seal() { printf '%s\n' "$1"; }
"""
        (self.media / "firmware.sh").write_text(firmware)
        # Developer/selector target publication is outside this touchscreen
        # compatibility fixture. Actual root and NVRAM CAS/transactions remain.
        with (self.media / "access.sh").open("a") as stream:
            stream.write(
                "\naccess_capture() { :; }\naccess_compose() { :; }\n"
                "selector_capture() { :; }\nselector_compose() { :; }\n"
            )
        self.write_manifest(self.media)
        (runtime / "usb-runtime").symlink_to(self.media)
        # No listener in this host fixture. A boot-selected modern endpoint
        # remains covered by the installed ownership tests elsewhere.

    @staticmethod
    def write_manifest(folder):
        (folder / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(folder.iterdir())
                if p.name != "files.sha256"
            )
        )

    def api(self, operation, revision, argument="-", media=None):
        return subprocess.run(
            [
                "sh",
                (media or self.media) / "backend.sh",
                "api",
                revision,
                operation,
                argument,
                "-",
                "-",
            ],
            env={**os.environ, "PATH": str(self.fixture.tools) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=20,
        )

    def select(self, before, after):
        f = self.fixture
        _, status = f.api("status")
        result, status = f.api("set", status["revision"], "touch", str(before), str(after))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return status

    def test_actual_old_media_refuses_disabled_without_any_target_or_record_write(self):
        status = self.select(1, 2)
        before = (self.data / "record").read_bytes()
        target = self.fixture.target(self.data, "target").read_bytes()
        nvram = self.fixture.target(self.data, "nvram").read_bytes()
        for operation in ("install", "uninstall"):
            result = self.api(operation, status["revision"])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["error"], "state_changed")
            self.assertEqual((self.data / "record").read_bytes(), before)
            self.assertEqual(self.fixture.target(self.data, "target").read_bytes(), target)
            self.assertEqual(self.fixture.target(self.data, "nvram").read_bytes(), nvram)
        result = self.api("status", "-", "settings")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["installed"])

    def upgrade_bit(self, choice):
        f = self.fixture
        _, status = f.api("status")
        if status["touch"] != choice:
            status = self.select(status["touch"], choice)
        # The archived USB must not inherit the Settings-only package
        # pin; model the receiver before starting its maintenance job.
        (f.root / "runtime/runtime").unlink(missing_ok=True)
        result = self.api("install", status["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        view = json.loads(result.stdout)
        self.assertEqual(view["touch"], choice)
        self.assertTrue(view["installed"])
        self.assertEqual(
            f.target(self.data, "nvram").read_text(), "disable\n" if choice == 1 else "absent\n"
        )
        # Upgrade the actual old-media installation back to the current
        # source. Keep the same physical/render adapters; OC1, package_save,
        # source-bound decoders and install transactions remain real.
        old_package = (self.data / "record").read_text().split("|")[3]
        successor = f.root / "successor"
        shutil.copytree(self.media, successor, symlinks=True)
        (successor / "admitted").unlink(missing_ok=True)
        runtime = f.root / "runtime"
        for source in (ROOT / "cmu/installer").iterdir():
            if source.is_file() and (successor / source.name).is_file():
                shutil.copyfile(source, successor / source.name)
        for name in ("backend.sh", "state.sh", "transaction.sh", "service.sh", "usb-service.sh"):
            path = successor / name
            path.write_text(
                path.read_text()
                .replace("/tmp/open-connect", str(runtime))
                .replace("/tmp/mnt/data_persist/open-connect", str(self.data))
                .replace("/usr/bin/autostart", str(f.target(self.data, "target")))
                .replace("/usr/bin/runlogin", str(f.root / "runlogin"))
                .replace("/usr/bin/.open-connect-runlogin-", str(f.root / ".runlogin-"))
                .replace("/proc/uptime", str(f.root / "uptime"))
                .replace(
                    "b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8",
                    hashlib.sha256((f.root / "runlogin").read_bytes()).hexdigest(),
                )
                .replace(
                    "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                    "uuid() { openssl rand -hex 16; }",
                )
            )
        shutil.copyfile(self.media / "access.sh", successor / "access.sh")
        firmware = (ROOT / "cmu/installer/firmware.sh").read_text()
        firmware += "\n" + (self.media / "firmware.sh").read_text().split("CUT=none\n", 1)[1]
        (successor / "firmware.sh").write_text("CUT=none\n" + firmware)
        (successor / "touch-disable.so").write_bytes(b"host touch DSO fixture\n")
        self.write_manifest(successor)
        (runtime / "usb-runtime").unlink()
        (runtime / "usb-runtime").symlink_to(successor)
        result = self.api("install", view["revision"], media=successor)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        upgraded = json.loads(result.stdout)
        self.assertEqual(upgraded["touch"], choice)
        package_id = (self.data / "record").read_text().split("|")[3]
        self.assertNotEqual(package_id, old_package)
        self.assertIn(
            "function touch_mode",
            (self.data / "packages" / package_id / "preferences.awk").read_text(),
        )

    def test_actual_old_media_upgrades_factory_behavior(self):
        self.upgrade_bit(0)

    def test_actual_old_media_upgrades_always_enabled(self):
        self.upgrade_bit(1)

    def uninstall_after_bit(self, after):
        f = self.fixture
        status = self.select(1, 2)
        runtime = f.root / "runtime"
        selected = status["revision"]
        (runtime / "selected").write_text(selected + "\n")
        feature = runtime / "feature"
        feature.mkdir()
        shim = feature / "touch-disable.so"
        # Hold a real native mapping while the actual archived purge runs.
        subprocess.run(
            ["clang", "-shared", "-fPIC", "-x", "c", "-o", shim, "-"],
            input=b"int touch_fixture(void) { return 87; }\n",
            check=True,
        )
        inode = (shim.stat().st_dev, shim.stat().st_ino)
        status = self.select(2, after)
        self.assertEqual((runtime / "selected").read_text(), selected + "\n")
        (runtime / "runtime").unlink()
        script = "import ctypes,subprocess,sys; lib=ctypes.CDLL(sys.argv[1]); "
        script += "assert lib.touch_fixture()==87; r=subprocess.run(sys.argv[2:]); "
        script += "assert r.returncode==0; assert lib.touch_fixture()==87"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(shim),
                "sh",
                str(self.media / "backend.sh"),
                "api",
                status["revision"],
                "uninstall",
                "-",
                "-",
                "-",
            ],
            env={**os.environ, "PATH": str(f.tools) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.data.exists())
        self.assertEqual((shim.stat().st_dev, shim.stat().st_ino), inode)
        self.assertEqual(f.target(self.data, "target").read_text(), "stock\n")
        self.assertEqual(f.target(self.data, "nvram").read_text(), "absent\n")

    def test_actual_old_media_uninstalls_after_disabled_to_factory_before_reboot(self):
        self.uninstall_after_bit(0)

    def test_actual_old_media_uninstalls_after_disabled_to_enabled_before_reboot(self):
        self.uninstall_after_bit(1)
