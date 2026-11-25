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
        source = source.replace('test "$(id -u)" = 0', f'test "$(id -u)" = {os.getuid()}')
        source = source.replace("700:0:0", f"700:{os.getuid()}:{os.getgid()}")
        source = source.replace(" = 36:0:0", f" = 36:{os.getuid()}:{os.getgid()}")
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
        for name in (
            "firmware.sh",
            "access.sh",
            "transaction.sh",
            "console.sh",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "VERSION",
            "runtime.js",
            "dialog.js",
            "settings.js",
        ):
            shutil.copyfile(ASSETS / name, self.source / name)
        shutil.copyfile(ROOT / "cmu/features/touch/setting.sh", self.source / "touch.sh")
        usb = (ASSETS / "usb-service.sh").read_text().replace("/tmp/open-connect", str(self.runtime))
        usb = usb.replace("/tmp/mnt/data_persist/open-connect", str(self.root / "data"))
        (self.source / "usb-service.sh").write_text(usb)
        self.manifest()
        self.addCleanup(self.stop_listener)

    def manifest(self):
        for item in self.source.iterdir():
            item.chmod(0o700 if item.name in ("api", "flush") else 0o600)
        (self.source / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(self.source.iterdir())
                if p.name != "files.sha256"
            )
        )

    def stop_listener(self):
        for name in ("listener", "usb-listener"):
            record = self.runtime / name
            if not record.exists():
                continue
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
            ["sh", self.source / "usb-service.sh"],
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

    def client(self, port=15557):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/")
            reply = conn.getresponse()
            self.assertEqual(reply.status, 200)
            return json.loads(reply.read())
        finally:
            conn.close()

    def test_boot_closure_omits_build_files_and_shares_verified_ui_inodes(self):
        self.runtime.mkdir(mode=0o700)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        for name in ("runtime.js", "dialog.js", "settings.js", "service.sh"):
            shutil.copyfile(self.source / name, feature / name)
            (feature / name).chmod(0o600)
        for name in ("LICENSE", "boot-select", "native.bin"):
            (self.source / name).write_text("not needed by the installed listener\n")
        self.manifest()
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        session = (self.runtime / "runtime").resolve()
        for name in ("LICENSE", "boot-select", "native.bin", "sm-profile.awk"):
            self.assertFalse((session / name).exists())
        for name in ("runtime.js", "dialog.js", "settings.js", "service.sh"):
            self.assertEqual((session / name).stat().st_ino, (feature / name).stat().st_ino)
        self.assertEqual(
            (session / "files.sha256").read_bytes(), (self.source / "files.sha256").read_bytes()
        )
        self.assertEqual(self.client(15555)["backend"], "backend-one\n")

    def legacy_selected_client(self):
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "selected").write_text("a" * 64 + "\n")

    def test_usb_before_delayed_worker_keeps_endpoints_independent(self):
        worker, _, _ = self.installed_worker()
        process = subprocess.Popen(["sh", worker, "boot"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            before = (self.runtime / "usb-listener").read_bytes()
            out, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, (out, error))
            self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
            self.assertEqual(self.client()["backend"], "backend-one\n")
            self.assertEqual(self.client(15555)["backend"], "backend-one\n")
            self.assertNotEqual((self.runtime / "token").read_text(), (Path(result.stdout.strip()) / "token").read_text())
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=3)

    def test_installed_port_collision_does_not_block_usb(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 15555))
            occupied.listen()
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_boot_closure_rejects_wrong_shared_bytes_before_listener(self):
        self.runtime.mkdir(mode=0o700)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        shared = feature / "runtime.js"
        shared.write_text("foreign bytes\n")
        shared.chmod(0o400)
        result = self.boot()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "listener").exists())
        self.assertEqual(shared.read_text(), "foreign bytes\n")
        self.assertEqual(shared.stat().st_mode & 0o777, 0o400)

    def test_usb_cancel_leaves_installed_endpoint_token_and_bytes_unchanged(self):
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.runtime / "runtime").resolve()
        record = (self.runtime / "listener").read_bytes()
        token = (self.runtime / "token").read_bytes()
        started = self.invoke()
        self.assertEqual(started.returncode, 0, started.stderr)
        usb = Path(started.stdout.strip())
        stopped = subprocess.run(["sh", usb / "usb-service.sh", "stop"], capture_output=True, text=True, timeout=5)
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertFalse((self.runtime / "usb-listener").exists())
        self.assertEqual((self.runtime / "runtime").resolve(), installed)
        self.assertEqual((self.runtime / "listener").read_bytes(), record)
        self.assertEqual((self.runtime / "token").read_bytes(), token)
        self.assertEqual(self.client(15555)["backend"], "backend-one\n")

    def test_ready_usb_shares_verified_packet_and_each_insertion_has_its_own_token(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        old = Path(first.stdout.strip())
        token = (old / "token").read_text().strip()
        self.assertEqual(self.client(), {"token": token, "backend": "backend-one\n"})
        for line in (self.source / "files.sha256").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(hashlib.sha256((old / name).read_bytes()).hexdigest(), digest)
            self.assertEqual((old / name).stat().st_ino, (self.source / name).stat().st_ino)
        # Another scan starts with another verified private staging directory.
        other = self.root / "source-two"
        shutil.copytree(self.source, other)
        self.source = other
        (other / "backend.sh").write_text("backend-two\n")
        self.manifest()
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        new = Path(second.stdout.strip())
        self.assertNotEqual((new / "token").read_text().strip(), token)
        self.assertEqual(self.client()["backend"], "backend-two\n")

    def test_boot_starts_independently_of_live_usb(self):
        self.assertEqual(self.invoke().returncode, 0)
        before = (self.runtime / "usb-listener").read_bytes()
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")
        self.assertEqual(self.client(15555)["backend"], "backend-one\n")

    def installed_worker(self):
        data = self.root / "data"
        data.mkdir(mode=0o700)
        (data / "packages").mkdir(mode=0o700)
        service = self.source / "service.sh"
        service.write_text(
            service.read_text().replace("/tmp/mnt/data_persist/open-connect", str(data))
        )
        self.manifest()
        package_id = hashlib.sha256((self.source / "files.sha256").read_bytes()).hexdigest()
        package = data / "packages" / package_id
        shutil.copytree(self.source, package)
        boot = "12345678-1234-1234-1234-123456789abc"
        current = "c" * 64
        (data / "record").write_text(
            f"OC1|active|{'a' * 32}|{package_id}|{'b' * 64}|{current}|-|-|-|2|-|{boot}|-\n"
        )
        (data / "record").chmod(0o600)
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "lock").touch(mode=0o600)
        (self.runtime / "selected").write_text(current + "\n")
        (self.runtime / "boot-id").symlink_to(boot)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        worker = feature / "service.sh"
        shutil.copyfile(service, worker)
        return worker, package, data

    def test_sm_worker_verifies_installed_source_and_serves_settings(self):
        worker, _, _ = self.installed_worker()
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.client(15555)["backend"], "backend-one\n")
        self.assertTrue((self.runtime / "selected").is_file())

    def test_sm_worker_refuses_missing_malformed_or_stale_boot_identity(self):
        worker, _, _ = self.installed_worker()
        marker = self.runtime / "boot-id"
        for value in (
            None,
            "invalid",
            "12345678-1234-1234-1234-123456789abc\n",
            "87654321-1234-1234-1234-123456789abc",
        ):
            with self.subTest(value=value):
                marker.unlink(missing_ok=True)
                if value is not None:
                    marker.symlink_to(value)
                result = subprocess.run(["sh", worker, "boot"], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                self.assertFalse((self.runtime / "runtime").exists())

    def test_sm_worker_refuses_corrupt_library_before_sourcing(self):
        worker, package, _ = self.installed_worker()
        marker = self.root / "unverified-ran"
        with (package / "state.sh").open("a") as target:
            target.write("\ntouch " + str(marker) + "\n")
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertFalse((self.runtime / "listener").exists())

    def test_sm_worker_does_not_replace_a_preceding_usb_listener(self):
        worker, _, _ = self.installed_worker()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = (self.runtime / "usb-listener").read_bytes()
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")
        self.assertEqual(self.client(15555)["backend"], "backend-one\n")

    def test_ash_sm_worker_refuses_missing_or_symlinked_selection(self):
        worker, _, _ = self.installed_worker()
        selected = self.runtime / "selected"
        selected.unlink()
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    selected.symlink_to(self.source / "state.sh")
                result = subprocess.run(
                    [self.busybox, "sh", worker, "boot"], capture_output=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                self.assertFalse((self.runtime / "runtime").exists())

    def test_ash_sm_worker_refuses_nonprivate_prerequisite_directories(self):
        worker, package, data = self.installed_worker()
        for folder in (data, self.runtime, package):
            with self.subTest(folder=folder.name):
                folder.chmod(0o755)
                result = subprocess.run(
                    [self.busybox, "sh", worker, "boot"], capture_output=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                folder.chmod(0o700)

    def recovery_files(self):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; P=$1; R=$2; . "$P/state.sh"; . "$P/service.sh"; '
                'service_lock usb; service_files "$(sha "$P/files.sha256")"; printf "%s\\n" "$runtime"',
                "test",
                self.source,
                self.runtime,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_recovery_files_preserve_existing_usb_listener(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = (self.runtime / "usb-listener").read_bytes()
        result = self.recovery_files()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((Path(result.stdout.strip()) / "state.sh").is_file())
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_recovery_files_do_not_require_an_available_port(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 15555))
            listener.listen()
            result = self.recovery_files()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((Path(result.stdout.strip()) / "backend.sh").is_file())
        self.assertFalse((self.runtime / "runtime").exists())
        self.assertFalse((self.runtime / "listener").exists())

    def test_foreign_socket_causes_failure_without_publishing_new_runtime(self):
        self.runtime.mkdir(mode=0o700)
        old = self.root / "old"
        old.mkdir()
        (self.runtime / "usb-runtime").symlink_to(old)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 15557))
            listener.listen()
            started = time.monotonic()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("listener_start_failed", result.stderr)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual((self.runtime / "usb-runtime").resolve(), old)
            self.assertFalse((self.runtime / "usb-listener").exists())

    def test_corrupt_shared_packet_refuses_and_removes_unpublished_links(self):
        tools = self.root / "tools"
        tools.mkdir()
        link = tools / "ln"
        link.write_text("#!/bin/sh\n" + shutil.which("ln") + ' "$@" || exit\n'
            'case "$2" in */api) printf "corrupt" >> "$2";; esac\n')
        link.chmod(0o700)
        result = self.invoke({**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"]})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("damaged_runtime", result.stderr)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        self.assertEqual(list((self.runtime / "sessions").iterdir()), [])

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
                ["sh", self.source / "usb-service.sh"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.15)
            self.assertIsNone(process.poll())
            self.assertFalse((self.runtime / "usb-runtime").exists())
            fcntl.flock(lock, fcntl.LOCK_UN)
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, err)
            self.assertTrue(out.strip())
            self.assertEqual(self.client()["backend"], "backend-one\n")

    def assert_interrupted_start(self, needle):
        script = self.source / "service.sh"
        script.write_text(
            script.read_text().replace(needle, self.busybox + " usleep 500000\n" + needle, 1)
        )
        self.manifest()
        process = subprocess.Popen(
            ["sh", self.source / "usb-service.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if any(
                fields[1] == "0100007F:3CC5" and fields[3] == "0A"
                for line in Path("/proc/net/tcp").read_text().splitlines()[1:]
                if len(fields := line.split()) > 3
            ):
                break
            time.sleep(0.01)
        else:
            process.kill()
            self.fail("new listener did not reach the interrupted-start window")
        self.assertFalse((self.runtime / "usb-runtime").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 15557))

    def test_signal_during_unpublished_start_reaps_child_and_cannot_publish_later(self):
        self.assert_interrupted_start("service_tick; deadline=")

    def test_parent_term_between_fork_and_pid_capture_reaps_unpublished_child(self):
        self.assert_interrupted_start("pid=$!")

    def test_term_at_ready_handoff_is_not_forgotten(self):
        script = self.source / "service.sh"
        script.write_text(
            script.read_text().replace(
                "trap - EXIT HUP INT TERM",
                self.busybox + " usleep 500000\ntrap - EXIT HUP INT TERM",
                1,
            )
        )
        self.manifest()
        process = subprocess.Popen(
            ["sh", self.source / "usb-service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        deadline = time.monotonic() + 2
        while not (self.runtime / "usb-runtime").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((self.runtime / "usb-runtime").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 15557))
