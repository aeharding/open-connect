"""Real local sockets exercise the same C parser/deadline used on ARM."""

import select
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "a" * 32 + ".01234567-89ab-cdef-0123-456789abcdef"


class ReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.temp.name) / "receiver"
        command = [
            shutil.which("cc"),
            "-DOC_HOST",
            "-std=c99",
            "-D_POSIX_C_SOURCE=200809L",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(ROOT / "cmu/startup/ready-receiver.c"),
            "-o",
            str(cls.exe),
        ]
        subprocess.run(command, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def start(self, seconds=2):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        p = subprocess.Popen(
            [str(self.exe), str(port), TOKEN, str(seconds)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(self.cleanup, p)
        self.assertTrue(select.select([p.stdout], [], [], 2)[0], "no listener ready record")
        self.assertEqual(p.stdout.readline(), b"OCHEALTH|listening\n")
        return p, port

    @staticmethod
    def cleanup(p):
        if p.poll() is None:
            p.kill()
        p.communicate(timeout=3)

    @staticmethod
    def request(token=TOKEN):
        return ("GET /" + token + " HTTP/1.1\r\nHost: localhost\r\n\r\n").encode()

    def test_fragmented_valid_request_and_closed_one_shot(self):
        p, port = self.start()
        with socket.create_connection(("127.0.0.1", port), timeout=1) as s:
            data = self.request()
            for part in (data[:5], data[5:72], data[72:]):
                s.sendall(part)
                time.sleep(0.02)
            self.assertIn(b"204", s.recv(256))
        out, err = p.communicate(timeout=3)
        self.assertEqual((p.returncode, out, err), (0, b"OCHEALTH|ready\n", b""))
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.2)

    def test_wrong_boot_method_and_oversize_do_not_ack(self):
        p, port = self.start()
        for data in [
            self.request(TOKEN[:-1] + "0"),
            self.request().replace(b"GET ", b"PUT "),
            self.request().replace(b"HTTP/1.1", b"HTTP/2.0"),
            b"x" * 4096,
            self.request().replace(b"Host:", b"Host:\x00"),
        ]:
            with socket.create_connection(("127.0.0.1", port), timeout=1) as s:
                s.sendall(data)
                try:
                    s.recv(256)
                except ConnectionResetError:
                    pass
        out, err = p.communicate(timeout=4)
        self.assertEqual((p.returncode, out, err), (75, b"OCHEALTH|timeout\n", b""))

    def test_partial_request_cannot_extend_global_deadline(self):
        p, port = self.start(seconds=1)
        start = time.monotonic()
        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.sendall(self.request()[:-2])
            out, err = p.communicate(timeout=3)
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertEqual((p.returncode, out, err), (75, b"OCHEALTH|timeout\n", b""))

    def test_port_conflict_fails_before_listening_and_argument_refusal(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            p = subprocess.run(
                [str(self.exe), str(s.getsockname()[1]), TOKEN, "2"], capture_output=True, timeout=2
            )
            self.assertEqual((p.returncode, p.stdout), (71, b""))
        for args in [[], ["1234", "bad", "2"], ["0", TOKEN, "2"], ["1234", TOKEN, "181"]]:
            p = subprocess.run([str(self.exe), *args], capture_output=True, timeout=2)
            self.assertEqual((p.returncode, p.stdout), (64, b""))

    def test_complete_minimal_http10_is_valid(self):
        p, port = self.start()
        with socket.create_connection(("127.0.0.1", port), timeout=1) as s:
            s.sendall(("GET /" + TOKEN + " HTTP/1.0\r\n\r\n").encode())
            s.recv(256)
        out, err = p.communicate(timeout=3)
        self.assertEqual((p.returncode, out, err), (0, b"OCHEALTH|ready\n", b""))


if __name__ == "__main__":
    unittest.main()
