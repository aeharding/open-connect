import collections
import errno
import json
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from types import SimpleNamespace

from open_connect.session import (AdapterLock, BenchError, Bundle, CommandDecoder,
                               IDENTITY, ProtocolError, Session, UnknownOutcome,
                               prompt_state, resolve_adapter, verify_identity, wrap_command)

TOKEN = "a" * 32
ROOT = Path(__file__).resolve().parents[1]
IDENTITY_OUTPUT = (b'uid=0(root) gid=0(root)\nLinux cmu 3.0.35\n'
                   b'JCI_SW_VER="MAZ_CMU-150_55.00.750"\nJCI_SW_VER_PATCH="B"\n'
                   b'JCI_SW_FLAVOR="cmu150_NA"\n')


def response(token, output=b"ok\n", status=0, prompt=b"/tmp/root # "):
    return (b"\r\nCMU1 " + token.encode() + b" BEGIN\r\n" + output
            + b"\r\nCMU1 " + token.encode() + b" END " + str(status).encode()
            + b"\r\n" + prompt)


class FakeTransport:
    def __init__(self, chunks=(), callback=None, max_write=100000):
        self.chunks = collections.deque(chunks)
        self.callback = callback
        self.max_write = max_write
        self.tx = bytearray()
        self.pending = bytearray()

    def read(self, size):
        if self.chunks:
            chunk = self.chunks.popleft()
            if len(chunk) > size:
                self.chunks.appendleft(chunk[size:])
            return chunk[:size]
        time.sleep(0.001)
        return b""

    def write(self, data):
        data = data[:self.max_write]
        self.tx.extend(data)
        self.pending.extend(data)
        if self.pending.endswith(b"\r") and self.callback:
            pending = bytes(self.pending)
            self.pending.clear()
            self.chunks.extend(self.callback(pending))
        return len(data)


