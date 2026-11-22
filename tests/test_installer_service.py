"""Real Linux flock, BusyBox listener ownership and first-client readiness."""

import fcntl
import hashlib
import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


BUSYBOX = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
HAS_TCPSVD = bool(
    sys.platform == "linux"
    and BUSYBOX
    and shutil.which("flock")
    and "tcpsvd" in subprocess.check_output([BUSYBOX, "--list"], text=True, timeout=3).splitlines()
)


@unittest.skipUnless(HAS_TCPSVD, "Linux /proc, flock and BusyBox tcpsvd required")
class InstallerService(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir(mode=0o700)
        self.runtime = self.root / "runtime"
        self.busybox = str(Path(BUSYBOX).resolve())
        source = (ASSETS / "service.sh").read_text()
        source = source.replace("/tmp/open-connect", str(self.runtime))
        source = source.replace("/bin/busybox", self.busybox)
        # Modern host BusyBox replaced the target 1.19.2 timeout's -t syntax.
        source = source.replace("timeout -t 180", "timeout 180")
        (self.source / "service.sh").write_text(source)
        shutil.copyfile(ASSETS / "state.sh", self.source / "state.sh")
        (self.source / "api").write_text(
            "#!/usr/bin/python3\n"
            "import json,sys\nfrom pathlib import Path\n"
            "while sys.stdin.buffer.readline().strip(): pass\n"
            "body=json.dumps({'token':Path(sys.argv[1]).read_text().strip(),"
            "'backend':Path(sys.argv[2]).read_text()}).encode()\n"
            "sys.stdout.buffer.write(b'HTTP/1.0 200 OK\\r\\nContent-Length: '+"
            "str(len(body)).encode()+b'\\r\\n\\r\\n'+body)\n"
        )
        (self.source / "flush").write_text("#!/bin/sh\nexit 0\n")
        (self.source / "backend.sh").write_text("backend-one\n")
        self.manifest()
        self.addCleanup(self.stop_listener)

    def manifest(self):
        (self.source / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(self.source.iterdir())
                if p.name != "files.sha256"
            )
        )

    def stop_listener(self):
        record = self.runtime / "listener"
        if not record.exists():
            return
        pid, start, session = record.read_text().split()
        proc = Path("/proc") / pid
        try:
            fields = (proc / "stat").read_text().split()
            args = (proc / "cmdline").read_bytes().split(b"\0")
            if fields[21] == start and (session + "/api").encode() in args:
                os.kill(int(pid), signal.SIGTERM)
        except (FileNotFoundError, ProcessLookupError):
            pass

    def invoke(self, env=None):
        return subprocess.run(
            ["sh", self.source / "service.sh"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def boot_command(self):
        return (
            'set -eu; P="$1"; R="$2"; . "$P/state.sh"; . "$P/service.sh"; '
            'service_lock boot; service_stage boot "$(sha "$P/files.sha256")"'
        )

    def boot(self):
        return subprocess.run(
            ["sh", "-c", self.boot_command(), "test", self.source, self.runtime],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def client(self):
        conn = http.client.HTTPConnection("127.0.0.1", 35555, timeout=2)
        try:
            conn.request("GET", "/")
            reply = conn.getresponse()
            self.assertEqual(reply.status, 200)
            return json.loads(reply.read())
        finally:
            conn.close()

    def test_ready_session_serves_first_client_and_replacement_preserves_old_bytes(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        session = Path(first.stdout.strip())
        token = (self.runtime / "token").read_text().strip()
        self.assertEqual(self.client(), {"token": token, "backend": "backend-one\n"})
        for line in (self.source / "files.sha256").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(hashlib.sha256((session / name).read_bytes()).hexdigest(), digest)
        (self.source / "backend.sh").write_text("backend-two\n")
        self.manifest()
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(second.stdout, first.stdout)
        self.assertEqual((session / "backend.sh").read_text(), "backend-one\n")
        self.assertEqual(self.client(), {"token": token, "backend": "backend-two\n"})

    def test_boot_preserves_live_usb_session_after_its_staging_lock_is_released(self):
        self.assertEqual(self.invoke().returncode, 0)
        before = (self.runtime / "listener").read_bytes()
        result = self.boot()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("busy", result.stderr)
        self.assertEqual((self.runtime / "listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_foreign_socket_causes_failure_without_publishing_new_runtime(self):
        self.runtime.mkdir(mode=0o700)
        old = self.root / "old"
        old.mkdir()
        (self.runtime / "runtime").symlink_to(old)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 35555))
            listener.listen()
            started = time.monotonic()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("listener_start_failed", result.stderr)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual((self.runtime / "runtime").resolve(), old)
            self.assertFalse((self.runtime / "listener").exists())

    def test_corrupt_ram_copy_refuses_before_listener_or_pointer(self):
        tools = self.root / "tools"
        tools.mkdir()
        cp = tools / "cp"
        cp.write_text(
            "#!/bin/sh\n" + shutil.which("cp") + ' "$@" || exit\n'
            "for dest; do :; done\n"
            'if test -d "$dest" && test -f "$dest/api"; then printf "\\n#corrupt\\n" >> "$dest/api"; fi\n'
        )
        cp.chmod(0o700)
        result = self.invoke({**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"]})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("damaged_runtime", result.stderr)
        self.assertFalse((self.runtime / "runtime").exists())
        self.assertFalse((self.runtime / "listener").exists())

    def test_boot_refuses_real_lock_contention_without_runtime_effects(self):
        self.runtime.mkdir(mode=0o700)
        with (self.runtime / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.monotonic()
            result = self.boot()
            self.assertLess(time.monotonic() - started, 1)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("busy", result.stderr)
            self.assertFalse((self.runtime / "runtime").exists())

    def test_usb_waits_for_existing_operation_lock_before_staging(self):
        self.runtime.mkdir(mode=0o700)
        with (self.runtime / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(
                ["sh", self.source / "service.sh"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.15)
            self.assertIsNone(process.poll())
            self.assertFalse((self.runtime / "runtime").exists())
            fcntl.flock(lock, fcntl.LOCK_UN)
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, err)
            self.assertTrue(out.strip())
            self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_signal_during_unpublished_start_reaps_child_and_cannot_publish_later(self):
        script = self.source / "service.sh"
        script.write_text(
            script.read_text().replace(
                "service_tick; deadline=", self.busybox + " usleep 500000\nservice_tick; deadline="
            )
        )
        self.manifest()
        process = subprocess.Popen(
            ["sh", self.source / "service.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if "0100007F:8AE3" in Path("/proc/net/tcp").read_text():
                break
            time.sleep(0.01)
        else:
            process.kill()
            self.fail("new listener did not reach the interrupted-start window")
        self.assertFalse((self.runtime / "runtime").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.runtime / "runtime").exists())
        self.assertFalse((self.runtime / "listener").exists())
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 35555))
