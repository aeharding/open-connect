"""Exercise the real native api HTTP parser, firmware guard, index renderer, and record invariants."""

import hashlib
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.host_bins import copy_host_api, host_api

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
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
        copy_host_api(self.api)

    def request(self, body=None, headers=None):
        body = body or (TOKEN + "|-|status|session|-|-").encode()
        headers = headers or (
            b"POST /control HTTP/1.1\r\nHost: 127.0.0.1:39883\r\nContent-Type: text/plain;charset=UTF-8\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
        )
        return headers + body

    def invoke(self, request):
        return subprocess.run(
            [self.api, self.token],
            input=request,
            capture_output=True,
            timeout=5,
            env={**os.environ, "OC_HOST_ROOT": str(self.root)},
        )

    def test_session_liveness_is_authenticated_and_returns_cors_headers(self):
        for closed in (False, True):
            if closed:
                (self.root / "closed").touch()
            result = self.invoke(self.request((TOKEN + "|-|status|session|-|-").encode()))
            self.assertEqual(result.returncode, 0, result.stderr)
            headers, body = result.stdout.split(b"\r\n\r\n", 1)
            self.assertIn(b"Access-Control-Allow-Origin: *", headers)
            self.assertEqual(json.loads(body), {"ok": True, "closed": closed})
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
            self.request((TOKEN + "|-|export|-|-|-").encode()),
            self.request((TOKEN + "|-|export|other|-|-").encode()),
            self.request((TOKEN + "|-|import|other|-|-").encode()),
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
                self.assertNotIn(b'"closed"', result.stdout)

    def test_wrong_or_symlinked_token_never_dispatches(self):
        result = self.invoke(self.request().replace(TOKEN.encode(), b"b" * 32))
        self.assertIn(b"403 Forbidden", result.stdout)
        self.token.rename(self.root / "real-token")
        self.token.symlink_to(self.root / "real-token")
        result = self.invoke(self.request())
        self.assertIn(b"403 Forbidden", result.stdout)
        self.assertNotIn(b'"closed"', result.stdout)

    def test_partial_reads(self):
        with subprocess.Popen(
            [self.api, self.token], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        ) as process:
            request = self.request()
            for offset in range(0, len(request), 7):
                process.stdin.write(request[offset : offset + 7])
                process.stdin.flush()
            process.stdin.close()
            response = process.stdout.read()
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertEqual(
                json.loads(response.split(b"\r\n\r\n", 1)[1]), {"ok": True, "closed": False}
            )


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerApiNative(unittest.TestCase):
    """Exercise native C oc_firmware_guard, oc_render_index_native, and record/fingerprint invariants."""

    def test_native_firmware_guard_and_completion_exemption(self):
        api = host_api()
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

            pkg_dir = data / "packages/.new-pkg"
            pkg_dir.mkdir(mode=0o700)
            for name in ("VERSION", "services.tsv"):
                shutil.copyfile(ASSETS / name, pkg_dir / name)
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
                    [str(api), str(sess / "token")],
                    input=raw,
                    env=env,
                    capture_output=True,
                    timeout=10,
                )
                _, payload = proc.stdout.split(b"\r\n\r\n", 1)
                return proc.returncode, json.loads(payload)

            rc, ans = req("-", "status", "settings")
            self.assertEqual(rc, 0, ans)
            self.assertTrue(ans["ok"])
            self.assertFalse(ans["wirelessFactory"])
            rc, comp = req("-", "status", "completion")
            self.assertEqual(rc, 0, comp)
            self.assertTrue(comp["completionReady"])

            if os.getuid() != 0:
                rc, ans = req("-", "status", "settings", env_override={"OC_HOST_NONROOT": None})
                self.assertNotEqual(rc, 0)
                self.assertEqual(ans["error"], "root_required")

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

            mounts.write_text(mounts_ro.replace("ro,noatime", "rw,noatime"))
            rc, ans = req("-", "status", "settings")
            self.assertEqual(rc, 0, ans)
            rc, err = req(snap_id, "set", "warning", "1", "0")
            self.assertEqual(err["error"], "root_mount_changed")

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

    def test_native_index_html_matrix_64_combos(self):
        """Exercise oc_render_index_native in oc-render.c across all 64 (w, b, a, aa, pa, sx) combos."""
        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>\n'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp).resolve()
            harness = tdir / "idx_harness.c"
            harness.write_text(
                '#include "oc-core.h"\n'
                "#include <stdlib.h>\n"
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
                '  p.source_order = getenv("OC_SO");\n'
                '  p.menu_loop = getenv("OC_ML");\n'
                '  p.hold_scroll = getenv("OC_HS");\n'
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
                    str(core / "oc-root.c"),
                    str(core / "oc-access.c"),
                    str(core / "oc-txn.c"),
                    str(core / "oc-render.c"),
                    "-o",
                    str(bin_path),
                ],
                check=True,
            )
            pdir, cdir = tdir / "pkg", tdir / "comp"
            pdir.mkdir(mode=0o700)
            cdir.mkdir(mode=0o700)
            for nm in ("system-hook.js", "base-logging.js"):
                shutil.copyfile(ASSETS / nm, pdir / nm)
            (pdir / "files.sha256").write_text(
                "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(pdir.iterdir())
                )
            )
            for nm in ("index-on.html", "index-off.html"):
                (cdir / nm).write_text(idx_tpl)
            (cdir / "files.sha256").write_text(
                "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(cdir.iterdir())
                )
            )
            base_log_text = (ASSETS / "base-logging.js").read_text().strip()
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
                rendered = (wdir / "index.html").read_text()
                self.assertEqual(base_log_text in rendered, b == "1")
                self.assertEqual("feature/carplay.js" in rendered, a == "1")
                hidden = []
                if b == "1":
                    hidden += ["stitcher", "dab", "tv", "aharadio", "dvd"]
                if pa == "0":
                    hidden.append("pandora")
                if sx == "0":
                    hidden += ["satradio", "xmaudio", "xmdata"]
                if b == "1" and aa == "0":
                    hidden.append("androidauto")
                if w == "1" or hidden:
                    self.assertIn(f'[{w},"{",".join(hidden)}"]', rendered)
                else:
                    self.assertNotIn("OPEN_CONNECT_APPLIED", rendered)
                    self.assertNotIn("framework, [", rendered)
                # Build-time marker comments must NEVER leak into rendered index.html.
                for marker in (
                    "OPEN_CONNECT_AA_CALL",
                    "OPEN_CONNECT_SO_CALL",
                    "OPEN_CONNECT_NAV_CALL",
                    "OPEN_CONNECT_AA_BEGIN",
                    "OPEN_CONNECT_SO_BEGIN",
                    "OPEN_CONNECT_NAV_BEGIN",
                ):
                    self.assertNotIn(marker, rendered)

            # Verify source-order, menu-loop, and hold-scroll render cleanly with zero leaked markers.
            for so, ml, hs in (
                ("1", "0", "0"),
                ("0", "1", "0"),
                ("0", "0", "1"),
                ("1", "1", "1"),
            ):
                wdir = tdir / f"nav_{so}{ml}{hs}"
                wdir.mkdir(mode=0o700)
                c_res = subprocess.run(
                    [str(bin_path), str(pdir), str(cdir), str(wdir), "0", "1", "0", "0", "1"],
                    env={**os.environ, "OC_SXM": "1", "OC_SO": so, "OC_ML": ml, "OC_HS": hs},
                    capture_output=True,
                    timeout=5,
                )
                self.assertEqual(c_res.returncode, 0, (so, ml, hs, c_res.stderr))
                rendered = (wdir / "index.html").read_text()
                for marker in (
                    "OPEN_CONNECT_AA_CALL",
                    "OPEN_CONNECT_SO_CALL",
                    "OPEN_CONNECT_NAV_CALL",
                ):
                    self.assertNotIn(marker, rendered)
                if ml == "1" or hs == "1":
                    self.assertIn(f",{so},{ml},{hs}]", rendered)
                else:
                    self.assertIn(",1]", rendered)

            # carplay-autoshow=1 alone (nd==0) must reject missing or duplicated framework.init().
            for label, bad_tpl in (
                (
                    "missing_init",
                    '<html><head><script src="common/js/logDefaults.js"></script></head>\n'
                    "<body><script>/*@TOKEN@*/</script></body></html>\n",
                ),
                (
                    "dup_init",
                    '<html><head><script src="common/js/logDefaults.js"></script></head>\n'
                    "<body><script>/*@TOKEN@*/framework.init();\nframework.init();</script></body></html>\n",
                ),
            ):
                bcdir = tdir / f"comp_{label}"
                bcdir.mkdir(mode=0o700)
                for nm in ("index-on.html", "index-off.html"):
                    (bcdir / nm).write_text(bad_tpl)
                (bcdir / "files.sha256").write_text(
                    "".join(
                        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                        for p in sorted(bcdir.iterdir())
                    )
                )
                wdir = tdir / f"w_{label}"
                wdir.mkdir(mode=0o700)
                c_res = subprocess.run(
                    [str(bin_path), str(pdir), str(bcdir), str(wdir), "0", "0", "1", "1", "1"],
                    env={**os.environ, "OC_SXM": "1"},
                    capture_output=True,
                    timeout=5,
                )
                self.assertNotEqual(c_res.returncode, 0, f"expected refusal for {label}")

    def test_record_apply_phase_invariants_fail_closed_and_key_fingerprint(self):
        """Cover OC1|apply recovery, phase/before/after invariants, dismiss:usb symlink refusal,
        and OC_HOST_SSH_KEYGEN fingerprint bounds."""
        api_bin = host_api()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram = root / "tmp/open-connect"
            data = root / "tmp/mnt/data_persist/open-connect"
            sess = ram / "sessions/session-apinv1"
            for d in (ram, sess, data / "packages", data / "snapshots", data / "keys"):
                d.mkdir(parents=True, mode=0o700)
            for d in (ram, ram / "sessions", sess, data):
                d.chmod(0o700)
            (ram / "lock").write_bytes(b"")
            (ram / "lock").chmod(0o600)
            (ram / "runtime").symlink_to(sess)

            pkg_dir = data / "packages/.pkg"
            pkg_dir.mkdir(mode=0o700)
            for name in ("VERSION", "services.tsv"):
                shutil.copyfile(ASSETS / name, pkg_dir / name)
                (pkg_dir / name).chmod(0o600)
            pmf = "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(pkg_dir.iterdir())
            )
            (pkg_dir / "files.sha256").write_text(pmf)
            pkg_id = hashlib.sha256(pmf.encode()).hexdigest()
            pkg_dir.rename(data / "packages" / pkg_id)
            shutil.copyfile(data / "packages" / pkg_id / "VERSION", sess / "VERSION")

            snap_work = data / "snapshots/.snap"
            snap_work.mkdir(mode=0o700)
            cfg = (
                f"OC2\nbase=0\ncarplay-autoshow=0\nmetadata=755:{os.getuid()}:{os.getgid()}\n"
                f"nvram=absent\npackage={pkg_id}\nservice-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n"
                "touch=0\nwarning=0\nwireless=0\n"
            )
            (snap_work / "config").write_text(cfg)
            (snap_work / "config").chmod(0o600)
            smf = f"{hashlib.sha256(cfg.encode()).hexdigest()}  config\n"
            (snap_work / "files.sha256").write_text(smf)
            (snap_work / "files.sha256").chmod(0o600)
            cur_snap = hashlib.sha256(smf.encode()).hexdigest()
            snap_work.rename(data / "snapshots" / cur_snap)

            base_fields = [
                "OC1",
                "active",
                "1" * 32,
                pkg_id,
                cur_snap,
                cur_snap,
                "-",
                "-",
                "-",
                "3",
                "-",
                "-",
                "-",
            ]
            orig_rec_bytes = ("|".join(base_fields) + "\n").encode()
            (data / "record").write_bytes(orig_rec_bytes)
            (data / "record").chmod(0o600)
            (ram / "selected").write_text(cur_snap + "\n")
            (ram / "selected").chmod(0o600)

            base_env = {
                **os.environ,
                "OC_HOST_ROOT": str(root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(root / "no-wireless"),
            }

            def run_cli(args, *, extra_env=None):
                env = {**base_env, **(extra_env or {})}
                proc = subprocess.run(
                    [str(api_bin), *args], capture_output=True, text=True, timeout=10, env=env
                )
                return proc, json.loads(proc.stdout)

            # 1) Valid OC1|apply pending record succeeds on both Settings and USB status:settings.
            apply_fields = list(base_fields)
            apply_fields[1] = "apply"
            apply_fields[6] = cur_snap
            apply_fields[7] = cur_snap
            (data / "record").write_text("|".join(apply_fields) + "\n")
            proc, st = run_cli(["--handle", str(sess), "-", "status", "settings", "-", "-"])
            self.assertEqual(proc.returncode, 0, (st, proc.stderr))
            self.assertTrue(st["ok"] and st["pending"])
            self.assertEqual(st["revision"], apply_fields[2])
            (ram / "runtime").unlink()
            (ram / "usb-runtime").symlink_to(sess)
            proc, ust = run_cli(["--handle", str(sess), "-", "status", "settings", "-", "-"])
            self.assertEqual(proc.returncode, 0, (ust, proc.stderr))
            self.assertTrue(ust["ok"] and ust["pending"])
            self.assertEqual(ust["revision"], apply_fields[2])

            # 2) dismiss:usb with a symlinked session/closed file must fail closed.
            target = root / "symlink-closed-target"
            target.write_text("")
            (sess / "closed").symlink_to(target)
            proc, derr = run_cli(["--handle", str(sess), "-", "dismiss", "usb", "-", "-"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(derr["ok"])
            (sess / "closed").unlink()
            (ram / "usb-runtime").unlink()
            (ram / "runtime").symlink_to(sess)

            # 3) Malformed phase <-> (before, after) combinations rejected as invalid_record.
            for bad_phase, bad_before, bad_after in (
                ("active", cur_snap, cur_snap),
                ("purge", cur_snap, cur_snap),
                ("removed", cur_snap, "-"),
                ("set", "-", "-"),
                ("apply", "-", cur_snap),
                ("install", cur_snap, "-"),
            ):
                with self.subTest(phase=bad_phase, before=bad_before, after=bad_after):
                    bad = list(base_fields)
                    bad[1], bad[6], bad[7] = bad_phase, bad_before, bad_after
                    (data / "record").write_text("|".join(bad) + "\n")
                    proc, err = run_cli(
                        ["--handle", str(sess), "-", "status", "settings", "-", "-"]
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(err, {"ok": False, "error": "invalid_record"})
            (data / "record").write_bytes(orig_rec_bytes)

            # 4) oc_key_fingerprint via OC_HOST_SSH_KEYGEN: valid vs oversized (>=128 chars) rejected.
            key_bytes = b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForOpenConnect test@host\n"
            key_id = hashlib.sha256(key_bytes).hexdigest()
            key_file = data / "keys" / f"{key_id}.cmu"
            key_file.write_bytes(key_bytes)
            key_file.chmod(0o600)
            snap_key = data / "snapshots/.new-keytest"
            shutil.copytree(data / "snapshots" / cur_snap, snap_key)
            (snap_key / "access").write_text(f"0|1|{key_id}|755:0:0|644:0:0|-\n")
            (snap_key / "access").chmod(0o600)
            (snap_key / "runlogin").write_text("rl\n")
            (snap_key / "runlogin").chmod(0o600)
            (snap_key / "sshd.conf").write_text("sc\n")
            (snap_key / "sshd.conf").chmod(0o600)
            (snap_key / "files.sha256").unlink()
            mf = "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(snap_key.iterdir())
            )
            (snap_key / "files.sha256").write_text(mf)
            (snap_key / "files.sha256").chmod(0o600)
            key_snap_id = hashlib.sha256(mf.encode()).hexdigest()
            snap_key.rename(data / "snapshots" / key_snap_id)
            krec = list(base_fields)
            krec[5] = key_snap_id
            (data / "record").write_text("|".join(krec) + "\n")
            (ram / "selected").write_text(key_snap_id + "\n")

            fake_kg = root / "fake-ssh-keygen"
            fp_valid = "ab:cd:ef:01:23:45:67:89:ab:cd:ef:01:23:45:67:89"
            fake_kg.write_text(f'#!/bin/sh\nprintf "256 %s %s (ED25519)\\n" "{fp_valid}" "$3"\n')
            fake_kg.chmod(0o700)
            proc, kst = run_cli(
                ["--handle", str(sess), "-", "status", "settings", "-", "-"],
                extra_env={"OC_HOST_SSH_KEYGEN": str(fake_kg)},
            )
            self.assertEqual(proc.returncode, 0, (kst, proc.stderr))
            self.assertEqual(kst["fingerprint"], fp_valid)
            fp_long = "ab:" * 45 + "cd"
            fake_kg.write_text(f'#!/bin/sh\nprintf "256 %s %s (ED25519)\\n" "{fp_long}" "$3"\n')
            proc, kst2 = run_cli(
                ["--handle", str(sess), "-", "status", "settings", "-", "-"],
                extra_env={"OC_HOST_SSH_KEYGEN": str(fake_kg)},
            )
            self.assertEqual(proc.returncode, 0, (kst2, proc.stderr))
            self.assertEqual(kst2["fingerprint"], "-")

    def test_listener_startup_race_returns_busy_not_session_replaced_185(self):
        import fcntl

        api_bin = host_api()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve() / "race185"
            ram = root / "tmp/open-connect"
            sess = ram / "sessions/session-abc123"
            sess.mkdir(parents=True, mode=0o700)
            ram.chmod(0o700)
            (ram / "sessions").chmod(0o700)
            lock = ram / "lock"
            lock.touch(mode=0o600)
            env = {
                **os.environ,
                "OC_HOST_ROOT": str(root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
            }

            def call():
                proc = subprocess.run(
                    [str(api_bin), "--handle", str(sess), "-", "status", "completion", "-", "-"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=env,
                )
                return proc, json.loads(proc.stdout)

            # 1) Lock exclusively held, no runtime symlink yet, session not closed -> transient "busy"
            with lock.open("r+b") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    proc, res = call()
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(res, {"ok": False, "error": "busy"})

                    # 2) Same lock held, but session explicitly closed -> terminal "session_replaced"
                    (sess / "closed").touch(mode=0o600)
                    proc, res = call()
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(res, {"ok": False, "error": "session_replaced"})
                    (sess / "closed").unlink()
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

            # 3) Lock released and still no pointer -> terminal "session_replaced"
            proc, res = call()
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(res, {"ok": False, "error": "session_replaced"})

    def test_oc_run_cmd_io_closed_stdio_and_fd_swap(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            src = d / "probe.c"
            exe = d / "probe"
            src.write_text(
                '#include "oc-core.h"\n'
                "#include <fcntl.h>\n"
                "#include <stdio.h>\n"
                "#include <string.h>\n"
                "#include <unistd.h>\n"
                "int main(int argc, char **argv) {\n"
                '    const char *mode = argc > 1 ? argv[1] : "";\n'
                "    char cap[64] = {0};\n"
                '    if (strcmp(mode, "pfd01") == 0) {\n'
                "        int fd = open(argv[2], O_RDONLY | O_CLOEXEC);\n"
                "        int hi = fcntl(fd, F_DUPFD_CLOEXEC, 10);\n"
                "        close(fd); close(0); close(1);\n"
                '        char *av[] = {"/bin/cat", 0};\n'
                '        int rc = oc_run_cmd_io("/bin/cat", av, hi, -1, cap, sizeof cap, -1);\n'
                '        return (rc == 0 && strcmp(cap, "hello\\n") == 0) ? 0 : 1;\n'
                "    }\n"
                '    if (strcmp(mode, "devnull0") == 0) {\n'
                "        close(0); close(1); close(2);\n"
                '        char *av[] = {"/bin/sh", "-c", "exec 3<&0 4>&1 5>&2", 0};\n'
                '        return oc_run_cmd_io("/bin/sh", av, -1, -1, 0, 0, -1) == 0 ? 0 : 1;\n'
                "    }\n"
                '    if (strcmp(mode, "pfd02") == 0) {\n'
                "        int fd = open(argv[2], O_RDONLY | O_CLOEXEC);\n"
                "        int hi = fcntl(fd, F_DUPFD_CLOEXEC, 10);\n"
                "        close(fd); close(0); close(2);\n"
                '        char *av[] = {"/bin/sh", "-c", "cat; exec 5>&2", 0};\n'
                '        int rc = oc_run_cmd_io("/bin/sh", av, hi, -1, cap, sizeof cap, -1);\n'
                '        return (rc == 0 && strcmp(cap, "hello\\n") == 0) ? 0 : 1;\n'
                "    }\n"
                '    if (strcmp(mode, "swap01") == 0) {\n'
                "        int in_f = open(argv[2], O_RDONLY | O_CLOEXEC);\n"
                "        int out_f = open(argv[3], O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);\n"
                "        dup2(out_f, 0); dup2(in_f, 1); close(in_f); close(out_f);\n"
                '        char *av[] = {"/bin/cat", 0};\n'
                '        return oc_run_cmd_io("/bin/cat", av, 1, 0, 0, 0, -1) == 0 ? 0 : 1;\n'
                "    }\n"
                "    return 2;\n"
                "}\n"
            )
            subprocess.run(
                [
                    "clang",
                    "-DOC_HOST",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    f"-I{ASSETS / 'core'}",
                    str(src),
                    str(ASSETS / "core/oc-io.c"),
                    str(ASSETS / "core/oc-hash.c"),
                    str(ASSETS / "core/oc-manifest.c"),
                    "-o",
                    str(exe),
                ],
                check=True,
                timeout=20,
            )
            inp = d / "in.txt"
            out = d / "out.txt"
            inp.write_text("hello\n")
            for mode in ("pfd01", "devnull0", "pfd02", "swap01"):
                with self.subTest(mode=mode):
                    r = subprocess.run([str(exe), mode, str(inp), str(out)], timeout=10)
                    self.assertEqual(r.returncode, 0)
            self.assertEqual(out.read_text(), "hello\n")
