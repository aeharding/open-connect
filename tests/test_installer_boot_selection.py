"""Exercise the real native decision and durable writer against complete files."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_installer_transaction import compile_host_api

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
BOOT = "12345678-1234-1234-1234-123456789abc"


def sha(data):
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class NativeBootSelection(unittest.TestCase):
    BASE_INPUTS = (
        (
            "settings.txt",
            "/config/common/log/settings.txt",
            "stock native log settings\n",
            "8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0",
        ),
        (
            "libjcicommon.so",
            "/jci/lib/libjcicommon.so",
            "stock native log library\n",
            "637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d",
        ),
        (
            "log-defaults.js",
            "/jci/gui/common/js/logDefaults.js",
            "stock GUI log settings\n",
            "83f5a71617f34427bb903c90ac5df53ed4e0e6437cca8a8bdb509909a324ba3a",
        ),
        (
            "vui/vui.so",
            "/jci/vui/svcjcivui.so",
            "stock voice library\n",
            "ba72171a04dcc264ff5f690ac25ac2b009624158499159cdb6aebb08a9ab34f4",
        ),
        (
            "vui/vui.xml",
            "/jci/vui/vui_config.xml",
            "stock voice config\n",
            "d2511533b59bc9773f92d8fff9cbcf591d9ff461c33839ff4eaaae6f5d0aaef0",
        ),
    )

    TOUCH_INPUTS = (
        (
            "svc",
            "/jci/devices/svc-com-jci-cpp-devices.so",
            "stock devices service\n",
            "e438bef5acb59c65c810df905488c7b1230cce88b20a295dc2da182f78da2695",
        ),
        (
            "lib",
            "/jci/lib/libjcidevices.so",
            "stock devices library\n",
            "4d05f4242ffab8ed2e21c4785b077b7225ea54c3e62c8e02a26eb400eb6a1171",
        ),
    )

    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        folder = Path(cls.build.name).resolve()
        cls.program = folder / "boot-select"
        cls.pins_file = folder / "host-pins.txt"
        pin_lines = []
        for name, _, data, _ in cls.BASE_INPUTS:
            pin_lines.append(f"base/{name}={sha(data.encode())}\n")
        for name, _, data, _ in cls.TOUCH_INPUTS:
            pin_lines.append(f"touch/devices/{name}={sha(data.encode())}\n")
        mgr_sha = sha(b"stock manager.so\n")
        mmui_sha = sha(b"stock original mmui.xml\n")
        pin_lines.append(f"manager.so={mgr_sha}\n")
        pin_lines.append(f"originals/mmui.xml={mmui_sha}\n")
        cls.pins_file.write_text("".join(pin_lines))
        from tests.host_bins import copy_host_boot_select, copy_host_flush

        copy_host_boot_select(cls.program)
        copy_host_flush(Path(cls.build.name) / "flush")
        if shutil.which("gstat"):
            (Path(cls.build.name) / "stat").symlink_to(shutil.which("gstat"))

    def _host_env(self, extra=None):
        env = {**os.environ, "OC_HOST_PINS": str(self.pins_file)}
        if extra:
            env.update(extra)
        return env

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def put(self, name, value, mode=0o600):
        path = self.root / name.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        path.chmod(mode)
        return path

    def manifest(self, directory):
        text = "".join(
            sha(p.read_bytes()) + "  " + p.name + "\n"
            for p in sorted(directory.iterdir())
            if p.name != "files.sha256"
        )
        (directory / "files.sha256").write_text(text)
        (directory / "files.sha256").chmod(0o600)
        return sha(text.encode())

    def publish(self, directory):
        identity = self.manifest(directory)
        target = directory.with_name(identity)
        directory.rename(target)
        return target

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "tmp/mnt/data_persist/open-connect"
        self.data.mkdir(parents=True, mode=0o700)
        self.ram = self.root / "tmp/open-connect"
        self.ram.mkdir(mode=0o700)
        for name in ("snapshots", "packages", "composed", "keys", "originals"):
            (self.data / name).mkdir(mode=0o700)
        (self.data / "originals/mmui.xml").write_text("stock original mmui.xml\n")
        (self.data / "originals/mmui.xml").chmod(0o600)
        self.put("proc/sys/kernel/random/boot_id", BOOT + "\n")
        self.put("proc/uptime", "8.00 1.00\n")
        self.put(
            "proc/self/mounts",
            "rootfs / rootfs rw 0 0\n/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n",
        )
        (self.root / "proc/mounts").symlink_to("self/mounts")
        self.put("sys/class/gpio/ACC_Sense/value", "1\n")
        self.put("sys/class/nvram/nv-config/keys/lvds_speed_restriction", "disable\n")
        self.put("dev/urandom", os.urandom(1024))
        self.put(
            "jci/version.ini",
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n',
        )
        self.mode = f"755:{os.getuid()}:{os.getgid()}"
        self.ssh_mode = f"600:{os.getuid()}:{os.getgid()}"
        login = self.put("usr/bin/runlogin", "stock login\n", 0o755)
        self.login_inode = login.stat().st_ino
        ssh = self.put("etc/ssh/sshd_config", "stock ssh\n")
        access = f"0|0|-|{self.mode}|{self.ssh_mode}|{self.login_inode}\n"

        package = self.data / "packages/.new-package"
        package.mkdir(mode=0o700)
        mandatory = [
            "boot.sh",
            "state.sh",
            "transaction.sh",
            "firmware.sh",
            "access.sh",
            "service.sh",
            "runtime.js",
            "dialog.js",
            "settings.js",
            "maintenance.js",
            "carplay.js",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "VERSION",
        ]
        for name in mandatory:
            (package / name).write_bytes((ASSETS / name).read_bytes())
        for name in (
            "flush",
            "touch-disable.so",
            "api",
            "wireless.sh",
            "wireless-device.awk",
            "defer-gap2.sh",
            "defer-nav.sh",
        ):
            (package / name).write_text("fixture " + name + "\n")
        shutil.copyfile(Path(self.build.name) / "flush", package / "flush")
        (package / "flush").chmod(0o700)
        from tests.host_bins import copy_host_ignition

        copy_host_ignition(package / "ignition")
        (package / "INSTANCE").write_text("1" * 32 + "\n")
        (package / "boot-select").write_bytes(self.program.read_bytes())
        (package / "boot-select").chmod(0o700)
        self.package = self.publish(package)
        self.package_id = self.package.name
        self.put("usr/bin/open-connect-boot-select", self.program.read_bytes(), 0o700)

        baseline = self.data / "snapshots/.new-baseline"
        baseline.mkdir(mode=0o700)
        for name, content in {
            "autostart": "stock autostart\n",
            "config": f"-|0|0|absent|{self.mode}\n",
            "dependencies": "",
            "access": access,
            "runlogin": login.read_text(),
            "sshd.conf": ssh.read_text(),
            "selector": "-\n",
        }.items():
            (baseline / name).write_text(content)
        identity = subprocess.check_output(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; . "$3"; '
                'snapshot_create "$4/autostart" - 0 0 absent "$5" "$4/dependencies" "$4"',
                "dev9-baseline",
                self.data,
                Path(self.build.name),
                ROOT / "tests/fixtures/dev9/state.sh",
                baseline,
                self.mode,
            ],
            text=True,
            env={**os.environ, "PATH": self.build.name + os.pathsep + os.environ["PATH"]},
        ).strip()
        self.baseline = self.data / "snapshots" / identity
        shutil.rmtree(baseline)
        self.assertEqual((self.baseline / "config").read_text(), f"-|0|0|absent|{self.mode}\n")

        composed = self.data / "composed" / self.package_id
        composed.mkdir(mode=0o700)
        names = [
            "autostart",
            "uia.so",
            "mmui.so",
            "mmui.xml",
            "index-on.html",
            "index-off.html",
            "sm-normal-on.conf",
            "sm-normal-off.conf",
            "sm-wcp-on.conf",
            "sm-wcp-off.conf",
            "vui.so",
            "vui.xml",
        ]
        for name in names:
            (composed / name).write_text("composed " + name + "\n")
        (composed / "autostart").write_text("installed autostart\n")
        self.manifest(composed)
        self.composed = composed
        self.put("usr/bin/autostart", "installed autostart\n", 0o755)
        # Use firmware.sh's real complete map, including sm_WCP's underscore.
        mapping = [
            row.split()
            for row in subprocess.check_output(
                ["sh", "-c", '. "$1"; firmware_dependencies', "fixture", ASSETS / "firmware.sh"],
                text=True,
            ).splitlines()
        ]
        self.root_map = {}
        for _, name, path in mapping:
            if name == "autostart":
                continue
            if name in self.root_map:
                continue
            self.put(path, "stock " + name + "\n")
            self.root_map[name] = path
        self.assertEqual(len(self.root_map), 19)

        self.snapshot = self.data / "snapshots/.new-current"
        self.snapshot.mkdir(mode=0o700)
        contents = {
            "autostart": "installed autostart\n",
            "config": f"OC2\nbase=0\nmetadata={self.mode}\nnvram=disable\npackage={self.package_id}\nservice-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\ntouch=1\nwarning=1\nwireless=1\n",
            "access": access,
            "runlogin": login.read_text(),
            "sshd.conf": ssh.read_text(),
            "selector": f"{sha(self.program.read_bytes())}|700:{os.getuid()}:{os.getgid()}|{self.package_id}\n",
            "sm-normal.conf": "prepared normal\n",
            "sm-wcp.conf": "prepared WCP\n",
            "mmui.xml": "prepared MMUI XML\n",
            "vui-plugins.list": "",
            "index.html": '<meta content="@TOKEN@"><meta content="@VERSION@"><meta content="@NOTICE@">\n',
        }
        dependencies = []
        self.inputs = []
        for name, path in self.root_map.items():
            digest = sha((self.root / path.lstrip("/")).read_bytes())
            dependencies.append(f"{digest}  root/{name}\n")
            self.inputs.append((f"root/{name}", path, digest))
        for kind, directory in (("package", self.package), ("composed", self.composed)):
            for path in sorted(directory.iterdir()):
                key = f"{kind}-{self.package_id}/{path.name}"
                digest = sha(path.read_bytes())
                dependencies.append(f"{digest}  {key}\n")
                self.inputs.append((key, "/" + str(path.relative_to(self.root)), digest))
        contents["dependencies"] = "".join(dependencies)
        for name, content in contents.items():
            (self.snapshot / name).write_text(content)
            self.inputs.append(("current/" + name, "@/" + name, sha(content.encode())))
        for path in sorted(self.baseline.iterdir()):
            self.inputs.append(
                (
                    "baseline/" + path.name,
                    "/" + str(path.relative_to(self.root)),
                    sha(path.read_bytes()),
                )
            )
        for key, path in (
            ("target/autostart", "/usr/bin/autostart"),
            ("target/boot-select", "/usr/bin/open-connect-boot-select"),
            ("target/runlogin", "/usr/bin/runlogin"),
            ("target/sshd.conf", "/etc/ssh/sshd_config"),
            ("guard/version.ini", "/jci/version.ini"),
        ):
            self.inputs.append((key, path, sha((self.root / path.lstrip("/")).read_bytes())))
        self.inputs.append(
            ("hold/runlogin", f"/usr/bin/.open-connect-runlogin-{self.login_inode}", "-")
        )
        self.seal()
        self.record = [
            "OC1",
            "active",
            "2" * 32,
            self.package_id,
            self.baseline.name,
            self.snapshot.name,
            "-",
            "-",
            "-",
            "3",
            "-",
            "-",
            "installed",
        ]
        self.save_record()

    def seal(self, inputs=None):
        rows = inputs if inputs is not None else self.inputs
        text = f"OCBP1|{self.baseline.name}|{self.package_id}\n" + "".join(
            "|".join(row) + "\n" for row in rows
        )
        with (self.snapshot / "boot.plan").open("wb") as output:
            result = subprocess.run(
                [self.program, "seal", self.root, str(self.snapshot.relative_to(self.root))],
                input=text.encode(),
                stdout=output,
                stderr=subprocess.PIPE,
                env=self._host_env(),
                timeout=5,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.snapshot = self.publish(self.snapshot)

    def save_record(self):
        (self.data / "record").write_text("|".join(self.record) + "\n")
        (self.data / "record").chmod(0o600)

    def change_current(self, name, content):
        (self.snapshot / name).write_text(content)
        self.inputs = [
            (key, path, sha(content.encode()) if key == "current/" + name else digest)
            for key, path, digest in self.inputs
        ]
        self.seal()
        self.record[5] = self.snapshot.name
        self.save_record()

    def touch_fixture(self):
        for name, path, data, _ in self.TOUCH_INPUTS:
            self.put(path, data)
            self.inputs.append(("touch/devices/" + name, path, sha(data.encode())))
        self.change_current(
            "config",
            (self.snapshot / "config")
            .read_text()
            .replace("touch=1", "touch=2")
            .replace("warning=1", "warning=0")
            .replace("nvram=disable", "nvram=absent"),
        )
        for name in ("sm-normal.conf", "sm-wcp.conf"):
            self.change_current(name, "/tmp/open-connect/feature/touch-disable.so\n")
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink()

    def test_touch_disabled_stages_verified_executable_without_warning_or_base(self):
        self.touch_fixture()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        shim = self.ram / "feature/touch-disable.so"
        self.assertEqual(shim.read_bytes(), (self.package / "touch-disable.so").read_bytes())
        self.assertEqual(shim.stat().st_mode & 0o777, 0o755)
        self.assertIn("touch-disable.so", (self.ram / "feature/sm.conf").read_text())
        self.assertFalse((self.ram / "feature/mmui.so").exists())

    def test_touch_modes_zero_and_one_do_not_stage_shim(self):
        # Default fixture is mode 1; the package still contains the DSO.
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.ram / "feature/touch-disable.so").exists())
        self.cold_boot()
        self.change_current(
            "config",
            (self.snapshot / "config")
            .read_text()
            .replace("touch=1", "touch=0")
            .replace("nvram=disable", "nvram=absent"),
        )
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.ram / "feature/touch-disable.so").exists())

    def test_touch_selector_requires_each_exact_pin_once_without_warning_or_base(self):
        self.touch_fixture()
        original = (self.snapshot / "boot.plan").read_text()
        for key, _, _, _ in self.TOUCH_INPUTS:
            row = next(
                line
                for line in original.splitlines(True)
                if line.startswith("touch/devices/" + key + "|")
            )
            for damage in (
                original.replace(row, ""),
                original + row,
                original.replace(row, row.replace("/jci/", "/bad/")),
                original.replace(row, row.replace(row.split("|")[2], "0" * 64)),
            ):
                with self.subTest(key=key, damage=damage[-180:]):
                    (self.snapshot / "boot.plan").write_text(damage)
                    self.snapshot = self.publish(self.snapshot)
                    self.record[5] = self.snapshot.name
                    self.save_record()
                    before = (self.data / "record").read_bytes()
                    result = self.invoke()
                    self.assertEqual(result.returncode, 95, result.stderr)
                    self.assertEqual((self.data / "record").read_bytes(), before)
                    self.assertFalse((self.ram / "feature").exists())

    def test_touch_physical_root_mismatch_refuses_before_debit(self):
        self.touch_fixture()
        before = (self.data / "record").read_bytes()
        result = self.invoke(extra_env={"OC_TOUCH_WRONG_FS": "1"})
        self.assertEqual(result.returncode, 95, result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.ram / "selected").exists())

    def test_touch_budget_fallback_uses_stock_service_and_baseline_nvram(self):
        self.touch_fixture()
        self.record[9] = "0"
        self.save_record()
        result = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.ram / "feature").exists())
        self.assertFalse((self.ram / "selected").exists())
        self.assertTrue((self.root / "jci/devices/svc-com-jci-cpp-devices.so").exists())
        self.assertFalse(
            (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").exists()
        )

    def test_completion_links_exact_selected_plan_member_and_survives_update(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.ram / "feature/maintenance.js"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.package / "maintenance.js")
        expected = (ASSETS / "maintenance.js").read_bytes()
        self.assertEqual(link.read_bytes(), expected)
        successor = self.data / "packages" / ("f" * 64)
        successor.mkdir(mode=0o700)
        (successor / "maintenance.js").write_text("successor\n")
        self.assertEqual(link.read_bytes(), expected)
        with link.open("rb") as reader:
            shutil.rmtree(self.data / "packages")
            self.assertFalse(link.exists())
            self.assertEqual(reader.read(), expected)

    def test_completion_native_omits_optional_link_without_notice(self):
        self.record[12] = "-"
        self.save_record()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.lexists(self.ram / "feature/maintenance.js"))

    def test_completion_native_rejects_unplanned_changed_or_symlink_source(self):
        source = self.package / "maintenance.js"
        original = source.read_bytes()
        for damage in ("missing", "symlink", "changed"):
            with self.subTest(damage=damage):
                source.unlink(missing_ok=True)
                if damage == "symlink":
                    source.symlink_to(ASSETS / "maintenance.js")
                elif damage == "changed":
                    source.write_bytes(original + b"changed")
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.ram / "feature").exists())
                source.unlink(missing_ok=True)
                source.write_bytes(original)

    def test_interrupted_package_staging_keeps_sealed_original_selectable(self):
        # The real writer must not create even a temporary hardlink to sealed
        # members: unlinking that name would change ctime and fail gated select.
        def fingerprint():
            return {
                p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_ino, p.stat().st_ctime_ns)
                for p in self.package.iterdir()
            }

        original = fingerprint()
        record = (self.data / "record").read_bytes()
        result = subprocess.run(
            [
                "sh",
                "-c",
                r"""
