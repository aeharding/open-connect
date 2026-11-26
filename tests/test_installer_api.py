"""Exercise the real request parser with a harmless shell backend and pipes."""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
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
            (TOKEN + "|-|status|settings|-|-", "status", "settings"),
            (TOKEN + "|-|status|completion|-|-", "status", "completion"),
            (TOKEN + "|-|dismiss|usb|-|-", "dismiss", "usb"),
            (TOKEN + "|" + "b" * 64 + "|dismiss|-|-|-", "dismiss", "-"),
            (TOKEN + "|" + "b" * 32 + "|set|touch|0|1", "set", "touch"),
            (TOKEN + "|" + "b" * 64 + "|set|warning|1|0", "set", "warning"),
            (TOKEN + "|" + "b" * 64 + "|set|touch|2|0", "set", "touch"),
            (TOKEN + "|" + "b" * 64 + "|set|touch|1|2", "set", "touch"),
            (TOKEN + "|" + "b" * 64 + "|set|ssh|0|1", "set", "ssh"),
            (TOKEN + "|" + "b" * 64 + "|set|uart|1|0", "set", "uart"),
            (TOKEN + "|" + "b" * 64 + "|set|pandora|1|0", "set", "pandora"),
            (TOKEN + "|" + "b" * 64 + "|set|android-auto|1|0", "set", "android-auto"),
            (TOKEN + "|" + "b" * 64 + "|set|base|0|1", "set", "base"),
            (TOKEN + "|" + "b" * 64 + "|set|wireless|0|1", "set", "wireless"),
            (TOKEN + "|" + "b" * 64 + "|import|-|-|-", "import", "-"),
            (TOKEN + "|" + "b" * 32 + "|recover|-|-|-", "recover", "-"),
        ):
            result = self.invoke(self.request(body.encode()))
            self.assertEqual(result.returncode, 0, result.stderr)
            headers, response = result.stdout.split(b"\r\n\r\n", 1)
            self.assertIn(b"Access-Control-Allow-Origin: *", headers)
            self.assertEqual(json.loads(response), {"operation": op, "arg": arg})

    def test_session_liveness_is_authenticated_and_never_executes_backend(self):
        self.backend.write_text("exit 99\n")
        for closed in (False, True):
            if closed:
                (self.root / "closed").touch()
            result = self.invoke(self.request((TOKEN + "|-|status|session|-|-").encode()))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout.split(b"\r\n\r\n", 1)[1]),
                {"ok": True, "closed": closed},
            )
        result = self.invoke(self.request(("f" * 32 + "|-|status|session|-|-").encode()))
        self.assertIn(b"403 Forbidden", result.stdout)

    def media_fixture(self):
        registry = self.root / "registry"
        sessions = registry / "sessions"
        installed, usb = (sessions / n for n in ("session-ABC123", "session-xyz789"))
        installed.mkdir(parents=True)
        usb.mkdir()
        self.token = installed / "token"
        self.token.write_text(TOKEN + "\n")
        self.backend.write_text("exit 99\n")
        (registry / "runtime").symlink_to(installed)
        (registry / "usb-runtime").symlink_to(usb)
        usb_token = "b" * 32
        (usb / "token").write_text(usb_token + "\n")
        offer = f"{usb.name}|{usb_token}\n"
        return registry, usb, offer

    def media(self):
        result = self.invoke(self.request((TOKEN + "|-|status|media|-|-").encode()))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.split(b"\r\n\r\n", 1)[1])

    def test_media_discovery_requires_a_final_offer_and_installed_role(self):
        registry, usb, offer = self.media_fixture()
        self.assertEqual(self.media(), {"ok": True, "media": None})
        (usb / "offer").write_text(offer)
        self.assertEqual(
            self.media(),
            {"ok": True, "media": {"session": usb.name, "token": "b" * 32}},
        )
        (usb / "closed").touch()
        self.assertEqual(self.media(), {"ok": True, "media": None})
        (usb / "closed").unlink()
        # Knowing a USB capability does not grant discovery of other sessions.
        installed_token = self.token
        self.token = usb / "token"
        request = self.request(("b" * 32 + "|-|status|media|-|-").encode())
        result = self.invoke(request)
        self.assertEqual(json.loads(result.stdout.split(b"\r\n\r\n", 1)[1])["media"], None)
        self.token = installed_token
        (registry / "runtime").unlink()
        self.assertEqual(self.media(), {"ok": True, "media": None})

    def test_media_discovery_rejects_malformed_or_unmatched_pairs(self):
        registry, usb, offer = self.media_fixture()
        for data in (
            offer.rstrip(),
            offer + "x",
            offer.replace("b", "c"),
            "session-OTHER1|" + "b" * 32 + "\n",
        ):
            with self.subTest(data=data):
                (usb / "offer").write_text(data)
                self.assertEqual(self.media(), {"ok": True, "media": None})
        (usb / "offer").unlink()
        (self.root / "offer").write_text(offer)
        (usb / "offer").symlink_to(self.root / "offer")
        self.assertEqual(self.media(), {"ok": True, "media": None})
        (usb / "offer").unlink()
        (usb / "offer").write_text(offer)
        (registry / "usb-runtime").unlink()
        # The offer cannot redirect discovery outside the private registry.
        (registry / "usb-runtime").symlink_to(self.root)
        self.assertEqual(self.media(), {"ok": True, "media": None})

    def test_media_discovery_discards_a_pointer_replaced_during_read(self):
        registry, usb, offer = self.media_fixture()
        successor = usb.parent / "session-NEW123"
        successor.mkdir()
        os.mkfifo(usb / "offer")
        failures = []

        def replace_while_reading():
            until = time.monotonic() + 3
            try:
                while True:
                    try:
                        fd = os.open(usb / "offer", os.O_WRONLY | os.O_NONBLOCK)
                        break
                    except OSError:
                        if time.monotonic() >= until:
                            raise
                        time.sleep(0.005)
                with os.fdopen(fd, "w") as writer:
                    (registry / "usb-runtime").unlink()
                    (registry / "usb-runtime").symlink_to(successor)
                    writer.write(offer)
            except Exception as error:
                failures.append(error)

        writer = threading.Thread(target=replace_while_reading)
        writer.start()
        try:
            self.assertEqual(self.media(), {"ok": True, "media": None})
        finally:
            writer.join(timeout=4)
        self.assertFalse(writer.is_alive())
        self.assertEqual(failures, [])

    def test_bad_framing_and_commands_never_dispatch(self):
        valid = self.request()
        cases = [
            *(
                self.request((TOKEN + "|-|set|" + key + "|" + pair).encode())
                for key in (
                    "warning",
                    "base",
                    "wireless",
                    "pandora",
                    "uart",
                    "ssh",
                    "carplay-autoshow",
                )
                for pair in ("0|2", "2|1")
            ),
            self.request((TOKEN + "|-|set|touch|2|3").encode()),
            self.request((TOKEN + "|-|restart|settings|-|-").encode()),
            self.request((TOKEN + "|-|status|settings|0|-").encode()),
            self.request((TOKEN + "|-|status|unknown|-|-").encode()),
            valid.replace(b"POST", b"GET", 1),
            valid.replace(b"/control", b"/anything", 1),
            valid.replace(b"Host:", b"Content-Length: 47\r\nHost:", 1),
            valid.replace(b"Host:", b"Transfer-Encoding: chunked\r\nHost:", 1),
            valid.replace(b"Host:", b"Expect: 100-continue\r\nHost:", 1),
            valid.replace(b"text/plain;charset=UTF-8", b"application/json"),
            valid + b"x",
            valid.replace(b"status", b"reboot"),
            self.request((TOKEN + "|-|undo|-|-|-").encode()),
            self.request((TOKEN + "|-|uninstall|confirm|-|-").encode()),
            valid.replace(b"status", b"sta\x00us"),
            self.request((TOKEN + "|-|status|-|-|-|extra").encode()),
            self.request((TOKEN + "|-|set|" + "a" * 33 + "|0|1").encode()),
            self.request((TOKEN + "|-|set|-bad|0|1").encode()),
            self.request((TOKEN + "|-|set|pandora|1|2").encode()),
            self.request((TOKEN + "|-|set|base|0|2").encode()),
            self.request((TOKEN + "|-|set|wireless|0|2").encode()),
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
