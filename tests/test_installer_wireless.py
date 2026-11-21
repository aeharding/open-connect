"""Exercise the actual bounded wireless helper with private synthetic files."""

import hashlib
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
XML = (
    b"<root>\n<config><name>serial</name><value>example-vehicle</value></config>\r\n"
    b"<config><name>bWifiSupport</name><value>FALSE</value></config>\n"
    b"<config><name>location</name><value>actual-gps-provider</value></config>\n"
    b"<config><name>bOOBSupport</name><value>FALSE</value></config>\n</root>\n"
)


class InstallerWireless(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.feature = self.root / "feature"
        self.tools = self.root / "tools"
        self.feature.mkdir(mode=0o700)
        self.tools.mkdir(mode=0o700)
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        self.target = self.root / "device.xml"
        self.target.write_bytes(XML)
        self.target.chmod(0o640)
        self.boot = self.root / "boot"
        self.boot.write_text("00000000-0000-0000-0000-000000000001\n")
        (self.feature / "boot-id").write_bytes(self.boot.read_bytes())
        (self.feature / "wireless-applied").write_text("0\n")
        shutil.copyfile(ASSETS / "wireless-device.awk", self.feature / "wireless-device.awk")
        source = (ASSETS / "wireless.sh").read_text()
        source = source.replace("/tmp/open-connect/feature", str(self.feature))
        source = source.replace("/tmp/devmgr_config_edit.xml", str(self.target))
        source = source.replace("/proc/sys/kernel/random/boot_id", str(self.boot))
        source = source.replace('test "$(id -u)" = 0', f'test "$(id -u)" = {os.getuid()}')
        source = source.replace("700:0:0", f"700:{os.getuid()}:{os.getgid()}")
        source = source.replace(
            "PATH=/usr/bin:/bin:/usr/sbin:/sbin",
            "PATH=" + shlex.quote(str(self.tools) + os.pathsep + os.environ["PATH"]),
        )
        self.originals = []
        for name, path, digest in (
            (
                "master",
                "/etc/devmgr_config_master.xml",
                "9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b",
            ),
            (
                "eem",
                "/jci/vbs/modules/libjcimod_eem.so",
                "0160354861d0dddf09f05dc69df95f14be074de706a4d7656166666d587439d9",
            ),
            (
                "manager",
                "/jci/devicemanager/libdevicemanager.so",
                "88d6291d74fe993536ec724064b8ccfbc133b2341282b93cfc7fb2927fbbc563",
            ),
        ):
            fixture = self.root / name
            fixture.write_text("synthetic original " + name + "\n")
            self.originals.append((fixture, fixture.read_bytes()))
            source = source.replace(path, str(fixture)).replace(
                digest, hashlib.sha256(fixture.read_bytes()).hexdigest()
            )
        self.script = self.root / "wireless.sh"
        self.script.write_text(source)

    def run_helper(self):
        return subprocess.run(["sh", self.script], capture_output=True, text=True, timeout=5)

    def assert_released(self, applied):
        self.assertTrue((self.feature / "wireless-ready").is_file())
        self.assertEqual((self.feature / "wireless-applied").read_text(), f"{applied}\n")

    def test_changes_only_two_flags_and_preserves_metadata_and_physical_inputs(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = XML
        for name in (b"bWifiSupport", b"bOOBSupport"):
            old = b"<name>" + name + b"</name><value>FALSE</value>"
            expected = expected.replace(old, old.replace(b"FALSE", b"TRUE"))
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.target.stat().st_uid, os.getuid())
        self.assertEqual(self.target.stat().st_gid, os.getgid())
        self.assertEqual((self.feature / "wireless-original.xml").read_bytes(), XML)
        for path, content in self.originals:
            self.assertEqual(path.read_bytes(), content)
        self.assert_released(1)

    def test_malformed_flags_leave_original_and_release_device_manager(self):
        invalid = XML.replace(b"bOOBSupport", b"unknownCapability")
        self.target.write_bytes(invalid)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), invalid)
        self.assert_released(0)

    def test_duplicate_flag_is_not_partially_published(self):
        duplicate = XML + b"<config><name>bWifiSupport</name><value>FALSE</value></config>\n"
        self.target.write_bytes(duplicate)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), duplicate)
        self.assert_released(0)

    def test_changed_physical_input_is_not_bypassed_by_conditional_errexit(self):
        path = self.originals[0][0]
        path.write_text("later foreign change\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), XML)
        self.assertEqual(path.read_text(), "later foreign change\n")
        self.assert_released(0)

    def test_differently_formatted_duplicate_flag_is_not_ignored(self):
        duplicate = XML + b"<config> <name>bWifiSupport</name><value>FALSE</value></config>\n"
        self.target.write_bytes(duplicate)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), duplicate)
        self.assert_released(0)

    def test_foreign_stage_is_preserved(self):
        stage = self.feature / "wireless-new.xml"
        stage.write_text("another provider\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stage.read_text(), "another provider\n")
        self.assertEqual(self.target.read_bytes(), XML)
        self.assert_released(0)

    def test_symlink_input_is_preserved(self):
        actual = self.root / "elsewhere.xml"
        self.target.rename(actual)
        self.target.symlink_to(actual)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(actual.read_bytes(), XML)
        self.assert_released(0)

    def replace_awk(self, after):
        script = self.tools / "awk"
        script.write_text(
            "#!/bin/sh\n" + shlex.quote(shutil.which("awk")) + ' "$@" || exit\n' + after
        )
        script.chmod(0o700)

    def test_concurrent_generation_is_not_overwritten(self):
        self.replace_awk("printf 'foreign generation\\n' > " + shlex.quote(str(self.target)) + "\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "foreign generation\n")
        self.assert_released(0)

    def test_same_bytes_on_replacement_inode_are_not_adopted(self):
        target = shlex.quote(str(self.target))
        self.replace_awk(f"cp {target} {target}.next && mv {target}.next {target}\n")
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), XML)
        self.assert_released(0)

    def test_wrong_boot_refuses_without_signaling_readiness(self):
        self.boot.write_text("00000000-0000-0000-0000-000000000002\n")
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.feature / "wireless-ready").exists())
        self.assertEqual(self.target.read_bytes(), XML)

    def test_termination_releases_original_initialization(self):
        marker = self.root / "waiting"
        self.replace_awk("touch " + shlex.quote(str(marker)) + "\nsleep 10\n")
        process = subprocess.Popen(
            ["sh", self.script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists())
            os.killpg(process.pid, signal.SIGTERM)
            out, error = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, (out, error))
            self.assertEqual(self.target.read_bytes(), XML)
            self.assert_released(0)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=3)
