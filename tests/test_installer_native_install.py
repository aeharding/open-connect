"""Exercise native cold USB install, composition, upgrade, and --boot-recover under ASan+UBSan."""

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
            txt = InstallerPreferences().profile(wcp)
            inject = (
                '  <service type="process" name="jciGUI" path="/jci/opera/opera_dir/userjs/opera" args="-u /jci/gui/index.html" autorun="yes"/>\n'
                '  <service type="process" name="jciMMUI" path="/jci/mmui/svcjcimmui.so" autorun="yes"/>\n'
            )
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
        (root / "etc/ssh/sshd_config").write_text("PermitRootLogin yes\n")
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
            timeout=20,
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
            p_as, r_as = self._call_api(
                api_bin, set_sess, r_t0["revision"], "set", "carplay-autoshow", "0", "1", env=env
            )
            self.assertEqual(p_as.returncode, 0, (r_as, p_as.stderr))
            snap_mod = r_as["revision"]

            # 3) Upgrade from active via a second USB session (different VERSION) -> preserves touch=0 & carplay-autoshow=1!
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

            # (M2) Unpinned legacy backend.sh in Settings session is refused by oc_usb_fence().
            leg_pkg_w = data / "packages/.leg"
            shutil.copytree(data / "packages" / new_rec[3], leg_pkg_w)
            leg_pkg_w.chmod(0o700)
            (leg_pkg_w / "backend.sh").write_text("#!/bin/sh\n# unpinned legacy dev.22\n")
            (leg_pkg_w / "backend.sh").chmod(0o600)
            (leg_pkg_w / "files.sha256").unlink()
            lmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(leg_pkg_w.iterdir()))
            (leg_pkg_w / "files.sha256").write_text(lmf)
            (leg_pkg_w / "files.sha256").chmod(0o600)
            leg_pkg = sha(lmf.encode())
            leg_pkg_w.rename(data / "packages" / leg_pkg)
            leg_snap_w = data / "snapshots/.legsnap"
            leg_snap_w.mkdir(mode=0o700)
            lcfg = f"OC2\npackage={leg_pkg}\n"
            (leg_snap_w / "config").write_text(lcfg)
            (leg_snap_w / "config").chmod(0o600)
            lsmf = f"{sha(lcfg.encode())}  config\n"
            (leg_snap_w / "files.sha256").write_text(lsmf)
            (leg_snap_w / "files.sha256").chmod(0o600)
            leg_snap = sha(lsmf.encode())
            leg_snap_w.rename(data / "snapshots" / leg_snap)
            saved_sel = (ram / "selected").read_bytes()
            (ram / "selected").write_text(leg_snap + "\n")
            shutil.copyfile(data / "packages" / leg_pkg / "files.sha256", set_sess / "files.sha256")
            shutil.copyfile(data / "packages" / leg_pkg / "backend.sh", set_sess / "backend.sh")
            p_unp, r_unp = self._call_api(api_bin, usb_sess, new_rec[5], "recover", env=env)
            self.assertNotEqual(p_unp.returncode, 0)
            self.assertEqual(r_unp["error"], "invalid_legacy_runtime")
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

            # (M3b) Wrong OCBP1 header in boot.plan with matching D/reseal must be refused before recheck!
            m3b_rec = (data / "record").read_text().strip().split("|")
            bad_bp_snap = data / "snapshots" / m3b_rec[5]
            orig_bp = (bad_bp_snap / "boot.plan").read_bytes()
            (bad_bp_snap / "boot.plan").write_bytes(
                orig_bp.replace(m3b_rec[4].encode(), b"f" * 64, 1)
            )
            (data / "reseal").write_text(m3b_rec[5] + "\n")
            (data / "reseal").chmod(0o600)
            br_m3b = subprocess.run(
                [str(inst_ram), "--boot-recover", str(pkg_now), str(rec_exec)],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(br_m3b.returncode, 0)
            (bad_bp_snap / "boot.plan").write_bytes(orig_bp)
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
