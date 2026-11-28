"""ASan+UBSan unit and E2E tests for PR 3b native maintenance in `api`.

Exercises oc-root.c, oc-access.c, oc-txn.c, and oc-api.c directly against rooted
host fixtures with zero `backend.sh` fallback:
- Native NVRAM read/change and firmware/lock guards
- Native root_publish (install/update/remove, crash cuts, hardlink holds, staging guard)
- Native SSH public-key import validation against real ssh-keygen
- Full E2E Settings/USB maintenance (status:-, set uart/ssh, import, sealed boot.plan
  continuity into fast set, restart, crash-interrupted recover, RAM-resident uninstall)
- PR 3b usb_fence() acceptance of native-only (no backend.sh) pinned Settings sessions
"""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.host_bins import host_api

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
BOOT = "12345678-1234-1234-1234-123456789abc"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mode_str(path: Path) -> str:
    st = path.stat()
    return f"{st.st_mode & 0o7777:o}:{st.st_uid}:{st.st_gid}"


@unittest.skipUnless(
    shutil.which("clang") and shutil.which("ssh-keygen"),
    "Clang and ssh-keygen required",
)
class NativeMaintenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_bin = host_api()

    def _base_env(self, root: Path, extra: dict | None = None) -> dict:
        env = {
            **os.environ,
            "OC_HOST_ROOT": str(root),
            "OC_HOST_NONROOT": "1",
        }
        if extra:
            env.update(extra)
        return env

    def _make_min_root(self, tmp: Path) -> Path:
        root = tmp / "root"
        for rel in (
            "tmp/mnt/data_persist/open-connect",
            "tmp/mnt/data_persist/open-connect/keys",
            "tmp/mnt/data_persist/open-connect/snapshots",
            "tmp/open-connect",
            "tmp/open-connect/sessions",
            "usr/bin",
            "etc/ssh",
            "proc/self",
            "dev",
            "jci/lvds",
            "sys/class/nvram",
            "sys/devices/virtual/nvram/nv-config/keys",
        ):
            p = root / rel
            p.mkdir(parents=True, mode=0o700, exist_ok=True)
            p.chmod(0o700)
        (root / "sys/class/nvram/nv-config").symlink_to("../../devices/virtual/nvram/nv-config")
        (root / "dev/urandom").write_bytes(os.urandom(1024))
        mounts = (
            "rootfs / rootfs rw 0 0\n"
            "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
        )
        (root / "proc/self/mounts").write_text(mounts)
        (root / "proc/mounts").write_text(mounts)
        (root / "proc/uptime").write_text("500.00 100.00\n")
        (root / "jci/version.ini").write_text(
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\n'
            'JCI_SW_VER_PATCH="A"\n'
            'JCI_SW_FLAVOR="cmu150_NA"\n'
            + ("# padding line for realistic 15 KiB v74 version.ini\n" * 350)
        )
        (root / "jci/lvds/lvds_service").write_bytes(b"lvds-fixture\n")
        for ctl in ("add", "remove", "commit"):
            (root / "sys/class/nvram/nv-config" / ctl).write_text("")
        return root

    def test_native_nvram_read_change_and_guards(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._make_min_root(Path(td).resolve())
            lvds_dig = sha((root / "jci/lvds/lvds_service").read_bytes())
            pin_file = Path(td) / "pins.txt"
            pin_file.write_text(f"root/lvds-service={lvds_dig}\n")
            env = self._base_env(root, {"OC_HOST_PINS": str(pin_file)})
            nv_key = root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
            commit = root / "sys/class/nvram/nv-config/commit"

            def run_nv(*args, extra=None):
                return subprocess.run(
                    [str(self.api_bin), "--nvram", *args],
                    env={**env, **(extra or {})},
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            # Read absent -> change absent->disable -> disable->enable -> enable->absent
            self.assertEqual(run_nv("read").stdout, "absent\n")
            self.assertEqual(run_nv("change", "absent", "disable").returncode, 0)
            self.assertEqual(nv_key.read_text(), "disable\n")
            self.assertEqual(commit.read_text(), "\n")
            self.assertEqual(run_nv("read").stdout, "disable\n")

            # Wrong expected refused
            self.assertNotEqual(run_nv("change", "absent", "enable").returncode, 0)
            self.assertEqual(nv_key.read_text(), "disable\n")

            # disable -> enable -> absent
            self.assertEqual(run_nv("change", "disable", "enable").returncode, 0)
            self.assertEqual(nv_key.read_text(), "enable\n")
            self.assertEqual(run_nv("change", "enable", "absent").returncode, 0)
            self.assertFalse(nv_key.exists())

            # Bad firmware version refused
            orig_ver = (root / "jci/version.ini").read_bytes()
            (root / "jci/version.ini").write_text('JCI_SW_VER="OTHER"\n')
            self.assertNotEqual(run_nv("change", "absent", "disable").returncode, 0)
            (root / "jci/version.ini").write_bytes(orig_ver)

            # Tampered lvds_service refused
            (root / "jci/lvds/lvds_service").write_bytes(b"tampered\n")
            self.assertNotEqual(run_nv("change", "absent", "disable").returncode, 0)
            (root / "jci/lvds/lvds_service").write_bytes(b"lvds-fixture\n")

            # Held lockfile refused
            lock_path = root / "tmp/oc-lvds-setting.lock"
            lock_path.touch(mode=0o600)
            with lock_path.open("r+") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                self.assertNotEqual(run_nv("change", "absent", "disable").returncode, 0)

    def test_native_root_publish_cuts_holds_and_guards(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._make_min_root(Path(td).resolve())
            data = root / "tmp/mnt/data_persist/open-connect"
            env = self._base_env(root)
            rev = "a" * 32
            auto = root / "usr/bin/autostart"
            auto.write_bytes(b"original autostart bytes\n")
            auto.chmod(0o755)
            orig_h, orig_m = sha(auto.read_bytes()), mode_str(auto)

            src_dir = data / "snapshots/src"
            src_dir.mkdir(mode=0o700)
            new_bytes = b"updated autostart payload for native publish\n"
            (src_dir / "autostart").write_bytes(new_bytes)
            (src_dir / "autostart").chmod(0o600)

            def pub(
                target,
                src,
                mode,
                exp_h,
                exp_m,
                hold="-",
                hmode="-",
                retire="0",
                base="-",
                extra=None,
            ):
                return subprocess.run(
                    [
                        str(self.api_bin),
                        "--test-root-publish",
                        rev,
                        target,
                        src,
                        mode,
                        exp_h,
                        exp_m,
                        hold,
                        hmode,
                        retire,
                        base,
                        "unused",
                    ],
                    env={**env, **(extra or {})},
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            # Cut at partial copy: staging file left behind, staging guard catches it, retire cleans it
            p_part = pub(
                "usr/bin/autostart",
                "snapshots/src/autostart",
                orig_m,
                orig_h,
                orig_m,
                extra={"OC_BOOT_CUT": "root_publish_partial"},
            )
            self.assertNotEqual(p_part.returncode, 0)
            self.assertTrue((root / f"usr/bin/.open-connect-{rev}").exists())
            self.assertNotEqual(
                subprocess.run([str(self.api_bin), "--test-staging-guard"], env=env).returncode, 0
            )
            # Retire cleans verified prefix stage and restores ro,noatime
            self.assertEqual(
                pub(
                    "usr/bin/autostart",
                    "snapshots/src/autostart",
                    "-",
                    orig_h,
                    orig_m,
                    retire="1",
                ).returncode,
                0,
            )
            self.assertFalse((root / f"usr/bin/.open-connect-{rev}").exists())
            self.assertEqual(
                subprocess.run([str(self.api_bin), "--test-staging-guard"], env=env).returncode, 0
            )
            self.assertIn("ro,noatime", (root / "proc/self/mounts").read_text())

            # Foreign staging bytes refused without deleting them
            stage = root / f"usr/bin/.open-connect-{rev}"
            stage.write_bytes(b"foreign bytes not matching prefix")
            self.assertNotEqual(
                pub(
                    "usr/bin/autostart", "snapshots/src/autostart", orig_m, orig_h, orig_m
                ).returncode,
                0,
            )
            self.assertTrue(stage.exists())
            stage.unlink()

            # Cut after staging, then resume cleanly -> completes atomic rename and remounts ro
            p_stg = pub(
                "usr/bin/autostart",
                "snapshots/src/autostart",
                orig_m,
                orig_h,
                orig_m,
                extra={"OC_BOOT_CUT": "root_publish_staged"},
            )
            self.assertNotEqual(p_stg.returncode, 0)
            self.assertTrue(stage.exists())
            self.assertEqual(
                pub(
                    "usr/bin/autostart", "snapshots/src/autostart", orig_m, orig_h, orig_m
                ).returncode,
                0,
            )
            self.assertEqual(auto.read_bytes(), new_bytes)
            self.assertFalse(stage.exists())
            self.assertIn("ro,noatime", (root / "proc/self/mounts").read_text())

            # Remount failure leaves target untouched
            self.assertNotEqual(
                pub(
                    "usr/bin/autostart",
                    "snapshots/src/autostart",
                    orig_m,
                    orig_h,
                    orig_m,
                    extra={"OC_HOST_REMOUNT_FAIL": "1"},
                ).returncode,
                0,
            )

            # Selector install + removal (including root_publish_unlinked cut & idempotent absent)
            sel = root / "usr/bin/open-connect-boot-select"
            pkg_sel_dir = data / "packages/p1"
            pkg_sel_dir.mkdir(parents=True, mode=0o700)
            (pkg_sel_dir / "boot-select").write_bytes(b"selector-bin\n")
            sel_m = f"700:{os.getuid()}:{os.getgid()}"
            self.assertEqual(
                pub(
                    "usr/bin/open-connect-boot-select",
                    "packages/p1/boot-select",
                    sel_m,
                    "-",
                    "-",
                ).returncode,
                0,
            )
            self.assertEqual(sel.read_bytes(), b"selector-bin\n")
            sel_h = sha(sel.read_bytes())
            self.assertEqual(
                pub("usr/bin/open-connect-boot-select", "-", "-", sel_h, sel_m).returncode, 0
            )
            self.assertFalse(sel.exists())
            # Idempotent remove when already absent
            self.assertEqual(
                pub("usr/bin/open-connect-boot-select", "-", "-", "-", "-").returncode, 0
            )

    def test_native_access_key_import_validation(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td).resolve()
            root = self._make_min_root(tmp)
            data = root / "tmp/mnt/data_persist/open-connect"
            vol = root / "tmp/mnt/sda1"
            vol.mkdir(parents=True, mode=0o700)
            (root / "proc/self/mounts").write_text(
                (root / "proc/self/mounts").read_text() + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
            )
            key_path = tmp / "ecdsa_key"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ecdsa", "-b", "256", "-N", "", "-f", str(key_path)],
                check=True,
            )
            pub_bytes = key_path.with_suffix(".pub").read_bytes()
            parts = pub_bytes.split()
            canonical = b" ".join(parts[:2]) + b"\n"
            env = self._base_env(root, {"OC_HOST_SSH_KEYGEN": shutil.which("ssh-keygen")})

            def do_import():
                return subprocess.run(
                    [str(self.api_bin), "--test-key-import"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            # Missing key -> public_key_not_found
            r_miss = do_import()
            self.assertNotEqual(r_miss.returncode, 0)
            self.assertIn("public_key_not_found", r_miss.stderr)

            # Valid key with comment + CRLF -> canonicalized and published atomically
            (vol / "open-connect.pub").write_bytes(b" ".join(parts[:2]) + b" owner@cmu\r\n")
            r_ok = do_import()
            self.assertEqual(r_ok.returncode, 0, r_ok.stderr)
            kid = r_ok.stdout.strip()
            self.assertEqual(kid, sha(canonical))
            self.assertEqual((data / "keys" / f"{kid}.cmu").read_bytes(), canonical)
            self.assertEqual(do_import().stdout.strip(), kid)  # idempotent reuse
            self.assertEqual(list((data / "keys").glob(".new-*")), [])

            # Multiple volumes with keys -> multiple_public_keys
            vol2 = root / "tmp/mnt/sdb1"
            vol2.mkdir(parents=True, mode=0o700)
            (vol2 / "open-connect.pub").write_bytes(pub_bytes)
            r_multi = do_import()
            self.assertNotEqual(r_multi.returncode, 0)
            self.assertIn("multiple_public_keys", r_multi.stderr)
            (vol2 / "open-connect.pub").unlink()

            # Reject private key, multi-line, optioned, ed25519, malformed, oversized
            for bad in (
                key_path.read_bytes(),
                pub_bytes + pub_bytes,
                b'command="id" ' + pub_bytes,
                b"ssh-ed25519 AAAA\n",
                b"ssh-rsa AAAA\n",
                b"",
                b"x" * 8193,
            ):
                (vol / "open-connect.pub").write_bytes(bad)
                self.assertNotEqual(do_import().returncode, 0)

            # Weak 1024-bit RSA rejected
            rsa_weak = tmp / "rsa1024"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "rsa", "-b", "1024", "-N", "", "-f", str(rsa_weak)],
                check=True,
            )
            (vol / "open-connect.pub").write_bytes(rsa_weak.with_suffix(".pub").read_bytes())
            r_weak = do_import()
            self.assertNotEqual(r_weak.returncode, 0)
            self.assertIn("weak_public_key", r_weak.stderr)

            # Symlink rejected
            (vol / "open-connect.pub").unlink()
            (vol / "open-connect.pub").symlink_to(key_path.with_suffix(".pub"))
            self.assertNotEqual(do_import().returncode, 0)

            # Non-vfat mount rejected
            (vol / "open-connect.pub").unlink()
            (vol / "open-connect.pub").write_bytes(pub_bytes)
            (root / "proc/self/mounts").write_text(
                (root / "proc/self/mounts").read_text().replace("vfat", "ext4")
            )
            r_vfat = do_import()
            self.assertNotEqual(r_vfat.returncode, 0)
            self.assertIn("invalid_key_volume", r_vfat.stderr)

    def test_native_e2e_status_restart_uart_ssh_import_recover_uninstall(self):
        from tests.test_installer_boot_selection import NativeBootSelection

        NativeBootSelection.setUpClass()
        self.addCleanup(NativeBootSelection.tearDownClass)
        f = NativeBootSelection(
            "test_touch_disabled_stages_verified_executable_without_warning_or_base"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)

        # Populate access + selector + full package assets in rooted fixture.
        (f.root / "etc").mkdir(parents=True, exist_ok=True)
        (f.root / "etc/passwd").write_text("cmu:x:0:0:owner:/root:/bin/sh\n")
        (f.root / "proc/uptime").write_text("600.00 100.00\n")
        (f.root / "proc/mounts").write_text((f.root / "proc/self/mounts").read_text())
        nv_store = f.root / "sys/class/nvram/nv-config"
        for ctl in ("add", "remove", "commit"):
            (nv_store / ctl).write_text("")

        runlogin = f.root / "usr/bin/runlogin"
        stock_login = b"#!/bin/sh\nexec /bin/login\n"
        runlogin.write_bytes(stock_login)
        runlogin.chmod(0o755)
        opened_login = runlogin.open("rb")
        self.addCleanup(opened_login.close)
        login_inode = os.fstat(opened_login.fileno()).st_ino
        login_meta = mode_str(runlogin)

        sshd_cfg = f.root / "etc/ssh/sshd_config"
        sshd_cfg.parent.mkdir(parents=True, exist_ok=True)
        stock_sshd = (
            b"Port 36000\n"
            b"AuthorizedKeysFile /config-mfg/authorized_keys /owner/keys.%u\n"
            b"PasswordAuthentication no\n"
        )
        sshd_cfg.write_bytes(stock_sshd)
        sshd_cfg.chmod(0o644)
        sshd_meta = mode_str(sshd_cfg)

        # Stub sshd -t -f
        sshd_stub = f.root / "sshd-stub"
        sshd_stub.write_text('#!/bin/sh\ntest "$1" = -t && test "$2" = -f && test -f "$3"\n')
        sshd_stub.chmod(0o700)

        # Rebuild package with all needed UI/awk/console assets
        pkg_tmp = f.data / "packages/.new-nat"
        pkg_tmp.mkdir(mode=0o700)
        for p in sorted(f.package.iterdir()):
            if p.name != "files.sha256":
                (pkg_tmp / p.name).write_bytes(p.read_bytes())
                (pkg_tmp / p.name).chmod(p.stat().st_mode & 0o777)
        for extra in (
            "ui-profile.awk",
            "ui-modules.tsv",
            "system-hook.js",
            "base-logging.js",
            "console.sh",
        ):
            (pkg_tmp / extra).write_bytes((ASSETS / extra).read_bytes())
            (pkg_tmp / extra).chmod(0o600)
        old_pkg_id = f.package_id
        pkg_mf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(pkg_tmp.iterdir()))
        (pkg_tmp / "files.sha256").write_text(pkg_mf)
        (pkg_tmp / "files.sha256").chmod(0o600)
        f.package_id = sha(pkg_mf.encode())
        f.package = f.data / "packages" / f.package_id
        pkg_tmp.rename(f.package)
        comp_dst = f.data / "composed" / f.package_id
        shutil.copytree(f.composed, comp_dst)
        from tests.test_installer_preferences import InstallerPreferences

        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        for nm in ("index-on.html", "index-off.html"):
            (comp_dst / nm).write_text(idx_tpl)
            (comp_dst / nm).chmod(0o600)
        for nm, wcp in (
            ("sm-normal-on.conf", False),
            ("sm-normal-off.conf", False),
            ("sm-wcp-on.conf", True),
            ("sm-wcp-off.conf", True),
        ):
            (comp_dst / nm).write_text(InstallerPreferences().profile(wcp))
            (comp_dst / nm).chmod(0o600)
        f.manifest(comp_dst)
        f.composed = comp_dst
        # Copy boot-select into /usr/bin/open-connect-boot-select
        sel_bin = f.root / "usr/bin/open-connect-boot-select"
        sel_bin.write_bytes((f.package / "boot-select").read_bytes())
        sel_bin.chmod(0o700)
        sel_line = f"{sha(sel_bin.read_bytes())}|{mode_str(sel_bin)}|{f.package_id}\n"
        acc_line = f"0|0|-|{login_meta}|{sshd_meta}|{login_inode}\n"

        # Add access + selector to R_BASE and current snapshot, rebuild dependencies + boot.plan.
        base_work = f.data / "snapshots/.new-base"
        shutil.copytree(f.baseline, base_work)
        (base_work / "files.sha256").unlink()
        (base_work / "access").write_text(acc_line)
        (base_work / "runlogin").write_bytes(stock_login)
        (base_work / "sshd.conf").write_bytes(stock_sshd)
        (base_work / "selector").write_text("-\n")
        for p in base_work.iterdir():
            p.chmod(0o600)
        bmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(base_work.iterdir()))
        (base_work / "files.sha256").write_text(bmf)
        (base_work / "files.sha256").chmod(0o600)
        new_base_id = sha(bmf.encode())
        base_work.rename(f.data / "snapshots" / new_base_id)
        f.baseline = f.data / "snapshots" / new_base_id

        # Update record's R_BACKEND & R_BASE, update dependencies, seal current snapshot.
        new_deps = []
        for kind, folder in (("package", f.package), ("composed", f.composed)):
            mf_id = sha((folder / "files.sha256").read_bytes())
            for p in sorted(folder.iterdir()):
                if p.name != "files.sha256":
                    new_deps.append((sha(p.read_bytes()), f"{kind}-{f.package_id}/{p.name}"))
            new_deps.append((mf_id, f"{kind}-{f.package_id}/files.sha256"))
        for line in (f.snapshot / "dependencies").read_text().splitlines():
            d, k = line.split("  ", 1)
            if k.startswith(f"package-{old_pkg_id}/") or k.startswith(f"composed-{old_pkg_id}/"):
                continue
            new_deps.append((d, k))

        cur_work = f.data / "snapshots/.new-cur"
        shutil.copytree(f.snapshot, cur_work)
        (cur_work / "files.sha256").unlink()
        (cur_work / "boot.plan").unlink()
        (cur_work / "config").write_text(
            (cur_work / "config")
            .read_text()
            .replace(old_pkg_id, f.package_id)
            .replace(
                "service-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\n",
                "service-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n",
            )
        )
        (cur_work / "dependencies").write_text("".join(f"{d}  {k}\n" for d, k in new_deps))
        (cur_work / "access").write_text(acc_line)
        (cur_work / "runlogin").write_bytes(stock_login)
        (cur_work / "sshd.conf").write_bytes(stock_sshd)
        (cur_work / "selector").write_text(sel_line)
        for p in cur_work.iterdir():
            p.chmod(0o600)
        cmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(cur_work.iterdir()))
        (cur_work / "files.sha256").write_text(cmf)
        (cur_work / "files.sha256").chmod(0o600)
        cur_id = sha(cmf.encode())
        cur_work.rename(f.data / "snapshots" / cur_id)
        f.snapshot = f.data / "snapshots" / cur_id

        rec_f = (f.data / "record").read_text().strip().split("|")
        rec_f[3] = f.package_id
        rec_f[4] = new_base_id
        rec_f[5] = cur_id
        (f.data / "record").write_text("|".join(rec_f) + "\n")
        (f.data / "keys").mkdir(mode=0o700, exist_ok=True)

        # Build an 8-file native Settings boot session (NO backend.sh!).
        session = f.ram / "sessions/session-nat001"
        session.mkdir(parents=True, mode=0o700)
        tok = "b" * 32
        shutil.copyfile(f.package / "files.sha256", session / "files.sha256")
        shutil.copyfile(f.package / "VERSION", session / "VERSION")
        shutil.copyfile(f.package / "console.sh", session / "console.sh")
        (session / "token").write_text(tok + "\n")
        for p in session.iterdir():
            p.chmod(0o600)
        (f.ram / "lock").touch(mode=0o600)
        (f.ram / "selected").write_text(cur_id + "\n")
        (f.ram / "selected").chmod(0o600)
        (f.ram / "access-selected").write_text(cur_id + "\n")
        (f.ram / "access-selected").chmod(0o600)
        (f.ram / "boot-id").symlink_to(BOOT)
        (f.ram / "runtime").symlink_to(session)

        reboot_marker = f.root / "reboot-marker"
        env = f._host_env(
            {
                "PATH": f.build.name + os.pathsep + os.environ["PATH"],
                "OC_HOST_ROOT": str(f.root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(f.root / "no-wireless"),
                "OC_HOST_SSHD": str(sshd_stub),
                "OC_HOST_SSH_KEYGEN": shutil.which("ssh-keygen"),
                "OC_HOST_REBOOT_MARKER": str(reboot_marker),
            }
        )

        def call(rev, op, arg="-", exp="-", des="-", *, extra_env=None):
            proc = subprocess.run(
                [str(self.api_bin), "--handle", str(session), rev, op, arg, exp, des],
                env={**env, **(extra_env or {})},
                capture_output=True,
                text=True,
                timeout=20,
            )
            return proc, json.loads(proc.stdout)

        # 1) Full unlocked status audit (`status:-`): clean -> conflict=False; tampered -> conflict=True
        proc, st = call("-", "status", "-")
        self.assertEqual(proc.returncode, 0, (st, proc.stderr))
        self.assertTrue(st["ok"] and st["installed"] and not st["conflict"])
        self.assertEqual(st["uart"], 0)
        self.assertEqual(st["ssh"], 0)

        saved_auto = (f.root / "usr/bin/autostart").read_bytes()
        (f.root / "usr/bin/autostart").write_bytes(saved_auto + b"# drift\n")
        _, st_bad = call("-", "status", "-")
        self.assertTrue(st_bad["ok"] and st_bad["conflict"])
        (f.root / "usr/bin/autostart").write_bytes(saved_auto)

        # 2) Native `set uart 0->1`: installs console.sh, preserves runlogin hold & seals boot.plan!
        proc, r_u1 = call(cur_id, "set", "uart", "0", "1")
        self.assertEqual(proc.returncode, 0, (r_u1, proc.stderr))
        self.assertTrue(r_u1["ok"] and r_u1["uart"] == 1)
        u1_id = r_u1["revision"]
        self.assertEqual(runlogin.read_bytes(), (ASSETS / "console.sh").read_bytes())
        self.assertGreater(os.fstat(opened_login.fileno()).st_nlink, 0)
        self.assertTrue((f.root / f"usr/bin/.open-connect-runlogin-{login_inode}").exists())
        self.assertTrue((f.data / "snapshots" / u1_id / "boot.plan").is_file())
        self.assertEqual(f._run_helper("audit", str(f.root), u1_id).returncode, 0)

        # 2b) No-op `set uart 1->1` short-circuits before creating any .access-* work dir or txn
        proc, r_u1_noop = call(u1_id, "set", "uart", "1", "1")
        self.assertEqual(proc.returncode, 0, (r_u1_noop, proc.stderr))
        self.assertTrue(r_u1_noop["ok"] and r_u1_noop["revision"] == u1_id)
        self.assertEqual(list(f.data.glob(".access-*")), [])

        # 3) Immediate follow-up `set carplay-autoshow 0->1` succeeds natively (proves sealed boot.plan!)
        proc, r_w0 = call(u1_id, "set", "carplay-autoshow", "0", "1")
        self.assertEqual(proc.returncode, 0, (r_w0, proc.stderr))
        self.assertTrue(r_w0["ok"] and r_w0["carplayAutoshow"] == 1)
        w0_id = r_w0["revision"]
        self.assertEqual(f._run_helper("audit", str(f.root), w0_id).returncode, 0)

        # 4) Native `import` + `set ssh 0->1->0`: imports ECDSA key, updates sshd_config, restores cleanly
        vol = f.root / "tmp/mnt/sda1"
        vol.mkdir(parents=True, mode=0o700)
        (f.root / "proc/self/mounts").write_text(
            (f.root / "proc/self/mounts").read_text() + "/dev/sda1 /tmp/mnt/sda1 vfat rw 0 0\n"
        )
        kp = f.root / "owner_ecdsa"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ecdsa", "-b", "256", "-N", "", "-f", str(kp)], check=True
        )
        (vol / "open-connect.pub").write_bytes(kp.with_suffix(".pub").read_bytes())
        proc, r_imp = call(w0_id, "import", "-", "-", "-")
        self.assertEqual(proc.returncode, 0, (r_imp, proc.stderr))
        self.assertTrue(r_imp["ok"] and len(r_imp["key"]) == 64)
        imp_id = r_imp["revision"]

        # 4b) Re-importing the exact same public key short-circuits without a spurious txn
        proc, r_imp2 = call(imp_id, "import", "-", "-", "-")
        self.assertEqual(proc.returncode, 0, (r_imp2, proc.stderr))
        self.assertTrue(
            r_imp2["ok"] and r_imp2["revision"] == imp_id and r_imp2["key"] == r_imp["key"]
        )
        self.assertEqual(list(f.data.glob(".access-*")), [])

        proc, r_s1 = call(imp_id, "set", "ssh", "0", "1")
        self.assertEqual(proc.returncode, 0, (r_s1, proc.stderr))
        self.assertTrue(r_s1["ok"] and r_s1["ssh"] == 1)
        s1_id = r_s1["revision"]
        self.assertIn(f"/data_persist/open-connect/keys/{r_imp['key']}.%u", sshd_cfg.read_text())
        self.assertEqual(f._run_helper("audit", str(f.root), s1_id).returncode, 0)

        proc, r_s0 = call(s1_id, "set", "ssh", "1", "0")
        self.assertEqual(proc.returncode, 0, (r_s0, proc.stderr))
        self.assertTrue(r_s0["ok"] and r_s0["ssh"] == 0)
        self.assertEqual(sshd_cfg.read_bytes(), stock_sshd)
        s0_id = r_s0["revision"]

        # 5) Native `set uart 1->0`: restores stock runlogin with the EXACT same original inode!
        proc, r_u0 = call(s0_id, "set", "uart", "1", "0")
        self.assertEqual(proc.returncode, 0, (r_u0, proc.stderr))
        self.assertTrue(r_u0["ok"] and r_u0["uart"] == 0)
        u0_id = r_u0["revision"]
        self.assertEqual(runlogin.read_bytes(), stock_login)
        self.assertEqual(runlogin.stat().st_ino, login_inode)

        # 6) Native `restart`: writes reboot marker when clean, refuses on rw mount or drift
        proc, r_rb = call(u0_id, "restart")
        self.assertEqual(proc.returncode, 0, (r_rb, proc.stderr))
        self.assertEqual(r_rb, {"ok": True, "restarting": True})
        self.assertTrue(reboot_marker.exists())
        reboot_marker.unlink()

        orig_mounts = (f.root / "proc/self/mounts").read_text()
        (f.root / "proc/self/mounts").write_text(orig_mounts.replace("ro,noatime", "rw,noatime"))
        _, r_rw = call(u0_id, "restart")
        self.assertEqual(r_rw["error"], "root_mount_changed")
        (f.root / "proc/self/mounts").write_text(orig_mounts)

        # 7) Native `recover`: real mid-transaction crash cut during `set uart 0->1`
        #    (leaves pending OC1|set + staged .open-connect-<rev>-runlogin on root), then recover cleanly!
        p_cut = subprocess.run(
            [str(self.api_bin), "--handle", str(session), u0_id, "set", "uart", "0", "1"],
            env={**env, "OC_BOOT_CUT": "root_publish_staged"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(p_cut.returncode, 0)
        rec_p = (f.data / "record").read_text().strip().split("|")
        self.assertEqual(rec_p[1], "set")
        self.assertEqual(rec_p[6], u0_id)
        # Mutating op refuses while pending
        _, r_pend = call(rec_p[2], "restart")
        self.assertEqual(r_pend["error"], "operation_pending")
        # Recover finishes the interrupted publish, cleans staging, and seals boot.plan
        proc, r_rec = call(rec_p[2], "recover")
        self.assertEqual(proc.returncode, 0, (r_rec, proc.stderr))
        self.assertTrue(r_rec["ok"] and r_rec["uart"] == 1 and not r_rec["pending"])
        rec_id = r_rec["revision"]
        self.assertEqual(runlogin.read_bytes(), (ASSETS / "console.sh").read_bytes())
        self.assertTrue((f.data / "snapshots" / rec_id / "boot.plan").is_file())
        self.assertEqual(f._run_helper("audit", str(f.root), rec_id).returncode, 0)

        # 8) Native `uninstall`: verify cleanup_requires_ram on flash session, then uninstall from RAM
        flash_sess = f.data / "on-flash"
        flash_sess.mkdir(mode=0o700)
        shutil.copyfile(session / "VERSION", flash_sess / "VERSION")
        shutil.copyfile(session / "files.sha256", flash_sess / "files.sha256")
        saved_rec = (f.data / "record").read_text()
        rec_f = saved_rec.strip().split("|")
        rec_f[1] = "removed"
        rec_f[6] = "-"
        rec_f[7] = "-"
        (f.data / "record").write_text("|".join(rec_f) + "\n")
        (f.ram / "runtime").unlink()
        (f.ram / "runtime").symlink_to(flash_sess)
        p_fl = subprocess.run(
            [str(self.api_bin), "--handle", str(flash_sess), rec_f[5], "uninstall", "-", "-", "-"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(json.loads(p_fl.stdout)["error"], "cleanup_requires_ram")
        (f.data / "record").write_text(saved_rec)
        (f.ram / "runtime").unlink()
        (f.ram / "runtime").symlink_to(session)
        shutil.rmtree(flash_sess)

        # 8b) Unsupported op (install) on 8-file Settings session (NO backend.sh) returns JSON error, never empty HTTP 200
        tok = "a" * 32
        (session / "token").write_text(tok + "\n")
        (session / "token").chmod(0o600)
        body = f"{tok}|{rec_id}|install|-|-|-"
        http_req = (
            f"POST /control HTTP/1.0\r\nContent-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n\r\n{body}"
        )
        p_http = subprocess.run(
            [str(self.api_bin), str(session / "token"), str(session / "backend.sh")],
            input=http_req,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertIn("200 OK", p_http.stdout)
        http_json = json.loads(p_http.stdout.split("\n\n", 1)[1])
        self.assertEqual(http_json, {"ok": False, "error": "invalid_request"})

        proc, r_un = call(rec_id, "uninstall")
        self.assertEqual(proc.returncode, 0, (r_un, proc.stderr))
        self.assertTrue(r_un["ok"] and not r_un["installed"] and r_un["restart"])
        self.assertFalse(f.data.exists())
        self.assertEqual(runlogin.read_bytes(), stock_login)
        self.assertEqual(runlogin.stat().st_ino, login_inode)
        self.assertEqual(sshd_cfg.read_bytes(), stock_sshd)
        self.assertFalse(sel_bin.exists())
        self.assertEqual(list((f.root / "usr/bin").glob(".open-connect-*")), [])
        self.assertFalse((nv_store / "keys/lvds_speed_restriction").exists())
        self.assertIn("ro,noatime", (f.root / "proc/self/mounts").read_text())

        # 9) Empty state dir `recover` removes empty D cleanly
        f.data.mkdir(mode=0o700)
        proc, r_emp = call("-", "recover")
        self.assertEqual(proc.returncode, 0, (r_emp, proc.stderr))
        self.assertTrue(r_emp["ok"] and not r_emp["pending"])
        self.assertFalse(f.data.exists())

    def test_adversarial_regressions_nvram_commit_pins_integrity_and_leases(self):
        """Regression suite for Neon R1 findings #1-#7, #10-#11, #14."""
        from tests.test_installer_boot_selection import NativeBootSelection

        NativeBootSelection.setUpClass()
        self.addCleanup(NativeBootSelection.tearDownClass)
        f = NativeBootSelection(
            "test_touch_disabled_stages_verified_executable_without_warning_or_base"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)

        (f.root / "etc").mkdir(parents=True, exist_ok=True)
        (f.root / "etc/passwd").write_text("cmu:x:0:0:owner:/root:/bin/sh\n")
        (f.root / "proc/uptime").write_text("100.00 0.00\n")
        (f.root / "proc/mounts").write_text((f.root / "proc/self/mounts").read_text())
        nv_store = f.root / "sys/class/nvram/nv-config"
        for ctl in ("add", "remove", "commit"):
            (nv_store / ctl).write_text("")
        for _, tpath, tdata, _ in f.TOUCH_INPUTS:
            f.put(tpath, tdata)
        for _, bpath, bdata, _ in f.BASE_INPUTS:
            f.put(bpath, bdata)
        vui_dir = f.root / "jci/vui/plugins"
        vui_dir.mkdir(parents=True, exist_ok=True)
        ui_lines = (ASSETS / "ui-modules.tsv").read_text().splitlines()
        vui_pins = [
            ln.split("\t")
            for ln in ui_lines
            if ln and not ln.startswith("#") and ln.startswith("vui\t")
        ][:40]
        for row in vui_pins:
            (vui_dir / row[1]).write_bytes(b"vui-plugin-" + row[1].encode() + b"\n")
        pin_overrides = {
            f"base/vui/{row[1]}": sha((vui_dir / row[1]).read_bytes()) for row in vui_pins
        }

        runlogin = f.root / "usr/bin/runlogin"
        stock_login = b"#!/bin/sh\nexec /bin/login\n"
        runlogin.write_bytes(stock_login)
        runlogin.chmod(0o755)
        opened_login = runlogin.open("rb")
        self.addCleanup(opened_login.close)
        login_inode = os.fstat(opened_login.fileno()).st_ino
        login_meta = mode_str(runlogin)

        sshd_cfg = f.root / "etc/ssh/sshd_config"
        sshd_cfg.parent.mkdir(parents=True, exist_ok=True)
        stock_sshd = (
            b"Port 36000\n"
            b"AuthorizedKeysFile /config-mfg/authorized_keys /owner/keys.%u\n"
            b"PasswordAuthentication no\n"
        )
        sshd_cfg.write_bytes(stock_sshd)
        sshd_cfg.chmod(0o644)
        sshd_meta = mode_str(sshd_cfg)

        sshd_stub = f.root / "sshd-stub"
        sshd_stub.write_text('#!/bin/sh\ntest "$1" = -t && test "$2" = -f && test -f "$3"\n')
        sshd_stub.chmod(0o700)

        pkg_tmp = f.data / "packages/.new-reg"
        pkg_tmp.mkdir(mode=0o700)
        for p in sorted(f.package.iterdir()):
            if p.name != "files.sha256":
                (pkg_tmp / p.name).write_bytes(p.read_bytes())
                (pkg_tmp / p.name).chmod(p.stat().st_mode & 0o777)
        for extra in (
            "ui-profile.awk",
            "system-hook.js",
            "base-logging.js",
            "console.sh",
            "services.tsv",
        ):
            (pkg_tmp / extra).write_bytes((ASSETS / extra).read_bytes())
            (pkg_tmp / extra).chmod(0o600)
        patched_ui = []
        for ln in ui_lines:
            if ln and not ln.startswith("#") and ln.startswith("vui\t"):
                parts = ln.split("\t")
                parts[3] = pin_overrides.get(f"base/vui/{parts[1]}", parts[3])
                patched_ui.append("\t".join(parts))
            else:
                patched_ui.append(ln)
        (pkg_tmp / "ui-modules.tsv").write_text("\n".join(patched_ui) + "\n")
        (pkg_tmp / "ui-modules.tsv").chmod(0o600)

        old_pkg_id = f.package_id
        pkg_mf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(pkg_tmp.iterdir()))
        (pkg_tmp / "files.sha256").write_text(pkg_mf)
        (pkg_tmp / "files.sha256").chmod(0o600)
        f.package_id = sha(pkg_mf.encode())
        f.package = f.data / "packages" / f.package_id
        pkg_tmp.rename(f.package)
        comp_dst = f.data / "composed" / f.package_id
        shutil.copytree(f.composed, comp_dst)
        from tests.test_installer_preferences import InstallerPreferences

        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        for nm in ("index-on.html", "index-off.html"):
            (comp_dst / nm).write_text(idx_tpl)
            (comp_dst / nm).chmod(0o600)
        for nm, wcp in (
            ("sm-normal-on.conf", False),
            ("sm-normal-off.conf", False),
            ("sm-wcp-on.conf", True),
            ("sm-wcp-off.conf", True),
        ):
            (comp_dst / nm).write_text(InstallerPreferences().profile(wcp))
            (comp_dst / nm).chmod(0o600)
        f.manifest(comp_dst)
        f.composed = comp_dst

        sel_bin = f.root / "usr/bin/open-connect-boot-select"
        sel_bin.write_bytes((f.package / "boot-select").read_bytes())
        sel_bin.chmod(0o700)
        sel_line = f"{sha(sel_bin.read_bytes())}|{mode_str(sel_bin)}|{f.package_id}\n"
        acc_line = f"0|0|-|{login_meta}|{sshd_meta}|{login_inode}\n"

        base_work = f.data / "snapshots/.new-base"
        shutil.copytree(f.baseline, base_work)
        (base_work / "files.sha256").unlink()
        (base_work / "access").write_text(acc_line)
        (base_work / "runlogin").write_bytes(stock_login)
        (base_work / "sshd.conf").write_bytes(stock_sshd)
        (base_work / "selector").write_text("-\n")
        for p in base_work.iterdir():
            p.chmod(0o600)
        bmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(base_work.iterdir()))
        (base_work / "files.sha256").write_text(bmf)
        (base_work / "files.sha256").chmod(0o600)
        base_id = sha(bmf.encode())
        base_dir = f.data / "snapshots" / base_id
        base_work.rename(base_dir)
        f.baseline = base_dir

        new_deps = []
        for kind, folder in (("package", f.package), ("composed", f.composed)):
            mf_id = sha((folder / "files.sha256").read_bytes())
            for p in sorted(folder.iterdir()):
                if p.name != "files.sha256":
                    new_deps.append((sha(p.read_bytes()), f"{kind}-{f.package_id}/{p.name}"))
            new_deps.append((mf_id, f"{kind}-{f.package_id}/files.sha256"))
        for line in (f.snapshot / "dependencies").read_text().splitlines():
            d, k = line.split("  ", 1)
            if k.startswith(f"package-{old_pkg_id}/") or k.startswith(f"composed-{old_pkg_id}/"):
                continue
            new_deps.append((d, k))

        cur_work = f.data / "snapshots/.new-cur"
        shutil.copytree(f.snapshot, cur_work)
        (cur_work / "files.sha256").unlink()
        (cur_work / "boot.plan").unlink()
        (cur_work / "config").write_text(
            (cur_work / "config")
            .read_text()
            .replace(old_pkg_id, f.package_id)
            .replace("base=0\n", "base=1\n")
            .replace("wireless=1\n", "wireless=0\n")
            .replace(
                "service-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\n",
                "service-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n",
            )
        )
        (cur_work / "dependencies").write_text("".join(f"{d}  {k}\n" for d, k in new_deps))
        (cur_work / "access").write_text(acc_line)
        (cur_work / "runlogin").write_bytes(stock_login)
        (cur_work / "sshd.conf").write_bytes(stock_sshd)
        (cur_work / "selector").write_text(sel_line)
        (cur_work / "vui-plugins.list").write_text("".join(f"{row[1]}\n" for row in vui_pins))
        for p in cur_work.iterdir():
            p.chmod(0o600)
        cmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(cur_work.iterdir()))
        (cur_work / "files.sha256").write_text(cmf)
        (cur_work / "files.sha256").chmod(0o600)
        cur_id = sha(cmf.encode())
        cur_work.rename(f.data / "snapshots" / cur_id)
        f.snapshot = f.data / "snapshots" / cur_id

        rec_f = (f.data / "record").read_text().strip().split("|")
        rec_f[3] = f.package_id
        rec_f[4] = base_id
        rec_f[5] = cur_id
        (f.data / "record").write_text("|".join(rec_f) + "\n")
        (f.data / "keys").mkdir(mode=0o700, exist_ok=True)

        session = f.ram / "sessions/session-reg001"
        session.mkdir(parents=True, mode=0o700)
        for nm in ("VERSION", "files.sha256", "console.sh"):
            shutil.copyfile(f.package / nm, session / nm)
            (session / nm).chmod(0o600)
        (f.ram / "runtime").symlink_to(session)
        (f.ram / "selected").write_text(cur_id + "\n")
        (f.ram / "selected").chmod(0o600)
        (f.ram / "lock").write_text("")
        (f.ram / "lock").chmod(0o600)
        env = f._host_env(
            {
                "PATH": f.build.name + os.pathsep + os.environ["PATH"],
                "OC_HOST_ROOT": str(f.root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SSHD": str(sshd_stub),
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(f.root / "no-wireless"),
            }
        )

        def call(rev, op, arg="-", exp="-", des="-", extra_env=None, sdir=session):
            p = subprocess.run(
                [str(self.api_bin), "--handle", str(sdir), rev, op, arg, exp, des],
                env={**env, **(extra_env or {})},
                capture_output=True,
                text=True,
                timeout=20,
            )
            return p, json.loads(p.stdout)

        # Seal cur_id natively with base=1 via uart 0->1->0
        p_s1, r_s1 = call(cur_id, "set", "uart", "0", "1")
        self.assertEqual(p_s1.returncode, 0, (r_s1, p_s1.stderr))
        p_s0, r_s0 = call(r_s1["revision"], "set", "uart", "1", "0")
        self.assertEqual(p_s0.returncode, 0, (r_s0, p_s0.stderr))
        cur_id = r_s0["revision"]
        (f.ram / "selected").write_text(cur_id + "\n")

        # (A) Finding #1: post-write / pre-commit NVRAM failure -> recover MUST still write commit!
        p_fail, r_fail = call(cur_id, "set", "touch", "1", "0", {"OC_HOST_NVRAM_FAIL": "after"})
        self.assertEqual(r_fail["error"], "nvram_commit_failed")
        self.assertFalse((nv_store / "keys/lvds_speed_restriction").exists())
        (nv_store / "commit").write_text("")
        rec_p = (f.data / "record").read_text().strip().split("|")
        self.assertEqual(rec_p[1], "set")
        p_rec, r_rec = call(rec_p[2], "recover")
        self.assertEqual(p_rec.returncode, 0, (r_rec, p_rec.stderr))
        self.assertTrue(r_rec["ok"] and r_rec["touch"] == 0 and not r_rec["pending"])
        self.assertEqual((nv_store / "commit").read_text(), "\n")
        cur_id = r_rec["revision"]

        # (F) Finding #3: touch=2 -> 0 recovery with drifted touch pins succeeds NATIVELY without backend.sh
        p_t2, r_t2 = call(cur_id, "set", "touch", "0", "2")
        self.assertEqual(p_t2.returncode, 0, (r_t2, p_t2.stderr))
        t2_id = r_t2["revision"]
        touch_pin = f.root / "jci/devices/svc-com-jci-cpp-devices.so"
        orig_tp = touch_pin.read_bytes()
        # (F2) Neon R2 Blocker #1: interrupt set uart 0->1 while touch=2, drift touch pin,
        # recover MUST downgrade touch=2->0 AND re-render sm-*.conf without touch-disable.so!
        p_cut2 = subprocess.run(
            [str(self.api_bin), "--handle", str(session), t2_id, "set", "uart", "0", "1"],
            env={**env, "OC_BOOT_CUT": "root_publish_staged"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(p_cut2.returncode, 0)
        rec_p2 = (f.data / "record").read_text().strip().split("|")
        self.assertEqual(rec_p2[1], "set")
        touch_pin.write_bytes(b"drifted-devices-so\n")
        p_rec2, r_rec2 = call(rec_p2[2], "recover")
        self.assertEqual(p_rec2.returncode, 0, (r_rec2, p_rec2.stderr))
        self.assertTrue(
            r_rec2["ok"] and r_rec2["touch"] == 0 and r_rec2["uart"] == 1 and not r_rec2["pending"],
            r_rec2,
        )
        dg_id = r_rec2["revision"]
        dg_snap = f.data / "snapshots" / dg_id
        self.assertIn("\ntouch=0\n", (dg_snap / "config").read_text())
        self.assertNotIn("touch-disable.so", (dg_snap / "sm-normal.conf").read_text())
        self.assertNotIn("touch-disable.so", (dg_snap / "sm-wcp.conf").read_text())
        self.assertTrue((dg_snap / "boot.plan").is_file())
        # Restore touch_pin and uart=0, then also verify direct native touch=2 -> 0 drift recovery (sp_rc==95)
        touch_pin.write_bytes(orig_tp)
        p_u0, r_u0 = call(dg_id, "set", "uart", "1", "0")
        self.assertEqual(p_u0.returncode, 0, (r_u0, p_u0.stderr))
        p_t2b, r_t2b = call(r_u0["revision"], "set", "touch", "0", "2")
        self.assertEqual(p_t2b.returncode, 0, (r_t2b, p_t2b.stderr))
        touch_pin.write_bytes(b"drifted-devices-so\n")
        p_t0, r_t0 = call(r_t2b["revision"], "set", "touch", "2", "0")
        self.assertEqual(p_t0.returncode, 0, (r_t0, p_t0.stderr))
        self.assertTrue(r_t0["ok"] and r_t0["touch"] == 0 and not r_t0["pending"])
        cur_id = r_t0["revision"]
        self.assertNotIn(
            "touch-disable.so", (f.data / "snapshots" / cur_id / "sm-normal.conf").read_text()
        )
        self.assertTrue((f.data / "snapshots" / cur_id / "boot.plan").is_file())
        touch_pin.write_bytes(orig_tp)

        # (F3) Neon R2 Blocker #3: OC_API_FALLBACK with missing absolute argv[2] returns backend_unavailable JSON
        tok_path = session / "alt-tok"
        tok_val = "c" * 32
        tok_path.write_text(tok_val + "\n")
        tok_path.chmod(0o600)
        fb_body = f"{tok_val}|-|status|settings|-|-"
        fb_req = (
            f"POST /control HTTP/1.0\r\nContent-Type: text/plain\r\n"
            f"Content-Length: {len(fb_body)}\r\n\r\n{fb_body}"
        )
        p_fb = subprocess.run(
            [str(self.api_bin), str(tok_path), str(session / "missing-backend.sh")],
            input=fb_req,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertIn("200 OK", p_fb.stdout)
        self.assertEqual(
            json.loads(p_fb.stdout.split("\n\n", 1)[1]),
            {"ok": False, "error": "backend_unavailable"},
        )
        tok_path.unlink()

        # (B) Finding #7: base=1 pin drift must refuse BEFORE mutating rootfs or record on set uart
        base_pin = f.root / "config/common/log/settings.txt"
        orig_base = base_pin.read_bytes()
        base_pin.write_bytes(b"drifted-base\n")
        _, r_drift = call(cur_id, "set", "uart", "0", "1")
        self.assertEqual(r_drift["error"], "base_inputs_changed")
        self.assertEqual((f.data / "record").read_text().strip().split("|")[1], "active")
        self.assertEqual(runlogin.read_bytes(), stock_login)
        base_pin.write_bytes(orig_base)

        # (C) Finding #11: tampered session console.sh must be refused on set uart 0->1
        orig_console = (session / "console.sh").read_bytes()
        (session / "console.sh").write_bytes(b"#!/bin/sh\necho tampered\n")
        _, r_tc = call(cur_id, "set", "uart", "0", "1")
        self.assertEqual(r_tc["error"], "access_plan_failed")
        (session / "console.sh").write_bytes(orig_console)

        # (G) Finding #4: USB retained lease rejects stale revision & out-of-range deadline
        usb_sess = f.ram / "sessions/session-usb999"
        usb_sess.mkdir(parents=True, mode=0o700)
        shutil.copyfile(f.package / "VERSION", usb_sess / "VERSION")
        (usb_sess / "closed").write_text("")
        (f.ram / "usb-runtime").symlink_to(usb_sess)
        (usb_sess / "admitted").symlink_to(f"OCUSB1|15000|{'0' * 64}")
        _, r_sr = call(cur_id, "restart", sdir=usb_sess)
        self.assertEqual(r_sr["error"], "session_closed")
        (usb_sess / "admitted").unlink()
        (usb_sess / "admitted").symlink_to(f"OCUSB1|99999|{cur_id}")
        _, r_ed = call(cur_id, "restart", sdir=usb_sess)
        self.assertEqual(r_ed["error"], "session_closed")
        (usb_sess / "admitted").unlink()
        (usb_sess / "admitted").symlink_to(f"OCUSB1|15000|{cur_id}")
        p_ok, r_ok = call(cur_id, "restart", sdir=usb_sess)
        self.assertEqual(p_ok.returncode, 0, (r_ok, p_ok.stderr))
        self.assertEqual(r_ok, {"ok": True, "restarting": True})

        # (D) Finding #5: corrupt profile file (index.html) in cur snapshot refused by status:- and set uart
        idx_file = f.data / "snapshots" / cur_id / "index.html"
        orig_idx = idx_file.read_bytes()
        idx_file.write_bytes(b"corrupted-index\n")
        _, r_st = call("-", "status", "-")
        self.assertTrue(
            r_st.get("error") == "invalid_snapshot" or (r_st.get("ok") and r_st.get("conflict")),
            r_st,
        )
        _, r_bu = call(cur_id, "set", "uart", "0", "1")
        self.assertEqual(r_bu["error"], "state_changed")
        idx_file.write_bytes(orig_idx)

        # (E) Finding #2: corrupt R_BASE must fail closed in status:- (conflict=True)
        base_cfg = base_dir / "config"
        orig_bcfg = base_cfg.read_bytes()
        base_cfg.write_bytes(b"corrupt-base\n")
        _, r_cb = call("-", "status", "-")
        self.assertTrue(r_cb["ok"] and r_cb["conflict"])
        base_cfg.write_bytes(orig_bcfg)

        # (H) Finding #6: stock snapshot with non-'-' selector refused
        bad_sel_dir = f.data / "snapshots/badsel"
        shutil.copytree(base_dir, bad_sel_dir)
        (bad_sel_dir / "files.sha256").unlink()
        (bad_sel_dir / "selector").write_text(sel_line)
        bad_mf = "".join(
            f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(bad_sel_dir.iterdir())
        )
        (bad_sel_dir / "files.sha256").write_text(bad_mf)
        (bad_sel_dir / "files.sha256").chmod(0o600)
        bad_sel_id = sha(bad_mf.encode())
        bad_sel_dir.rename(f.data / "snapshots" / bad_sel_id)
        rec_orig = (f.data / "record").read_text()
        rf = rec_orig.strip().split("|")
        rf[4] = bad_sel_id
        (f.data / "record").write_text("|".join(rf) + "\n")
        _, r_bs = call("-", "status", "-")
        self.assertTrue(r_bs["ok"] and r_bs["conflict"])
        (f.data / "record").write_text(rec_orig)

        # (I) stale_setting compare-and-swap refusals on both access (uart) and prefs (warning)
        p_su, r_su = call(cur_id, "set", "uart", "1", "0")
        self.assertNotEqual(p_su.returncode, 0)
        self.assertEqual(r_su["error"], "stale_setting")
        cur_warn = (
            "1"
            if "\nwarning=1\n" in (f.data / "snapshots" / cur_id / "config").read_text()
            else "0"
        )
        stale_warn = "0" if cur_warn == "1" else "1"
        p_sw, r_sw = call(cur_id, "set", "warning", stale_warn, cur_warn)
        self.assertNotEqual(p_sw.returncode, 0)
        self.assertEqual(r_sw["error"], "stale_setting")

        # (J) completion_unavailable on USB session and on Settings session with mismatched boot ID
        p_cu1, r_cu1 = call("-", "status", "completion", sdir=usb_sess)
        self.assertNotEqual(p_cu1.returncode, 0)
        self.assertEqual(r_cu1["error"], "completion_unavailable")
        (f.ram / "boot-id").write_text(BOOT + "\n")
        (f.ram / "boot-id").chmod(0o600)
        p_cu2, r_cu2 = call("-", "status", "completion")
        self.assertNotEqual(p_cu2.returncode, 0)
        self.assertEqual(r_cu2["error"], "completion_unavailable")

        # (K) oc_transaction_reconcile drift refusals: dependencies_changed, nvram_changed,
        #     access_changed, selector_changed, and startup_stage_changed
        p_cut3 = subprocess.run(
            [str(self.api_bin), "--handle", str(session), cur_id, "set", "uart", "0", "1"],
            env={**env, "OC_BOOT_CUT": "root_publish_staged"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(p_cut3.returncode, 0)
        rec_p3 = (f.data / "record").read_text().strip().split("|")
        self.assertEqual(rec_p3[1], "set")

        root_idx = f.root / "jci/gui/index.html"
        saved_root_idx = root_idx.read_bytes()
        root_idx.write_bytes(b"drifted-root-index\n")
        p_dc, r_dc = call(rec_p3[2], "recover")
        root_idx.write_bytes(saved_root_idx)
        self.assertNotEqual(p_dc.returncode, 0)
        self.assertEqual(r_dc["error"], "dependencies_changed")

        nv_key = nv_store / "keys/lvds_speed_restriction"
        nv_key.write_text("enable\n")
        p_nc, r_nc = call(rec_p3[2], "recover")
        nv_key.unlink()
        self.assertNotEqual(p_nc.returncode, 0)
        self.assertEqual(r_nc["error"], "nvram_changed")

        saved_login = runlogin.read_bytes()
        runlogin.write_bytes(b"#!/bin/sh\n# third unknown login\n")
        p_ac, r_ac = call(rec_p3[2], "recover")
        runlogin.write_bytes(saved_login)
        self.assertNotEqual(p_ac.returncode, 0)
        self.assertEqual(r_ac["error"], "access_changed")

        saved_sel_bin = sel_bin.read_bytes()
        sel_bin.write_bytes(b"drifted-boot-select\n")
        p_sc, r_sc = call(rec_p3[2], "recover")
        sel_bin.write_bytes(saved_sel_bin)
        self.assertNotEqual(p_sc.returncode, 0)
        self.assertEqual(r_sc["error"], "selector_changed")

        p_rc3, r_rc3 = call(rec_p3[2], "recover")
        self.assertEqual(p_rc3.returncode, 0, (r_rc3, p_rc3.stderr))
        cur_id = r_rc3["revision"]
        (f.ram / "selected").write_text(cur_id + "\n")

        # startup_stage_changed on touch=2 drift rollback inside oc_transaction_reconcile
        p_t2c, r_t2c = call(cur_id, "set", "touch", "0", "2")
        self.assertEqual(p_t2c.returncode, 0, (r_t2c, p_t2c.stderr))
        t2c_id = r_t2c["revision"]
        p_cut4 = subprocess.run(
            [str(self.api_bin), "--handle", str(session), t2c_id, "set", "uart", "1", "0"],
            env={**env, "OC_BOOT_CUT": "root_publish_staged"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(p_cut4.returncode, 0)
        rec_p4 = (f.data / "record").read_text().strip().split("|")
        touch_pin.write_bytes(b"drifted-devices-so\n")
        cur_stage = f.root / f"usr/bin/.open-connect-{rec_p4[2]}"
        saved_stage = cur_stage.read_bytes() if cur_stage.exists() else None
        cur_stage.write_bytes(b"tampered-stage\n")
        p_ss, r_ss = call(rec_p4[2], "recover")
        if saved_stage is None:
            cur_stage.unlink()
        else:
            cur_stage.write_bytes(saved_stage)
        touch_pin.write_bytes(orig_tp)
        self.assertNotEqual(p_ss.returncode, 0)
        self.assertEqual(r_ss["error"], "startup_stage_changed")
        p_rc4, r_rc4 = call(rec_p4[2], "recover")
        self.assertEqual(p_rc4.returncode, 0, (r_rc4, p_rc4.stderr))
        cur_id = r_rc4["revision"]
        (f.ram / "selected").write_text(cur_id + "\n")

        # (L) oc_mounts_mode rejects /tmp/mnt/data_persist/open-connect/* before uninstall,
        #     and oc_uninstall_cleanup refuses cleanup_mount_present and startup_stage_changed.
        mounts_path = f.root / "proc/self/mounts"
        orig_mounts = mounts_path.read_text()
        mounts_path.write_text(
            orig_mounts + "tmpfs /tmp/mnt/data_persist/open-connect/packages tmpfs rw 0 0\n"
        )
        p_rm, r_rm = call(cur_id, "uninstall")
        self.assertNotEqual(p_rm.returncode, 0)
        self.assertEqual(r_rm["error"], "root_mount_changed")

        mounts_path.write_text(orig_mounts + f"tmpfs {f.data}/packages tmpfs rw 0 0\n")
        p_um, r_um = call(cur_id, "uninstall")
        mounts_path.write_text(orig_mounts)
        self.assertNotEqual(p_um.returncode, 0)
        self.assertEqual(r_um["error"], "cleanup_mount_present")
        rec_rem = (f.data / "record").read_text().strip().split("|")
        self.assertEqual(rec_rem[1], "removed")

        stray_stage = f.root / "usr/bin/.open-connect-foreign"
        stray_stage.write_bytes(b"stray\n")
        p_us, r_us = call(rec_rem[5], "uninstall")
        stray_stage.unlink()
        self.assertNotEqual(p_us.returncode, 0)
        self.assertEqual(r_us["error"], "startup_stage_changed")

        p_fin, r_fin = call(rec_rem[5], "uninstall")
        self.assertEqual(p_fin.returncode, 0, (r_fin, p_fin.stderr))
        self.assertTrue(r_fin["ok"] and not r_fin["installed"], r_fin)
        self.assertFalse(f.data.exists())

    def test_usb_fence_accepts_native_only_pinned_settings_session(self):
        # Native C oc_usb_fence() in api validates active Settings session on USB mutating ops.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            ram = root / "tmp/open-connect"
            data = root / "tmp/mnt/data_persist/open-connect"
            settings_sess = ram / "sessions/session-nat002"
            usb_sess = ram / "sessions/session-usb002"
            for d in (ram, data / "packages", data / "snapshots", settings_sess, usb_sess):
                d.mkdir(parents=True, mode=0o700)
            for d in (ram, ram / "sessions", data, settings_sess, usb_sess):
                d.chmod(0o700)
            (ram / "lock").write_bytes(b"")
            (ram / "lock").chmod(0o600)
            pkg_tmp = data / "packages/.pkg"
            pkg_tmp.mkdir(mode=0o700)
            (pkg_tmp / "api").write_bytes(b"native-api-bytes\n")
            (pkg_tmp / "api").chmod(0o700)
            (pkg_tmp / "VERSION").write_bytes((ASSETS / "VERSION").read_bytes())
            (pkg_tmp / "VERSION").chmod(0o600)
            (pkg_tmp / "services.tsv").write_bytes((ASSETS / "services.tsv").read_bytes())
            (pkg_tmp / "services.tsv").chmod(0o600)
            pmf = "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(pkg_tmp.iterdir()))
            (pkg_tmp / "files.sha256").write_text(pmf)
            (pkg_tmp / "files.sha256").chmod(0o600)
            pkg_id = sha(pmf.encode())
            pkg_tmp.rename(data / "packages" / pkg_id)

            snap_tmp = data / "snapshots/.s"
            snap_tmp.mkdir(mode=0o700)
            cfg = (
                f"OC2\nbase=0\ncarplay-autoshow=0\nmetadata=755:{os.getuid()}:{os.getgid()}\n"
                f"nvram=absent\npackage={pkg_id}\nservice-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n"
                "touch=0\nwarning=0\nwireless=0\n"
            )
            (snap_tmp / "config").write_text(cfg)
            (snap_tmp / "config").chmod(0o600)
            smf = f"{sha(cfg.encode())}  config\n"
            (snap_tmp / "files.sha256").write_text(smf)
            (snap_tmp / "files.sha256").chmod(0o600)
            snap_id = sha(smf.encode())
            snap_tmp.rename(data / "snapshots" / snap_id)

            shutil.copyfile(
                data / "packages" / pkg_id / "files.sha256", settings_sess / "files.sha256"
            )
            shutil.copyfile(data / "packages" / pkg_id / "api", settings_sess / "api")
            (settings_sess / "api").chmod(0o700)
            (usb_sess / "VERSION").write_bytes((ASSETS / "VERSION").read_bytes())
            (ram / "selected").write_text(snap_id + "\n")
            (ram / "selected").chmod(0o600)
            (ram / "runtime").symlink_to(settings_sess)
            (ram / "usb-runtime").symlink_to(usb_sess)
            (data / "record").write_text(
                f"OC1|active|{'1' * 32}|{pkg_id}|{snap_id}|{snap_id}|-|-|-|3|-|-|-\n"
            )
            (data / "record").chmod(0o600)

            fence_env = {
                **os.environ,
                "OC_HOST_ROOT": str(root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(root / "no-wireless"),
            }

            def run_fence_op():
                proc = subprocess.run(
                    [
                        str(self.api_bin),
                        "--handle",
                        str(usb_sess),
                        snap_id,
                        "recover",
                        "-",
                        "-",
                        "-",
                    ],
                    env=fence_env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return proc.returncode, json.loads(proc.stdout)

            # 1) Valid pinned native Settings session passes oc_usb_fence().
            rc, ans = run_fence_op()
            self.assertEqual(rc, 0, ans)
            self.assertTrue(ans["ok"], ans)

            # 2) Tampered api in Settings session is refused with invalid_legacy_runtime.
            (settings_sess / "api").write_bytes(b"tampered-api\n")
            rc, bad = run_fence_op()
            self.assertNotEqual(rc, 0)
            self.assertEqual(bad["error"], "invalid_legacy_runtime")
            shutil.copyfile(data / "packages" / pkg_id / "api", settings_sess / "api")
            (settings_sess / "api").chmod(0o700)

            # 3) Symlink pointing outside ram/sessions/session-* is refused with invalid_legacy_runtime.
            outside = root / "outside-session"
            outside.mkdir(mode=0o700)
            shutil.copyfile(settings_sess / "files.sha256", outside / "files.sha256")
            shutil.copyfile(settings_sess / "api", outside / "api")
            (ram / "runtime").unlink()
            (ram / "runtime").symlink_to(outside)
            rc, bad2 = run_fence_op()
            self.assertNotEqual(rc, 0)
            self.assertEqual(bad2["error"], "invalid_legacy_runtime")
