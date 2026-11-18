"""Exercise the real request parser with a harmless shell backend and pipes."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "a" * 32


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerApi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.api = self.root / "api"
        self.token = self.root / "token"
        self.token.write_text(TOKEN + "\n")
        self.backend = self.root / "backend.sh"
        self.backend.write_text('printf \'{"operation":"%s","arg":"%s"}\\n\' "$3" "$4"\n')
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(ROOT / "cmu/installer/api.c"),
                "-o",
                str(self.api),
            ],
            check=True,
        )

    def request(self, body=None, headers=None):
        body = body or (TOKEN + "|-|status|-|-|-").encode()
        headers = headers or (
            b"POST /control HTTP/1.1\r\nHost: 127.0.0.1:39883\r\nContent-Type: text/plain;charset=UTF-8\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
        )
        return headers + body

    def invoke(self, request):
        return subprocess.run(
            [self.api, self.token, self.backend], input=request, capture_output=True, timeout=5
        )

    def test_status_and_setting_dispatch_only_arguments(self):
        for body, op, arg in (
            (TOKEN + "|-|status|-|-|-", "status", "-"),
            (TOKEN + "|" + "b" * 32 + "|set|touch|0|1", "set", "touch"),
            (TOKEN + "|" + "b" * 64 + "|set|warning|1|0", "set", "warning"),
            (TOKEN + "|" + "b" * 32 + "|recover|-|-|-", "recover", "-"),
        ):
            result = self.invoke(self.request(body.encode()))
            self.assertEqual(result.returncode, 0, result.stderr)
            headers, response = result.stdout.split(b"\r\n\r\n", 1)
            self.assertIn(b"Access-Control-Allow-Origin: *", headers)
            self.assertEqual(json.loads(response), {"operation": op, "arg": arg})

    def test_bad_framing_and_commands_never_dispatch(self):
        valid = self.request()
        cases = [
            valid.replace(b"POST", b"GET", 1),
            valid.replace(b"/control", b"/anything", 1),
            valid.replace(b"Host:", b"Content-Length: 47\r\nHost:", 1),
            valid.replace(b"Host:", b"Transfer-Encoding: chunked\r\nHost:", 1),
            valid.replace(b"Host:", b"Expect: 100-continue\r\nHost:", 1),
            valid.replace(b"text/plain;charset=UTF-8", b"application/json"),
            valid + b"x",
            valid.replace(b"status", b"reboot"),
            valid.replace(b"status", b"sta\x00us"),
            self.request((TOKEN + "|-|status|-|-|-|extra").encode()),
            self.request((TOKEN + "|-|set|unrelated|0|1").encode()),
            b"POST /control HTTP/1.1\r\n" + b"x" * 4100,
        ]
        for request in cases:
            with self.subTest(request=request[:70]):
                result = self.invoke(request)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b'"operation"', result.stdout)

    def test_wrong_or_symlinked_token_never_dispatches(self):
        result = self.invoke(self.request().replace(TOKEN.encode(), b"b" * 32))
        self.assertIn(b"403 Forbidden", result.stdout)
        self.token.rename(self.root / "real-token")
        self.token.symlink_to(self.root / "real-token")
        result = self.invoke(self.request())
        self.assertIn(b"403 Forbidden", result.stdout)
        self.assertNotIn(b'"operation"', result.stdout)

    def test_partial_reads(self):
        with subprocess.Popen(
            [self.api, self.token, self.backend], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        ) as process:
            request = self.request()
            for offset in range(0, len(request), 7):
                process.stdin.write(request[offset : offset + 7])
                process.stdin.flush()
            process.stdin.close()
            response = process.stdout.read()
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertIn(b'"operation":"status"', response)