set -eu
D=$1; P=$2; R_BACKEND=$3
. "$4/state.sh"; . "$4/firmware.sh"
uuid() { openssl rand -hex 16; }
flush() { case "$2" in */.new-*/boot-select) fail interrupted;; esac; }
package_save
""",
                "interrupted-package",
                self.data,
                self.package,
                self.package_id,
                ASSETS,
            ],
            env={**os.environ, "PATH": self.build.name + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interrupted", result.stderr)
        self.assertEqual(fingerprint(), original)
        self.assertEqual((self.data / "record").read_bytes(), record)
        self.assertFalse(list((self.data / "packages").glob(".new-*")))
        selected = self.invoke(mode="select-gated")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual((self.ram / "selected").read_text().strip(), self.snapshot.name)
        self.assertFalse((self.data / "reseal").exists())

    def test_autoshow_stages_only_applied_choice_with_nonsecret_boot_mark(self):
        self.change_current(
            "index.html", (self.snapshot / "index.html").read_text() + '<meta data-boot="@BOOT@">\n'
        )
        config = (
            (self.snapshot / "config")
            .read_text()
            .replace("base=0\n", "base=0\ncarplay-autoshow=1\n")
            .replace("warning=1", "warning=0")
            .replace("wireless=1", "wireless=0")
        )
        self.change_current("config", config)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.ram / "feature/carplay.js").read_bytes(), (ASSETS / "carplay.js").read_bytes()
        )
        index = (self.ram / "feature/index.html").read_text()
        self.assertIn('data-boot="' + self.boot_token() + '"', index)
        self.assertNotIn("@BOOT@", index)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_retired_dvd_config_selects_and_debits_with_its_authenticated_keys(self):
        config = (
            (self.snapshot / "config")
            .read_text()
            .replace(
                "service-ids=android-auto,pandora",
                "service-ids=android-auto,dvd,pandora,siriusxm",
            )
            .replace(
                "service.pandora=1\n", "service.dvd=1\nservice.pandora=1\nservice.siriusxm=1\n"
            )
        )
        self.change_current("config", config)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.ram / "selected").read_text().strip(), self.snapshot.name)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_autoshow_missing_boot_provenance_refuses_before_debit(self):
        config = (
            (self.snapshot / "config")
            .read_text()
            .replace("base=0\n", "base=0\ncarplay-autoshow=1\n")
        )
        self.change_current("config", config)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ram / "selected").exists())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "3")

    def boot_token(self):
        return (self.ram / "boot-id").readlink().as_posix()

    def cold_boot(self):
        # Only volatile state disappears. The kernel UUID deliberately repeats.
        shutil.rmtree(self.ram)
        self.ram.mkdir(mode=0o700)

    def test_repeated_kernel_uuid_renews_legacy_off_then_next_cold_boot(self):
        self.record[9:12] = ["0", BOOT, BOOT]
        self.save_record()
        previous = BOOT
        for _ in range(2):
            with self.subTest(previous=previous):
                self.assertEqual(self.invoke().returncode, 0)
                token = self.boot_token()
                self.assertNotIn(token, (BOOT, previous))
                fields = (self.data / "record").read_text().strip().split("|")
                self.assertEqual(fields[9:12], ["2", "-", token])
                self.assertEqual((self.ram / "feature/boot-id").read_text(), token + "\n")
                self.assertEqual((self.ram / "boot-id").lstat().st_blocks, 0)
                # The durable identity refuses re-entry even if publications
                # were removed after a crash. Never regenerate from new R_REV.
                for path in self.ram.iterdir():
                    if path.name in ("boot-id", "lock"):
                        continue
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                before = (self.data / "record").read_bytes()
                self.assertEqual(self.invoke().returncode, 1)
                self.assertEqual((self.data / "record").read_bytes(), before)
                self.assertEqual(self.boot_token(), token)
                fields[10] = token
                self.record = fields
                self.save_record()
                previous = token
                self.cold_boot()
        self.assertEqual((self.root / "proc/sys/kernel/random/boot_id").read_text(), BOOT + "\n")

    def test_repeated_kernel_uuid_keeps_finite_budget_including_stock_boot(self):
        config = (
            (self.snapshot / "config")
            .read_text()
            .replace("touch=1", "touch=0")
            .replace("nvram=disable", "nvram=absent")
        )
        self.change_current("config", config)
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink()
        tokens = set()
        for remaining, outcome in ((2, 0), (1, 0), (0, 0), (0, 2), (0, 2)):
            result = self.invoke()
            self.assertEqual(result.returncode, outcome, result.stderr)
            token = self.boot_token()
            self.assertNotIn(token, tokens)
            tokens.add(token)
            fields = (self.data / "record").read_text().strip().split("|")
            self.assertEqual(fields[9:12], [str(remaining), "-", token])
            before = (self.data / "record").read_bytes()
            self.assertEqual(self.invoke().returncode, 1)
            self.assertEqual((self.data / "record").read_bytes(), before)
            self.cold_boot()
        # Sustained OFF in the stock boot still permits the next ignition cycle.
        fields[10] = fields[11]
        self.record = fields
        self.save_record()
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_native_slow_path_and_pending_recovery_share_shell_identity(self):
        # NVRAM mismatch requests shell reconciliation after identity creation.
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").write_text("enable\n")
        original = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 95)
        token = self.boot_token()
        self.assertEqual((self.data / "record").read_bytes(), original)
        self.assertEqual(self.shell_identity(), token)
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, self.snapshot.name]
        self.save_record()
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual(self.shell_identity(), token)
        self.assertEqual(self.boot_token(), token)

    def shell_identity(self):
        state = self.root / "state.sh"
        state.write_text(
            (ASSETS / "state.sh")
            .read_text()
            .replace("/tmp/open-connect", str(self.ram))
            .replace(
                "/proc/sys/kernel/random/boot_id", str(self.root / "proc/sys/kernel/random/boot_id")
            )
        )
        tools = Path(self.build.name)
        return subprocess.check_output(
            [
                "sh",
                "-c",
                'D=$1; . "$2"; record_read && boot_identity',
                "identity",
                self.data,
                state,
            ],
            text=True,
            env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
        ).strip()

    def test_native_and_shell_identity_derivation_agree(self):
        before = self.record.copy()
        self.assertEqual(self.invoke().returncode, 0)
        native = self.boot_token()
        self.cold_boot()
        self.record = before
        self.save_record()
        self.assertEqual(self.shell_identity(), native)
        # Subsequent record revisions cannot change an existing marker.
        self.record[2] = "f" * 32
        self.save_record()
        self.assertEqual(self.shell_identity(), native)

    def test_identity_owner_mismatch_refuses_without_debit(self):
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke(extra_env={"OC_BOOT_OWNER_FAIL": "1"}).returncode, 1)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_malformed_volatile_identity_never_regenerates_or_debits(self):
        for value in (
            None,
            "invalid",
            BOOT + "\n",
            BOOT + "0",
            "-2345678-1234-1234-1234-123456789abc",
        ):
            with self.subTest(value=value):
                marker = self.ram / "boot-id"
                marker.unlink(missing_ok=True)
                if value is None:
                    marker.write_text(BOOT)
                else:
                    marker.symlink_to(value)
                before = (self.data / "record").read_bytes()
                self.assertEqual(self.invoke().returncode, 1)
                self.assertEqual((self.data / "record").read_bytes(), before)
                with self.assertRaises(subprocess.CalledProcessError):
                    self.shell_identity()

    def invoke(
        self, cut=None, term=None, output_limit=None, mode="select", stderr_fd=None, extra_env=None
    ):
        # A regular fixture models urandom's bytes, refreshing them per entry.
        self.put("dev/urandom", os.urandom(1024))
        env = self._host_env(extra_env)
        if cut:
            env["OC_BOOT_CUT"] = cut
        if term:
            env["OC_BOOT_TERM"] = term

        def limit_output():
            import resource
            import signal

            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))

        return subprocess.run(
            [self.program, mode, self.root],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if stderr_fd is None else stderr_fd,
            timeout=5,
            preexec_fn=limit_output if output_limit is not None else None,
        )

    def test_gate_releases_before_staging_for_both_base_settings(self):
        for base in (0, 1):
            with self.subTest(base=base):
                config = (self.snapshot / "config").read_text().replace("base=0", f"base={base}")
                self.change_current("config", config)
                before = (self.data / "record").read_bytes()
                result = self.invoke(cut="gate_released", mode="select-gated")
                self.assertEqual((result.stdout, result.returncode), (b"G", 97), result.stderr)
                self.assertEqual((self.data / "record").read_bytes(), before)
                self.assertFalse((self.ram / "feature").exists())
                self.assertFalse(list(self.ram.glob(".feature-*")))

    def base_fixture(self):
        for name, path, data, _ in self.BASE_INPUTS:
            self.put(path, data)
            self.inputs.append(("base/" + name, path, sha(data.encode())))
        names = []
        for line in (ASSETS / "ui-modules.tsv").read_text().splitlines():
            if not line.startswith("vui\t"):
                continue
            _, name, group, _ = line.split("\t")
            if group == "base":
                continue
            payload = "authored retained plugin " + name + "\n"
            path = "/jci/vui/plugins/" + name
            self.put(path, payload)
            self.inputs.append(("base/vui/" + name, path, sha(payload.encode())))
            names.append(name)
        self.change_current("vui-plugins.list", "\n".join(names) + "\n")
        self.change_current(
            "config", (self.snapshot / "config").read_text().replace("base=0", "base=1")
        )
        self.put("sys/devices/virtual/block/ffx01/dev", "253:16\n")
        return self.put("sys/devices/virtual/block/ffx01/queue/read_ahead_kb", "128\n", 0o644)

    def test_wave_c_aliases_survive_purge_without_persistent_payload_targets(self):
        self.base_fixture()
        self.assertEqual(self.invoke().returncode, 0)
        main = self.ram / "feature/vui.so"
        self.assertFalse(main.is_symlink())
        self.assertEqual(main.stat().st_ino, (self.ram / "vui-hold.so").stat().st_ino)
        self.assertEqual(
            (self.ram / "v.xml").stat().st_ino, (self.ram / "feature/vui.xml").stat().st_ino
        )
        self.assertEqual(os.readlink(self.ram / "vui-plugins"), "feature/vui-plugins")
        names = (self.snapshot / "vui-plugins.list").read_text().splitlines()
        self.assertEqual(sorted(p.name for p in (self.ram / "vui-plugins").iterdir()), names)
        for name in names:
            self.assertEqual(
                os.readlink(self.ram / "vui-plugins" / name), "/jci/vui/plugins/" + name
            )
        with (self.ram / "feature/uia.so").open("rb") as loaded:
            expected = loaded.read()
            shutil.rmtree(self.data)
            loaded.seek(0)
            self.assertEqual(loaded.read(), expected)
            self.assertFalse((self.ram / "feature/uia.so").exists())
            self.assertEqual(main.read_bytes(), b"composed vui.so\n")
            self.assertEqual((self.ram / "vui-hold.so").read_bytes(), main.read_bytes())
            self.assertEqual((self.ram / "v.xml").read_bytes(), b"composed vui.xml\n")

    def test_wave_c_foreign_alias_refuses_before_gate_and_debit(self):
        self.base_fixture()
        foreign = self.ram / "vui-plugins"
        foreign.symlink_to("foreign")
        before = (self.data / "record").read_bytes()
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.returncode, result.stdout), (1, b"J"))
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertEqual(os.readlink(foreign), "foreign")

    def test_wave_c_alias_failures_unwind_every_owned_root_name(self):
        for fault in (
            "OC_ALIAS_LINK_FAIL",
            "OC_ALIAS_LINK_AFTER",
            "OC_ALIAS_FOREIGN",
        ):
            for alias in ("v.xml", "vui-hold.so", "vui-plugins"):
                with self.subTest(fault=fault, alias=alias):
                    self.setUp()
                    self.base_fixture()
                    result = self.invoke(mode="select-gated", extra_env={fault: alias})
                    self.assertEqual((result.returncode, result.stdout), (1, b"G"), result.stderr)
                    self.assertEqual((self.data / "record").read_text().split("|")[9], "2")
                    self.assertFalse((self.ram / "selected").exists())
                    for name in ("v.xml", "vui-hold.so", "vui-plugins"):
                        if fault == "OC_ALIAS_FOREIGN" and name == alias:
                            self.assertEqual((self.ram / name).read_bytes(), b"foreign\n")
                        else:
                            self.assertFalse(os.path.lexists(self.ram / name))

    def test_wave_c_completed_links_do_not_depend_on_two_root_metadata_reads(self):
        for late_failure in (False, True):
            with self.subTest(late_failure=late_failure):
                self.setUp()
                self.base_fixture()
                env = {"OC_ALIAS_META_FAIL": "vui-hold.so"}
                if late_failure:
                    env["OC_ALIAS_LINK_FAIL"] = "vui-plugins"
                result = self.invoke(mode="select-gated", extra_env=env)
                self.assertEqual(
                    (result.returncode, result.stdout), (int(late_failure), b"G"), result.stderr
                )
                self.assertEqual((self.data / "record").read_text().split("|")[9], "2")
                self.assertEqual((self.ram / "selected").exists(), not late_failure)
                for name in ("v.xml", "vui-hold.so", "vui-plugins"):
                    self.assertEqual(os.path.lexists(self.ram / name), not late_failure)
                if not late_failure:
                    self.assertEqual(
                        (self.ram / "vui-hold.so").stat().st_ino,
                        (self.ram / "feature/vui.so").stat().st_ino,
                    )

    @unittest.skipUnless(os.path.isdir("/dev/shm"), "a separate Linux tmpfs is required")
    def test_sealer_refuses_byte_identical_plugin_from_another_filesystem(self):
        if os.stat("/").st_dev == os.stat("/dev/shm").st_dev:
            self.skipTest("tmpfs shares the stock filesystem")
        with tempfile.NamedTemporaryFile(dir="/dev/shm") as plugin:
            plugin.write(b"byte-identical plugin\n")
            plugin.flush()
            text = f"OCBP1|{'b' * 64}|{'c' * 64}\nbase/vui/plugin.so|{plugin.name}|{sha(b'byte-identical plugin' + bytes([10]))}\n"
            for key in ("touch/devices/svc", "touch/devices/lib"):
                touch = text.replace("base/vui/plugin.so", key)
                result = subprocess.run(
                    [self.program, "seal", "/", str(self.snapshot).lstrip("/")],
                    input=touch.encode(),
                    capture_output=True,
                    timeout=5,
                )
                self.assertNotEqual(result.returncode, 0)
            with (self.root / "foreign-device-plan").open("wb") as output:
                result = subprocess.run(
                    [self.program, "seal", "/", str(self.snapshot).lstrip("/")],
                    input=text.encode(),
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=5,
                )
            self.assertNotEqual(result.returncode, 0)
            with (self.root / "ordinary-device-plan").open("wb") as output:
                control = subprocess.run(
                    [self.program, "seal", "/", str(self.snapshot).lstrip("/")],
                    input=text.replace("base/vui/plugin.so|", "guard/plugin.so|").encode(),
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=5,
                )
            self.assertEqual(control.returncode, 0, control.stderr)

    def test_wave_c_late_plugin_refusal_does_not_debit_or_publish_aliases(self):
        self.base_fixture()
        plugin = (
            self.root
            / "jci/vui/plugins"
            / (self.snapshot / "vui-plugins.list").read_text().splitlines()[0]
        )
        plugin.write_bytes(b"changed source\n")
        before = (self.data / "record").read_bytes()
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.returncode, result.stdout), (1, b"G"))
        self.assertEqual((self.data / "record").read_bytes(), before)
        for name in ("v.xml", "vui-hold.so", "vui-plugins", "selected"):
            self.assertFalse(os.path.lexists(self.ram / name))

    def test_shell_copy_helper_binds_snapshot_and_never_changes_record_or_aliases(self):
        self.base_fixture()
        stage = self.ram / ".feature-shell"
        stage.mkdir(mode=0o700)
        before = (self.data / "record").read_bytes()
        result = subprocess.run(
            [self.program, "copy-ui", self.root, self.snapshot.name, stage.name],
            env=self._host_env(),
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((stage / "vui.so").read_bytes(), (self.composed / "vui.so").read_bytes())
        self.assertEqual(
            (stage / "mmui.xml").read_bytes(), (self.snapshot / "mmui.xml").read_bytes()
        )
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse(os.path.lexists(self.ram / "v.xml"))
        rejected = subprocess.run(
            [self.program, "copy-ui", self.root, "0" * 64, stage.name],
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(rejected.returncode, 1)

    def test_base_publication_and_diagnostic_io_never_reverses_it(self):
        queue = self.base_fixture()
        queue.write_text("4\n")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b"base_read_ahead_unavailable", result.stderr)
        self.assertFalse((self.ram / "feature/log-defaults.js").exists())
        self.assertTrue((self.ram / "feature/defer-gap2.sh").is_file())

    def test_queue_readback_failure_keeps_the_committed_selection(self):
        queue = self.base_fixture()
        result = self.invoke()
        # An ordinary host file retains its old suffix, unlike kernel sysfs.
        # This deliberately exercises a failed readback AFTER the real write.
        self.assertEqual(queue.read_bytes(), b"4\n8\n")
        self.assertIn("base_read_ahead_unavailable|", (self.ram / "startup-times").read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.ram / "selected").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_missing_queue_does_not_turn_success_into_stock_or_a_second_debit(self):
        queue = self.base_fixture()
        queue.unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("base_read_ahead_unavailable|", (self.ram / "startup-times").read_text())
        self.assertTrue((self.ram / "selected").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_closed_diagnostic_pipe_cannot_kill_a_published_selection(self):
        self.base_fixture().unlink()
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = self.invoke(stderr_fd=write_fd)
        finally:
            os.close(write_fd)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.ram / "selected").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_full_diagnostic_pipe_cannot_hang_a_published_selection(self):
        self.base_fixture().unlink()
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            with self.assertRaises(BlockingIOError):
                while True:
                    os.write(write_fd, b"x" * 4096)
            os.set_blocking(write_fd, True)
            result = self.invoke(stderr_fd=write_fd)
        finally:
            os.close(read_fd)
            os.close(write_fd)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.ram / "selected").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")
        self.assertIn("base_read_ahead_unavailable|", (self.ram / "startup-times").read_text())

    def test_no_queue_write_after_guard_refusal(self):
        queue = self.base_fixture()
        before = (self.data / "record").read_bytes()
        path = self.root / "jci/gui/common/js/logDefaults.js"
        path.write_text("foreign GUI logging\n")
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual(queue.read_text(), "128\n")
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_no_queue_write_between_durable_debit_and_publication(self):
        queue = self.base_fixture()
        result = self.invoke(cut="before_publication")
        self.assertEqual(result.returncode, 97)
        self.assertEqual(queue.read_text(), "128\n")
        self.assertFalse((self.ram / "selected").exists())

    def test_base_logging_index_is_staged_with_disclaimer_disabled(self):
        queue = self.base_fixture()
        queue.write_text("4\n")
        config = (self.snapshot / "config").read_text().replace("warning=1", "warning=0")
        self.change_current("config", config)
        self.change_current(
            "index.html",
            '<script src="common/js/logDefaults.js"></script><script>logDefaults.__global__ = "warn";</script>@TOKEN@ @VERSION@ @NOTICE@\n',
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            'logDefaults.__global__ = "warn"', (self.ram / "feature/index.html").read_text()
        )
        self.assertFalse((self.ram / "feature/log-defaults.js").exists())
        self.assertTrue((self.ram / "feature/mmui.so").exists())

    def test_base_off_never_changes_an_existing_queue_choice(self):
        queue = self.put("sys/devices/virtual/block/ffx01/queue/read_ahead_kb", "128\n", 0o644)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(queue.read_text(), "128\n")
        self.assertFalse((self.ram / "feature/log-defaults.js").exists())
        self.assertFalse((self.ram / "feature/defer-gap2.sh").exists())

    def test_gate_requests_early_join_for_nvram_recovery(self):
        self.put("sys/class/nvram/nv-config/keys/lvds_speed_restriction", "enable\n")
        before = (self.data / "record").read_bytes()
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"J", 95), result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_gate_late_metadata_refusal_never_requests_shell_recovery(self):
        target = self.root / "jci/gui/framework/js/GuiFramework.js"
        target.write_bytes(target.read_bytes())
        before = (self.data / "record").read_bytes()
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"G", 1), result.stderr)
        self.assertIn(b"late_verification_refused", result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.ram / "selected").exists())
        self.assertEqual((self.data / "reseal").read_text(), self.snapshot.name + "\n")
        self.assertEqual((self.data / "reseal").stat().st_mode & 0o777, 0o600)
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"J", 95), result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_reseal_request_requires_every_input_digest_and_preserves_plan(self):
        plan = (self.snapshot / "boot.plan").read_bytes()
        target = self.root / "jci/gui/framework/js/GuiFramework.js"
        target.write_bytes(target.read_bytes())
        runtime = self.package / "runtime.js"
        original = runtime.read_bytes()
        runtime.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        before = (self.data / "record").read_bytes()
        for _ in range(2):
            result = self.invoke(mode="select-gated")
            self.assertEqual((result.stdout, result.returncode), (b"G", 1), result.stderr)
            self.assertFalse((self.data / "reseal").exists())
        self.assertEqual((self.snapshot / "boot.plan").read_bytes(), plan)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_stale_reseal_request_does_not_change_selection_authority(self):
        hint = self.data / "reseal"
        hint.write_text("0" * 64 + "\n")
        hint.chmod(0o600)
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"G", 0), result.stderr)
        self.assertEqual(hint.read_text(), "0" * 64 + "\n")

    def test_foreign_reseal_request_refuses_before_gate_without_debit(self):
        hint = self.data / "reseal"
        before = (self.data / "record").read_bytes()
        for kind in ("malformed", "wrong-mode", "symlink", "fifo"):
            with self.subTest(kind=kind):
                if hint.exists() or hint.is_symlink():
                    hint.unlink()
                if kind == "symlink":
                    hint.symlink_to(self.data / "record")
                elif kind == "fifo":
                    os.mkfifo(hint)
                else:
                    hint.write_text("bad\n" if kind == "malformed" else self.snapshot.name + "\n")
                    hint.chmod(0o644 if kind == "wrong-mode" else 0o600)
                result = self.invoke(mode="select-gated")
                self.assertEqual((result.stdout, result.returncode), (b"J", 1), result.stderr)
                self.assertEqual((self.data / "record").read_bytes(), before)

    def test_reseal_request_power_cuts_never_debit_or_publish(self):
        target = self.root / "jci/gui/framework/js/GuiFramework.js"
        target.write_bytes(target.read_bytes())
        before = (self.data / "record").read_bytes()
        for phase in ("reseal_synced", "reseal_published"):
            with self.subTest(phase=phase):
                result = self.invoke(cut=phase, mode="select-gated")
                self.assertEqual((result.stdout, result.returncode), (b"G", 97), result.stderr)
                self.assertEqual((self.data / "record").read_bytes(), before)
                self.assertFalse((self.ram / "selected").exists())
                self.assertFalse((self.ram / "feature").exists())
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"J", 95), result.stderr)

    def test_gate_joins_on_competing_lock_without_debit(self):
        import fcntl

        lock = self.ram / "lock"
        lock.touch(mode=0o600)
        before = (self.data / "record").read_bytes()
        with lock.open("r+") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"J", 1), result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_gate_selects_once_and_refuses_same_kernel(self):
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"G", 0), result.stderr)
        self.assertIn("gate_released|", (self.ram / "startup-times").read_text())
        before = (self.data / "record").read_bytes()
        result = self.invoke(mode="select-gated")
        self.assertEqual((result.stdout, result.returncode), (b"J", 1), result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_selects_complete_policy_and_debits_once(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        record = (self.data / "record").read_text().split("|")
        self.assertEqual(record[9:12], ["2", "-", self.boot_token()])
        self.assertEqual((self.ram / "selected").read_text(), self.snapshot.name + "\n")
        self.assertEqual(
            (self.ram / "feature/uia.so").read_bytes(), (self.composed / "uia.so").read_bytes()
        )
        for name in ("uia.so",):
            feature = self.ram / "feature" / name
            self.assertTrue(feature.is_symlink())
            self.assertEqual(feature.resolve(), self.composed / name)
        self.assertNotIn("@TOKEN@", (self.ram / "feature/index.html").read_text())
        self.assertEqual(
            (self.ram / "ignition/ignition").read_bytes(), (self.package / "ignition").read_bytes()
        )
        self.assertFalse((self.ram / "ignition/state.sh").exists())
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_stale_metadata_refuses_before_debit(self):
        target = self.root / "jci/gui/framework/js/GuiFramework.js"
        target.write_bytes(target.read_bytes())
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.ram / "selected").exists())

    def test_inflight_digest_failure_requests_full_verifier_before_debit(self):
        key = f"package-{self.package_id}/runtime.js"
        path = self.package / "runtime.js"
        original = sha(path.read_bytes())
        path.write_bytes(path.read_bytes() + b"\nchanged after metadata check\n")
        changed = sha(path.read_bytes())
        rows = [(k, p, changed if k == key else digest) for k, p, digest in self.inputs]
        self.seal(rows)
        # Model a source changing after stat by retaining expected bytes but
        # using its new stat fields. The required in-flight hash must catch it.
        plan = (self.snapshot / "boot.plan").read_text()
        prefix = next(p for k, p, _ in rows if k == key)
        old = f"{key}|{prefix}|{changed}|"
        self.assertEqual(plan.count(old), 1)
        (self.snapshot / "boot.plan").write_text(plan.replace(old, f"{key}|{prefix}|{original}|"))
        self.snapshot = self.publish(self.snapshot)
        self.record[5] = self.snapshot.name
        self.save_record()
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.ram / "selected").exists())

    def test_extra_package_member_refuses_before_debit(self):
        (self.package / "foreign").write_text("external\n")
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "3")

    def test_nvram_accepts_observed_terminal_nul_but_rejects_interior_data(self):
        path = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        before = (self.data / "record").read_bytes()
        for raw in (b"disable\0extra", b"dis\0able", b"disable \0"):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                self.assertEqual(self.invoke().returncode, 95)
                self.assertEqual((self.data / "record").read_bytes(), before)
        path.write_bytes(b"disable\0")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_nvram_nonregular_or_symlink_leaf_falls_back_without_debit(self):
        path = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        before = (self.data / "record").read_bytes()
        path.unlink()
        os.mkfifo(path)
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)
        path.unlink()
        target = self.root / "foreign-nvram"
        target.write_bytes(b"disable\0")
        path.symlink_to(target)
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_ram_write_failure_returns_stock_without_handoff_or_debit(self):
        before = (self.data / "record").read_bytes()
        result = self.invoke(output_limit=4096)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before)
        self.assertFalse((self.ram / "selected").exists())
        partial = list(self.ram.glob(".ignition-*/ignition"))
        self.assertEqual(len(partial), 1)
        self.assertEqual(partial[0].stat().st_size, 4096)

    def test_protected_tree_overlay_requests_full_verifier_without_debit(self):
        mounts = self.root / "proc/self/mounts"
        original = mounts.read_text()
        before = (self.data / "record").read_bytes()
        for path in ("/tmp/open-connect/feature", "/tmp/mnt/data_persist/open-connect"):
            with self.subTest(path=path):
                mounts.write_text(original + f"tmpfs {path} tmpfs rw 0 0\n")
                self.assertEqual(self.invoke().returncode, 95)
                self.assertEqual((self.data / "record").read_bytes(), before)

    def test_missing_oem_row_cannot_be_authorized_by_a_valid_plan_hash(self):
        rows = [row for row in self.inputs if row[0] != "root/sm_WCP.conf"]
        self.seal(rows)
        self.record[5] = self.snapshot.name
        self.save_record()
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_mount_nvram_and_pending_state_use_full_verifier_without_debit(self):
        cases = [
            ("proc/self/mounts", "/dev/ffx01p1 / relfs rw,noatime 0 0\n"),
            ("sys/class/nvram/nv-config/keys/lvds_speed_restriction", "enable\n"),
            ("jci/version.ini", "foreign version\n"),
        ]
        for name, value in cases:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                self.put(name, value)
                before = (self.data / "record").read_bytes()
                self.assertEqual(self.invoke().returncode, 95)
                self.assertEqual((self.data / "record").read_bytes(), before)
                path.write_bytes(original)
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, self.snapshot.name]
        self.save_record()
        self.assertEqual(self.invoke().returncode, 95)

    def test_existing_publication_refuses_even_when_settings_cleared_boot_id(self):
        (self.ram / "feature").mkdir()
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 1)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_exhausted_budget_stages_observer_and_factory_behavior(self):
        config = (
            (self.snapshot / "config")
            .read_text()
            .replace("touch=1", "touch=0")
            .replace("nvram=disable", "nvram=absent")
        )
        self.change_current("config", config)
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink()
        self.record[9] = "0"
        self.save_record()
        self.assertEqual(self.invoke().returncode, 2)
        self.assertTrue((self.ram / "ignition/ignition").is_file())
        self.assertFalse((self.ram / "ignition/state.sh").exists())
        self.assertTrue((self.ram / "access-selected").is_file())
        self.assertFalse((self.ram / "selected").exists())
        self.assertFalse((self.ram / "feature").exists())
        self.assertEqual(
            (self.data / "record").read_text().split("|")[9:12], ["0", "-", self.boot_token()]
        )

    def test_only_off_from_a_different_kernel_renews_budget(self):
        self.record[9] = "0"
        self.record[10] = "87654321-1234-1234-1234-123456789abc"
        self.save_record()
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(
            (self.data / "record").read_text().split("|")[9:12], ["2", "-", self.boot_token()]
        )

    def test_same_kernel_off_requires_factory_nvram_restore_in_full_verifier(self):
        (self.ram / "boot-id").symlink_to(BOOT)
        self.record[9:11] = ["0", BOOT]
        self.save_record()
        before = (self.data / "record").read_bytes()
        self.assertEqual(self.invoke().returncode, 95)
        self.assertEqual((self.data / "record").read_bytes(), before)

    def test_record_cut_boundaries_never_publish_before_commit(self):
        for phase in ("record_written", "record_synced", "record_renamed", "directory_synced"):
            with self.subTest(phase=phase):
                self.save_record()
                result = self.invoke(cut=phase)
                self.assertEqual(result.returncode, 97, result.stderr)
                self.assertFalse((self.ram / "selected").exists())
                self.assertFalse((self.ram / "feature").exists())
                committed = phase in ("record_renamed", "directory_synced")
                expected = "2" if committed else "3"
                self.assertEqual((self.data / "record").read_text().split("|")[9], expected)
                if committed:
                    self.assertEqual(self.invoke().returncode, 1)
                    self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_term_before_publication_returns_stock_after_one_durable_debit(self):
        import signal

        self.assertEqual(self.invoke(term="before_publication").returncode, -signal.SIGTERM)
        self.assertFalse((self.ram / "selected").exists())
        self.assertFalse((self.ram / "feature").exists())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_term_during_short_publication_finishes_selected_before_return(self):
        self.assertEqual(self.invoke(term="publication").returncode, 0)
        self.assertTrue((self.ram / "selected").is_file())
        self.assertTrue((self.ram / "feature/index.html").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def _run_helper(self, *args, stdin=b"", env=None, stdout_path=None):
        run_env = self._host_env(env)
        if stdout_path is not None:
            with Path(stdout_path).open("wb") as out:
                return subprocess.run(
                    [self.program, *args],
                    input=stdin,
                    stdout=out,
                    stderr=subprocess.PIPE,
                    env=run_env,
                    timeout=5,
                )
        return subprocess.run(
            [self.program, *args],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=run_env,
            timeout=5,
        )

    def _clone_work(self, name=".new-delta", config_replace=None, profiles=None):
        work = self.data / "snapshots" / name
        work.mkdir(mode=0o700)
        if profiles is None:
            profiles = (
                "sm-normal.conf",
                "sm-wcp.conf",
                "index.html",
                "mmui.xml",
                "vui-plugins.list",
            )
        for member in ("config", *profiles):
            src = self.snapshot / member
            if src.exists():
                dst = work / member
                dst.write_bytes(src.read_bytes())
                dst.chmod(0o600)
        if config_replace:
            old, new = config_replace
            cfg = (work / "config").read_text()
            self.assertIn(old, cfg)
            (work / "config").write_text(cfg.replace(old, new))
            (work / "config").chmod(0o600)
        rows = []
        for key, path, digest in self.inputs:
            if key.startswith("current/"):
                member = key.split("/", 1)[1]
                src = work / member if (work / member).exists() else self.snapshot / member
                digest = sha(src.read_bytes())
            rows.append((key, path, digest))
        return work, rows

    def test_audit_current_and_candidate_enforce_policy_and_zero_side_effects(self):
        before_record = (self.data / "record").read_bytes()
        res = self._run_helper("audit", str(self.root), self.snapshot.name)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual((self.data / "record").read_bytes(), before_record)
        self.assertEqual(list(self.ram.iterdir()), [])

        # Wrong expected_current or pending record must be refused.
        self.assertNotEqual(self._run_helper("audit", str(self.root), "0" * 64).returncode, 0)
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, self.snapshot.name]
        self.save_record()
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        self.record[1] = "active"
        self.record[6:8] = ["-", "-"]
        self.save_record()

        # Wrong NVRAM must be refused.
        nvram = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        nvram.write_text("enable\n")
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        nvram.write_text("disable\n")

        # Writable rootfs or overlay mount must be refused.
        mounts = self.root / "proc/self/mounts"
        good_mounts = mounts.read_text()
        mounts.write_text(good_mounts.replace("ro,noatime", "rw,noatime"))
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        mounts.write_text(good_mounts + "tmpfs /tmp/open-connect tmpfs rw 0 0\n")
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        mounts.write_text(good_mounts)

        # Metadata drift / tampered root file must be refused.
        target = self.root / "jci/sm/sm.conf"
        orig = target.read_bytes()
        target.write_bytes(orig + b"x")
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        target.write_bytes(orig)

        # Restore fresh sealed current with an owner key and verify key dir/mode checks.
        key_bytes = b"ssh-ed25519 AAAA test@host\n"
        key_id = sha(key_bytes)
        key_path = self.data / "keys" / f"{key_id}.cmu"
        key_path.write_bytes(key_bytes)
        key_path.chmod(0o600)
        self.inputs.append(("key/owner", f"/{key_path.relative_to(self.root)}", key_id))
        self.change_current(
            "access", f"0|1|{key_id}|{self.mode}|{self.ssh_mode}|{self.login_inode}\n"
        )
        self.assertEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )

        # Candidate audit requires pending-set intent (R_PHASE=set, R_BEFORE=prev, R_AFTER=cand)
        # and refuses active records even when live NVRAM matches candidate.
        work, _ = self._clone_work(".new-cand", ("warning=1", "warning=0"))
        pub = self._run_helper(
            "seal-publish",
            str(self.root),
            self.snapshot.name,
            str(work.relative_to(self.root)),
        )
        self.assertEqual(pub.returncode, 0, pub.stderr)
        cand_id = pub.stdout.decode().strip()
        self.assertEqual(len(cand_id), 64)
        self.assertFalse(work.exists())
        self.assertTrue((self.data / "snapshots" / cand_id / "boot.plan").is_file())
        before_record = (self.data / "record").read_bytes()
        # Active record MUST be refused by candidate audit (pending-only predicate).
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, cand_id).returncode,
            0,
        )
        self.assertEqual((self.data / "record").read_bytes(), before_record)
        # Pending-set record naming cand_id passes candidate audit without mutating record.
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, cand_id]
        self.save_record()
        pending_record = (self.data / "record").read_bytes()
        self.assertEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, cand_id).returncode,
            0,
        )
        self.assertEqual((self.data / "record").read_bytes(), pending_record)
        self.record[1] = "active"
        self.record[6:8] = ["-", "-"]
        self.save_record()

        # NVRAM-changing seal-publish (touch 1 -> 0, nvram disable -> absent) requires
        # expected_nvram and passes pending-set audit only after R_PHASE=set + live NVRAM match.
        nv_work, _ = self._clone_work(".new-nv", ("touch=1", "touch=0"), profiles=())
        (nv_work / "config").write_text(
            (nv_work / "config").read_text().replace("nvram=disable", "nvram=absent")
        )
        (nv_work / "config").chmod(0o600)
        # Without expected_nvram, data-only seal-publish refuses NVRAM mismatch.
        self.assertNotEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(nv_work.relative_to(self.root)),
            ).returncode,
            0,
        )
        # With expected_nvram="absent", seal-publish copies all invariant + unchanged profiles in C and succeeds.
        nv_pub = self._run_helper(
            "seal-publish",
            str(self.root),
            self.snapshot.name,
            str(nv_work.relative_to(self.root)),
            "absent",
        )
        self.assertEqual(nv_pub.returncode, 0, nv_pub.stderr)
        nv_cand_id = nv_pub.stdout.decode().strip()
        self.assertEqual(len(nv_cand_id), 64)
        # Active record with matching live NVRAM MUST still be refused by candidate audit.
        nvram.unlink()
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, nv_cand_id).returncode,
            0,
        )
        nvram.write_text("disable\n")
        # Before NVRAM changes, candidate audit refuses (live NVRAM is still disable).
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, nv_cand_id]
        self.save_record()
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, nv_cand_id).returncode,
            0,
        )
        # After NVRAM switches to absent (file unlinked), pending-set audit passes for nv_cand_id only.
        nvram.unlink()
        self.assertEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, nv_cand_id).returncode,
            0,
        )
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, cand_id).returncode,
            0,
        )
        nvram.write_text("disable\n")
        self.record[1] = "active"
        self.record[6:8] = ["-", "-"]
        self.save_record()

        # Non-private keys dir or bad key file mode must be refused.
        (self.data / "keys").chmod(0o755)
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        (self.data / "keys").chmod(0o700)
        key_path.chmod(0o644)
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name).returncode, 0
        )
        key_path.chmod(0o600)

    def test_seal_publish_matches_full_seal_and_rejects_tamper_drift_and_forged_prev(self):
        work, rows = self._clone_work(".new-eq", ("warning=1", "warning=0"))
        plan_in = (
            f"OCBP1|{self.baseline.name}|{self.package_id}\n"
            + "".join("|".join(r) + "\n" for r in rows)
        ).encode()
        full_out = self.ram / "full.plan"

        # Forged predecessor ID and non-.new-* work path are refused with rc=1.
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                "0" * 64,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(self.snapshot.relative_to(self.root)),
            ).returncode,
            1,
        )

        # Extra stray file in work is refused.
        stray = work / "stray"
        stray.write_text("bad\n")
        stray.chmod(0o600)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        stray.unlink()

        # Pre-planted invariant member (autostart) in work is refused (C must copy from snapshot).
        pre = work / "autostart"
        pre.write_bytes((self.snapshot / "autostart").read_bytes())
        pre.chmod(0o600)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        pre.unlink()

        # Modified supplied reusable profile (vui-plugins.list unchanged by warning 1->0) is refused.
        orig_vui_p = (work / "vui-plugins.list").read_bytes()
        (work / "vui-plugins.list").write_bytes(b"tampered-reusable\n")
        (work / "vui-plugins.list").chmod(0o600)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        (work / "vui-plugins.list").write_bytes(orig_vui_p)
        (work / "vui-plugins.list").chmod(0o600)
        for cleanup in (
            "autostart",
            "dependencies",
            "selector",
            "access",
            "runlogin",
            "sshd.conf",
            "boot.plan",
            "files.sha256",
        ):
            if (work / cleanup).exists():
                (work / cleanup).unlink()

        # Omitting a profile whose input changed (warning 1->0 requires mmui.xml) is refused.
        orig_mmui_p = (work / "mmui.xml").read_bytes()
        (work / "mmui.xml").unlink()
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        (work / "mmui.xml").write_bytes(orig_mmui_p)
        (work / "mmui.xml").chmod(0o600)
        for cleanup in (
            "autostart",
            "dependencies",
            "selector",
            "access",
            "runlogin",
            "sshd.conf",
            "boot.plan",
            "files.sha256",
        ):
            if (work / cleanup).exists():
                (work / cleanup).unlink()

        # Tampered or missing originals/mmui.xml is refused with rc=1.
        orig_xml = self.data / "originals/mmui.xml"
        orig_xml_bytes = orig_xml.read_bytes()
        orig_xml.write_bytes(b"corrupt xml\n")
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        orig_xml.unlink()
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        orig_xml.write_bytes(orig_xml_bytes)
        orig_xml.chmod(0o600)

        # Extra stray file in packages/<id> is refused with rc=1 (never fallback rc=95).
        pkg_stray = self.package / "stray-extra"
        pkg_stray.write_text("stray\n")
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        pkg_stray.unlink()

        # Tampered composed template read for warning=0 (sm-normal-off.conf) is refused with rc=1.
        comp_sm = self.composed / "sm-normal-off.conf"
        orig_comp_sm = comp_sm.read_bytes()
        comp_sm.write_bytes(orig_comp_sm + b"x")
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        comp_sm.write_bytes(orig_comp_sm)
        # Re-seal current snapshot's boot.plan after rewriting comp_sm so stat mtime matches.
        self.change_current("config", (self.snapshot / "config").read_text())

        # Wrong mode on a work member is refused.
        (work / "config").chmod(0o644)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(work.relative_to(self.root)),
            ).returncode,
            1,
        )
        (work / "config").chmod(0o600)

        # Valid seal-publish copies invariant members in C and produces a boot.plan
        # matching full seal on the published directory, accepted by check, audit, and select.
        pub = self._run_helper(
            "seal-publish",
            str(self.root),
            self.snapshot.name,
            str(work.relative_to(self.root)),
        )
        self.assertEqual(pub.returncode, 0, pub.stderr)
        snap_id = pub.stdout.decode().strip()
        self.assertEqual(len(snap_id), 64)
        published = self.data / "snapshots" / snap_id
        # Compare published boot.plan row set against a fresh full seal on the exact published files.
        full = self._run_helper(
            "seal",
            str(self.root),
            str(published.relative_to(self.root)),
            stdin=plan_in,
            stdout_path=full_out,
        )
        self.assertEqual(full.returncode, 0, full.stderr)
        full_lines = full_out.read_text().splitlines()
        pub_lines = (published / "boot.plan").read_text().splitlines()
        self.assertEqual(pub_lines[0], full_lines[0])
        self.assertEqual(sorted(pub_lines[1:]), sorted(full_lines[1:]))
        chk = self._run_helper(
            "check",
            str(self.root),
            str(published.relative_to(self.root)),
            stdin=(published / "boot.plan").read_bytes(),
        )
        self.assertEqual(chk.returncode, 0, chk.stderr)
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, snap_id]
        self.save_record()
        self.assertEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, snap_id).returncode,
            0,
        )
        self.record[1] = "active"
        self.record[6:8] = ["-", "-"]
        self.record[5] = snap_id
        self.save_record()
        self.assertEqual(self.invoke().returncode, 0)
        shutil.rmtree(self.ram)
        self.ram.mkdir(mode=0o700)
        self.record[5] = self.snapshot.name
        self.record[9] = "3"
        self.record[11] = "-"
        self.save_record()

        # Newly added conditional touch=2 rows return rc=92 on wrong stock device or tamper.
        for _, path, data, _ in self.TOUCH_INPUTS:
            self.put(path, data)
        t_work, _ = self._clone_work(".new-t2", ("touch=1", "touch=2"))
        (t_work / "config").write_text(
            (t_work / "config").read_text().replace("nvram=disable", "nvram=absent")
        )
        (t_work / "config").chmod(0o600)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(t_work.relative_to(self.root)),
                "absent",
                env={"OC_TOUCH_WRONG_FS": "1"},
            ).returncode,
            92,
        )
        shutil.rmtree(t_work)
        t_work, _ = self._clone_work(".new-t2", ("touch=1", "touch=2"))
        (t_work / "config").write_text(
            (t_work / "config").read_text().replace("nvram=disable", "nvram=absent")
        )
        (t_work / "config").chmod(0o600)
        self.put(self.TOUCH_INPUTS[0][1], "tampered devices\n")
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(t_work.relative_to(self.root)),
                "absent",
            ).returncode,
            92,
        )
        shutil.rmtree(t_work)
        t_work, _ = self._clone_work(".new-t2", ("touch=1", "touch=2"))
        (t_work / "config").write_text(
            (t_work / "config").read_text().replace("nvram=disable", "nvram=absent")
        )
        (t_work / "config").chmod(0o600)
        self.put(self.TOUCH_INPUTS[0][1], self.TOUCH_INPUTS[0][2])
        ok_touch = self._run_helper(
            "seal-publish",
            str(self.root),
            self.snapshot.name,
            str(t_work.relative_to(self.root)),
            "absent",
        )
        self.assertEqual(ok_touch.returncode, 0, ok_touch.stderr)
        t_id = ok_touch.stdout.decode().strip()
        t_plan = (self.data / "snapshots" / t_id / "boot.plan").read_text()
        self.assertIn("touch/devices/svc|", t_plan)
        self.assertIn("touch/devices/lib|", t_plan)

        # Supported exit from touch=2 when OEM devices lib changes:
        # leaving touch=2 (2->0) returns rc=95 (OC_SLOW fallback); staying at touch=2 returns rc=92.
        nvram = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        nvram.unlink()
        old_snap = self.snapshot
        self.snapshot = self.data / "snapshots" / t_id
        self.record[5] = t_id
        self.save_record()
        self.put(self.TOUCH_INPUTS[1][1], "changed OEM devices library\n")
        leave_work, _ = self._clone_work(".new-leave2", ("touch=2", "touch=0"))
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                t_id,
                str(leave_work.relative_to(self.root)),
            ).returncode,
            95,
        )
        shutil.rmtree(leave_work)
        stay_work, _ = self._clone_work(".new-stay2", ("warning=1", "warning=0"))
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                t_id,
                str(stay_work.relative_to(self.root)),
            ).returncode,
            92,
        )
        shutil.rmtree(stay_work)
        self.put(self.TOUCH_INPUTS[1][1], self.TOUCH_INPUTS[1][2])
        self.snapshot = old_snap
        self.record[5] = old_snap.name
        self.save_record()
        nvram.write_text("disable\n")

        # Base=1 newly added conditional inputs + ui-modules.tsv VUI plugin pin lookup.
        # Add ui-modules.tsv matching synthetic VUI payloads into a refreshed package + snapshot.
        vui_names = []
        tsv_lines = []
        for line in (ASSETS / "ui-modules.tsv").read_text().splitlines():
            if not line.startswith("vui\t"):
                tsv_lines.append(line)
                continue
            kind, name, group, _ = line.split("\t")
            payload = "authored retained plugin " + name + "\n"
            digest = sha(payload.encode())
            tsv_lines.append(f"{kind}\t{name}\t{group}\t{digest}")
            if group != "base":
                self.put("/jci/vui/plugins/" + name, payload)
                vui_names.append(name)
        for _, path, data, _ in self.BASE_INPUTS:
            self.put(path, data)
        # Re-publish package with ui-modules.tsv and re-seal current snapshot.
        new_pkg = self.data / "packages/.new-with-vui"
        new_pkg.mkdir(mode=0o700)
        for p in sorted(self.package.iterdir()):
            if p.name != "files.sha256":
                (new_pkg / p.name).write_bytes(p.read_bytes())
                (new_pkg / p.name).chmod(p.stat().st_mode & 0o777)
        (new_pkg / "ui-modules.tsv").write_text("\n".join(tsv_lines) + "\n")
        (new_pkg / "ui-modules.tsv").chmod(0o600)
        old_pkg_id = self.package_id
        self.package = self.publish(new_pkg)
        self.package_id = self.package.name
        new_comp = self.data / "composed" / self.package_id
        shutil.copytree(self.composed, new_comp)
        self.composed = new_comp
        self.record[3] = self.package_id
        # Rebuild dependencies and inputs for the updated package.
        new_deps = []
        new_inputs = []
        for key, path, digest in self.inputs:
            if key.startswith(f"package-{old_pkg_id}/"):
                continue
            if key.startswith(f"composed-{old_pkg_id}/"):
                leaf = key.split("/", 1)[1]
                key = f"composed-{self.package_id}/{leaf}"
                path = f"/tmp/mnt/data_persist/open-connect/composed/{self.package_id}/{leaf}"
            new_inputs.append((key, path, digest))
        for p in sorted(self.package.iterdir()):
            if p.name == "files.sha256":
                continue
            d = sha(p.read_bytes())
            new_inputs.append(
                (f"package-{self.package_id}/{p.name}", f"/{p.relative_to(self.root)}", d)
            )
            new_deps.append((d, f"package-{self.package_id}/{p.name}"))
        new_inputs.append(
            (
                f"package-{self.package_id}/files.sha256",
                f"/{(self.package / 'files.sha256').relative_to(self.root)}",
                self.package_id,
            )
        )
        new_deps.append((self.package_id, f"package-{self.package_id}/files.sha256"))
        for line in (self.snapshot / "dependencies").read_text().splitlines():
            d, k = line.split("  ", 1)
            if k.startswith(f"package-{old_pkg_id}/"):
                continue
            if k.startswith(f"composed-{old_pkg_id}/"):
                k = f"composed-{self.package_id}/" + k.split("/", 1)[1]
            new_deps.append((d, k))
        self.inputs = new_inputs
        self.change_current(
            "selector",
            f"{sha((self.package / 'boot-select').read_bytes())}|700:{os.getuid()}:{os.getgid()}|{self.package_id}\n",
        )
        self.change_current(
            "config",
            (self.snapshot / "config")
            .read_text()
            .replace(old_pkg_id, self.package_id)
            .replace(
                "service-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\n",
                "service-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n",
            ),
        )
        self.change_current(
            "dependencies",
            "".join(f"{d}  {k}\n" for d, k in new_deps),
        )
        # Test base=0 with non-empty vui-plugins.list is refused.
        b_bad, _ = self._clone_work(".new-vui-bad")
        (b_bad / "vui-plugins.list").write_text(vui_names[0] + "\n")
        (b_bad / "vui-plugins.list").chmod(0o600)
        self.assertNotEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(b_bad.relative_to(self.root)),
            ).returncode,
            0,
        )
        shutil.rmtree(b_bad)
        # Test base=1 with valid vui-plugins.list succeeds and records base/vui/* pins.
        b_work, _ = self._clone_work(".new-base1", ("base=0", "base=1"))
        (b_work / "vui-plugins.list").write_text("\n".join(vui_names) + "\n")
        (b_work / "vui-plugins.list").chmod(0o600)
        ok_base = self._run_helper(
            "seal-publish",
            str(self.root),
            self.snapshot.name,
            str(b_work.relative_to(self.root)),
        )
        self.assertEqual(ok_base.returncode, 0, ok_base.stderr)
        b_id = ok_base.stdout.decode().strip()
        b_plan = (self.data / "snapshots" / b_id / "boot.plan").read_text()
        self.assertIn(f"base/vui/{vui_names[0]}|", b_plan)
        self.record[1] = "set"
        self.record[6:8] = [self.snapshot.name, b_id]
        self.save_record()
        self.assertEqual(
            self._run_helper("audit", str(self.root), self.snapshot.name, b_id).returncode,
            0,
        )
        self.record[1] = "active"
        self.record[6:8] = ["-", "-"]
        self.save_record()
        # Smart pin reuse: toggling wireless while base=1 stays 1 reuses
        # verified base/* and base/vui/* rows cleanly and passes audit.
        saved_snap = self.snapshot
        self.snapshot = self.data / "snapshots" / b_id
        self.record[5] = b_id
        self.save_record()
        b_reuse, _ = self._clone_work(".new-base1-reuse", ("wireless=1", "wireless=0"))
        (b_reuse / "vui-plugins.list").unlink()
        ok_reuse = self._run_helper(
            "seal-publish",
            str(self.root),
            b_id,
            str(b_reuse.relative_to(self.root)),
        )
        self.assertEqual(ok_reuse.returncode, 0, ok_reuse.stderr)
        b_reuse_id = ok_reuse.stdout.decode().strip()
        b_reuse_plan = (self.data / "snapshots" / b_reuse_id / "boot.plan").read_text()
        self.assertIn(f"base/vui/{vui_names[0]}|", b_reuse_plan)
        self.record[5] = b_reuse_id
        self.save_record()
        self.assertEqual(self._run_helper("audit", str(self.root), b_reuse_id).returncode, 0)
        # Smart pin reuse for touch=2 staying 2: toggling wireless reuses touch/devices/* pins
        # cleanly, and tampering a touch/devices/* file during reuse is still refused with rc=92.
        self.snapshot = self.data / "snapshots" / b_reuse_id
        t2_work, _ = self._clone_work(
            ".new-touch2-seed", ("touch=1", "touch=2"), profiles=("sm-normal.conf", "sm-wcp.conf")
        )
        (t2_work / "config").write_text(
            (t2_work / "config").read_text().replace("nvram=disable", "nvram=absent")
        )
        (t2_work / "config").chmod(0o600)
        ok_t2 = self._run_helper(
            "seal-publish",
            str(self.root),
            b_reuse_id,
            str(t2_work.relative_to(self.root)),
            "absent",
        )
        self.assertEqual(ok_t2.returncode, 0, ok_t2.stderr)
        t2_id = ok_t2.stdout.decode().strip()
        self.snapshot = self.data / "snapshots" / t2_id
        self.record[5] = t2_id
        self.save_record()
        nvram_path = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        saved_nv = nvram_path.read_bytes()
        nvram_path.unlink()
        t2_reuse, _ = self._clone_work(
            ".new-touch2-reuse",
            ("wireless=0", "wireless=1"),
            profiles=("sm-normal.conf", "sm-wcp.conf"),
        )
        ok_t2r = self._run_helper(
            "seal-publish",
            str(self.root),
            t2_id,
            str(t2_reuse.relative_to(self.root)),
        )
        self.assertEqual(ok_t2r.returncode, 0, ok_t2r.stderr)
        t2r_id = ok_t2r.stdout.decode().strip()
        t2r_plan = (self.data / "snapshots" / t2r_id / "boot.plan").read_text()
        self.assertIn("touch/devices/svc|", t2r_plan)
        self.snapshot = self.data / "snapshots" / t2r_id
        self.record[5] = t2r_id
        self.save_record()
        self.assertEqual(self._run_helper("audit", str(self.root), t2r_id).returncode, 0)
        # Tampering touch/devices/svc while touch=2 stays 2 must be refused with rc=92.
        saved_svc = (self.root / "jci/devices/svc-com-jci-cpp-devices.so").read_bytes()
        self.put("/jci/devices/svc-com-jci-cpp-devices.so", "tampered devices\n")
        t2_bad, _ = self._clone_work(
            ".new-touch2-bad",
            ("wireless=1", "wireless=0"),
            profiles=("sm-normal.conf", "sm-wcp.conf"),
        )
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                t2r_id,
                str(t2_bad.relative_to(self.root)),
            ).returncode,
            92,
        )
        shutil.rmtree(t2_bad)
        self.put("/jci/devices/svc-com-jci-cpp-devices.so", saved_svc)
        nvram_path.write_bytes(saved_nv)
        self.snapshot = saved_snap
        self.record[5] = saved_snap.name
        self.save_record()
        # Tampered VUI plugin on disk is refused with rc=93 (base_inputs_changed).
        self.put("/jci/vui/plugins/" + vui_names[0], "tampered vui plugin\n")
        b_tamper, _ = self._clone_work(".new-base1-tamper", ("base=0", "base=1"))
        (b_tamper / "vui-plugins.list").write_text("\n".join(vui_names) + "\n")
        (b_tamper / "vui-plugins.list").chmod(0o600)
        self.assertEqual(
            self._run_helper(
                "seal-publish",
                str(self.root),
                self.snapshot.name,
                str(b_tamper.relative_to(self.root)),
            ).returncode,
            93,
        )
        shutil.rmtree(b_tamper)

    def test_native_api_fast_set_e2e_nvram_cuts_and_integrity_hard_refusal(self):
        # Exercise the REAL host-compiled ASan+UBSan `api` binary over HTTP POST /control
        # against the rooted fixture and real `boot-select`:
        # 1) Trust-anchor / tamper checks (tampered/missing session files.sha256, wrong mode
        #    or tampered persistent boot-select, stray undeclared boot.plan, extra package file)
        #    all hard-refuse with state_changed without falling back to backend.sh.
        # 2) NO_BS package and genuinely unsealed OC2 snapshot fall back cleanly to backend.sh.
        # 3) Data-only save (carplay-autoshow 0->1->0) runs 100% natively in `api` (sentinel
        #    backend.sh never executed), matches AWK index.html rendering, preserves unchanged
        #    profiles, passes audit, and runs GC.
        # 4) NVRAM-changing save (touch 1->0->1) uses native oc_nvram_change, witnesses pending
        #    OC1 before NVRAM write, handles pre/post-NVRAM cuts, and commits cleanly.
        # 5) Real backend.sh unsealed OC2 fallback check remains green.
        api_bin = compile_host_api()
        nvram_file = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        tok = "a" * 32

        pkg_dir = self.data / "packages/.new-e2epkg"
        pkg_dir.mkdir(mode=0o700)
        for p in sorted(self.package.iterdir()):
            if p.name != "files.sha256":
                (pkg_dir / p.name).write_bytes(p.read_bytes())
                (pkg_dir / p.name).chmod(p.stat().st_mode & 0o777)
        for extra in ("ui-profile.awk", "ui-modules.tsv", "system-hook.js", "base-logging.js"):
            (pkg_dir / extra).write_bytes((ASSETS / extra).read_bytes())
            (pkg_dir / extra).chmod(0o600)
        old_pkg_id = self.package_id
        self.package = self.publish(pkg_dir)
        self.package_id = self.package.name
        new_comp = self.data / "composed" / self.package_id
        shutil.copytree(self.composed, new_comp)
        from tests.test_installer_preferences import InstallerPreferences

        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        for nm in ("index-on.html", "index-off.html"):
            (new_comp / nm).write_text(idx_tpl)
            (new_comp / nm).chmod(0o600)
        for nm, wcp in (
            ("sm-normal-on.conf", False),
            ("sm-normal-off.conf", False),
            ("sm-wcp-on.conf", True),
            ("sm-wcp-off.conf", True),
        ):
            (new_comp / nm).write_text(InstallerPreferences().profile(wcp))
            (new_comp / nm).chmod(0o600)
        self.manifest(new_comp)
        self.composed = new_comp
        self.record[3] = self.package_id
        new_deps, new_inputs = [], []
        for key, path, digest in self.inputs:
            if key.startswith(f"package-{old_pkg_id}/") or key.startswith(
                f"composed-{old_pkg_id}/"
            ):
                continue
            new_inputs.append((key, path, digest))
        for kind, folder in (("package", self.package), ("composed", self.composed)):
            mf_id = sha((folder / "files.sha256").read_bytes())
            for p in sorted(folder.iterdir()):
                if p.name == "files.sha256":
                    continue
                d = sha(p.read_bytes())
                new_inputs.append(
                    (f"{kind}-{self.package_id}/{p.name}", f"/{p.relative_to(self.root)}", d)
                )
                new_deps.append((d, f"{kind}-{self.package_id}/{p.name}"))
            new_inputs.append(
                (
                    f"{kind}-{self.package_id}/files.sha256",
                    f"/{(folder / 'files.sha256').relative_to(self.root)}",
                    mf_id,
                )
            )
            new_deps.append((mf_id, f"{kind}-{self.package_id}/files.sha256"))
        for line in (self.snapshot / "dependencies").read_text().splitlines():
            d, k = line.split("  ", 1)
            if k.startswith(f"package-{old_pkg_id}/") or k.startswith(f"composed-{old_pkg_id}/"):
                continue
            new_deps.append((d, k))
        self.inputs = new_inputs
        self.change_current(
            "selector",
            f"{sha((self.package / 'boot-select').read_bytes())}|700:{os.getuid()}:{os.getgid()}|{self.package_id}\n",
        )
        self.change_current(
            "config",
            (self.snapshot / "config")
            .read_text()
            .replace(old_pkg_id, self.package_id)
            .replace(
                "service-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\n",
                "service-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n",
            ),
        )
        self.change_current("dependencies", "".join(f"{d}  {k}\n" for d, k in new_deps))

        session = self.ram / "sessions/session-ap0001"
        session.mkdir(parents=True, mode=0o700)
        shutil.copyfile(self.package / "files.sha256", session / "files.sha256")
        (session / "files.sha256").chmod(0o600)
        shutil.copyfile(self.package / "VERSION", session / "VERSION")
        (session / "VERSION").chmod(0o600)
        (session / "token").write_text(tok + "\n")
        (session / "token").chmod(0o600)
        sentinel_be = session / "backend.sh"
        sentinel_be.write_text('printf \'{"ok":false,"error":"fell_back"}\\n\'\nexit 0\n')
        sentinel_be.chmod(0o700)
        nv_store = nvram_file.parent.parent
        for ctl in ("add", "remove", "commit"):
            (nv_store / ctl).write_text("")
        (self.ram / "lock").write_text("")
        (self.ram / "lock").chmod(0o600)
        (self.ram / "selected").write_text(self.snapshot.name + "\n")
        (self.ram / "selected").chmod(0o600)
        (self.ram / "boot-id").symlink_to(BOOT)
        (self.ram / "runtime").symlink_to(session)

        env = self._host_env(
            {
                "PATH": self.build.name + os.pathsep + os.environ["PATH"],
                "OC_HOST_ROOT": str(self.root),
                "OC_HOST_NONROOT": "1",
                "OC_HOST_SKIP_FW_GUARD": "1",
                "OC_HOST_WIRELESS_FILE": str(self.root / "no-wireless"),
            }
        )

        def call_api(rev, op, arg, exp="-", des="-", *, extra_env=None):
            body = f"{tok}|{rev}|{op}|{arg}|{exp}|{des}".encode()
            req = (
                b"POST /control HTTP/1.1\r\nHost: 127.0.0.1:15555\r\n"
                b"Content-Type: text/plain;charset=UTF-8\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
                + body
            )
            run_env = {**env, **(extra_env or {})}
            proc = subprocess.run(
                [str(api_bin), str(session / "token"), str(sentinel_be)],
                input=req,
                env=run_env,
                capture_output=True,
                timeout=15,
            )
            _, payload = proc.stdout.split(b"\r\n\r\n", 1)
            return proc, json.loads(payload)

        # 1) Data-only save: carplay-autoshow 0 -> 1 via native api (never hits sentinel backend.sh).
        orig_cur = self.snapshot.name
        proc, reply = call_api(orig_cur, "set", "carplay-autoshow", "0", "1")
        self.assertEqual(proc.returncode, 0, (reply, proc.stderr))
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["carplayAutoshow"], 1)
        cur1 = reply["revision"]
        self.assertNotEqual(cur1, orig_cur)
        self.assertEqual(self._run_helper("audit", str(self.root), cur1).returncode, 0)
        new_snap = self.data / "snapshots" / cur1
        for unchanged in ("mmui.xml", "vui-plugins.list", "sm-normal.conf", "sm-wcp.conf"):
            self.assertEqual(
                (new_snap / unchanged).read_bytes(), (self.snapshot / unchanged).read_bytes()
            )
        self.assertIn("carplay.js", (new_snap / "index.html").read_text())

        # No-op set runs native audit and never falls back.
        proc, noop_reply = call_api(cur1, "set", "carplay-autoshow", "1", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(noop_reply["ok"], noop_reply)
        self.assertEqual(noop_reply["revision"], cur1)

        # 2) Trust-anchor & tamper refusals (non-ctime-mutating): hard state_changed, NEVER falls back.
        # (a) Tampered RAM session files.sha256
        orig_ram_mf = (session / "files.sha256").read_bytes()
        (session / "files.sha256").write_bytes(orig_ram_mf + b"\n")
        _, r_mf = call_api(cur1, "set", "carplay-autoshow", "1", "0")
        (session / "files.sha256").write_bytes(orig_ram_mf)
        self.assertEqual(r_mf["error"], "state_changed")
        # (b) Extra package file causes hard state_changed on both no-op and mutating set.
        pkg_extra = self.package / "be-extra"
        pkg_extra.write_text("bad\n")
        _, r_en = call_api(cur1, "set", "carplay-autoshow", "1", "1")
        _, r_es = call_api(cur1, "set", "carplay-autoshow", "1", "0")
        pkg_extra.unlink()
        self.assertEqual(r_en["error"], "state_changed")
        self.assertEqual(r_es["error"], "state_changed")

        # 3) NVRAM-changing save: touch 1 -> 0 -> 1 via native oc_nvram_change.
        # Pre-NVRAM cut witnesses pending OC1 written BEFORE NVRAM mutation.
        _, r_pre0 = call_api(
            cur1, "set", "touch", "1", "0", extra_env={"OC_HOST_NVRAM_FAIL": "before"}
        )
        self.assertEqual(r_pre0["error"], "nvram_commit_failed")
        witnessed = (self.data / "record").read_text().strip().split("|")
        self.assertEqual((witnessed[1], witnessed[5], witnessed[6]), ("set", cur1, cur1))
        self.assertEqual(nvram_file.read_text(), "disable\n")
        # Restore active cur1 and complete touch 1 -> 0 cleanly.
        witnessed[1] = "active"
        witnessed[6:8] = ["-", "-"]
        (self.data / "record").write_text("|".join(witnessed) + "\n")
        proc, r_off = call_api(cur1, "set", "touch", "1", "0")
        self.assertEqual(proc.returncode, 0, (r_off, proc.stderr))
        self.assertTrue(r_off["ok"], r_off)
        off_cur = r_off["revision"]
        self.assertFalse(nvram_file.exists())
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur).returncode, 0)

        # Pre-NVRAM cut on 0 -> 1: pending OC1 intact, current-only audit refuses, candidate audit requires NVRAM.
        _, r_pre = call_api(
            off_cur, "set", "touch", "0", "1", extra_env={"OC_HOST_NVRAM_FAIL": "before"}
        )
        self.assertEqual(r_pre["error"], "nvram_commit_failed")
        rec = (self.data / "record").read_text().strip().split("|")
        self.assertEqual((rec[1], rec[5], rec[6]), ("set", off_cur, off_cur))
        self.assertNotEqual(self._run_helper("audit", str(self.root), off_cur).returncode, 0)
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), off_cur, rec[7]).returncode, 0
        )
        nvram_file.write_text("disable\n")
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur, rec[7]).returncode, 0)

        # Restore active off_cur + absent NVRAM, then exercise post-NVRAM cut (after_nvram).
        nvram_file.unlink()
        rec[1] = "active"
        rec[6:8] = ["-", "-"]
        (self.data / "record").write_text("|".join(rec) + "\n")
        _, r_post = call_api(
            off_cur, "set", "touch", "0", "1", extra_env={"OC_HOST_NVRAM_FAIL": "after"}
        )
        self.assertEqual(r_post["error"], "nvram_commit_failed")
        rec2 = (self.data / "record").read_text().strip().split("|")
        self.assertEqual((rec2[1], rec2[5], rec2[6]), ("set", off_cur, off_cur))
        self.assertEqual(nvram_file.read_text(), "disable\n")
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur, rec2[7]).returncode, 0)

        # Restore active off_cur + absent NVRAM and complete touch 0 -> 1 cleanly.
        nvram_file.unlink()
        rec2[1] = "active"
        rec2[6:8] = ["-", "-"]
        (self.data / "record").write_text("|".join(rec2) + "\n")
        proc, r_on = call_api(off_cur, "set", "touch", "0", "1")
        self.assertEqual(proc.returncode, 0, (r_on, proc.stderr))
        self.assertTrue(r_on["ok"], r_on)
        on_cur = r_on["revision"]
        self.assertEqual(nvram_file.read_text(), "disable\n")
        self.assertEqual(self._run_helper("audit", str(self.root), on_cur).returncode, 0)

        # Toggle carplay-autoshow 1 -> 0 cleanly too.
        proc, r_back = call_api(on_cur, "set", "carplay-autoshow", "1", "0")
        self.assertEqual(proc.returncode, 0, (r_back, proc.stderr))
        self.assertEqual(r_back["carplayAutoshow"], 0)
        on_cur = r_back["revision"]

        # 4) E2E sp_rc == 95 (OC_SLOW) fallback through api: touch=2 with drifted
        # touch/devices/svc while setting touch 2 -> 1 unlocks and falls back cleanly.
        pre_t2_rec = (self.data / "record").read_bytes()
        for _, tpath, tdata, _ in self.TOUCH_INPUTS:
            self.put(tpath, tdata)
        (self.ram / "selected").write_text(on_cur + "\n")
        proc, r_t2 = call_api(on_cur, "set", "touch", "1", "2")
        self.assertEqual(proc.returncode, 0, (r_t2, proc.stderr))
        self.assertTrue(r_t2["ok"], r_t2)
        t2_cur = r_t2["revision"]
        saved_dev_svc = (self.root / "jci/devices/svc-com-jci-cpp-devices.so").read_bytes()
        self.put("/jci/devices/svc-com-jci-cpp-devices.so", "drifted devices\n")
        _, r_slow = call_api(t2_cur, "set", "touch", "2", "1")
        self.assertEqual(r_slow["error"], "fell_back")
        self.put("/jci/devices/svc-com-jci-cpp-devices.so", saved_dev_svc)
        (self.data / "record").write_bytes(pre_t2_rec)
        nvram_file.write_text("disable\n")

        # 5) Native api falls back cleanly to backend.sh on genuinely unsealed OC2 snapshot
        # and NO_BS selector-less package, while hard-refusing tamper/malformed-manifest/
        # stray-plan/tampered-AWK conditions.
        unsealed_work = self.data / "snapshots/.new-be-unsealed"
        unsealed_work.mkdir(mode=0o700)
        for p in sorted((self.data / "snapshots" / on_cur).iterdir()):
            if p.name not in ("files.sha256", "boot.plan"):
                (unsealed_work / p.name).write_bytes(p.read_bytes())
                (unsealed_work / p.name).chmod(0o600)
        unsealed_snap = self.publish(unsealed_work)
        saved_rec = (self.data / "record").read_bytes()
        unsealed_rec = saved_rec.decode().strip().split("|")
        unsealed_rec[5] = unsealed_snap.name
        (self.data / "record").write_text("|".join(unsealed_rec) + "\n")
        (self.ram / "selected").write_text(unsealed_snap.name + "\n")
        _, r_fb = call_api(unsealed_snap.name, "set", "carplay-autoshow", "0", "1")
        self.assertEqual(r_fb["error"], "fell_back")
        # Undeclared boot.plan on disk inside unsealed snapshot hard-fails (never falls back).
        (unsealed_snap / "boot.plan").write_bytes(b"stray\n")
        (unsealed_snap / "boot.plan").chmod(0o600)
        _, r_stray = call_api(unsealed_snap.name, "set", "carplay-autoshow", "0", "1")
        (unsealed_snap / "boot.plan").unlink()
        self.assertEqual(r_stray["error"], "state_changed")
        # Missing declared boot.plan on disk hard-fails (never falls back).
        (self.data / "record").write_bytes(saved_rec)
        (self.ram / "selected").write_text(on_cur + "\n")
        saved_plan = (self.data / "snapshots" / on_cur / "boot.plan").read_bytes()
        (self.data / "snapshots" / on_cur / "boot.plan").unlink()
        _, r_miss_plan = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        (self.data / "snapshots" / on_cur / "boot.plan").write_bytes(saved_plan)
        (self.data / "snapshots" / on_cur / "boot.plan").chmod(0o600)
        self.assertEqual(r_miss_plan["error"], "state_changed")
        # Malformed session/package manifest shapes all hard-fail with state_changed.
        orig_sess_mf = (session / "files.sha256").read_bytes()
        for bad_mf in (
            b"",
            orig_sess_mf + orig_sess_mf,
            orig_sess_mf.replace(b"  ", b" ", 1),
            orig_sess_mf.rstrip(b"\n"),
            orig_sess_mf + b"\x00",
        ):
            (session / "files.sha256").write_bytes(bad_mf)
            _, r_badmf = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
            self.assertEqual(r_badmf["error"], "state_changed")
        (session / "files.sha256").write_bytes(orig_sess_mf)
        # Tampered persistent AWK script (sm-profile.awk) hard-fails without fallback.
        sm_awk = self.package / "sm-profile.awk"
        orig_sm_awk = sm_awk.read_bytes()
        sm_awk.write_bytes(orig_sm_awk + b"\n# tamper\n")
        _, r_awk = call_api(on_cur, "set", "wireless", "1", "0")
        sm_awk.write_bytes(orig_sm_awk)
        self.assertEqual(r_awk["error"], "state_changed")
        # NO_BS selector-less package: clean unsealed snapshot falls back; declared boot.plan
        # or stray undeclared boot-select on disk hard-fails with state_changed.
        nobs_dir = self.data / "packages/.new-nobs-e2e"
        nobs_dir.mkdir(mode=0o700)
        for p in sorted(self.package.iterdir()):
            if p.name not in ("files.sha256", "boot-select"):
                (nobs_dir / p.name).write_bytes(p.read_bytes())
                (nobs_dir / p.name).chmod(p.stat().st_mode & 0o777)
        nobs_pkg = self.publish(nobs_dir)
        nobs_snap_work = self.data / "snapshots/.new-nobs-snap"
        nobs_snap_work.mkdir(mode=0o700)
        for p in sorted((self.data / "snapshots" / on_cur).iterdir()):
            if p.name not in ("files.sha256", "boot.plan"):
                body = p.read_bytes()
                if p.name == "config":
                    body = body.replace(self.package_id.encode(), nobs_pkg.name.encode())
                (nobs_snap_work / p.name).write_bytes(body)
                (nobs_snap_work / p.name).chmod(0o600)
        nobs_snap = self.publish(nobs_snap_work)
        nobs_rec = saved_rec.decode().strip().split("|")
        nobs_rec[3] = nobs_pkg.name
        nobs_rec[5] = nobs_snap.name
        (self.data / "record").write_text("|".join(nobs_rec) + "\n")
        (self.ram / "selected").write_text(nobs_snap.name + "\n")
        shutil.copyfile(nobs_pkg / "files.sha256", session / "files.sha256")
        _, r_nobs_fb = call_api(nobs_snap.name, "set", "carplay-autoshow", "0", "1")
        self.assertEqual(r_nobs_fb["error"], "fell_back")
        # NO_BS + stray undeclared boot-select on disk -> hard state_changed.
        (nobs_pkg / "boot-select").write_bytes(b"stray\n")
        (nobs_pkg / "boot-select").chmod(0o700)
        _, r_nobs_stray = call_api(nobs_snap.name, "set", "carplay-autoshow", "0", "1")
        (nobs_pkg / "boot-select").unlink()
        self.assertEqual(r_nobs_stray["error"], "state_changed")
        # NO_BS + declared boot.plan -> hard state_changed.
        nobs_plan_work = self.data / "snapshots/.new-nobs-plan"
        nobs_plan_work.mkdir(mode=0o700)
        for p in sorted(nobs_snap.iterdir()):
            if p.name != "files.sha256":
                (nobs_plan_work / p.name).write_bytes(p.read_bytes())
                (nobs_plan_work / p.name).chmod(0o600)
        (nobs_plan_work / "boot.plan").write_text("OCBP1\n")
        (nobs_plan_work / "boot.plan").chmod(0o600)
        nobs_plan_snap = self.publish(nobs_plan_work)
        nobs_rec[5] = nobs_plan_snap.name
        (self.data / "record").write_text("|".join(nobs_rec) + "\n")
        (self.ram / "selected").write_text(nobs_plan_snap.name + "\n")
        _, r_nobs_plan = call_api(nobs_plan_snap.name, "set", "carplay-autoshow", "0", "1")
        self.assertEqual(r_nobs_plan["error"], "state_changed")
        # Restore clean sealed state before real backend.sh fallback check.
        shutil.copyfile(self.package / "files.sha256", session / "files.sha256")
        (self.data / "record").write_bytes(saved_rec)
        (self.ram / "selected").write_text(on_cur + "\n")

        # Real backend.sh unsealed OC2 fallback check:
        # Build a genuinely unsealed OC2 snapshot (no boot.plan in manifest or disk) and
        # run real backend.sh with real transaction_prepare/transaction_reconcile.
        # Clean control must succeed; an extra package file must return state_changed with
        # original OC1 bytes and unchanged NVRAM on both no-op and touch 1->0.
        fb_session = self.ram / "sessions/session-befb01"
        fb_session.mkdir(parents=True, mode=0o700)
        for p in sorted(self.package.iterdir()):
            (fb_session / p.name).write_bytes(p.read_bytes())
            (fb_session / p.name).chmod(p.stat().st_mode & 0o777)
        shutil.copyfile(api_bin, fb_session / "api")
        (fb_session / "api").chmod(0o700)
        fb_be = (
            (ASSETS / "backend.sh")
            .read_text()
            .replace("/tmp/mnt/data_persist/open-connect", str(self.data))
            .replace("/tmp/open-connect", str(self.ram))
            .replace("/usr/bin/autostart", str(self.root / "usr/bin/autostart"))
            .replace("firmware_guard ", "# firmware_guard ")
            .replace("flock -n -x 9 || fail busy", ":")
            .replace("flock -n -s 9 || fail busy", ":")
            .replace(
                '. "$P/transaction.sh"',
                '. "$P/transaction.sh"\n'
                'uuid() { printf "%s\\n" "0123456789abcdef0123456789abcdef"; }\n'
                "firmware_guard() { :; }\n"
                "factory_wireless() { return 1; }\n"
                f"nvram_read() {{ if test -f {shlex.quote(str(nvram_file))}; then cat {shlex.quote(str(nvram_file))}; else echo absent; fi; }}\n"
                f'nvram_change() {{ if test "$2" = absent; then rm -f {shlex.quote(str(nvram_file))}; else printf "%s\\n" "$2" > {shlex.quote(str(nvram_file))}; fi; }}\n'
                "selector_matches_loaded() { return 0; }\n"
                "selector_pair_check() { return 0; }\n"
                "startup_publish() { :; }\n",
            )
        )
        (fb_session / "backend.sh").write_text(fb_be)
        (fb_session / "backend.sh").chmod(0o700)
        fb_fw = (
            (ASSETS / "firmware.sh")
            .read_text()
            .replace("/proc/mounts", str(self.root / "proc/mounts"))
            .replace("/tmp/mnt/data_persist/open-connect", str(self.data))
            .replace("/tmp/open-connect", str(self.ram))
            .replace("firmware_dependencies()", "_unused_fw_deps()")
        )
        # Preserve host root paths in firmware_dependencies for real dependencies_match.
        fw_deps_lines = "\n".join(
            f"  printf '%s\\n' '{d} {k.split('/', 1)[1]} {self.root}{p}'"
            for k, p, d in self.inputs
            if k.startswith("root/")
        )
        fb_fw = fb_fw.replace(
            "/usr/bin/open-connect-boot-select",
            str(self.root / "usr/bin/open-connect-boot-select"),
        ).replace(
            "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29",
            sha(b"stock manager.so\n"),
        )
        fb_fw += (
            f"\nfirmware_dependencies() {{\n{fw_deps_lines}\n}}\n"
            'boot_snapshot_seal() { P=$D/packages/$R_BACKEND boot_dependencies_match "$1" || return 1; printf "%s\\n" "$1"; }\n'
        )
        (fb_session / "firmware.sh").write_text(fb_fw)
        (fb_session / "access.sh").write_text(
            (ASSETS / "access.sh")
            .read_text()
            .replace("/usr/bin/runlogin", str(self.root / "usr/bin/runlogin"))
            .replace("/etc/ssh/sshd_config", str(self.root / "etc/ssh/sshd_config"))
            .replace(
                "/usr/bin/.open-connect-runlogin-",
                str(self.root / "usr/bin/.open-connect-runlogin-"),
            )
        )
        (fb_session / "state.sh").write_text(
            (ASSETS / "state.sh")
            .read_text()
            .replace("SEAL_BOOT_PLAN=$6", "SEAL_BOOT_PLAN=0")
            .replace(
                '. "$P/firmware.sh";',
                '. "$P/firmware.sh"; '
                'boot_render_profiles() { for n in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do cp "$D/snapshots/'
                + unsealed_snap.name
                + '/$n" "$1/$n"; done; };',
            )
        )
        # Point runtime to fb_session, OC1 to unsealed_snap, NVRAM to disable.
        orig_rec_bytes = (self.data / "record").read_bytes()
        fb_rec = orig_rec_bytes.decode().strip().split("|")
        fb_rec[5] = unsealed_snap.name
        unsealed_rec_bytes = ("|".join(fb_rec) + "\n").encode()
        (self.data / "record").write_bytes(unsealed_rec_bytes)
        (self.ram / "selected").write_text(unsealed_snap.name + "\n")
        (self.ram / "runtime").unlink()
        (self.ram / "runtime").symlink_to(fb_session)
        nvram_file.write_text("disable\n")

        def call_fb(*args):
            return subprocess.run(
                ["sh", str(fb_session / "backend.sh"), "api", *args],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

        # Extra file in package: both no-op and touch 1->0 fail with state_changed,
        # preserving original OC1 bytes and NVRAM = disable.
        extra_fb = self.package / "stray-fallback"
        extra_fb.write_text("stray\n")
        fb_noop = call_fb(unsealed_snap.name, "set", "carplay-autoshow", "0", "0")
        self.assertNotEqual(fb_noop.returncode, 0)
        self.assertEqual(json.loads(fb_noop.stdout)["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), unsealed_rec_bytes)
        self.assertEqual(nvram_file.read_text(), "disable\n")
        fb_touch = call_fb(unsealed_snap.name, "set", "touch", "1", "0")
        self.assertNotEqual(fb_touch.returncode, 0)
        self.assertEqual(json.loads(fb_touch.stdout)["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), unsealed_rec_bytes)
        self.assertEqual(nvram_file.read_text(), "disable\n")
        extra_fb.unlink()

        # Clean control: unsealed OC2 touch 1->0 succeeds, settles active, clears NVRAM.
        fb_clean = call_fb(unsealed_snap.name, "set", "touch", "1", "0")
        self.assertEqual(fb_clean.returncode, 0, fb_clean.stdout + fb_clean.stderr)
        fb_clean_out = json.loads(fb_clean.stdout)
        self.assertTrue(fb_clean_out["ok"])
        self.assertEqual(fb_clean_out["touch"], 0)
        self.assertEqual((self.data / "record").read_text().strip().split("|")[1], "active")
        self.assertFalse(nvram_file.exists())

        # Restore original sealed snapshot + runtime + NVRAM for subsequent checks.
        (self.data / "record").write_bytes(orig_rec_bytes)
        (self.ram / "selected").write_text(on_cur + "\n")
        (self.ram / "runtime").unlink()
        (self.ram / "runtime").symlink_to(session)
        nvram_file.write_text("disable\n")

        # Oversized composed template (> 262144 B) is refused before native index render.
        idx_on = self.composed / "index-on.html"
        orig_idx_on = idx_on.read_bytes()
        idx_on.write_bytes(b"a" * 262145)
        before_ov = (self.data / "record").read_bytes()
        ov_proc, ov_res = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        idx_on.write_bytes(orig_idx_on)
        idx_on.chmod(0o600)
        self.assertNotEqual(ov_proc.returncode, 0)
        self.assertEqual(ov_res["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_ov)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])

        # Hard integrity refusals reach caller as state_changed and leave OC1/work clean.
        before_rec = (self.data / "record").read_bytes()
        extra = self.package / "unexpected-extra"
        extra.write_text("bad\n")
        ref_proc, refused = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        extra.unlink()
        self.assertNotEqual(ref_proc.returncode, 0)
        self.assertEqual(refused["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_rec)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])

        # Symlink in predecessor snapshot (autostart) is refused by C O_NOFOLLOW without copying.
        cur_snap = self.data / "snapshots" / on_cur
        orig_auto = (cur_snap / "autostart").read_bytes()
        (cur_snap / "autostart").unlink()
        (cur_snap / "autostart").symlink_to("/etc/passwd")
        link_proc, refused_link = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        (cur_snap / "autostart").unlink()
        (cur_snap / "autostart").write_bytes(orig_auto)
        (cur_snap / "autostart").chmod(0o600)
        self.assertNotEqual(link_proc.returncode, 0)
        self.assertEqual(refused_link["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_rec)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])

        # Persistent boot-select mode/byte tamper hard-refuses state_changed (never falls back).
        (self.package / "boot-select").chmod(0o600)
        _, r_mode = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        (self.package / "boot-select").chmod(0o700)
        self.assertEqual(r_mode["error"], "state_changed")
        orig_bs = (self.package / "boot-select").read_bytes()
        (self.package / "boot-select").write_bytes(orig_bs[:-1] + bytes([orig_bs[-1] ^ 1]))
        (self.package / "boot-select").chmod(0o700)
        _, r_bs = call_api(on_cur, "set", "carplay-autoshow", "0", "1")
        (self.package / "boot-select").write_bytes(orig_bs)
        (self.package / "boot-select").chmod(0o700)
        self.assertEqual(r_bs["error"], "state_changed")

    def _make_dummy_snapshot(self, tag, extra_file=None):
        work = self.data / "snapshots" / f".new-gc-{tag}"
        work.mkdir(mode=0o700)
        for nm, val in (
            ("autostart", f"snap-{tag}\n"),
            ("config", f"OC2\ntag={tag}\n"),
            ("boot.plan", f"OCBP1|plan-{tag}\n"),
        ):
            (work / nm).write_text(val)
            (work / nm).chmod(0o600)
        snap = self.publish(work)
        if extra_file is not None:
            (snap / extra_file).write_text("unlisted\n")
            (snap / extra_file).chmod(0o600)
        return snap

    def _run_gc(self, *, lock_fd=None, cut=None):
        cmd = [self.program, "gc", self.root]
        pass_fds = ()
        if lock_fd is not None:
            cmd.append(str(lock_fd))
            pass_fds = (lock_fd,)
        env = self._host_env({"OC_BOOT_CUT": cut} if cut else None)
        return subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            pass_fds=pass_fds,
            timeout=5,
        )

    def test_gc_prunes_unreachable_bounded_resumes_tombstones_and_protects_pins(self):
        import fcntl

        lock_path = self.ram / "lock"
        lock_path.write_bytes(b"")
        lock_path.chmod(0o600)

        # Create pinned selected & access-selected snapshots distinct from R_BASE / R_CURRENT.
        pin_sel = self._make_dummy_snapshot("pin-sel")
        pin_acc = self._make_dummy_snapshot("pin-acc")
        (self.ram / "selected").write_text(pin_sel.name + "\n")
        (self.ram / "selected").chmod(0o600)
        (self.ram / "access-selected").write_text(pin_acc.name + "\n")
        (self.ram / "access-selected").chmod(0o600)

        # Create 6 unreachable valid snapshots + 1 unknown directory + 1 dir with unlisted file.
        garbage = [self._make_dummy_snapshot(f"g{i}") for i in range(6)]
        unknown = self.data / "snapshots" / ("a" * 64)
        unknown.mkdir(mode=0o700)
        (unknown / "foreign.txt").write_text("keep\n")
        extra_snap = self._make_dummy_snapshot("extra", extra_file="stray.txt")

        # 1) Inherited lock_fd pointing to wrong inode, unlocked real lock, or
        #    LOCK_SH-locked real lock are all refused with zero deletions.
        wrong_lock = self.ram / "wrong-lock"
        wrong_lock.write_bytes(b"")
        wrong_lock.chmod(0o600)
        with wrong_lock.open("r+b") as wf:
            self.assertNotEqual(self._run_gc(lock_fd=wf.fileno()).returncode, 0)
        with lock_path.open("r+b") as ulf:
            self.assertNotEqual(self._run_gc(lock_fd=ulf.fileno()).returncode, 0)
            fcntl.flock(ulf.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            self.assertNotEqual(self._run_gc(lock_fd=ulf.fileno()).returncode, 0)
        self.assertTrue(all(p.is_dir() for p in garbage))

        # 1b) Unowned / damaged .prune-* entries (5 > OC_GC_MAX) and disallowed-leaf
        #     or symlink-containing candidates never wedge GC and remain untouched.
        stuck_tombs = []
        for idx, kind in enumerate(("nonempty", "bad_mf", "foreign_leaf", "symlink", "file")):
            tpath = self.data / "snapshots" / f".prune-{idx:064x}"
            stuck_tombs.append(tpath)
            if kind == "symlink":
                tpath.symlink_to(unknown)
            elif kind == "file":
                tpath.write_text("not-a-dir\n")
                tpath.chmod(0o600)
            else:
                tpath.mkdir(mode=0o700)
                if kind == "nonempty":
                    (tpath / "autostart").write_text("orphaned\n")
                    (tpath / "autostart").chmod(0o600)
                elif kind == "bad_mf":
                    (tpath / "files.sha256").write_text("tampered\n")
                    (tpath / "files.sha256").chmod(0o600)
                else:
                    (tpath / "evil.sh").write_text("bad\n")
                    (tpath / "evil.sh").chmod(0o600)
                    mf = sha(b"bad\n") + "  evil.sh\n"
                    (tpath / "files.sha256").write_text(mf)
                    (tpath / "files.sha256").chmod(0o600)
        disallowed_work = self.data / "snapshots" / ".new-disallowed"
        disallowed_work.mkdir(mode=0o700)
        (disallowed_work / "evil.sh").write_text("keep-me\n")
        (disallowed_work / "evil.sh").chmod(0o600)
        disallowed_snap = self.publish(disallowed_work)
        sym_snap = self._make_dummy_snapshot("sym-member")
        (sym_snap / "autostart").unlink()
        (sym_snap / "autostart").symlink_to("/etc/passwd")

        # 2) Standalone GC fails when lock is held by another open descriptor; succeeds with inherited fd.
        with lock_path.open("r+b") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self._run_gc().returncode, 0)

            # 3) Non-settled OC1 or legacy_undo != - skips GC cleanly.
            orig_rec = (self.data / "record").read_bytes()
            rec_set = list(self.record)
            rec_set[1] = "set"
            rec_set[6] = self.snapshot.name
            rec_set[7] = garbage[0].name
            (self.data / "record").write_text("|".join(rec_set) + "\n")
            self.assertNotEqual(self._run_gc(lock_fd=lf.fileno()).returncode, 0)
            rec_undo = list(self.record)
            rec_undo[8] = garbage[0].name
            (self.data / "record").write_text("|".join(rec_undo) + "\n")
            self.assertNotEqual(self._run_gc(lock_fd=lf.fileno()).returncode, 0)
            (self.data / "record").write_bytes(orig_rec)

            # 4) Malformed, symlinked, or dangling selected/access-selected markers skip GC.
            for bad_kind in ("malformed", "symlink", "dangling"):
                orig_sel = (self.ram / "selected").read_text()
                (self.ram / "selected").unlink()
                if bad_kind == "malformed":
                    (self.ram / "selected").write_text("not-a-hex-id\n")
                elif bad_kind == "symlink":
                    (self.ram / "selected").symlink_to(self.ram / "access-selected")
                else:
                    (self.ram / "selected").write_text("f" * 64 + "\n")
                self.assertNotEqual(self._run_gc(lock_fd=lf.fileno()).returncode, 0, bad_kind)
                (self.ram / "selected").unlink()
                (self.ram / "selected").write_text(orig_sel)
                (self.ram / "selected").chmod(0o600)
            self.assertTrue(all(p.is_dir() for p in garbage))

            # 5) Bounded sweep: first call removes at most 4 of the 6 garbage snapshots.
            first = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(first.returncode, 0, first.stderr)
            remaining = [p for p in garbage if p.exists()]
            self.assertEqual(len(remaining), 2)
            for pinned in (
                self.baseline,
                self.snapshot,
                pin_sel,
                pin_acc,
                unknown,
                extra_snap,
                disallowed_snap,
                sym_snap,
            ):
                self.assertTrue(pinned.is_dir(), f"must preserve {pinned.name}")
            for st in stuck_tombs:
                self.assertTrue(os.path.lexists(st), f"must leave unowned tombstone {st.name}")

            # Second call finishes the remaining 2 garbage snapshots.
            second = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual([p for p in garbage if p.exists()], [])

            # 6) Tombstone-first crash resume across all 3 cut points.
            for cut_point in (
                "gc_tombstone_renamed",
                "gc_before_manifest_unlink",
                "gc_after_manifest_unlink",
            ):
                victim = self._make_dummy_snapshot(f"cut-{cut_point}")
                tomb = self.data / "snapshots" / f".prune-{victim.name}"
                cut_res = self._run_gc(lock_fd=lf.fileno(), cut=cut_point)
                self.assertEqual(cut_res.returncode, 97, cut_point)
                self.assertFalse(victim.exists(), cut_point)
                self.assertTrue(tomb.is_dir(), cut_point)
                if cut_point == "gc_tombstone_renamed":
                    self.assertTrue((tomb / "autostart").is_file())
                    self.assertTrue((tomb / "files.sha256").is_file())
                elif cut_point == "gc_before_manifest_unlink":
                    self.assertFalse((tomb / "autostart").exists())
                    self.assertTrue((tomb / "files.sha256").is_file())
                else:
                    self.assertEqual(list(tomb.iterdir()), [])
                resumed = self._run_gc(lock_fd=lf.fileno())
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertFalse(tomb.exists(), cut_point)

        # 7) Standalone lock succeeds when unlocked and pins stay intact.
        extra_victim = self._make_dummy_snapshot("standalone")
        solo = self._run_gc()
        self.assertEqual(solo.returncode, 0, solo.stderr)
        self.assertFalse(extra_victim.exists())
        for pinned in (self.baseline, self.snapshot, pin_sel, pin_acc, unknown, extra_snap):
            self.assertTrue(pinned.is_dir())

    def _make_dummy_pkg_and_comp(self, tag: str) -> tuple[str, Path, Path]:
        pwork = self.data / "packages" / f".new-pkg-{tag}"
        pwork.mkdir(mode=0o700)
        (pwork / "VERSION").write_text(f"0.3.0-{tag}\n")
        (pwork / "VERSION").chmod(0o600)
        (pwork / "INSTANCE").write_text(f"{tag}\n")
        (pwork / "INSTANCE").chmod(0o600)
        pdir = self.publish(pwork)
        pid = pdir.name
        cdir = self.data / "composed" / pid
        cdir.mkdir(mode=0o700)
        comp_names = (
            "autostart",
            "uia.so",
            "mmui.so",
            "mmui.xml",
            "index-on.html",
            "index-off.html",
            "sm-normal-on.conf",
            "sm-normal-off.conf",
            "sm-wcp-on.conf",
            "sm-wcp-off.conf",
            "vui.so",
            "vui.xml",
        )
        rows = []
        for nm in comp_names:
            body = f"composed-{tag}-{nm}\n".encode()
            (cdir / nm).write_bytes(body)
            (cdir / nm).chmod(0o600)
            rows.append(f"{sha(body)}  {nm}\n")
        (cdir / "files.sha256").write_text("".join(rows))
        (cdir / "files.sha256").chmod(0o600)
        return pid, pdir, cdir

    def _make_snap_with_pkg(self, tag: str, cfg_pkg: str, sel_pkg: str | None = None) -> Path:
        work = self.data / "snapshots" / f".new-spkg-{tag}"
        work.mkdir(mode=0o700)
        cfg = (
            f"OC2\nbase=0\nmetadata={self.mode}\nnvram=absent\npackage={cfg_pkg}\n"
            "service-ids=pandora\nservice.pandora=1\ntouch=0\nwarning=0\nwireless=0\n"
        )
        (work / "config").write_text(cfg)
        (work / "config").chmod(0o600)
        (work / "autostart").write_text(f"auto-{tag}\n")
        (work / "autostart").chmod(0o600)
        if sel_pkg is not None:
            (work / "selector").write_text(f"{'b' * 64}|700:0:0|{sel_pkg}\n")
            (work / "selector").chmod(0o600)
        return self.publish(work)

    def test_gc_prunes_unreachable_packages_and_composed_protects_all_pins_and_resumes_cuts(self):
        import fcntl

        lock_path = self.ram / "lock"
        lock_path.write_bytes(b"")
        lock_path.chmod(0o600)

        # Create 6 pinned generations covering every live pin source:
        #   - self.package_id (R_BACKEND)
        #   - snap_cfg_pkg & snap_sel_pkg (referenced by a pinned surviving snapshot)
        #   - rt_pkg (live ram/runtime session)
        #   - usb_pkg (live ram/usb-runtime session)
        #   - uia_pkg (live ram/feature/uia.so symlink)
        #   - maint_pkg (live ram/feature/maintenance.js symlink)
        snap_cfg_id, snap_cfg_p, snap_cfg_c = self._make_dummy_pkg_and_comp("pin-snap-cfg")
        snap_sel_id, snap_sel_p, snap_sel_c = self._make_dummy_pkg_and_comp("pin-snap-sel")
        rt_id, rt_p, rt_c = self._make_dummy_pkg_and_comp("pin-runtime")
        usb_id, usb_p, usb_c = self._make_dummy_pkg_and_comp("pin-usb-runtime")
        uia_id, uia_p, uia_c = self._make_dummy_pkg_and_comp("pin-feature-uia")
        maint_id, maint_p, maint_c = self._make_dummy_pkg_and_comp("pin-feature-maint")

        pin_snap = self._make_snap_with_pkg("pin-sel", snap_cfg_id, snap_sel_id)
        (self.ram / "selected").write_text(pin_snap.name + "\n")
        (self.ram / "selected").chmod(0o600)

        sessions = self.ram / "sessions"
        sessions.mkdir(mode=0o700)
        s_rt = sessions / "session-boot01"
        s_rt.mkdir(mode=0o700)
        shutil.copyfile(rt_p / "files.sha256", s_rt / "files.sha256")
        (self.ram / "runtime").symlink_to(str(s_rt))
        s_usb = sessions / "session-usb001"
        s_usb.mkdir(mode=0o700)
        shutil.copyfile(usb_p / "files.sha256", s_usb / "files.sha256")
        (self.ram / "usb-runtime").symlink_to("sessions/session-usb001")

        fdir = self.ram / "feature"
        fdir.mkdir(mode=0o700)
        (fdir / "uia.so").symlink_to(
            f"../../mnt/data_persist/open-connect/composed/{uia_id}/uia.so"
        )
        (fdir / "maintenance.js").symlink_to(
            f"../../mnt/data_persist/open-connect/packages/{maint_id}/maintenance.js"
        )

        # Create 5 unreachable old generations + foreign/unowned/tampered/staging dirs.
        old_gens = [self._make_dummy_pkg_and_comp(f"old-{i}") for i in range(5)]
        foreign_pkg = self.data / "packages" / ("c" * 64)
        foreign_pkg.mkdir(mode=0o700)
        (foreign_pkg / "keep.txt").write_text("keep\n")
        foreign_comp = self.data / "composed" / ("d" * 64)
        foreign_comp.mkdir(mode=0o700)
        (foreign_comp / "evil.sh").write_text("bad\n")
        (foreign_comp / "files.sha256").write_text(sha(b"bad\n") + "  evil.sh\n")
        # Tampered member bytes in composed/<id> and wrong manifest mode 0644 must NOT be pruned.
        tampered_comp_id, tampered_pkg_p, tampered_comp_c = self._make_dummy_pkg_and_comp(
            "tampered-comp"
        )
        shutil.rmtree(tampered_pkg_p)
        (tampered_comp_c / "autostart").write_text("tampered bytes\n")
        (tampered_comp_c / "autostart").chmod(0o600)
        badmode_comp_id, badmode_pkg_p, badmode_comp_c = self._make_dummy_pkg_and_comp(
            "badmode-comp"
        )
        shutil.rmtree(badmode_pkg_p)
        (badmode_comp_c / "files.sha256").chmod(0o644)
        # Active .new-* staging dirs in packages/ & composed/ must be left untouched.
        staging_pkg = self.data / "packages" / ".new-staging"
        staging_pkg.mkdir(mode=0o700)
        (staging_pkg / "VERSION").write_text("in-flight\n")
        staging_comp = self.data / "composed" / ".new-staging"
        staging_comp.mkdir(mode=0o700)
        (staging_comp / "autostart").write_text("in-flight\n")
        # Legacy 5-field OC1 active snapshot (non-"-" pkg) pins its package.
        oc1_id, oc1_p, oc1_c = self._make_dummy_pkg_and_comp("pin-oc1-snap")
        oc1_work = self.data / "snapshots" / ".new-oc1-active"
        oc1_work.mkdir(mode=0o700)
        (oc1_work / "config").write_text(f"{oc1_id}|0|0|absent|{self.mode}\n")
        (oc1_work / "config").chmod(0o600)
        (oc1_work / "autostart").write_text("oc1-auto\n")
        (oc1_work / "autostart").chmod(0o600)
        oc1_snap = self.publish(oc1_work)
        (self.ram / "access-selected").write_text(oc1_snap.name + "\n")
        (self.ram / "access-selected").chmod(0o600)

        with lock_path.open("r+b") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # 1) Fail-closed on malformed/prefix-spoofed RAM runtime or feature symlinks: 0 deletions.
            orig_rt = os.readlink(self.ram / "runtime")
            for bad_rt in (
                "sessions/session-missing",
                "/elsewhere/sessions/session-boot01",
                f"{self.ram}/sessions/session-a/sessions/session-boot01",
            ):
                (self.ram / "runtime").unlink()
                (self.ram / "runtime").symlink_to(bad_rt)
                self.assertEqual(self._run_gc(lock_fd=lf.fileno()).returncode, 0, bad_rt)
                self.assertTrue(all(p.is_dir() and c.is_dir() for _, p, c in old_gens), bad_rt)
            (self.ram / "runtime").unlink()
            (self.ram / "runtime").symlink_to(orig_rt)

            orig_uia = os.readlink(fdir / "uia.so")
            (fdir / "uia.so").unlink()
            (fdir / "uia.so").symlink_to("../../etc/passwd")
            self.assertEqual(self._run_gc(lock_fd=lf.fileno()).returncode, 0)
            self.assertTrue(all(p.is_dir() and c.is_dir() for _, p, c in old_gens))
            (fdir / "uia.so").unlink()
            (fdir / "uia.so").symlink_to(orig_uia)

            # 2) Fail-closed skip if an unverified/unowned 64-hex dir sits in snapshots/
            #    or if surviving snapshots overflow OC_GC_PINS_MAX (32).
            corrupt_snap = self.data / "snapshots" / ("e" * 64)
            corrupt_snap.mkdir(mode=0o700)
            (corrupt_snap / "foreign.txt").write_text("unknown\n")
            skip_res = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(skip_res.returncode, 0, skip_res.stderr)
            self.assertTrue(all(p.is_dir() and c.is_dir() for _, p, c in old_gens))
            shutil.rmtree(corrupt_snap)

            overflow_snaps = []
            for idx in range(33):
                # Keep snapshots pinned via unknown extra file so snapshot GC leaves them,
                # forcing pin table overflow (>32 distinct packages) in phase 2.
                pid_hex = f"{idx + 1:064x}"
                s = self._make_snap_with_pkg(f"ov-{idx}", pid_hex)
                overflow_snaps.append(s)
            # Only run with pin-overflow snaps temporarily; note snapshot GC will prune 4
            # of them per run, leaving 29 + 7 other pins = 36 > 32 -> must skip phase 2.
            ov_res = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(ov_res.returncode, 0, ov_res.stderr)
            self.assertTrue(all(p.is_dir() and c.is_dir() for _, p, c in old_gens))
            for s in overflow_snaps:
                shutil.rmtree(s, ignore_errors=True)

            # 3) Bounded sweep: first call removes 4 of 5 old packages and 4 of 5 old composed dirs.
            first = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(sum(1 for _, p, _ in old_gens if p.exists()), 1)
            self.assertEqual(sum(1 for _, _, c in old_gens if c.exists()), 1)

            # Second call finishes the 5th generation while keeping every pin, tampered,
            # staging, and foreign dir.
            second = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual([p for _, p, _ in old_gens if p.exists()], [])
            self.assertEqual([c for _, _, c in old_gens if c.exists()], [])
            for keep in (
                self.package,
                self.composed,
                snap_cfg_p,
                snap_cfg_c,
                snap_sel_p,
                snap_sel_c,
                oc1_p,
                oc1_c,
                rt_p,
                rt_c,
                usb_p,
                usb_c,
                uia_p,
                uia_c,
                maint_p,
                maint_c,
                foreign_pkg,
                foreign_comp,
                tampered_comp_c,
                badmode_comp_c,
                staging_pkg,
                staging_comp,
            ):
                self.assertTrue(keep.is_dir(), f"must preserve {keep}")

            # 3b) Regular-file feature/uia.so & feature/maintenance.js allow GC cleanly.
            (fdir / "uia.so").unlink()
            (fdir / "uia.so").write_bytes(b"regular-uia\n")
            (fdir / "uia.so").chmod(0o600)
            (fdir / "maintenance.js").unlink()
            (fdir / "maintenance.js").write_bytes(b"regular-maint\n")
            (fdir / "maintenance.js").chmod(0o600)
            reg_res = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(reg_res.returncode, 0, reg_res.stderr)
            self.assertFalse(uia_p.exists())
            self.assertFalse(uia_c.exists())
            self.assertFalse(maint_p.exists())
            self.assertFalse(maint_c.exists())

            # 4) Tombstone-first crash resume across all 3 cut points for packages/ and composed/.
            for store_kind in ("packages", "composed"):
                for cut_point in (
                    "gc_tombstone_renamed",
                    "gc_before_manifest_unlink",
                    "gc_after_manifest_unlink",
                ):
                    pid, pdir, cdir = self._make_dummy_pkg_and_comp(f"cut-{store_kind}-{cut_point}")
                    if store_kind == "composed":
                        # Remove package dir first so the cut triggers specifically on composed/.
                        shutil.rmtree(pdir)
                        victim, tomb = cdir, self.data / "composed" / f".prune-{pid}"
                    else:
                        shutil.rmtree(cdir)
                        victim, tomb = pdir, self.data / "packages" / f".prune-{pid}"
                    cut_res = self._run_gc(lock_fd=lf.fileno(), cut=cut_point)
                    self.assertEqual(cut_res.returncode, 97, (store_kind, cut_point))
                    self.assertFalse(victim.exists(), (store_kind, cut_point))
                    self.assertTrue(tomb.is_dir(), (store_kind, cut_point))
                    resumed = self._run_gc(lock_fd=lf.fileno())
                    self.assertEqual(resumed.returncode, 0, resumed.stderr)
                    self.assertFalse(tomb.exists(), (store_kind, cut_point))

    def test_gc_failure_isolated_from_save_and_unlocked_status_returns_busy(self):
        # Verify: (a) gc_snap failure never breaks a settled save; (b) unlocked
        # full-status audit detects a concurrent commit+GC of S1 -> S2 and returns busy.
        import fcntl

        lock_path = self.ram / "lock"
        lock_path.write_bytes(b"")
        lock_path.chmod(0o600)
        s1 = self.snapshot
        # Create a valid OC2 boot-selected snapshot distinct from R_CURRENT (s1),
        # so backend.sh accepts settings_package and GC can prune s1 once s2 commits.
        s0_work = self.data / "snapshots" / ".new-gc-selected"
        s0_work.mkdir(mode=0o700)
        for p in s1.iterdir():
            if p.name != "files.sha256":
                (s0_work / p.name).write_bytes(p.read_bytes())
                (s0_work / p.name).chmod(0o600)
        (s0_work / "autostart").write_text("boot-selected autostart\n")
        (s0_work / "config").write_text(
            f"OC2\nbase=0\ncarplay-autoshow=0\nmetadata={self.mode}\nnvram=disable\n"
            f"package={self.package_id}\nservice-ids=android-auto,pandora,siriusxm\n"
            "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n"
            "touch=1\nwarning=1\nwireless=1\n"
        )
        s0 = self.publish(s0_work)
        (self.ram / "selected").write_text(s0.name + "\n")
        (self.ram / "selected").chmod(0o600)

        # (a) gc_snap with a failing boot-select still returns 0 (isolated from save),
        #     and when BOOT_SELECT is unset it refuses symlinked or tampered package
        #     boot-select without executing it.
        bad_bs = Path(self.build.name) / "fail-bs"
        bad_bs.write_text("#!/bin/sh\nexit 17\n")
        bad_bs.chmod(0o700)
        iso = subprocess.run(
            [
                "sh",
                "-c",
                f"set -eu; D={shlex.quote(str(self.data))}; R_BACKEND={self.package_id}; "
                f"BOOT_SELECT={shlex.quote(str(bad_bs))}; . {shlex.quote(str(ASSETS / 'state.sh'))}; "
                "gc_snap; printf ok",
            ],
            env=self._host_env({"PATH": self.build.name + os.pathsep + os.environ["PATH"]}),
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual((iso.returncode, iso.stdout), (0, "ok"), iso.stderr)
        pwn = self.ram / "pwned-by-gc"
        evil = Path(self.build.name) / "evil-bs"
        evil.write_text(f"#!/bin/sh\nprintf pwn > {shlex.quote(str(pwn))}\n")
        evil.chmod(0o700)
        orig_bs = (self.package / "boot-select").read_bytes()
        for mode in ("symlink", "tampered"):
            (self.package / "boot-select").unlink()
            if mode == "symlink":
                (self.package / "boot-select").symlink_to(evil)
            else:
                (self.package / "boot-select").write_bytes(evil.read_bytes())
                (self.package / "boot-select").chmod(0o700)
            ref = subprocess.run(
                [
                    "sh",
                    "-c",
                    f"set -eu; P={shlex.quote(str(self.package))}; D={shlex.quote(str(self.data))}; "
                    f"R_BACKEND={self.package_id}; BOOT_SELECT=; . {shlex.quote(str(ASSETS / 'state.sh'))}; "
                    "gc_snap; printf ok",
                ],
                env=self._host_env({"PATH": self.build.name + os.pathsep + os.environ["PATH"]}),
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual((ref.returncode, ref.stdout), (0, "ok"), mode + ": " + ref.stderr)
            self.assertFalse(pwn.exists(), f"gc_snap executed {mode} boot-select!")
        (self.package / "boot-select").unlink()
        (self.package / "boot-select").write_bytes(orig_bs)
        (self.package / "boot-select").chmod(0o700)

        # (b) Simulate unlocked full-status audit observing S1, then concurrent set
        # commits S2 + GCs S1 while full-status dropped lock fd 9: backend.sh status
        # must return busy rather than conflict:true.
        if not shutil.which("flock"):
            import sys

            flock_shim = Path(self.build.name) / "flock"
            flock_shim.write_text(
                f"#!{sys.executable}\n"
                "import fcntl, sys\n"
                "args = sys.argv[1:]\n"
                "fd = int(args[-1])\n"
                "if '-u' in args:\n"
                "    fcntl.flock(fd, fcntl.LOCK_UN)\n"
                "else:\n"
                "    op = fcntl.LOCK_SH if '-s' in args else fcntl.LOCK_EX\n"
                "    if '-n' in args: op |= fcntl.LOCK_NB\n"
                "    fcntl.flock(fd, op)\n"
            )
            flock_shim.chmod(0o700)
        be = Path(self.build.name) / "gc-status-session"
        shutil.rmtree(be, ignore_errors=True)
        shutil.copytree(ASSETS, be)
        shutil.copyfile(Path(self.build.name) / "flush", be / "flush")
        (be / "flush").chmod(0o700)
        shutil.copyfile(compile_host_api(), be / "api")
        (be / "api").chmod(0o700)
        for sh_name in ("state.sh", "firmware.sh", "access.sh", "transaction.sh", "backend.sh"):
            txt = (be / sh_name).read_text()
            txt = txt.replace("/tmp/mnt/data_persist/open-connect", str(self.data))
            txt = txt.replace("/tmp/open-connect", str(self.ram))
            txt = txt.replace("/usr/bin/autostart", str(self.root / "usr/bin/autostart"))
            txt = txt.replace("/usr/bin/runlogin", str(self.root / "usr/bin/runlogin"))
            txt = txt.replace("/etc/ssh/sshd_config", str(self.root / "etc/ssh/sshd_config"))
            txt = txt.replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
            (be / sh_name).write_text(txt)
        (be / "firmware.sh").write_text(
            (be / "firmware.sh").read_text() + "\nfirmware_guard() { :; }\n"
        )
        (be / "transaction.sh").write_text(
            (be / "transaction.sh").read_text()
            + "\ntargets_match() {\n"
            + f'  if test "$1" = {shlex.quote(s1.name)}; then\n'
            + '    printf "waiting\\n" > '
            + shlex.quote(str(self.ram / "audit-entered"))
            + "\n"
            + "    i=0; while test ! -f "
            + shlex.quote(str(self.ram / "audit-release"))
            + ' && test "$i" -lt 100; do sleep 0.05; i=$((i+1)); done\n'
            + "    return 1\n"
            + "  fi\n"
            + "  return 0\n"
            + "}\n"
            + "dependencies_match() { return 0; }\n"
        )
        (self.ram / "runtime").symlink_to(be)
        env = self._host_env({"PATH": self.build.name + os.pathsep + os.environ["PATH"]})
        proc = subprocess.Popen(
            ["sh", str(be / "backend.sh"), "api", "-", "status", "-", "-", "-"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        import time

        deadline = time.monotonic() + 5.0
        while not (self.ram / "audit-entered").exists() and time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.02)
        if not (self.ram / "audit-entered").exists():
            out, err = proc.communicate(timeout=5)
            self.fail(
                f"backend.sh exited before audit: rc={proc.returncode} out={out!r} err={err!r}"
            )
        # Concurrent writer takes lock, advances R_CURRENT to S2, and GCs S1.
        s2 = self._make_dummy_snapshot("concurrent-s2")
        with lock_path.open("r+b") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.record[5] = s2.name
            self.save_record()
            gc_res = self._run_gc(lock_fd=lf.fileno())
            self.assertEqual(gc_res.returncode, 0, gc_res.stderr)
            self.assertFalse(s1.exists())
        (self.ram / "audit-release").write_text("go\n")
        out, err = proc.communicate(timeout=5)
        self.assertNotEqual(proc.returncode, 0, out + err)
        self.assertEqual(json.loads(out)["error"], "busy")