class MasterTransport:
    def __init__(self, fd):
        self.fd = fd

    def read(self, size):
        if select.select([self.fd], [], [], 0.01)[0]:
            return os.read(self.fd, size)
        return b""

    def write(self, data):
        return os.write(self.fd, data)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundle = Bundle(Path(self.tmp.name) / "bundle", "offline unittest", "test")

    def tearDown(self):
        self.bundle.finish("offline_test_finished")
        self.tmp.cleanup()

    def session(self, transport, timeout=0.1):
        return Session(transport, self.bundle, timeout=timeout)

    def test_fragmented_prompt_and_noise(self):
        t = FakeTransport([b"noise\x00\xff\r\n/tmp/", b"root # "])
        s = self.session(t)
        s.observe_prompt()
        self.assertEqual(s.state, "shell")
        self.assertEqual(t.tx, b"")

    def test_prompt_states_and_continuation_refusal_even_with_probe(self):
        for text, expected in ((b"cmu login: ", "login"), (b"Password: ", "password"),
                               (b"\r\n> 0", "continuation"), (b"log # text", "unknown")):
            self.assertEqual(prompt_state(text), expected)
            if expected != "unknown":
                t = FakeTransport([text])
                with self.assertRaises(BenchError):
                    self.session(t).observe_prompt(solicit=True)
                self.assertEqual(t.tx, b"")

    def test_receive_only_binary_lossless_and_zero_tx(self):
        original = b"\x00\xffnoise\r\n/tmp/root # \x1b[0m"
        t = FakeTransport([original[:4], original[4:]])
        self.assertEqual(self.session(t).receive(0.02), original)
        self.assertEqual(t.tx, b"")
        self.assertEqual((self.bundle.path / "rx.bin").read_bytes(), original)
        events = [json.loads(line) for line in (self.bundle.path / "events.jsonl").read_text().splitlines()]
        self.assertEqual(b"".join(bytes.fromhex(e["hex"]) for e in events if e.get("direction") == "rx"), original)
        self.assertFalse(any(e.get("direction") == "tx" for e in events))

    def test_echo_fake_markers_ignored_and_fragmented_exit(self):
        wire = wrap_command("printf ok", TOKEN)
        self.assertNotIn(b"CMU1 " + TOKEN.encode() + b" BEGIN", wire)
        decoder = CommandDecoder(TOKEN)
        payload = (wire + b"\r\nlog CMU1 " + TOKEN.encode() + b" END 0\r\n"
                   + response(TOKEN, status=7))
        for byte in payload:
            decoder.feed(bytes([byte]))
        self.assertTrue(decoder.complete)
        self.assertEqual(decoder.exit_status, 7)
        self.assertIn(b"ok", decoder.output)

    def test_echo_only_never_completes(self):
        d = CommandDecoder(TOKEN)
        d.feed(wrap_command("true", TOKEN) + b"\r\n/tmp/root # ")
        self.assertFalse(d.complete)
        self.assertFalse(d.started)

    def test_duplicate_missing_and_partial_frames(self):
        begin = b"CMU1 " + TOKEN.encode() + b" BEGIN\n"
        end = b"CMU1 " + TOKEN.encode() + b" END 0\n"
        for payload in (begin + begin, end, begin + end + end):
            with self.assertRaises(ProtocolError):
                CommandDecoder(TOKEN).feed(payload)
        for payload in (begin + end[:-2], b"/tmp/root # ", begin + b"output\n"):
            d = CommandDecoder(TOKEN)
            d.feed(payload)
            self.assertFalse(d.complete)

    def test_timeout_after_tx_unknown_and_cannot_retry(self):
        t = FakeTransport()
        s = self.session(t, 0.02)
        s.state, s.identity = "shell", {"uid": 0}
        with self.assertRaises(UnknownOutcome):
            s.execute("printf x")
        before = bytes(t.tx)
        with self.assertRaises(UnknownOutcome):
            s.execute("printf y")
        with self.assertRaises(UnknownOutcome):
            s.observe_prompt(solicit=True)
        self.assertEqual(bytes(t.tx), before)
        self.assertEqual(s.state, "uncertain")
        self.assertEqual(self.bundle.meta["operations"][0]["outcome"], "unknown")

    def test_partial_writes_logged_and_real_status(self):
        def callback(wire):
            token = re.search(rb"' ([a-f0-9]{32}); sh -c", wire).group(1).decode()
            return [wire + response(token, status=9)]
        t = FakeTransport(callback=callback, max_write=7)
        s = self.session(t)
        s.state, s.identity = "shell", {"uid": 0}
        status, output = s.execute("exit 9")
        self.assertEqual(status, 9)
        self.assertEqual((self.bundle.path / "tx.bin").read_bytes(), bytes(t.tx))

    def test_identity_must_be_fresh_root_and_expected_firmware(self):
        self.assertEqual(verify_identity(IDENTITY_OUTPUT)["firmware"], "55.00.750B")
        for bad in (IDENTITY_OUTPUT.replace(b"uid=0(root)", b"uid=1000(user)"),
                    IDENTITY_OUTPUT + b'JCI_SW_VER_PATCH="B"\n',
                    IDENTITY_OUTPUT.replace(b"55.00.750", b"55.00.800")):
            with self.assertRaises(ProtocolError):
                verify_identity(bad)
        s = self.session(FakeTransport())
        s.state = "shell"
        with self.assertRaises(BenchError):
            s.execute("true")

    def test_tx_bound_includes_quoting_overhead(self):
        with self.assertRaises(ValueError):
            wrap_command("x" * 600, TOKEN)
        with self.assertRaises(ValueError):
            wrap_command("'" * 150, TOKEN)

    def test_descriptor_lock_contention_and_release(self):
        directory = Path(self.tmp.name) / "locks"
        with AdapterLock(directory) as first:
            fd = first.fd
            with self.assertRaises(BlockingIOError):
                with AdapterLock(directory):
                    self.fail("second owner acquired lock")
            self.assertIsNotNone(os.fstat(fd))
            inode = first.path.stat().st_ino
        with AdapterLock(directory) as later:
            self.assertEqual(later.path.stat().st_ino, inode)

    def test_lock_contention_other_process(self):
        directory = Path(self.tmp.name) / "locks"
        with AdapterLock(directory):
            code = ('from open_connect.session import AdapterLock; import sys; '
                    'AdapterLock(sys.argv[1]).__enter__()')
            child = subprocess.run([sys.executable, "-B", "-c", code, str(directory)], cwd=ROOT,
                                   capture_output=True, timeout=3)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn(b"BlockingIOError", child.stderr)

    def test_production_identity_not_weakened_for_pty(self):
        def port(device="/dev/cu.usbserial-A9048JM0", serial="A9048JM0"):
            return SimpleNamespace(vid=0x0403, pid=0x6001, serial_number=serial,
                                   device=device, location="test")
        self.assertEqual(resolve_adapter(lambda: [port()])["serial_number"], "A9048JM0")
        for ports in ([], [port(), port()], [port(serial="other")], [port(device="/dev/ttys999")]):
            with self.assertRaises(BenchError):
                resolve_adapter(lambda: ports)

    def test_real_pty_shell_exit_and_identity(self):
        master, slave = pty.openpty()
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        env = dict(os.environ, PS1="/tmp/root # ", PS2="> ", ENV="")
        child = subprocess.Popen(["/bin/sh", "-i"], stdin=slave, stdout=slave, stderr=slave,
                                 env=env, start_new_session=True)
        os.close(slave)
        try:
            s = self.session(MasterTransport(master), timeout=2)
            s.observe_prompt()
            s.identity = {"uid": 0, "source": "synthetic PTY only"}
            status, output = s.execute("printf 'hello\\n'; exit 17")
            self.assertEqual(status, 17)
            self.assertIn(b"hello", output)
            self.assertEqual(s.state, "shell")
        finally:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)
            os.close(master)

    def test_pyserial35_receive_only_over_explicit_test_pty(self):
        import serial
        from open_connect.session import SETTINGS
        master, slave = pty.openpty()
        port = serial.Serial(port=None, **SETTINGS)
        try:
            port.dtr = False
            port.rts = False
            port.port = os.ttyname(slave)
            port.open()  # PTY injection lives in this test only.
            data = bytes([0, 255]) + b"synthetic\r\n"
            os.write(master, data)
            session = self.session(port)
            self.assertEqual(session.receive(0.08), data)
            self.assertFalse(select.select([master], [], [], 0.01)[0])
            self.assertEqual((self.bundle.path / "tx.bin").read_bytes(), b"")
        finally:
            port.close()
            os.close(master)
            os.close(slave)

    def test_cli_default_no_hardware_or_output_files(self):
        child = subprocess.run([sys.executable, "-B", "-m", "open_connect", "uart"],
                               capture_output=True, cwd=self.tmp.name, timeout=2)
        self.assertEqual(child.returncode, 0, child.stderr)
        plan = json.loads(child.stdout)
        self.assertFalse(plan["opens_port"])
        self.assertFalse(plan["sends_bytes"])


if __name__ == "__main__":
    unittest.main()
