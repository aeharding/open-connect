"""Exercise native cold USB install, composition, upgrade, and --boot-recover under ASan+UBSan."""

import fcntl
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.host_bins import (
    copy_host_api,
    copy_host_boot_select,
    copy_host_flush,
    copy_host_ignition,
    copy_host_install,
)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
BOOT = "12345678-1234-1234-1234-123456789abc"
TOKEN = "a" * 32


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class NativeInstall(unittest.TestCase):
    """End-to-end ASan+UBSan tests for native install.c, oc-compose.c, oc-render.c, and oc_boot_recover."""

    def _build_fixture(self, root: Path):
        ram = root / "tmp/open-connect"
        usb_sess = ram / "sessions/session-usb100"
        data_parent = root / "tmp/mnt/data_persist"
        data = data_parent / "open-connect"
        for d in (
            ram,
            usb_sess,
            data_parent,
            root / "proc/self",
            root / "proc/sys/kernel/random",
            root / "sys/class/gpio/ACC_Sense",
            root / "sys/class/nvram/nv-config/keys",
            root / "dev",
            root / "usr/bin",
            root / "usr/sbin",
            root / "etc/ssh",
            root / "jci/sm",
            root / "jci/scripts",
            root / "jci/mmui/uia",
            root / "jci/gui/apps/system/js",
            root / "jci/gui/apps/syssettings/js",
            root / "jci/gui/framework/js",
            root / "jci/gui/common/js",
            root / "jci/lib",
            root / "jci/vbs/modules",
            root / "jci/devicemanager",
            root / "jci/lvds",
            root / "jci/vui/plugins",
            root / "jci/devices",
            root / "config/common/log",
        ):
            d.mkdir(parents=True, exist_ok=True)
        for d in (ram, ram / "sessions", usb_sess):
            d.chmod(0o700)
        (root / "dev/urandom").write_bytes(os.urandom(8192))
        (root / "proc/uptime").write_text("120.50 10.00\n")
        (root / "proc/sys/kernel/random/boot_id").write_text(BOOT + "\n")
        (root / "proc/self/mounts").write_text(
            "rootfs / rootfs rw 0 0\n"
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
        )
        (root / "proc/mounts").symlink_to("self/mounts")
        (root / "sys/class/gpio/ACC_Sense/value").write_text("1\n")
        nv_dir = root / "sys/class/nvram/nv-config"
        for ctl in ("add", "remove", "commit"):
            (nv_dir / ctl).write_text("")
        (root / "jci/version.ini").write_text(
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
        )
        (ram / "lock").write_bytes(b"")
        (ram / "lock").chmod(0o600)
        (ram / "usb-runtime").symlink_to(usb_sess)

        # Synthetic stock firmware files matching every composition anchor & binary layout offset.
        autostart_bytes = (
            b"#!/bin/sh\n"
            b"if true; then\n"
            b"        echo $MESSAGE_NORMALMODE\n"
            b"                sleep 1\n"
            b"                $(/jci/scripts/get_board_type.sh)\n"
            b"fi\n"
        )
        from tests.test_installer_preferences import InstallerPreferences

        def stock_sm(wcp: bool) -> bytes:
            txt = (
                InstallerPreferences()
                .profile(wcp)
                .replace(
                    'name="jciMMUI" autorun="yes" reset_board="yes" path="/tmp/open-connect/feature/mmui.so"',
                    'name="jciMMUI" path="/jci/mmui/svcjcimmui.so" autorun="yes" reset_board="yes"',
                    1,
                )
            )
            inject = '  <service type="process" name="jciGUI" path="/jci/opera/opera_dir/userjs/opera" args="-u /jci/gui/index.html" autorun="yes"/>\n'
            return txt.replace("<services>\n", "<services>\n" + inject, 1).encode()

        sm_normal = stock_sm(False)
        sm_wcp = stock_sm(True)
        index_html = (
            b"<!DOCTYPE html>\n<html>\n<head>\n"
            b'  <script type="text/javascript" src="common/js/logDefaults.js"></script>\n'
            b"</head>\n<body>\n"
            b"  <!-- stock comment -->\n"
            b"  <script>\n"
            b"  var baseApp = new BaseApp(); // trailing\n"
            b"  framework.init();\n"
            b"  </script>\n"
            b"</body>\n</html>\n"
        )
        mmui_xml = (ROOT / "tests/fixtures/ui-profile.xml").read_bytes()
        vui_xml = b'<vui><PluginsFolder value="/jci/vui/plugins"/></vui>\n'
        uia_so = bytes(674047)
        mmui_so = bytes(20000)
        vui_so = bytearray(95537)
        vui_so[68196 : 68196 + 24] = b"/jci/vui/vui_config.xml\x00"
        vui_so_bytes = bytes(vui_so)
        vui_path_blob = b"/tmp/open-connect/v.xml\x00"
        vui_expected = bytearray(vui_so_bytes)
        vui_expected[68196 : 68196 + 24] = vui_path_blob

        stock_files = {
            "originals/autostart": ("usr/bin/autostart", autostart_bytes, 0o755),
            "root/sm.conf": ("jci/sm/sm.conf", sm_normal, 0o644),
            "root/sm_WCP.conf": ("jci/sm/sm_WCP.conf", sm_wcp, 0o644),
            "root/board.sh": ("jci/scripts/get_board_type.sh", b"#!/bin/sh\nexit 1\n", 0o755),
            "root/mmui.so": ("jci/mmui/svcjcimmui.so", mmui_so, 0o755),
            "root/mmui.xml": ("jci/mmui/mmui_config.xml", mmui_xml, 0o644),
            "root/uia.so": ("jci/mmui/uia/libjciuiasystem.so", uia_so, 0o755),
            "root/index.html": ("jci/gui/index.html", index_html, 0o644),
            "root/system-app.js": ("jci/gui/apps/system/js/systemApp.js", b"// sys\n", 0o644),
            "root/settings-app.js": (
                "jci/gui/apps/syssettings/js/syssettingsApp.js",
                b"// set\n",
                0o644,
            ),
            "root/base-app.js": ("jci/gui/framework/js/BaseApp.js", b"// base\n", 0o644),
            "root/manager.so": ("jci/lib/libjciuiamgr.so", b"stock manager\n", 0o755),
            "root/device-master.xml": ("etc/devmgr_config_master.xml", b"<dm/>\n", 0o644),
            "root/eem.so": ("jci/vbs/modules/libjcimod_eem.so", b"eem\n", 0o755),
            "root/device-manager.so": (
                "jci/devicemanager/libdevicemanager.so",
                b"devmgr\n",
                0o755,
            ),
            "root/rungetty": ("usr/bin/rungetty", b"rungetty\n", 0o755),
            "root/sshd": ("usr/sbin/sshd", b"sshd\n", 0o755),
            "root/ssh-keygen": ("usr/bin/ssh-keygen", b"ssh-keygen\n", 0o755),
            "root/framework.js": ("jci/gui/framework/js/GuiFramework.js", b"// fw\n", 0o644),
            "root/lvds-service": ("jci/lvds/lvds_service", b"lvds\n", 0o755),
            "root/runlogin": ("usr/bin/runlogin", b"stock runlogin\n", 0o755),
            "base/settings.txt": (
                "config/common/log/settings.txt",
                b"COMMON_LOG_LEVEL=Info\n",
                0o644,
            ),
            "base/libjcicommon.so": ("jci/lib/libjcicommon.so", b"libjcicommon\n", 0o755),
            "base/log-defaults.js": ("jci/gui/common/js/logDefaults.js", b"// log\n", 0o644),
            "base/vui/vui.so": ("jci/vui/svcjcivui.so", vui_so_bytes, 0o755),
            "base/vui/vui.xml": ("jci/vui/vui_config.xml", vui_xml, 0o644),
            "touch/devices/svc": (
                "jci/devices/svc-com-jci-cpp-devices.so",
                b"devices svc\n",
                0o755,
            ),
            "touch/devices/lib": ("jci/lib/libjcidevices.so", b"devices lib\n", 0o755),
        }
        pin_lines = []
        for pin_key, (rel, content, mode) in stock_files.items():
            p = root / rel
            p.write_bytes(content)
            p.chmod(mode)
            pin_lines.append(f"{pin_key}={sha(content)}\n")
        (root / "etc/passwd").write_text("cmu:x:0:0:CMU:/home/cmu:/bin/sh\n")
        (root / "etc/passwd").chmod(0o644)
        (root / "etc/ssh/sshd_config").write_text(
            "Port 36000\n"
            "AuthorizedKeysFile /config-mfg/authorized_keys /owner/keys.%u\n"
            "PasswordAuthentication no\n"
        )
        (root / "etc/ssh/sshd_config").chmod(0o644)
        mgr_sha = sha(b"stock manager\n")
        pin_lines.append(f"originals/mmui.xml={sha(mmui_xml)}\n")
        pin_lines.append(f"manager.so={mgr_sha}\n")
        pin_lines.append(f"composed/vui.so={sha(bytes(vui_expected))}\n")
        pins_file = root / "pins.txt"
        pins_file.write_text("".join(pin_lines))

        # Populate USB session directory with real host-compiled binaries + real static files + synthetic blobs.
        for name in (
            "run.sh",
            "session.sh",
            "service.sh",
            "usb-service.sh",
            "loader.js",
            "runtime.js",
            "maintenance.js",
            "dialog.js",
            "settings.js",
            "carplay.js",
            "console.sh",
            "startup-hook.sh",
            "startup-join.sh",
            "system-hook.js",
            "base-logging.js",
            "defer-gap2.sh",
            "defer-nav.sh",
            "ui-profile.awk",
            "ui-modules.tsv",
            "wireless.sh",
            "wireless-device.awk",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "VERSION",
            "KENATIA-LICENSE",
        ):
            shutil.copyfile(ASSETS / name, usb_sess / name)
            (usb_sess / name).chmod(0o600)
        copy_host_api(usb_sess / "api")
        copy_host_install(usb_sess / "install")
        copy_host_flush(usb_sess / "flush")
        copy_host_boot_select(usb_sess / "boot-select")
        copy_host_ignition(usb_sess / "ignition")
        (usb_sess / "touch-disable.so").write_bytes(b"touch-shim\n")
        (usb_sess / "touch-disable.so").chmod(0o600)
        (usb_sess / "native.bin").write_bytes(b"\x01\x02\x03\x04" * 16)
        (usb_sess / "branch.bin").write_bytes(b"\xeb\x00\x00\x00")
        (usb_sess / "sizes.bin").write_bytes(struct.pack("<II", 0x6F79C + 64, 0x6F79C + 64))
        (usb_sess / "layout.bin").write_bytes(struct.pack("<II", 0x11223344, 0x55667788))
        (usb_sess / "layout.txt").write_text("40 0\n44 4\n")
        (usb_sess / "vui-path.bin").write_bytes(vui_path_blob)
        (usb_sess / "mmui-path.bin").write_bytes(b"/tmp/open-connect/feature/mmui.xml\x00")
        (usb_sess / "mmui-sizes.bin").write_bytes(struct.pack("<II", 15847, 15847))
        (usb_sess / "mmui-length.bin").write_bytes(struct.pack("<I", 0xE3A02023))
        (usb_sess / "mmui-pointer.bin").write_bytes(struct.pack("<I", 0x00001400))
        (usb_sess / "mmui-count-pointer.bin").write_bytes(struct.pack("<I", 0x000021F8))
        for p in usb_sess.iterdir():
            if p.name not in ("api", "install", "flush", "boot-select", "ignition"):
                p.chmod(0o600)
        mf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_sess.iterdir()))
        (usb_sess / "files.sha256").write_text(mf)
        (usb_sess / "files.sha256").chmod(0o600)
        (usb_sess / "token").write_text(TOKEN + "\n")
        (usb_sess / "token").chmod(0o600)

        fake_sshd = root / "fake-sshd"
        fake_sshd.write_text("#!/bin/sh\nexit 0\n")
        fake_sshd.chmod(0o700)
        env = {
            **os.environ,
            "OC_HOST_ROOT": str(root),
            "OC_HOST_NONROOT": "1",
            "OC_HOST_PINS": str(pins_file),
            "OC_HOST_SSHD": str(fake_sshd),
            "OC_HOST_WIRELESS_FILE": str(root / "no-wireless"),
        }
        return ram, data, usb_sess, env

    def _call_api(
        self, api_bin: Path, sess: Path, rev: str, op: str, arg="-", exp="-", des="-", *, env
    ):
        (Path(env["OC_HOST_ROOT"]) / "dev/urandom").write_bytes(os.urandom(8192))
        proc = subprocess.run(
            [str(api_bin), "--handle", str(sess), rev, op, arg, exp, des],
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        return proc, json.loads(proc.stdout)

    def test_fresh_usb_install_upgrade_and_gc_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"

            # 1) Fresh cold USB install via native api -> install binary.
            proc, res = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(proc.returncode, 0, (res, proc.stderr))
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["installed"])
            self.assertEqual(res["notice"], "installed")
            self.assertEqual(res["touch"], 1)
            self.assertEqual(res["warning"], 1)
            self.assertEqual(res["base"], 0)
            self.assertEqual(res["carplayAutoshow"], 0)

            rec = (data / "record").read_text().strip().split("|")
            self.assertEqual(rec[1], "active")
            self.assertEqual(rec[9], "3")
            self.assertEqual(rec[12], "installed")
            pkg1 = rec[3]
            snap1 = rec[5]

            # Verify composed outputs: uia.so (+32768 gap + layout patches), mmui.so, vui.so, autostart, index, sm.conf.
            comp1 = data / "composed" / pkg1
            uia_out = (comp1 / "uia.so").read_bytes()
            self.assertEqual(len(uia_out), 674047 + 32768)
            self.assertEqual(uia_out[456604 : 456604 + 64], b"\x01\x02\x03\x04" * 16)
            self.assertEqual(uia_out[49076 : 49076 + 4], b"\xeb\x00\x00\x00")
            self.assertEqual(struct.unpack_from("<II", uia_out, 40), (0x11223344, 0x55667788))
            mmui_out = (comp1 / "mmui.so").read_bytes()
            self.assertEqual(
                mmui_out[15812 : 15812 + 35], b"/tmp/open-connect/feature/mmui.xml\x00"
            )
            vui_out = (comp1 / "vui.so").read_bytes()
            self.assertEqual(vui_out[68196 : 68196 + 24], b"/tmp/open-connect/v.xml\x00")
            self.assertIn("open-connect-boot-select", (root / "usr/bin/autostart").read_text())
            self.assertTrue((root / "usr/bin/open-connect-boot-select").is_file())
            self.assertEqual(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").read_text(),
                "disable\n",
            )
            self.assertTrue((data / "snapshots" / snap1 / "boot.plan").is_file())
            self.assertTrue((usb_sess / "admitted").is_symlink())
            self.assertEqual(list(data.glob(".open-connect-initial-*")), [])

            # 2) Boot once via real native boot-select so Settings session can toggle preferences.
            bs_res = subprocess.run(
                [str(root / "usr/bin/open-connect-boot-select"), "select", str(root)],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(bs_res.returncode, 0, bs_res.stderr)
            self.assertEqual((ram / "selected").read_text().strip(), snap1)

            # Mount a pinned Settings session for pkg1 and toggle touch=0 & carplay-autoshow=1.
            set_sess = ram / "sessions/session-set100"
            set_sess.mkdir(mode=0o700)
            for nm in ("files.sha256", "api", "VERSION"):
                shutil.copyfile(data / "packages" / pkg1 / nm, set_sess / nm)
                (set_sess / nm).chmod(0o700 if nm == "api" else 0o600)
            (ram / "runtime").symlink_to(set_sess)

            p_t0, r_t0 = self._call_api(api_bin, set_sess, snap1, "set", "touch", "1", "0", env=env)
            self.assertEqual(p_t0.returncode, 0, (r_t0, p_t0.stderr))
            self.assertEqual(r_t0["sourceOrder"], 0)
            self.assertEqual(r_t0["sourceOrderCurrent"], 0)
            self.assertEqual(r_t0["menuLoop"], 0)
            self.assertEqual(r_t0["menuLoopCurrent"], 0)
            self.assertEqual(r_t0["holdScroll"], 0)
            self.assertEqual(r_t0["holdScrollCurrent"], 0)
            self.assertNotIn(
                "reorderSources", (data / "snapshots" / snap1 / "index.html").read_text()
            )
            self.assertNotIn("installNav", (data / "snapshots" / snap1 / "index.html").read_text())
            p_as, r_as = self._call_api(
                api_bin, set_sess, r_t0["revision"], "set", "carplay-autoshow", "0", "1", env=env
            )
            self.assertEqual(p_as.returncode, 0, (r_as, p_as.stderr))
            no_awk_env = dict(env, OC_HOST_AWK="/nonexistent/awk")
            p_so, r_so = self._call_api(
                api_bin,
                set_sess,
                r_as["revision"],
                "set",
                "source-order",
                "0",
                "1",
                env=no_awk_env,
            )
            self.assertEqual(p_so.returncode, 0, (r_so, p_so.stderr))
            self.assertEqual(r_so["sourceOrder"], 1)
            self.assertEqual(r_so["sourceOrderCurrent"], 0)
            self.assertTrue(r_so["restart"])
            p_ml, r_ml = self._call_api(
                api_bin,
                set_sess,
                r_so["revision"],
                "set",
                "menu-loop",
                "0",
                "1",
                env=no_awk_env,
            )
            self.assertEqual(p_ml.returncode, 0, (r_ml, p_ml.stderr))
            self.assertEqual(r_ml["menuLoop"], 1)
            self.assertEqual(r_ml["menuLoopCurrent"], 0)
            self.assertTrue(r_ml["restart"])
            p_hs, r_hs = self._call_api(
                api_bin,
                set_sess,
                r_ml["revision"],
                "set",
                "hold-scroll",
                "0",
                "1",
                env=no_awk_env,
            )
            self.assertEqual(p_hs.returncode, 0, (r_hs, p_hs.stderr))
            self.assertEqual(r_hs["holdScroll"], 1)
            self.assertEqual(r_hs["holdScrollCurrent"], 0)
            self.assertTrue(r_hs["restart"])
            snap_mod = r_hs["revision"]
            snap_idx = (data / "snapshots" / snap_mod / "index.html").read_text()
            self.assertIn("reorderSources", snap_idx)
            self.assertIn("installNav", snap_idx)
            self.assertIn(",1,1,1]));", snap_idx)

            # 3) Upgrade from active via a second USB session (different VERSION) -> preserves touch=0, carplay-autoshow=1, source-order=1, menu-loop=1 & hold-scroll=1!
            usb2 = ram / "sessions/session-usb200"
            shutil.copytree(
                usb_sess, usb2, symlinks=False, ignore=shutil.ignore_patterns("admitted")
            )
            usb2.chmod(0o700)
            (usb2 / "VERSION").write_text("0.4.0-upgrade\n")
            (usb2 / "files.sha256").unlink()
            (usb2 / "token").unlink()
            mf2 = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb2.iterdir()))
            (usb2 / "files.sha256").write_text(mf2)
            (usb2 / "files.sha256").chmod(0o600)
            (usb2 / "token").write_text(TOKEN + "\n")
            (usb2 / "token").chmod(0o600)
            (ram / "usb-runtime").unlink()
            (ram / "usb-runtime").symlink_to(usb2)

            p_up, r_up = self._call_api(usb2 / "api", usb2, snap_mod, "install", env=env)
            self.assertEqual(p_up.returncode, 0, (r_up, p_up.stderr))
            self.assertTrue(r_up["ok"], r_up)
            self.assertEqual(r_up["touch"], 0)
            self.assertEqual(r_up["carplayAutoshow"], 1)
            self.assertEqual(r_up["sourceOrder"], 1)
            self.assertEqual(r_up["menuLoop"], 1)
            self.assertEqual(r_up["holdScroll"], 1)
            rec_up = (data / "record").read_text().strip().split("|")
            self.assertNotEqual(rec_up[3], pkg1)
            self.assertEqual(rec_up[1], "active")
            self.assertFalse(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            )

    def test_fresh_install_fail_closed_and_cleans_initial_staging_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"

            # Tampered stock dependency -> unsupported_original & no leftover data or .open-connect-initial-*
            mgr = root / "jci/lib/libjciuiamgr.so"
            orig_mgr = mgr.read_bytes()
            mgr.write_bytes(b"corrupted manager\n")
            proc, err = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(err["error"], "unsupported_original")
            self.assertFalse(data.exists())
            self.assertEqual(list(data.parent.glob(".open-connect-initial-*")), [])
            mgr.write_bytes(orig_mgr)

            # Tampered install binary in USB session -> incomplete_maintenance_bundle
            orig_inst = (usb_sess / "install").read_bytes()
            (usb_sess / "install").write_bytes(b"corrupt")
            (usb_sess / "install").chmod(0o700)
            proc2, err2 = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertNotEqual(proc2.returncode, 0)
            self.assertEqual(err2["error"], "incomplete_maintenance_bundle")
            (usb_sess / "install").write_bytes(orig_inst)
            (usb_sess / "install").chmod(0o700)

    def test_boot_recover_reconciles_pending_nvram_budget_reseal_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"
            bs_bin = root / "usr/bin/open-connect-boot-select"

            # Fresh install first so we have a real valid state directory & package.
            proc, res = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(proc.returncode, 0, (res, proc.stderr))
            rec = (data / "record").read_text().strip().split("|")
            pkg_id, base_id = rec[3], rec[4]
            pkg_dir = data / "packages" / pkg_id
            rec_exec = ram / ".recover-test"
            rec_exec.mkdir(mode=0o700)
            inst_ram = rec_exec / "install"
            shutil.copyfile(pkg_dir / "install", inst_ram)
            inst_ram.chmod(0o700)

            def cold_ram():
                for child in ram.iterdir():
                    if child.name in ("lock", ".recover-test"):
                        continue
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()

            # 1) budget==0 with touch=1 (nvram=disable): boot-select returns 95,
            #    install --boot-recover reverts NVRAM to base (absent), then boot-select exits 2 (stock)!
            cold_ram()
            rec[9] = "0"
            (data / "record").write_text("|".join(rec) + "\n")
            bs0 = subprocess.run([str(bs_bin), "select", str(root)], env=env, capture_output=True)
            self.assertEqual(bs0.returncode, 95)
            br0 = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_dir), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(br0.returncode, 0, br0.stdout + br0.stderr)
            self.assertFalse(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            )
            bs_stock = subprocess.run(
                [str(bs_bin), "select", str(root)], env=env, capture_output=True
            )
            self.assertEqual(bs_stock.returncode, 2, bs_stock.stderr)

            # 2) Post-ACC-off replenishment (rec[10] != boot & ACC_Sense=1): budget replenishes to 3,
            #    touch=1 needs nvram=disable again -> boot-select returns 95 -> install --boot-recover
            #    re-applies NVRAM=disable -> boot-select exits 0!
            rec2 = (data / "record").read_text().strip().split("|")
            rec2[10] = rec2[11]  # mark previous boot as clean ACC-off
            (data / "record").write_text("|".join(rec2) + "\n")
            cold_ram()
            bs1 = subprocess.run([str(bs_bin), "select", str(root)], env=env, capture_output=True)
            self.assertEqual(bs1.returncode, 95)
            br1 = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_dir), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(br1.returncode, 0, br1.stdout + br1.stderr)
            self.assertEqual(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").read_text(),
                "disable\n",
            )
            bs_ok = subprocess.run([str(bs_bin), "select", str(root)], env=env, capture_output=True)
            self.assertEqual(bs_ok.returncode, 0, bs_ok.stderr)

            # 3) D/reseal hint -> recheck + reseal + unlink D/reseal -> boot-select exits 0!
            rec3 = (data / "record").read_text().strip().split("|")
            cold_ram()
            (data / "reseal").write_text(rec3[5] + "\n")
            (data / "reseal").chmod(0o600)
            br2 = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_dir), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(br2.returncode, 0, br2.stdout + br2.stderr)
            self.assertFalse((data / "reseal").exists())
            bs_ok2 = subprocess.run(
                [str(bs_bin), "select", str(root)], env=env, capture_output=True
            )
            self.assertEqual(bs_ok2.returncode, 0, bs_ok2.stderr)

            # 4) Tampered D/reseal (bad mode) -> fails closed!
            cold_ram()
            (data / "reseal").write_text(rec3[5] + "\n")
            (data / "reseal").chmod(0o644)
            br_bad = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_dir), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(br_bad.returncode, 0)
            (data / "reseal").unlink()

            # 5) Pending uninstall -> install --boot-recover reconciles, restores stock autostart,
            #    removes open-connect-boot-select & data dir, returns 1 so startup-hook boots stock!
            rec4 = (data / "record").read_text().strip().split("|")
            rec4[1] = "uninstall"
            rec4[6] = rec4[5]
            rec4[7] = base_id
            (data / "record").write_text("|".join(rec4) + "\n")
            br_un = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_dir), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(br_un.returncode, 0)
            self.assertFalse(data.exists())
            self.assertFalse(bs_bin.exists())
            self.assertNotIn("open-connect-boot-select", (root / "usr/bin/autostart").read_text())
            self.assertFalse(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            )

    def test_r1_regressions_purge_recover_dvd_upgrade_touch2_drift_fence_and_reinstall(self):
        """Cover PR #222 R1 findings: H1 (purge/empty D recover w/ live Settings), M1 (retired dvd
        catalog upgrade), M2 (unpinned legacy backend.sh fence), M3 (Step-3 rotated reseal cleanup
        & OCBP1 header check), M4 (touch=2 drift pre-prepare refusal), and reinstall from removed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"
            bs_bin = root / "usr/bin/open-connect-boot-select"

            # Fresh install + boot once so Settings session is live.
            proc, res = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(proc.returncode, 0, (res, proc.stderr))
            rec = (data / "record").read_text().strip().split("|")
            pkg1, base_id, snap1 = rec[3], rec[4], rec[5]
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "select", str(root)], env=env, capture_output=True
                ).returncode,
                0,
            )
            set_sess = ram / "sessions/session-setr1"
            set_sess.mkdir(mode=0o700)
            for nm in ("files.sha256", "api", "VERSION"):
                shutil.copyfile(data / "packages" / pkg1 / nm, set_sess / nm)
                (set_sess / nm).chmod(0o700 if nm == "api" else 0o600)
            (ram / "runtime").symlink_to(set_sess)

            # (M4) Switch to touch=2, drift touch pin -> USB upgrade must fail pre-prepare with touch_inputs_changed!
            p_t2, r_t2 = self._call_api(api_bin, set_sess, snap1, "set", "touch", "1", "2", env=env)
            self.assertEqual(p_t2.returncode, 0, (r_t2, p_t2.stderr))
            t2_snap = r_t2["revision"]
            dev_svc = root / "jci/devices/svc-com-jci-cpp-devices.so"
            orig_dev = dev_svc.read_bytes()
            dev_svc.write_bytes(b"drifted devices svc\n")
            before_rec = (data / "record").read_bytes()
            p_dr, r_dr = self._call_api(api_bin, usb_sess, t2_snap, "install", env=env)
            self.assertNotEqual(p_dr.returncode, 0)
            self.assertEqual(r_dr["error"], "touch_inputs_changed")
            self.assertEqual((data / "record").read_bytes(), before_rec)
            dev_svc.write_bytes(orig_dev)
            # Switch back to touch=1 for subsequent tests.
            p_t1, r_t1 = self._call_api(
                api_bin, set_sess, t2_snap, "set", "touch", "2", "1", env=env
            )
            self.assertEqual(p_t1.returncode, 0, (r_t1, p_t1.stderr))
            cur_snap = r_t1["revision"]

            # (M1) Upgrade from active snapshot containing retired service.dvd=0 succeeds and drops dvd.
            dvd_work = data / "snapshots/.new-dvd"
            shutil.copytree(data / "snapshots" / cur_snap, dvd_work)
            dvd_work.chmod(0o700)
            dvd_cfg = (
                (dvd_work / "config")
                .read_text()
                .replace(
                    "service-ids=android-auto,pandora,siriusxm\n",
                    "service-ids=android-auto,dvd,pandora,siriusxm\n",
                )
                .replace(
                    "service.pandora=1\n",
                    "service.dvd=0\nservice.pandora=0\n",
                )
            )
            (dvd_work / "config").write_text(dvd_cfg)
            (dvd_work / "config").chmod(0o600)
            (dvd_work / "files.sha256").unlink()
            (dvd_work / "boot.plan").unlink(missing_ok=True)
            dvd_mf = "".join(
                f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(dvd_work.iterdir())
            )
            (dvd_work / "files.sha256").write_text(dvd_mf)
            (dvd_work / "files.sha256").chmod(0o600)
            dvd_snap = sha(dvd_mf.encode())
            dvd_work.rename(data / "snapshots" / dvd_snap)
            dvd_rec = (data / "record").read_text().strip().split("|")
            dvd_rec[5] = dvd_snap
            (data / "record").write_text("|".join(dvd_rec) + "\n")

            p_dvd, r_dvd = self._call_api(api_bin, usb_sess, dvd_snap, "install", env=env)
            self.assertEqual(p_dvd.returncode, 0, (r_dvd, p_dvd.stderr))
            self.assertTrue(r_dvd["ok"], r_dvd)
            self.assertEqual(r_dvd["pandora"], 0)
            new_rec = (data / "record").read_text().strip().split("|")
            new_cfg_txt = (data / "snapshots" / new_rec[5] / "config").read_text()
            self.assertNotIn("service.dvd=", new_cfg_txt)
            self.assertIn("service.pandora=0\n", new_cfg_txt)

            # (M2) Unpinned (or substring-spoofed) legacy backend.sh is refused by oc_usb_fence(),
            # while a genuine whole-line pinned backend.sh passes oc_usb_fence().
            def make_legacy_pkg_snap(tag: str, backend_text: str):
                lp_w = data / f"packages/.leg-{tag}"
                shutil.copytree(data / "packages" / new_rec[3], lp_w)
                lp_w.chmod(0o700)
                (lp_w / "backend.sh").write_text(backend_text)
                (lp_w / "backend.sh").chmod(0o600)
                (lp_w / "files.sha256").unlink()
                lmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(lp_w.iterdir()))
                (lp_w / "files.sha256").write_text(lmf)
                (lp_w / "files.sha256").chmod(0o600)
                lp_id = sha(lmf.encode())
                lp_w.rename(data / "packages" / lp_id)
                ls_w = data / f"snapshots/.legsnap-{tag}"
                shutil.copytree(data / "snapshots" / new_rec[5], ls_w)
                ls_w.chmod(0o700)
                lcfg = new_cfg_txt.replace(f"package={new_rec[3]}\n", f"package={lp_id}\n", 1)
                (ls_w / "config").write_text(lcfg)
                (ls_w / "config").chmod(0o600)
                (ls_w / "files.sha256").unlink()
                (ls_w / "boot.plan").unlink(missing_ok=True)
                lsmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(ls_w.iterdir()))
                (ls_w / "files.sha256").write_text(lsmf)
                (ls_w / "files.sha256").chmod(0o600)
                ls_id = sha(lsmf.encode())
                ls_w.rename(data / "snapshots" / ls_id)
                return lp_id, ls_id

            saved_sel = (ram / "selected").read_bytes()
            for tag, body in (
                ("unpinned", "#!/bin/sh\n# unpinned legacy dev.22\n"),
                ("substring", "#!/bin/sh\n# spoof # Open Connect pinned Settings 1\n"),
                ("suffix", "#!/bin/sh\n# Open Connect pinned Settings 10\n"),
            ):
                lp_id, ls_id = make_legacy_pkg_snap(tag, body)
                (ram / "selected").write_text(ls_id + "\n")
                shutil.copyfile(
                    data / "packages" / lp_id / "files.sha256", set_sess / "files.sha256"
                )
                shutil.copyfile(data / "packages" / lp_id / "backend.sh", set_sess / "backend.sh")
                p_unp, r_unp = self._call_api(api_bin, usb_sess, new_rec[5], "recover", env=env)
                self.assertNotEqual(p_unp.returncode, 0, tag)
                self.assertEqual(r_unp["error"], "invalid_legacy_runtime", tag)
            lp_pin, ls_pin = make_legacy_pkg_snap(
                "pinned", "#!/bin/sh\n# Open Connect pinned Settings 1\n"
            )
            (ram / "selected").write_text(ls_pin + "\n")
            shutil.copyfile(data / "packages" / lp_pin / "files.sha256", set_sess / "files.sha256")
            shutil.copyfile(data / "packages" / lp_pin / "backend.sh", set_sess / "backend.sh")
            p_pin, r_pin = self._call_api(api_bin, usb_sess, new_rec[5], "recover", env=env)
            self.assertEqual(p_pin.returncode, 0, (r_pin, p_pin.stderr))
            self.assertTrue(r_pin["ok"], r_pin)
            (set_sess / "backend.sh").unlink()
            shutil.copyfile(data / "packages" / pkg1 / "files.sha256", set_sess / "files.sha256")
            (ram / "selected").write_bytes(saved_sel)

            # (M3) oc_boot_recover unlinks D/reseal even if Step 3 NVRAM apply rotates rec[5].
            pkg_now = data / "packages" / new_rec[3]
            rec_exec = ram / ".recover-r1"
            rec_exec.mkdir(mode=0o700)
            inst_ram = rec_exec / "install"
            shutil.copyfile(pkg_now / "install", inst_ram)
            inst_ram.chmod(0o700)
            for child in list(ram.iterdir()):
                if child.name not in ("lock", ".recover-r1", "sessions", "usb-runtime"):
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            m3_rec = list(new_rec)
            m3_rec[9] = "0"
            (data / "record").write_text("|".join(m3_rec) + "\n")
            (data / "reseal").write_text(m3_rec[5] + "\n")
            (data / "reseal").chmod(0o600)
            br_m3 = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_now), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(br_m3.returncode, 0, br_m3.stdout + br_m3.stderr)
            self.assertFalse((data / "reseal").exists())

            # (M3b) Wrong OCBP1 header in a hash-valid snapshot with matching D/reseal must be
            # refused at Step 4 (after Step 2 passes and writes ram/boot-id)!
            m3b_rec_raw = (data / "record").read_text()
            m3b_rec = m3b_rec_raw.strip().split("|")
            bad_bp_w = data / "snapshots/.badbp"
            shutil.copytree(data / "snapshots" / m3b_rec[5], bad_bp_w)
            bad_bp_w.chmod(0o700)
            orig_bp = (bad_bp_w / "boot.plan").read_bytes()
            (bad_bp_w / "boot.plan").write_bytes(orig_bp.replace(m3b_rec[4].encode(), b"f" * 64, 1))
            (bad_bp_w / "boot.plan").chmod(0o600)
            (bad_bp_w / "files.sha256").unlink()
            bad_mf = "".join(
                f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(bad_bp_w.iterdir())
            )
            (bad_bp_w / "files.sha256").write_text(bad_mf)
            (bad_bp_w / "files.sha256").chmod(0o600)
            bad_bp_id = sha(bad_mf.encode())
            bad_bp_w.rename(data / "snapshots" / bad_bp_id)
            m3b_mut = list(m3b_rec)
            m3b_mut[5] = bad_bp_id
            (data / "record").write_text("|".join(m3b_mut) + "\n")
            (data / "reseal").write_text(bad_bp_id + "\n")
            (data / "reseal").chmod(0o600)
            for child in list(ram.iterdir()):
                if child.name not in ("lock", ".recover-r1", "sessions", "usb-runtime"):
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            br_m3b = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_now), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(br_m3b.returncode, 0)
            self.assertTrue((ram / "boot-id").is_symlink())
            self.assertTrue((data / "reseal").exists())
            (data / "record").write_text(m3b_rec_raw)
            shutil.rmtree(data / "snapshots" / bad_bp_id)
            (data / "reseal").unlink()

            # (H2) Verify oc_handle_completion shell invocation passes non-empty cur_boot via B=$2.
            h2_boot = "12345678-1234-1234-1234-123456789abc"
            h2_cmd = (
                'P=$1; B=$2; . "$P/service.sh"; current_boot_id() { printf "%s\\n" "$B"; }; '
                "current_boot_id"
            )
            h2_out = subprocess.check_output(
                ["sh", "-c", h2_cmd, "observe", str(usb_sess), h2_boot], text=True, timeout=5
            )
            self.assertEqual(h2_out, h2_boot + "\n")

            # (L6) Reinstall from phase=removed succeeds cleanly.
            rec_un = (data / "record").read_text().strip().split("|")
            # Restore stock autostart/removed state by uninstalling cleanly first, then simulate phase=removed.
            (ram / "runtime").symlink_to(set_sess)
            (ram / "selected").write_bytes(saved_sel)
            # Re-enable live Settings runtime pointing to current pkg for uninstall fence check.
            shutil.copyfile(pkg_now / "files.sha256", set_sess / "files.sha256")
            shutil.copyfile(pkg_now / "api", set_sess / "api")
            (set_sess / "api").chmod(0o700)
            (ram / "selected").write_text(rec_un[5] + "\n")
            # Run uninstall via api -> completes and removes data.
            p_un, r_un = self._call_api(api_bin, usb_sess, rec_un[5], "uninstall", env=env)
            self.assertEqual(p_un.returncode, 0, (r_un, p_un.stderr))
            self.assertFalse(data.exists())

            # (H1) Interrupted uninstall_cleanup: phase=purge (no snapshots/packages) AND empty D
            # both recover cleanly via USB even when Settings R/runtime is still live!
            for mode in ("purge", "empty"):
                with self.subTest(h1_mode=mode):
                    data.mkdir(mode=0o700, exist_ok=True)
                    if mode == "purge":
                        nonce = "9" * 32
                        (data / "record").write_text(
                            f"OC1|purge|{nonce}|{pkg1}|{base_id}|{base_id}|-|-|-|0|-|-|removed\n"
                        )
                        (data / "record").chmod(0o600)
                        rev_arg = nonce
                    else:
                        rev_arg = "-"
                    p_rec, r_rec = self._call_api(api_bin, usb_sess, rev_arg, "recover", env=env)
                    self.assertEqual(p_rec.returncode, 0, (mode, r_rec, p_rec.stderr))
                    self.assertTrue(r_rec["ok"], r_rec)
                    self.assertFalse(data.exists())

            # (L6) Fresh install followed by simulated phase=removed -> reinstall succeeds!
            (ram / "runtime").unlink()
            (ram / "selected").unlink()
            p_i1, r_i1 = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(p_i1.returncode, 0, (r_i1, p_i1.stderr))
            rec_i1 = (data / "record").read_text().strip().split("|")
            # Reconcile pending uninstall to reach settled phase=removed, then reinstall from removed!
            rec_rem = list(rec_i1)
            rec_rem[1] = "uninstall"
            rec_rem[6] = rec_i1[5]
            rec_rem[7] = rec_i1[4]
            (data / "record").write_text("|".join(rec_rem) + "\n")
            # Directly invoke uninstall_reconcile by restoring stock targets via api recover (wait: recover purges removed),
            # so test settled phase=removed directly by restoring stock autostart/nvram/selector to match base!
            shutil.copyfile(data / "originals/autostart", root / "usr/bin/autostart")
            (root / "usr/bin/autostart").chmod(0o755)
            bs_bin.unlink()
            (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink(missing_ok=True)
            rec_rem[1] = "removed"
            rec_rem[5] = rec_i1[4]
            rec_rem[6] = "-"
            rec_rem[7] = "-"
            rec_rem[9] = "0"
            (data / "record").write_text("|".join(rec_rem) + "\n")
            p_re, r_re = self._call_api(api_bin, usb_sess, rec_i1[4], "install", env=env)
            self.assertEqual(p_re.returncode, 0, (r_re, p_re.stderr))
            self.assertTrue(r_re["ok"] and r_re["installed"], r_re)
            self.assertEqual((data / "record").read_text().strip().split("|")[1], "active")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen required")
    def test_upgrade_preserves_base_uart_ssh_and_imported_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            env = {**env, "OC_HOST_SSH_KEYGEN": shutil.which("ssh-keygen")}
            api_bin = usb_sess / "api"

            # Populate synthetic VUI plugins matching ui-modules.tsv so base=1 pins validate.
            vui_dir = root / "jci/vui/plugins"
            ui_lines = (usb_sess / "ui-modules.tsv").read_text().splitlines()
            patched_ui = []
            for ln in ui_lines:
                if ln.startswith("vui\t"):
                    parts = ln.split("\t")
                    blob = b"vui-plugin-" + parts[1].encode() + b"\n"
                    (vui_dir / parts[1]).write_bytes(blob)
                    (vui_dir / parts[1]).chmod(0o755)
                    parts[3] = sha(blob)
                    patched_ui.append("\t".join(parts))
                else:
                    patched_ui.append(ln)
            (usb_sess / "ui-modules.tsv").write_text("\n".join(patched_ui) + "\n")
            (usb_sess / "ui-modules.tsv").chmod(0o600)
            (usb_sess / "files.sha256").unlink()
            (usb_sess / "token").unlink()
            mf0 = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_sess.iterdir()))
            (usb_sess / "files.sha256").write_text(mf0)
            (usb_sess / "files.sha256").chmod(0o600)
            (usb_sess / "token").write_text(TOKEN + "\n")
            (usb_sess / "token").chmod(0o600)

            # Add a mounted vfat USB volume carrying a valid ECDSA public key.
            vol = root / "tmp/mnt/sda1"
            vol.mkdir(parents=True, mode=0o700)
            (root / "proc/self/mounts").write_text(
                (root / "proc/self/mounts").read_text() + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
            )
            key_path = root / "test_ecdsa"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ecdsa", "-b", "256", "-N", "", "-f", str(key_path)],
                check=True,
            )
            (vol / "open-connect.pub").write_bytes(key_path.with_suffix(".pub").read_bytes())

            # Fresh install, boot once so Settings session is active, then enable base=1,
            # import SSH key, enable uart=1 and ssh=1 via Settings session.
            p0, r0 = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(p0.returncode, 0, (r0, p0.stderr))
            rec0 = (data / "record").read_text().strip().split("|")
            bs_bin = root / "usr/bin/open-connect-boot-select"
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "select", str(root)], env=env, capture_output=True
                ).returncode,
                0,
            )
            set_sess = ram / "sessions/session-setkey"
            set_sess.mkdir(mode=0o700)
            for nm in ("files.sha256", "api", "console.sh", "VERSION"):
                shutil.copyfile(data / "packages" / rec0[3] / nm, set_sess / nm)
                (set_sess / nm).chmod(0o700 if nm == "api" else 0o600)
            (ram / "runtime").symlink_to(set_sess)

            rev = r0["revision"]
            p_b, r_b = self._call_api(api_bin, set_sess, rev, "set", "base", "0", "1", env=env)
            self.assertEqual(p_b.returncode, 0, (r_b, p_b.stderr))
            rev = r_b["revision"]
            p_k, r_k = self._call_api(api_bin, set_sess, rev, "import", env=env)
            self.assertEqual(p_k.returncode, 0, (r_k, p_k.stderr))
            rev = r_k["revision"]
            imported_key = r_k["key"]
            self.assertEqual(len(imported_key), 64)
            p_u, r_u = self._call_api(api_bin, set_sess, rev, "set", "uart", "0", "1", env=env)
            self.assertEqual(p_u.returncode, 0, (r_u, p_u.stderr))
            rev = r_u["revision"]
            p_s, r_s = self._call_api(api_bin, set_sess, rev, "set", "ssh", "0", "1", env=env)
            self.assertEqual(p_s.returncode, 0, (r_s, p_s.stderr))
            rev = r_s["revision"]
            self.assertEqual((r_s["base"], r_s["uart"], r_s["ssh"]), (1, 1, 1))

            # Upgrade to a fresh package revision and assert base=1, uart=1, ssh=1, and key survive.
            (usb_sess / "VERSION").write_text("0.3.0-dev.99\n")
            (usb_sess / "VERSION").chmod(0o600)
            for meta_nm in ("files.sha256", "token", "admitted", "closed"):
                (usb_sess / meta_nm).unlink(missing_ok=True)
            mf = "".join(
                f"{sha(p.read_bytes())}  {p.name}\n"
                for p in sorted(usb_sess.iterdir())
                if not p.is_symlink() and p.is_file()
            )
            (usb_sess / "files.sha256").write_text(mf)
            (usb_sess / "files.sha256").chmod(0o600)
            (usb_sess / "token").write_text(TOKEN + "\n")
            (usb_sess / "token").chmod(0o600)

            p_up, r_up = self._call_api(api_bin, usb_sess, rev, "install", env=env)
            self.assertEqual(p_up.returncode, 0, (r_up, p_up.stderr))
            self.assertTrue(r_up["ok"] and r_up["installed"], r_up)
            self.assertEqual((r_up["base"], r_up["uart"], r_up["ssh"]), (1, 1, 1))
            self.assertEqual(r_up["key"], imported_key)
            self.assertTrue((data / "keys" / f"{imported_key}.cmu").is_file())
            rec_up = (data / "record").read_text().strip().split("|")
            self.assertEqual(rec_up[1], "active")
            self.assertNotEqual(rec_up[3], rec0[3])

    def test_usb_failure_diagnostic_log_and_safety_guards(self):
        """Issue #220: sanitized USB diagnostic log on install/uninstall/recover failures & strict safety guards."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"

            # Add an extra non-allowlisted line in version.ini to verify strict allowlist filtering.
            # Add an unallowlisted line + realistic ~15 KiB padding (real v74 version.ini is
            # 14,625 B > 8 KiB oc_mscratch) to verify version_ini: is captured without secret leak.
            (root / "jci/version.ini").write_text(
                (root / "jci/version.ini").read_text()
                + "SECRET_OEM_LINE=DO_NOT_LOG\n"
                + ("# padding line to exceed 8 KiB scratch buffer on real v74 CMU\n" * 240)
            )

            # Mount a verified rw vfat USB volume + real Mazda /tmp/mnt/sd_nav (must NOT be logged).
            vol = root / "tmp/mnt/sda1"
            (vol / "open-connect").mkdir(parents=True)
            shutil.copyfile(usb_sess / "run.sh", vol / "open-connect/run.sh")
            shutil.copyfile(usb_sess / "files.sha256", vol / "open-connect/files.sha256")
            base_mounts = (
                root / "proc/self/mounts"
            ).read_text() + "/dev/mmcblk1p1 /tmp/mnt/sd_nav vfat ro,fmask=0022 0 0\n"
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat rw,fmask=0022 0 0\n"
            )
            log_file = vol / "open-connect-error.log"

            # 1) Cold USB install failure (tampered OEM file -> unsupported_original) writes detailed log
            #    after api releases LOCK_EX (via DIAG| stdout forwarding -> install --log-failure).
            idx = root / "jci/gui/index.html"
            orig_idx = idx.read_bytes()
            tampered_idx = b"tampered index\n"
            idx.write_bytes(tampered_idx)
            p_fail, r_fail = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertNotEqual(p_fail.returncode, 0)
            self.assertEqual(r_fail["error"], "unsupported_original")
            self.assertTrue(log_file.is_file())
            txt = log_file.read_text()
            self.assertLessEqual(len(txt.encode()), 4096)
            self.assertIn("operation=install\n", txt)
            self.assertIn("error=unsupported_original\n", txt)
            self.assertIn("step=stock_dependencies\n", txt)
            self.assertIn("path=/jci/gui/index.html\n", txt)
            self.assertIn("reason=sha256_mismatch\n", txt)
            self.assertIn(f"expected={sha(orig_idx)}\n", txt)
            self.assertIn(f"actual={sha(tampered_idx)}\n", txt)
            self.assertIn('JCI_SW_VER="MAZ_CMU-150_74.00.324"', txt)
            self.assertNotIn("SECRET_OEM_LINE", txt)
            self.assertNotIn("/tmp/mnt/sd_nav", txt)
            self.assertNotIn(TOKEN, txt)

            # 1b) Transient/lifecycle rejections (`busy` and `session_closed`) must NOT clobber
            #     an existing open-connect-error.log!
            sentinel_log = txt
            with (ram / "lock").open("r+b") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    p_busy, r_busy = self._call_api(api_bin, usb_sess, "-", "install", env=env)
                    self.assertNotEqual(p_busy.returncode, 0)
                    self.assertEqual(r_busy["error"], "busy")
                    self.assertEqual(log_file.read_text(), sentinel_log)
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            (usb_sess / "closed").write_text("1\n")
            (usb_sess / "closed").chmod(0o600)
            p_cl, r_cl = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertNotEqual(p_cl.returncode, 0)
            self.assertEqual(r_cl["error"], "session_closed")
            self.assertEqual(log_file.read_text(), sentinel_log)
            (usb_sess / "closed").unlink()

            idx.write_bytes(orig_idx)
            log_file.unlink()

            # 2) Pre-install api firmware_guard failure writes log + enforces <=4095 B & printable ASCII.
            orig_ver = (root / "jci/version.ini").read_text()
            (root / "jci/version.ini").write_text(
                'JCI_SW_VER="MAZ_CMU-150_70.00.100\x01\x7f' + ("X" * 5000) + '"\n'
            )
            p_fw, r_fw = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertNotEqual(p_fw.returncode, 0)
            self.assertEqual(r_fw["error"], "unsupported_firmware")
            raw_fw = log_file.read_bytes()
            self.assertLessEqual(len(raw_fw), 4095)
            self.assertTrue(all(b == 10 or (32 <= b < 127) for b in raw_fw))
            txt_fw = raw_fw.decode()
            self.assertIn("operation=install\n", txt_fw)
            self.assertIn("error=unsupported_firmware\n", txt_fw)
            self.assertIn("step=firmware_guard\n", txt_fw)
            self.assertIn("path=/jci/version.ini\n", txt_fw)
            self.assertIn("reason=version_mismatch\n", txt_fw)
            (root / "jci/version.ini").write_text(orig_ver)
            log_file.unlink()

            # 3) Clean install succeeds and writes NO error log; boot once so Settings session is ready.
            p_ok, r_ok = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(p_ok.returncode, 0, (r_ok, p_ok.stderr))
            self.assertFalse(log_file.exists())
            rec = (data / "record").read_text().strip().split("|")
            nonce_secret = rec[2]
            bs_bin = root / "usr/bin/open-connect-boot-select"
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "select", str(root)], env=env, capture_output=True
                ).returncode,
                0,
            )
            set_sess = ram / "sessions/session-setlog"
            set_sess.mkdir(mode=0o700)
            for nm in ("files.sha256", "api", "console.sh", "VERSION"):
                shutil.copyfile(data / "packages" / rec[3] / nm, set_sess / nm)
                (set_sess / nm).chmod(0o700 if nm == "api" else 0o600)
            (ram / "runtime").symlink_to(set_sess)

            # 4) USB uninstall failure (tampered autostart -> state_changed) writes sanitized log with
            #    record phase/budget/notice and NEVER leaks record nonce or token!
            auto = root / "usr/bin/autostart"
            orig_auto = auto.read_bytes()
            auto.write_bytes(b"#!/bin/sh\n# drifted\n")
            p_un, r_un = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertNotEqual(p_un.returncode, 0)
            self.assertEqual(r_un["error"], "state_changed")
            txt_un = log_file.read_text()
            self.assertIn("operation=uninstall\n", txt_un)
            self.assertIn("error=state_changed\n", txt_un)
            self.assertIn("step=targets_match\n", txt_un)
            self.assertIn("path=/usr/bin/autostart\n", txt_un)
            self.assertIn("reason=sha256_mismatch\n", txt_un)
            self.assertIn("  phase=active\n", txt_un)
            self.assertIn("  budget=2\n", txt_un)
            self.assertIn("  notice=installed\n", txt_un)
            self.assertNotIn(nonce_secret, txt_un)
            self.assertNotIn(TOKEN, txt_un)
            self.assertNotIn("/tmp/mnt/sd_nav", txt_un)
            log_file.unlink()

            # 5) RO vfat remount lifecycle + safety guards (remount fail, non-vfat, mismatched USB,
            #    2 matching sticks, symlinked log, non-USB session).
            # 5a. RO vfat mount (default on real Mazda CMU v74!) temporarily remounts rw, writes
            #     open-connect-error.log (recording original ro mount), and restores ro!
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat ro,fmask=0022 0 0\n"
            )
            p_ro, r_ro = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertNotEqual(p_ro.returncode, 0)
            self.assertEqual(r_ro["error"], "state_changed")
            self.assertTrue(log_file.is_file())
            txt_ro = log_file.read_text()
            self.assertIn("/dev/sda1 /tmp/mnt/sda1 vfat ro,fmask=0022 0 0\n", txt_ro)
            self.assertIn(
                "/dev/sda1 /tmp/mnt/sda1 vfat ro,fmask=0022 0 0\n",
                (root / "proc/self/mounts").read_text(),
            )
            log_file.unlink()

            # 5a2. RO vfat mount where remount,rw fails (e.g. write-protected USB): refuses cleanly.
            env_ro_fail = dict(env, OC_HOST_USB_REMOUNT_FAIL="1")
            p_rof, r_rof = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env_ro_fail)
            self.assertNotEqual(p_rof.returncode, 0)
            self.assertEqual(r_rof["error"], "state_changed")
            self.assertFalse(log_file.exists())
            self.assertIn(
                "/dev/sda1 /tmp/mnt/sda1 vfat ro,fmask=0022 0 0\n",
                (root / "proc/self/mounts").read_text(),
            )

            # 5b. Non-vfat mount
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 ext4 rw 0 0\n"
            )
            p_ext, r_ext = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertEqual(r_ext["error"], "state_changed")
            self.assertFalse(log_file.exists())

            # 5c. Mismatched USB manifest
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
            )
            (vol / "open-connect/files.sha256").write_text("other stick\n")
            p_mis, r_mis = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertEqual(r_mis["error"], "state_changed")
            self.assertFalse(log_file.exists())
            shutil.copyfile(usb_sess / "files.sha256", vol / "open-connect/files.sha256")

            # 5d. Ambiguous two matching USB volumes
            vol2 = root / "tmp/mnt/sdb1"
            (vol2 / "open-connect").mkdir(parents=True)
            shutil.copyfile(usb_sess / "run.sh", vol2 / "open-connect/run.sh")
            shutil.copyfile(usb_sess / "files.sha256", vol2 / "open-connect/files.sha256")
            (root / "proc/self/mounts").write_text(
                base_mounts
                + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
                + "/dev/sdb1 /tmp/mnt/sdb1 vfat rw 0 0\n"
            )
            p_amb, r_amb = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertEqual(r_amb["error"], "state_changed")
            self.assertFalse(log_file.exists())
            self.assertFalse((vol2 / "open-connect-error.log").exists())
            shutil.rmtree(vol2)
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
            )

            # 5e. Symlinked open-connect-error.log refused via O_NOFOLLOW; target untouched!
            victim = root / "victim.txt"
            victim.write_text("untouched\n")
            log_file.symlink_to(victim)
            p_sym, r_sym = self._call_api(api_bin, usb_sess, rec[5], "uninstall", env=env)
            self.assertEqual(r_sym["error"], "state_changed")
            self.assertEqual(victim.read_text(), "untouched\n")
            log_file.unlink()

            # 5f. Non-USB Settings session failure must NEVER write a USB error log!
            p_set, r_set = self._call_api(api_bin, set_sess, rec[5], "uninstall", env=env)
            self.assertNotEqual(p_set.returncode, 0)
            self.assertEqual(r_set["error"], "state_changed")
            self.assertFalse(log_file.exists())

            # 6) USB recover failure (pending install with drifted autostart) writes operation=recover log.
            rec_pend = list(rec)
            rec_pend[1] = "install"
            rec_pend[6] = rec[4]
            rec_pend[7] = rec[5]
            (data / "record").write_text("|".join(rec_pend) + "\n")
            p_rec, r_rec = self._call_api(api_bin, usb_sess, rec[2], "recover", env=env)
            self.assertNotEqual(p_rec.returncode, 0)
            self.assertEqual(r_rec["error"], "startup_changed")
            self.assertTrue(log_file.is_file())
            txt_rec = log_file.read_text()
            self.assertIn("operation=recover\n", txt_rec)
            self.assertIn("error=startup_changed\n", txt_rec)
            self.assertIn("  phase=install\n", txt_rec)
            self.assertNotIn(nonce_secret, txt_rec)
            self.assertNotIn(TOKEN, txt_rec)
            auto.write_bytes(orig_auto)

    def test_reinstall_and_upgrade_reuse_immutable_inodes_safely(self):
        """Issue #167: Identical reinstalls and non-compose upgrades hardlink verified immutable
        package & composed files while preserving fresh INSTANCE/pkg_id, originals immutability,
        live /jci/vui pin checks, compose-input invalidation, and clean cross-gen GC."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"

            # 1) Cold install -> generation 1, then boot into snap1 so pkg1 is live-pinned!
            p1, r1 = self._call_api(api_bin, usb_sess, "-", "install", env=env)
            self.assertEqual(p1.returncode, 0, (r1, p1.stderr))
            rec1 = (data / "record").read_text().strip().split("|")
            pkg1, snap1 = rec1[3], rec1[5]
            bs_bin = root / "usr/bin/open-connect-boot-select"
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "select", str(root)], env=env, capture_output=True
                ).returncode,
                0,
            )
            orig_inos = {
                p.name: (p.stat().st_ino, p.stat().st_nlink) for p in (data / "originals").iterdir()
            }
            pkg1_inos = {p.name: p.stat().st_ino for p in (data / "packages" / pkg1).iterdir()}
            comp1_inos = {p.name: p.stat().st_ino for p in (data / "composed" / pkg1).iterdir()}
            inst1 = (data / "packages" / pkg1 / "INSTANCE").read_text()

            # 2) Identical reinstall from active -> brand-new pkg2/INSTANCE/files.sha256,
            #    while ALL non-INSTANCE package files and ALL 12 composed outputs share inodes!
            p2, r2 = self._call_api(api_bin, usb_sess, snap1, "install", env=env)
            self.assertEqual(p2.returncode, 0, (r2, p2.stderr))
            rec2 = (data / "record").read_text().strip().split("|")
            pkg2, snap2 = rec2[3], rec2[5]
            self.assertNotEqual(pkg2, pkg1)
            self.assertNotEqual(snap2, snap1)
            self.assertNotEqual((data / "packages" / pkg2 / "INSTANCE").read_text(), inst1)
            self.assertNotEqual(
                (data / "packages" / pkg2 / "INSTANCE").stat().st_ino, pkg1_inos["INSTANCE"]
            )
            self.assertNotEqual(
                (data / "packages" / pkg2 / "files.sha256").stat().st_ino, pkg1_inos["files.sha256"]
            )
            for nm, ino1 in pkg1_inos.items():
                if nm in ("INSTANCE", "files.sha256"):
                    continue
                st2 = (data / "packages" / pkg2 / nm).stat()
                self.assertEqual(st2.st_ino, ino1, f"expected package hardlink reuse for {nm}")
                self.assertEqual(st2.st_nlink, 2, nm)
            self.assertNotEqual(
                (data / "composed" / pkg2 / "files.sha256").stat().st_ino,
                comp1_inos["files.sha256"],
            )
            for nm, ino1 in comp1_inos.items():
                if nm == "files.sha256":
                    continue
                st2 = (data / "composed" / pkg2 / nm).stat()
                self.assertEqual(st2.st_ino, ino1, f"expected composed hardlink reuse for {nm}")
                self.assertEqual(st2.st_nlink, 2, nm)
            # Originals must remain untouched with nlink==1.
            for nm, (oino, onlink) in orig_inos.items():
                ost = (data / "originals" / nm).stat()
                self.assertEqual((ost.st_ino, ost.st_nlink), (oino, onlink))
                self.assertEqual(ost.st_nlink, 1)

            # 3) Simulate reboot into snap2 (clean boot-scoped RAM markers + new boot_id) and run
            #    Settings set -> GC prunes pkg1/composed1; pkg2 & composed2 survive with st_nlink==1!
            for child in list(ram.iterdir()):
                if child.name in ("sessions", "usb-runtime", "lock"):
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            (root / "proc/sys/kernel/random/boot_id").write_text(
                "22222222-2222-2222-2222-222222222222\n"
            )
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "select", str(root)], env=env, capture_output=True
                ).returncode,
                0,
            )
            set_sess = ram / "sessions/session-set167"
            set_sess.mkdir(mode=0o700)
            for nm in ("files.sha256", "api", "VERSION"):
                shutil.copyfile(data / "packages" / pkg2 / nm, set_sess / nm)
                (set_sess / nm).chmod(0o700 if nm == "api" else 0o600)
            (ram / "runtime").symlink_to(set_sess)
            pt, rt = self._call_api(api_bin, set_sess, snap2, "set", "warning", "1", "0", env=env)
            self.assertEqual(pt.returncode, 0, (rt, pt.stderr))
            self.assertEqual([p.name for p in (data / "packages").iterdir()], [pkg2])
            self.assertEqual([p.name for p in (data / "composed").iterdir()], [pkg2])
            self.assertEqual((data / "composed" / pkg2 / "uia.so").stat().st_nlink, 1)
            self.assertEqual((data / "packages" / pkg2 / "api").stat().st_nlink, 1)
            snap_after_gc = rt["revision"]

            # 3b) C1 regression (Probe 1): After GC drops st_nlink 2->1 (mutating st_ctime on
            #     shared inodes), Settings set #2, boot-select audit, AND next-boot select/select-gated
            #     MUST all still succeed (zero state_changed, zero OC_REFUSE)!
            pt2, rt2 = self._call_api(
                api_bin, set_sess, snap_after_gc, "set", "warning", "0", "1", env=env
            )
            self.assertEqual(pt2.returncode, 0, (rt2, pt2.stderr))
            snap_after_gc = rt2["revision"]
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap_after_gc], env=env, capture_output=True
                ).returncode,
                0,
            )
            for child in list(ram.iterdir()):
                if child.name in ("sessions", "usb-runtime", "lock"):
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            (root / "proc/sys/kernel/random/boot_id").write_text(
                "33333333-3333-3333-3333-333333333333\n"
            )
            p_sg = subprocess.run(
                [str(bs_bin), "select-gated", str(root)],
                env=env,
                capture_output=True,
            )
            self.assertEqual(p_sg.returncode, 0, p_sg.stderr)
            self.assertEqual(p_sg.stdout, b"G")
            self.assertFalse((data / "reseal").exists())
            (ram / "runtime").symlink_to(set_sess)

            # 4) Upgrade changing ONLY VERSION: VERSION gets a fresh inode, unchanged payload files
            #    AND all 12 composed outputs are reused via hardlinks!
            usb_ver = ram / "sessions/session-usb167v"
            shutil.copytree(
                usb_sess, usb_ver, symlinks=False, ignore=shutil.ignore_patterns("admitted")
            )
            usb_ver.chmod(0o700)
            (usb_ver / "VERSION").write_text("0.4.0-reuselink\n")
            (usb_ver / "files.sha256").unlink()
            (usb_ver / "token").unlink()
            (usb_ver / "files.sha256").write_text(
                "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_ver.iterdir()))
            )
            (usb_ver / "files.sha256").chmod(0o600)
            (usb_ver / "token").write_text(TOKEN + "\n")
            (usb_ver / "token").chmod(0o600)
            (ram / "usb-runtime").unlink()
            (ram / "usb-runtime").symlink_to(usb_ver)
            p3, r3 = self._call_api(usb_ver / "api", usb_ver, snap_after_gc, "install", env=env)
            self.assertEqual(p3.returncode, 0, (r3, p3.stderr))
            rec3 = (data / "record").read_text().strip().split("|")
            pkg3, snap3 = rec3[3], rec3[5]
            self.assertNotEqual(
                (data / "packages" / pkg3 / "VERSION").stat().st_ino,
                (data / "packages" / pkg2 / "VERSION").stat().st_ino,
            )
            self.assertEqual(
                (data / "packages" / pkg3 / "api").stat().st_ino,
                (data / "packages" / pkg2 / "api").stat().st_ino,
            )
            self.assertEqual(
                (data / "composed" / pkg3 / "uia.so").stat().st_ino,
                (data / "composed" / pkg2 / "uia.so").stat().st_ino,
            )

            pkg3_auto_ino = (data / "composed" / pkg3 / "autostart").stat().st_ino
            pkg3_api_ino = (data / "packages" / pkg3 / "api").stat().st_ino

            # 5) Upgrade changing a compose input (startup-hook.sh) MUST re-compose fresh inodes
            #    and emit the updated autostart bytes!
            usb_hook = ram / "sessions/session-usb167h"
            shutil.copytree(
                usb_ver, usb_hook, symlinks=False, ignore=shutil.ignore_patterns("admitted")
            )
            usb_hook.chmod(0o700)
            (usb_hook / "startup-hook.sh").write_text(
                (usb_hook / "startup-hook.sh").read_text() + "\n# marker-167-recompose\n"
            )
            (usb_hook / "files.sha256").unlink()
            (usb_hook / "token").unlink()
            (usb_hook / "files.sha256").write_text(
                "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_hook.iterdir()))
            )
            (usb_hook / "files.sha256").chmod(0o600)
            (usb_hook / "token").write_text(TOKEN + "\n")
            (usb_hook / "token").chmod(0o600)
            (ram / "usb-runtime").unlink()
            (ram / "usb-runtime").symlink_to(usb_hook)
            p4, r4 = self._call_api(usb_hook / "api", usb_hook, snap3, "install", env=env)
            self.assertEqual(p4.returncode, 0, (r4, p4.stderr))
            rec4 = (data / "record").read_text().strip().split("|")
            pkg4, snap4 = rec4[3], rec4[5]
            self.assertNotEqual(
                (data / "composed" / pkg4 / "autostart").stat().st_ino,
                pkg3_auto_ino,
            )
            self.assertIn(
                "# marker-167-recompose", (data / "composed" / pkg4 / "autostart").read_text()
            )
            # Unchanged package files like api are STILL hardlinked (even after GC prunes pkg3)!
            self.assertEqual(
                (data / "packages" / pkg4 / "api").stat().st_ino,
                pkg3_api_ino,
            )

            # 6) C1 regression (Probe 3): Tampered live /jci/vui/svcjcivui.so MUST refuse BEFORE
            #    mutating packages/ or hardlinking active pkg4, keeping active audit & Settings OK!
            vui_so = root / "jci/vui/svcjcivui.so"
            orig_vui = vui_so.read_bytes()
            pkgs_before_fail = sorted(p.name for p in (data / "packages").iterdir())
            pkg4_api_ctime = (data / "packages" / pkg4 / "api").stat().st_ctime_ns
            vui_so.write_bytes(b"tampered vui\n")
            p5, r5 = self._call_api(usb_hook / "api", usb_hook, snap4, "install", env=env)
            self.assertNotEqual(p5.returncode, 0)
            self.assertEqual(r5["error"], "vui_inputs_changed")
            vui_so.write_bytes(orig_vui)
            self.assertEqual(
                sorted(p.name for p in (data / "packages").iterdir()), pkgs_before_fail
            )
            self.assertEqual((data / "packages" / pkg4 / "api").stat().st_ctime_ns, pkg4_api_ctime)
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap4], env=env, capture_output=True
                ).returncode,
                0,
            )

            # 7) H1 regression (Probe 4): Changing the composer binary ('install') digest MUST
            #    invalidate composed reuse and re-compose fresh inodes!
            pkg4_uia_ino = (data / "composed" / pkg4 / "uia.so").stat().st_ino
            usb_comp = ram / "sessions/session-usb167c"
            shutil.copytree(
                usb_hook, usb_comp, symlinks=False, ignore=shutil.ignore_patterns("admitted")
            )
            usb_comp.chmod(0o700)
            # Append a harmless trailing byte to a copy of host install binary? Instead use a
            # thin wrapper script? No: copy install and append 1 trailing NUL byte (valid ELF/Mach-O
            # padding outside loadable segments, changes SHA-256 while remaining executable!).
            (usb_comp / "install").write_bytes((usb_comp / "install").read_bytes() + b"\x00")
            (usb_comp / "install").chmod(0o700)
            (usb_comp / "files.sha256").unlink()
            (usb_comp / "token").unlink()
            (usb_comp / "files.sha256").write_text(
                "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_comp.iterdir()))
            )
            (usb_comp / "files.sha256").chmod(0o600)
            (usb_comp / "token").write_text(TOKEN + "\n")
            (usb_comp / "token").chmod(0o600)
            (ram / "usb-runtime").unlink()
            (ram / "usb-runtime").symlink_to(usb_comp)
            p6, r6 = self._call_api(usb_comp / "api", usb_comp, snap4, "install", env=env)
            self.assertEqual(p6.returncode, 0, (r6, p6.stderr))
            rec6 = (data / "record").read_text().strip().split("|")
            pkg6, snap6 = rec6[3], rec6[5]
            self.assertNotEqual(
                (data / "composed" / pkg6 / "uia.so").stat().st_ino,
                pkg4_uia_ino,
            )

            # 8) H2 regression (Probe 5): Active snapshot with empty dependencies + tampered
            #    self-signed composed/<pkg6>/uia.so MUST NOT propagate tampered uia.so;
            #    oc_open_composed_verified rejects unanchored manifest and recomposes cleanly!
            #    (Also test C1 Probe 2/8a: same-boot immediate reinstall passes audit & select-gated!)
            comp6 = data / "composed" / pkg6
            good_uia = (comp6 / "uia.so").read_bytes()
            (comp6 / "uia.so").write_bytes(b"EVIL_TAMPERED_UIA_BINARY" + b"\x00" * 100)
            (comp6 / "uia.so").chmod(0o600)
            (comp6 / "files.sha256").write_text(
                "".join(
                    f"{sha((comp6 / nm).read_bytes())}  {nm}\n"
                    for nm in sorted(p.name for p in comp6.iterdir() if p.name != "files.sha256")
                )
            )
            (comp6 / "files.sha256").chmod(0o600)
            # Rebuild snap6 with empty dependencies & matching boot.plan/files.sha256/record so
            # oc_targets_match and oc_dependencies_match pass (reproducing Probe 5!).
            snap6_dir = data / "snapshots" / snap6
            old_plan_lines = (snap6_dir / "boot.plan").read_text().splitlines()
            (snap6_dir / "dependencies").write_text("")
            (snap6_dir / "dependencies").chmod(0o600)
            (snap6_dir / "boot.plan").unlink()
            (snap6_dir / "files.sha256").unlink()
            unsealed = [old_plan_lines[0]]
            for ln in old_plan_lines[1:]:
                cols = ln.split("|")
                if cols[0].startswith(f"composed-{pkg6}/") or cols[0].startswith(
                    f"package-{pkg6}/"
                ):
                    continue
                if cols[1] == "@/dependencies":
                    cols[2] = sha(b"")
                unsealed.append("|".join(cols[:3]))
            with (snap6_dir / "boot.plan").open("wb") as pl_f:
                subprocess.run(
                    [
                        str(bs_bin),
                        "seal",
                        str(root),
                        f"tmp/mnt/data_persist/open-connect/snapshots/{snap6}",
                    ],
                    input=("\n".join(unsealed) + "\n").encode(),
                    stdout=pl_f,
                    stderr=subprocess.PIPE,
                    env=env,
                    check=True,
                )
            (snap6_dir / "boot.plan").chmod(0o600)
            new_s6_mf = "".join(
                f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(snap6_dir.iterdir())
            )
            (snap6_dir / "files.sha256").write_text(new_s6_mf)
            (snap6_dir / "files.sha256").chmod(0o600)
            new_snap6 = sha(new_s6_mf.encode())
            snap6_dir.rename(data / "snapshots" / new_snap6)
            rec6[5] = new_snap6
            (data / "record").write_text("|".join(rec6) + "\n")
            p7, r7 = self._call_api(usb_comp / "api", usb_comp, new_snap6, "install", env=env)
            self.assertEqual(p7.returncode, 0, (r7, p7.stderr))
            rec7 = (data / "record").read_text().strip().split("|")
            pkg7, snap7 = rec7[3], rec7[5]
            self.assertEqual((data / "composed" / pkg7 / "uia.so").read_bytes(), good_uia)
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap7], env=env, capture_output=True
                ).returncode,
                0,
            )

            # 8b) C1 regression (Probe 2): Same-boot immediate identical reinstall where GC prunes
            #     unpinned pkg7 (mutating shared inode st_ctime on pkg8/composed8) MUST still pass
            #     audit AND next-boot select-gated (rc=0, b"G", zero D/reseal)!
            p8, r8 = self._call_api(usb_comp / "api", usb_comp, snap7, "install", env=env)
            self.assertEqual(p8.returncode, 0, (r8, p8.stderr))
            rec8 = (data / "record").read_text().strip().split("|")
            pkg8, snap8 = rec8[3], rec8[5]
            self.assertFalse((data / "packages" / pkg7).exists())
            # api is still shared with live-booted pkg2 (nlink 3->2 after pkg7 pruned), while
            # composed/uia.so (recomposed in Step 7) drops nlink 2->1; both mutate st_ctime!
            self.assertEqual((data / "packages" / pkg8 / "api").stat().st_nlink, 2)
            self.assertEqual((data / "composed" / pkg8 / "uia.so").stat().st_nlink, 1)
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap8], env=env, capture_output=True
                ).returncode,
                0,
            )
            for child in list(ram.iterdir()):
                if child.name in ("sessions", "usb-runtime", "lock"):
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            (root / "proc/sys/kernel/random/boot_id").write_text(
                "44444444-4444-4444-4444-444444444444\n"
            )
            p_sg8 = subprocess.run(
                [str(bs_bin), "select-gated", str(root)],
                env=env,
                capture_output=True,
            )
            self.assertEqual(p_sg8.returncode, 0, p_sg8.stderr)
            self.assertEqual(p_sg8.stdout, b"G")
            self.assertFalse((data / "reseal").exists())

    def test_usb_preferences_preset_and_settings_export_import_130(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            ram, data, usb_sess, env = self._build_fixture(root)
            api_bin = usb_sess / "api"
            bs_bin = root / "usr/bin/open-connect-boot-select"
            # Populate synthetic VUI plugins matching ui-modules.tsv so base=1 preset validates cleanly.
            vui_dir = root / "jci/vui/plugins"
            patched_ui = []
            for ln in (usb_sess / "ui-modules.tsv").read_text().splitlines():
                if ln.startswith("vui\t"):
                    parts = ln.split("\t")
                    blob = b"vui-plugin-" + parts[1].encode() + b"\n"
                    (vui_dir / parts[1]).write_bytes(blob)
                    (vui_dir / parts[1]).chmod(0o755)
                    parts[3] = sha(blob)
                    patched_ui.append("\t".join(parts))
                else:
                    patched_ui.append(ln)
            (usb_sess / "ui-modules.tsv").write_text("\n".join(patched_ui) + "\n")
            (usb_sess / "ui-modules.tsv").chmod(0o600)
            (usb_sess / "files.sha256").unlink()
            (usb_sess / "token").unlink()
            mf0 = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(usb_sess.iterdir()))
            (usb_sess / "files.sha256").write_text(mf0)
            (usb_sess / "files.sha256").chmod(0o600)
            (usb_sess / "token").write_text(TOKEN + "\n")
            (usb_sess / "token").chmod(0o600)
            # Mount verified USB drive at /tmp/mnt/sda1 with matching open-connect/files.sha256 + run.sh
            vol = root / "tmp/mnt/sda1"
            (vol / "open-connect").mkdir(parents=True, mode=0o700)
            shutil.copyfile(usb_sess / "files.sha256", vol / "open-connect/files.sha256")
            (vol / "open-connect/run.sh").write_text("#!/bin/sh\n")
            base_mounts = (root / "proc/self/mounts").read_text()
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat ro,noatime 0 0\n"
            )
            # Mark non-factory-wireless via OC_HOST_WIRELESS_FILE existing file
            wf = root / "not-factory-wireless"
            wf.write_text("0\n")
            env_wl = {**env, "OC_HOST_WIRELESS_FILE": str(wf)}

            # 1) Invalid presets on fresh install fail closed without publishing state
            for label, payload in (
                ("bad_header", b"OC2\ntouch=1\n"),
                ("empty", b"OCPREFS1\n# only comment\n"),
                ("forbidden_pkg", b"OCPREFS1\npackage=" + b"a" * 64 + b"\n"),
                ("forbidden_nvram", b"OCPREFS1\nnvram=disable\n"),
                ("forbidden_uart", b"OCPREFS1\nuart=1\n"),
                ("forbidden_ssh", b"OCPREFS1\nssh=1\n"),
                ("unknown_svc", b"OCPREFS1\nservice.bogus=0\n"),
                ("dup_key", b"OCPREFS1\ntouch=0\ntouch=1\n"),
                ("bad_val", b"OCPREFS1\nwarning=2\n"),
                ("oversized", b"OCPREFS1\n# " + b"x" * 1020 + b"\ntouch=1\n"),
            ):
                with self.subTest(bad_preset=label):
                    (vol / "open-connect.prefs").write_bytes(payload)
                    p, r = self._call_api(api_bin, usb_sess, "-", "install", env=env_wl)
                    self.assertNotEqual(p.returncode, 0)
                    self.assertEqual(r["error"], "invalid_preferences_preset")
                    self.assertFalse(data.exists())
            # Symlink preset refused
            target = root / "real.prefs"
            target.write_text("OCPREFS1\ntouch=0\n")
            (vol / "open-connect.prefs").unlink()
            (vol / "open-connect.prefs").symlink_to(target)
            p, r = self._call_api(api_bin, usb_sess, "-", "install", env=env_wl)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(r["error"], "invalid_preferences_preset")
            self.assertFalse(data.exists())
            (vol / "open-connect.prefs").unlink()

            # 2) Factory-wireless CMU refuses wireless=1 preset
            (vol / "open-connect.prefs").write_text("OCPREFS1\nwireless=1\n")
            p, r = self._call_api(
                api_bin,
                usb_sess,
                "-",
                "install",
                env={**env, "OC_HOST_WIRELESS_FILE": str(root / "absent-means-factory-wl")},
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(r["error"], "wireless_factory_enabled")
            self.assertFalse(data.exists())

            # 3) Valid fresh-install preset (comments + CRLF + touch=2 + base=1 + all toggles)
            (vol / "open-connect.prefs").write_bytes(
                b"OCPREFS1\r\n"
                b"# Owner preset\r\n"
                b"\r\n"
                b"base=1\r\n"
                b"carplay-autoshow=1\r\n"
                b"hold-scroll=1\r\n"
                b"menu-loop=1\r\n"
                b"source-order=1\r\n"
                b"touch=2\r\n"
                b"warning=0\r\n"
                b"wireless=1\r\n"
                b"service.android-auto=0\r\n"
                b"service.pandora=0\r\n"
                b"service.siriusxm=1\r\n"
            )
            p, r = self._call_api(api_bin, usb_sess, "-", "install", env=env_wl)
            self.assertEqual(p.returncode, 0, (r, p.stderr))
            self.assertTrue(r["ok"] and r["installed"])
            rec = (data / "record").read_text().strip().split("|")
            snap1 = rec[5]
            cfg1 = (data / "snapshots" / snap1 / "config").read_text()
            for expected_line in (
                "base=1",
                "carplay-autoshow=1",
                "hold-scroll=1",
                "menu-loop=1",
                "nvram=absent",
                "service.android-auto=0",
                "service.pandora=0",
                "service.siriusxm=1",
                "source-order=1",
                "touch=2",
                "warning=0",
                "wireless=1",
            ):
                self.assertIn(expected_line + "\n", cfg1)
            self.assertFalse(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            )
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap1], env=env_wl, capture_output=True
                ).returncode,
                0,
            )

            # 4) Upgrade with different preset on USB preserves existing OC2 prefs (never clobbers!)
            (vol / "open-connect.prefs").write_text("OCPREFS1\ntouch=0\nbase=0\n")
            p_up, r_up = self._call_api(api_bin, usb_sess, snap1, "install", env=env_wl)
            self.assertEqual(p_up.returncode, 0, (r_up, p_up.stderr))
            rec2 = (data / "record").read_text().strip().split("|")
            snap2, pkg2 = rec2[5], rec2[3]
            cfg2 = (data / "snapshots" / snap2 / "config").read_text()
            self.assertIn("touch=2\n", cfg2)
            self.assertIn("base=1\n", cfg2)

            # 5) Settings session export|prefs and import|prefs (USB session refused!)
            p_usb_ex, r_usb_ex = self._call_api(
                api_bin, usb_sess, snap2, "export", "prefs", env=env_wl
            )
            self.assertNotEqual(p_usb_ex.returncode, 0)
            self.assertEqual(r_usb_ex["error"], "invalid_request")
            p_usb_im, r_usb_im = self._call_api(
                api_bin, usb_sess, snap2, "import", "prefs", env=env_wl
            )
            self.assertNotEqual(p_usb_im.returncode, 0)
            self.assertEqual(r_usb_im["error"], "invalid_request")

            set_sess = ram / "sessions/session-set130"
            set_sess.mkdir(mode=0o700)
            shutil.copyfile(data / "packages" / pkg2 / "files.sha256", set_sess / "files.sha256")
            shutil.copyfile(data / "packages" / pkg2 / "VERSION", set_sess / "VERSION")
            (ram / "selected").write_text(snap2 + "\n")
            (ram / "selected").chmod(0o600)
            (ram / "runtime").symlink_to(set_sess)

            # Export on RO vfat -> remounts RW, writes canonical OCPREFS1, restores RO
            (vol / "open-connect.prefs").unlink()
            p_ex, r_ex = self._call_api(api_bin, set_sess, snap2, "export", "prefs", env=env_wl)
            self.assertEqual(p_ex.returncode, 0, (r_ex, p_ex.stderr))
            self.assertTrue(r_ex["ok"] and r_ex["revision"] == snap2)
            exported = (vol / "open-connect.prefs").read_text()
            self.assertEqual(
                exported,
                "OCPREFS1\n"
                "base=1\n"
                "carplay-autoshow=1\n"
                "hold-scroll=1\n"
                "menu-loop=1\n"
                "service.android-auto=0\n"
                "service.pandora=0\n"
                "service.siriusxm=1\n"
                "source-order=1\n"
                "touch=2\n"
                "warning=0\n"
                "wireless=1\n",
            )
            self.assertIn("/tmp/mnt/sda1 vfat ro,noatime", (root / "proc/self/mounts").read_text())

            # Export with symlink open-connect.prefs refused
            (vol / "open-connect.prefs").unlink()
            (vol / "open-connect.prefs").symlink_to(target)
            p_ex_sym, r_ex_sym = self._call_api(
                api_bin, set_sess, snap2, "export", "prefs", env=env_wl
            )
            self.assertNotEqual(p_ex_sym.returncode, 0)
            self.assertEqual(r_ex_sym["error"], "export_failed")
            (vol / "open-connect.prefs").unlink()
            (vol / "open-connect.prefs").write_text(exported)

            # Export with 2 vfat volumes -> multiple_usb_volumes; 0 -> usb_not_found
            vol2 = root / "tmp/mnt/sdb1"
            vol2.mkdir(mode=0o700)
            (root / "proc/self/mounts").write_text(
                base_mounts
                + "/dev/sda1 /tmp/mnt/sda1 vfat ro,noatime 0 0\n"
                + "/dev/sdb1 /tmp/mnt/sdb1 vfat ro,noatime 0 0\n"
            )
            _, r_m = self._call_api(api_bin, set_sess, snap2, "export", "prefs", env=env_wl)
            self.assertEqual(r_m["error"], "multiple_usb_volumes")
            # Import with 2 files -> multiple_preferences_files
            (vol2 / "open-connect.prefs").write_text(exported)
            _, r_mi = self._call_api(api_bin, set_sess, snap2, "import", "prefs", env=env_wl)
            self.assertEqual(r_mi["error"], "multiple_preferences_files")
            (vol2 / "open-connect.prefs").unlink()
            (root / "proc/self/mounts").write_text(base_mounts)
            _, r_none = self._call_api(api_bin, set_sess, snap2, "export", "prefs", env=env_wl)
            self.assertEqual(r_none["error"], "usb_not_found")
            _, r_nv = self._call_api(api_bin, set_sess, snap2, "import", "prefs", env=env_wl)
            self.assertEqual(r_nv["error"], "invalid_preferences_volume")
            (root / "proc/self/mounts").write_text(
                base_mounts + "/dev/sda1 /tmp/mnt/sda1 vfat ro,noatime 0 0\n"
            )

            # Re-importing identical exported prefs is a zero-transaction no-op
            p_noop, r_noop = self._call_api(api_bin, set_sess, snap2, "import", "prefs", env=env_wl)
            self.assertEqual(p_noop.returncode, 0, (r_noop, p_noop.stderr))
            self.assertEqual(r_noop["revision"], snap2)

            # Multi-toggle import: changes touch 2->1 (NVRAM absent->disable), warning 0->1,
            # source-order 1->0, menu-loop 1->0, service.pandora 0->1 in one transaction!
            (vol / "open-connect.prefs").write_text(
                "OCPREFS1\ntouch=1\nwarning=1\nsource-order=0\nmenu-loop=0\nservice.pandora=1\n"
            )
            p_im, r_im = self._call_api(api_bin, set_sess, snap2, "import", "prefs", env=env_wl)
            self.assertEqual(p_im.returncode, 0, (r_im, p_im.stderr))
            self.assertTrue(r_im["ok"] and r_im["revision"] != snap2)
            self.assertEqual(r_im["touch"], 1)
            self.assertEqual(r_im["warning"], 1)
            self.assertEqual(r_im["sourceOrder"], 0)
            self.assertEqual(r_im["menuLoop"], 0)
            self.assertEqual(r_im["holdScroll"], 1)
            self.assertEqual(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction")
                .read_text()
                .strip(),
                "disable",
            )
            snap3 = r_im["revision"]
            self.assertEqual(
                subprocess.run(
                    [str(bs_bin), "audit", str(root), snap3], env=env_wl, capture_output=True
                ).returncode,
                0,
            )

            # Round-trip import of original exported file restores exact original state + NVRAM!
            (vol / "open-connect.prefs").write_text(exported)
            p_rt, r_rt = self._call_api(api_bin, set_sess, snap3, "import", "prefs", env=env_wl)
            self.assertEqual(p_rt.returncode, 0, (r_rt, p_rt.stderr))
            self.assertEqual(r_rt["touch"], 2)
            self.assertEqual(r_rt["warning"], 0)
            self.assertEqual(r_rt["sourceOrder"], 1)
            self.assertEqual(r_rt["menuLoop"], 1)
            self.assertFalse(
                (root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
            )
