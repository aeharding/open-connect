"""Exercise the actual bounded wireless helper with private synthetic files."""

import hashlib
import os
import shlex
import shutil
import signal
import subprocess
import sys
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
        busybox = shutil.which("busybox")
        self.shell = [busybox, "sh"] if busybox else ["/bin/bash"]
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
        self.launcher = self.root / "session.py"
        self.launcher.write_text(
            "import os,sys\nfrom pathlib import Path\n"
            "os.setsid()\n"
            f"Path({str(self.root / 'session-pid')!r}).write_text(str(os.getpid()))\n"
            "os.execv(sys.argv[1],sys.argv[1:])\n"
        )
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
        # Some host BusyBox builds run their applets without searching PATH.
        # Route only the injected commands through explicit private fixtures.
        for name in ("awk", "mv"):
            command = self.tools / name
            command.write_text("#!/bin/sh\nexec " + shlex.quote(shutil.which(name)) + ' "$@"\n')
            command.chmod(0o700)
            source = source.replace(f"\n    {name} ", "\n    " + shlex.quote(str(command)) + " ")
        # macOS has no BusyBox/procfs. Use its real setsid/group/session APIs;
        # Linux CI and the target probe use the unmodified procfs identity read.
        source = source.replace(
            '/bin/sh -c \'exec /bin/busybox setsid /bin/sh "$1" --prepare "$$"\' wireless-worker "$0" &',
            '/bin/sh -c \'exec "$2" "$3" '
            + shlex.join(self.shell)
            + ' "$1" --prepare "$$"\' wireless-worker "$0" '
            + shlex.quote(sys.executable)
            + " "
            + shlex.quote(str(self.launcher))
            + " &",
        )
        if not Path("/proc/self/stat").exists():
            proc = self.root / "process-stat.py"
            proc.write_text(
                "import os,sys,subprocess\n"
                "p=int(sys.argv[1])\n"
                "parent=int(subprocess.check_output(['ps','-p',str(p),'-o','ppid=']))\n"
                "print(f'{p} (worker) S {parent} {os.getpgid(p)} {os.getsid(p)}')\n"
            )
            source = source.replace(
                'read -r process_stat 2>/dev/null < "/proc/$worker/stat"',
                "process_stat=$("
                + shlex.quote(sys.executable)
                + " "
                + shlex.quote(str(proc))
                + ' "$worker" 2>/dev/null)',
            )
            # macOS's old Bash does not time out this RDWR FIFO read. Its host
            # adapter uses select; Linux CI and native probes use BusyBox read.
            timed = self.root / "read-timed.py"
            timed.write_text(
                "import os,select,sys,time\n"
                "fd=int(sys.argv[1]); end=time.monotonic()+int(sys.argv[2]); data=b''\n"
                "while time.monotonic()<end:\n"
                " if not select.select([fd],[],[],max(0,end-time.monotonic()))[0]: break\n"
                " data+=os.read(fd,1)\n"
                " if data.endswith(b'\\n'): print(data.decode().rstrip('\\n')); sys.exit(0)\n"
                "sys.exit(1)\n"
            )
            command = shlex.join([sys.executable, str(timed)])
            source = source.replace(
                "IFS= read -r -t 12 permission <&4", f"permission=$({command} 4 12)"
            ).replace("IFS= read -r -t 1 acknowledged <&3", f"acknowledged=$({command} 3 1)")
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
        return subprocess.run([*self.shell, self.script], capture_output=True, text=True, timeout=5)

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

    def interrupt_at(self, marker, expected):
        process = subprocess.Popen(
            [*self.shell, self.script],
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
            started = time.monotonic()
            # Match BusyBox timeout: TERM only the supervisor's positive PID.
            os.kill(process.pid, signal.SIGTERM)
            out, error = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, (out, error))
            self.assertLess(time.monotonic() - started, 3)
            self.assert_released(expected)
            content = self.target.read_bytes()
            time.sleep(0.2)
            self.assertEqual(self.target.read_bytes(), content)
            return content
        finally:
            # Match the live session leader's identity before cleaning a failed
            # host probe; never signal a remembered or unrelated process group.
            pid_file = self.root / "session-pid"
            if pid_file.exists():
                child = int(pid_file.read_text())
                live = subprocess.run(
                    ["ps", "-p", str(child), "-o", "command="],
                    capture_output=True,
                    text=True,
                )
                if str(self.root) in live.stdout and os.getpgid(child) == child:
                    os.killpg(child, signal.SIGKILL)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=3)

    def test_positive_pid_termination_releases_original_initialization(self):
        marker = self.root / "waiting"
        self.replace_awk("touch " + shlex.quote(str(marker)) + "\nsleep 10\n")
        self.assertEqual(self.interrupt_at(marker, 0), XML)

    def pause_launcher(self, after_session):
        marker = self.root / "launcher-waiting"
        source = self.launcher.read_text()
        pause = f"Path({str(marker)!r}).touch()\n__import__('time').sleep(10)\n"
        location = "os.setsid()\n"
        source = source.replace(location, location + pause if after_session else pause + location)
        self.launcher.write_text(source)
        return marker

    def test_positive_pid_termination_before_session_does_not_authorize_preparation(self):
        self.assertEqual(self.interrupt_at(self.pause_launcher(False), 0), XML)

    def test_positive_pid_termination_after_session_before_ack_does_not_authorize_preparation(self):
        self.assertEqual(self.interrupt_at(self.pause_launcher(True), 0), XML)

    def test_positive_pid_termination_before_xml_rename_cannot_publish_later(self):
        marker = self.root / "before-rename"
        wrapper = self.tools / "mv"
        wrapper.write_text(
            '#!/bin/sh\nif test "$2" = ' + shlex.quote(str(self.target)) + "; then\n"
            "touch "
            + shlex.quote(str(marker))
            + "\nsleep 10\nfi\nexec "
            + shlex.quote(shutil.which("mv"))
            + ' "$@"\n'
        )
        wrapper.chmod(0o700)
        self.assertEqual(self.interrupt_at(marker, 0), XML)

    def test_positive_pid_termination_after_xml_rename_reports_applied_policy(self):
        marker = self.root / "after-rename"
        wrapper = self.tools / "mv"
        wrapper.write_text(
            "#!/bin/sh\n" + shlex.quote(shutil.which("mv")) + ' "$@" || exit\n'
            'if test "$2" = ' + shlex.quote(str(self.target)) + "; then\n"
            "touch " + shlex.quote(str(marker)) + "\nsleep 10\nfi\n"
        )
        wrapper.chmod(0o700)
        content = self.interrupt_at(marker, 1)
        self.assertEqual(content, XML.replace(b">FALSE<", b">TRUE<"))
