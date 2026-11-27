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
        core = ROOT / "cmu/installer/core"
        api_srcs = [
            ROOT / "cmu/installer/api.c",
            core / "oc-hash.c",
            core / "oc-io.c",
            core / "oc-manifest.c",
            core / "oc-record.c",
            core / "oc-config.c",
            core / "oc-guard.c",
            core / "oc-api.c",
        ]
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                *(str(s) for s in api_srcs),
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


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerApiNative(unittest.TestCase):
    """Exercise native C oc_firmware_guard, index.html parity, and smart pin reuse under ASan+UBSan."""

    def test_native_firmware_guard_and_completion_exemption(self):
        import hashlib

        from tests.test_installer_transaction import compile_host_api

        api = compile_host_api()
        assets = ROOT / "cmu/installer"
        boot_id = "12345678-1234-1234-1234-123456789abc"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram = root / "tmp/open-connect"
            data = root / "tmp/mnt/data_persist/open-connect"
            sess = ram / "sessions/session-fg0001"
            for d in (
                ram,
                sess,
                data,
                data / "packages",
                data / "snapshots",
                root / "proc/self",
                root / "jci/gui/framework/js",
                root / "jci/lvds",
                root / "jci/scripts",
                root / "dev",
            ):
                d.mkdir(parents=True, exist_ok=True)
            for d in (ram, sess, data, data / "packages", data / "snapshots"):
                d.chmod(0o700)
            (root / "dev/urandom").symlink_to("/dev/urandom")
            (ram / "lock").write_bytes(b"")
            (ram / "lock").chmod(0o600)
            (ram / "boot-id").symlink_to(boot_id)
            (ram / "runtime").symlink_to(sess)
            (sess / "token").write_text(TOKEN + "\n")
            (sess / "token").chmod(0o600)
            (sess / "backend.sh").write_text('printf \'{"ok":false,"error":"fell_back"}\\n\'\n')
            (sess / "backend.sh").chmod(0o700)

            pkg_dir = data / "packages/.new-pkg"
            pkg_dir.mkdir(mode=0o700)
            for name in ("VERSION", "services.tsv"):
                shutil.copyfile(assets / name, pkg_dir / name)
                (pkg_dir / name).chmod(0o600)
            pkg_mf = "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(pkg_dir.iterdir())
            )
            (pkg_dir / "files.sha256").write_text(pkg_mf)
            pkg_id = hashlib.sha256(pkg_mf.encode()).hexdigest()
            pkg = data / "packages" / pkg_id
            pkg_dir.rename(pkg)
            shutil.copyfile(pkg / "files.sha256", sess / "files.sha256")
            shutil.copyfile(pkg / "VERSION", sess / "VERSION")

            snap_dir = data / "snapshots/.new-snap"
            snap_dir.mkdir(mode=0o700)
            cfg = (
                f"OC2\nbase=0\ncarplay-autoshow=0\nmetadata=755:{os.getuid()}:{os.getgid()}\n"
                f"nvram=disable\npackage={pkg_id}\nservice-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n"
                "touch=1\nwarning=1\nwireless=0\n"
            )
            (snap_dir / "config").write_text(cfg)
            (snap_dir / "config").chmod(0o600)
            snap_mf = "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(snap_dir.iterdir())
            )
            (snap_dir / "files.sha256").write_text(snap_mf)
            snap_id = hashlib.sha256(snap_mf.encode()).hexdigest()
            snap = data / "snapshots" / snap_id
            snap_dir.rename(snap)
            (ram / "selected").write_text(snap_id + "\n")
            (ram / "selected").chmod(0o600)
            (data / "record").write_text(
                f"OC1|active|{'1' * 32}|{pkg_id}|{snap_id}|{snap_id}|-|-|-|3|-|{boot_id}|installed\n"
            )
            (data / "record").chmod(0o600)

            ver = root / "jci/version.ini"
            ver.write_text(
                "[VersionInfo]\n"
                'JCI_SW_VER="MAZ_CMU-150_74.00.324"\n'
                'JCI_SW_VER_PATCH="A"\n'
                'JCI_SW_FLAVOR="cmu150_NA"\n'
                + "".join(f'JCI_BLM_MOD_{i:03d}="BLM_MOD_{i:03d}_01.00.000"\n' for i in range(400))
            )
            mounts = root / "proc/self/mounts"
            mounts_ro = (
                "rootfs / rootfs rw 0 0\n"
                "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
                "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
            )
            mounts.write_text(mounts_ro)
            fw = root / "jci/gui/framework/js/GuiFramework.js"
            lvds = root / "jci/lvds/lvds_service"
            board = root / "jci/scripts/get_board_type.sh"
            fw.write_bytes(b"synthetic framework\n")
            lvds.write_bytes(b"synthetic lvds\n")
            board.write_text("#!/bin/sh\nexit 1\n")
            board.chmod(0o700)
            pins = root / "pins.txt"
            pins.write_text(
                f"root/framework.js={hashlib.sha256(fw.read_bytes()).hexdigest()}\n"
                f"root/lvds-service={hashlib.sha256(lvds.read_bytes()).hexdigest()}\n"
                f"root/board.sh={hashlib.sha256(board.read_bytes()).hexdigest()}\n"
            )

            base_env = {
                **os.environ,
                "OC_HOST_ROOT": str(root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_PINS": str(pins),
            }

            def req(rev, op, arg, exp="-", des="-", env_override=None):
                body = f"{TOKEN}|{rev}|{op}|{arg}|{exp}|{des}".encode()
                raw = (
                    b"POST /control HTTP/1.1\r\nHost: 127.0.0.1:15555\r\n"
                    b"Content-Type: text/plain;charset=UTF-8\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode()
                    + body
                )
                env = {**base_env, **(env_override or {})}
                if (
                    env_override
                    and "OC_HOST_NONROOT" in env_override
                    and env_override["OC_HOST_NONROOT"] is None
                ):
                    env.pop("OC_HOST_NONROOT", None)
                proc = subprocess.run(
                    [str(api), str(sess / "token"), str(sess / "backend.sh")],
                    input=raw,
                    env=env,
                    capture_output=True,
                    timeout=10,
                )
                _, payload = proc.stdout.split(b"\r\n\r\n", 1)
                return proc.returncode, json.loads(payload)

            # Happy paths: status:settings and status:completion both pass real oc_firmware_guard.
            rc, ans = req("-", "status", "settings")
            self.assertEqual(rc, 0, ans)
            self.assertTrue(ans["ok"])
            self.assertFalse(ans["wirelessFactory"])
            rc, comp = req("-", "status", "completion")
            self.assertEqual(rc, 0, comp)
            self.assertTrue(comp["completionReady"])

            # Non-root without OC_HOST_NONROOT returns root_required.
            if os.getuid() != 0:
                rc, ans = req("-", "status", "settings", env_override={"OC_HOST_NONROOT": None})
                self.assertNotEqual(rc, 0)
                self.assertEqual(ans["error"], "root_required")

            # Missing GuiFramework.js & lvds_service: settings:status:completion STILL succeeds,
            # while status:settings, dismiss:-, and set fail with unsupported_framework!
            fw_bytes, lvds_bytes = fw.read_bytes(), lvds.read_bytes()
            fw.unlink()
            lvds.unlink()
            rc, comp = req("-", "status", "completion")
            self.assertEqual(rc, 0, comp)
            self.assertTrue(comp["completionReady"])
            for call_args in (
                ("-", "status", "settings", "-", "-"),
                (snap_id, "dismiss", "-", "-", "-"),
                (snap_id, "set", "warning", "1", "0"),
            ):
                rc, err = req(*call_args)
                self.assertNotEqual(rc, 0)
                self.assertEqual(err["error"], "unsupported_framework")
            fw.write_bytes(fw_bytes)
            rc, err = req("-", "status", "settings")
            self.assertEqual(err["error"], "unsupported_display")
            lvds.write_bytes(lvds_bytes)

            # rw,noatime: status:settings succeeds (allow_rw=1), set refuses root_mount_changed (allow_rw=0).
            mounts.write_text(mounts_ro.replace("ro,noatime", "rw,noatime"))
            rc, ans = req("-", "status", "settings")
            self.assertEqual(rc, 0, ans)
            rc, err = req(snap_id, "set", "warning", "1", "0")
            self.assertEqual(err["error"], "root_mount_changed")

            # Persistence ro -> persistence_unavailable; bad root mount -> invalid_boot_mounts; bad version -> unsupported_firmware.
            mounts.write_text(mounts_ro.replace("rw,noatime", "ro,noatime"))
            _, err = req("-", "status", "completion")
            self.assertEqual(err["error"], "persistence_unavailable")
            mounts.write_text(mounts_ro.replace("ro,noatime", "rw"))
            _, err = req("-", "status", "completion")
            self.assertEqual(err["error"], "invalid_boot_mounts")
            mounts.write_text(mounts_ro)
            ver.write_text('JCI_SW_VER="wrong"\n')
            _, err = req("-", "status", "completion")
            self.assertEqual(err["error"], "unsupported_firmware")

    def test_native_index_html_differential_parity_vs_awk(self):
        """Assert byte-for-byte parity between oc_render_index_native and firmware.sh AWK across all 64 combos."""
        import itertools

        from tests.test_installer_boot_selection import NativeBootSelection, sha

        # Extract the exact AWK renderer from firmware.sh.
        fw_src = (ROOT / "cmu/installer/firmware.sh").read_text()
        awk_start = fw_src.index("BEGIN{c=split(services")
        awk_end = fw_src.index('\' "$src/index-$st.html"', awk_start)
        awk_prog = fw_src[awk_start:awk_end]

        assets = ROOT / "cmu/installer"
        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>\n'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        # Compile a tiny host harness calling oc_render_index_native indirectly via real api
        # is slow for 64 combos; compile oc-api.c's exact function in a 15-line host driver!
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp).resolve()
            harness = tdir / "idx_harness.c"
            harness.write_text(
                '#include "oc-api.c"\n'
                "int main(int argc, char **argv) {\n"
                "  if (argc != 9) return 64;\n"
                "  int pdir = (int)oc_openat(OC_CWD, argv[1], OC_DIRECTORY, 0);\n"
                "  int cdir = (int)oc_openat(OC_CWD, argv[2], OC_DIRECTORY, 0);\n"
                "  int wdir = (int)oc_openat(OC_CWD, argv[3], OC_DIRECTORY, 0);\n"
                "  char pmf_buf[4096], cmf_buf[4096]; OcManifest pmf, cmf;\n"
                '  if (oc_text(pdir, "files.sha256", pmf_buf, sizeof pmf_buf, 0) <= 0 || !oc_manifest(pmf_buf, &pmf, 0)) return 2;\n'
                '  if (oc_text(cdir, "files.sha256", cmf_buf, sizeof cmf_buf, 0) <= 0 || !oc_manifest(cmf_buf, &cmf, 0)) return 3;\n'
                "  OcPrefs p = {0};\n"
                "  p.warning = argv[4]; p.base = argv[5]; p.autoshow = argv[6];\n"
                '  p.svc_ids[0] = "android-auto"; p.svc_vals[0] = argv[7];\n'
                '  p.svc_ids[1] = "pandora"; p.svc_vals[1] = argv[8];\n'
                '  p.svc_ids[2] = "siriusxm"; p.svc_vals[2] = getenv("OC_SXM");\n'
                "  p.svc_count = 3;\n"
                "  return oc_render_index_native(pdir, &pmf, cdir, &cmf, wdir, &p) ? 0 : 1;\n"
                "}\n"
            )
            core = ROOT / "cmu/installer/core"
            bin_path = tdir / "idx_harness"
            subprocess.run(
                [
                    "clang",
                    "-DOC_HOST",
                    "-I",
                    str(core),
                    "-fsanitize=address,undefined",
                    str(harness),
                    str(core / "oc-hash.c"),
                    str(core / "oc-io.c"),
                    str(core / "oc-manifest.c"),
                    str(core / "oc-record.c"),
                    str(core / "oc-config.c"),
                    str(core / "oc-guard.c"),
                    "-o",
                    str(bin_path),
                ],
                check=True,
            )
            pdir, cdir = tdir / "pkg", tdir / "comp"
            pdir.mkdir(mode=0o700)
            cdir.mkdir(mode=0o700)
            for nm in ("system-hook.js", "base-logging.js"):
                shutil.copyfile(assets / nm, pdir / nm)
            (pdir / "files.sha256").write_text(
                "".join(sha(p.read_bytes()) + "  " + p.name + "\n" for p in sorted(pdir.iterdir()))
            )
            for nm in ("index-on.html", "index-off.html"):
                (cdir / nm).write_text(idx_tpl)
            (cdir / "files.sha256").write_text(
                "".join(sha(p.read_bytes()) + "  " + p.name + "\n" for p in sorted(cdir.iterdir()))
            )

            for w, b, a, aa, pa, sx in itertools.product("01", repeat=6):
                wdir = tdir / f"w_{w}{b}{a}{aa}{pa}{sx}"
                wdir.mkdir(mode=0o700)
                c_res = subprocess.run(
                    [str(bin_path), str(pdir), str(cdir), str(wdir), w, b, a, aa, pa],
                    env={**os.environ, "OC_SXM": sx},
                    capture_output=True,
                    timeout=5,
                )
                self.assertEqual(c_res.returncode, 0, (w, b, a, aa, pa, sx, c_res.stderr))
                awk_res = subprocess.run(
                    [
                        "awk",
                        "-v",
                        f"base={b}",
                        "-v",
                        f"warning={w}",
                        "-v",
                        f"services=android-auto={aa},pandora={pa},siriusxm={sx}",
                        "-v",
                        f"autoshow={a}",
                        "-v",
                        f"hook={pdir / 'system-hook.js'}",
                        "-v",
                        f"logger={pdir / 'base-logging.js'}",
                        awk_prog,
                        str(cdir / ("index-on.html" if w == "1" else "index-off.html")),
                    ],
                    capture_output=True,
                    timeout=5,
                )
                self.assertEqual(awk_res.returncode, 0, awk_res.stderr)
                self.assertEqual(
                    (wdir / "index.html").read_bytes(),
                    awk_res.stdout,
                    f"Mismatch for w={w} b={b} a={a} aa={aa} pa={pa} sx={sx}",
                )
        _ = NativeBootSelection  # keep import clean
