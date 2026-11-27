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
        # Only physical Base/touch input digests are adapted to authored
        # fixtures. The selector, metadata, commit and publication logic is real.
        for source in (*ASSETS.glob("boot-*.h"), ASSETS / "boot-select.c"):
            text = source.read_text()
            for _, _, data, original in (
                *cls.BASE_INPUTS,
                *cls.TOUCH_INPUTS,
                (
                    "manager.so",
                    "/jci/lib/libjciuiamgr.so",
                    "stock manager.so\n",
                    "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29",
                ),
                (
                    "originals/mmui.xml",
                    "/tmp/mnt/data_persist/open-connect/originals/mmui.xml",
                    "stock original mmui.xml\n",
                    "ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0",
                ),
            ):
                text = text.replace(original, sha(data.encode()))
            text = text.replace(
                "static int oc_stock_meta(int root,OcMeta *stock) { return oc_stat(root,stock)>=0; }",
                'static int oc_stock_meta(int root,OcMeta *stock) { int ok=oc_stat(root,stock)>=0; if(getenv("OC_TOUCH_WRONG_FS")) ++stock->device; return ok; }',
            )
            # Inject syscall failures in the private host adapter, not in the
            # shipped selector. All policy/publication/unwind code stays real.
            if source.name == "boot-io.h":
                text = text.replace(
                    "#include <errno.h>",
                    "#include <errno.h>\n#include <stdlib.h>\n#include <string.h>",
                )
                text = text.replace(
                    "static long oc_metadata(int fd, const char *path, OcMeta *m)",
                    "static long oc_metadata_raw(int fd, const char *path, OcMeta *m)",
                    1,
                )
                text = text.replace(
                    "#else\n#define OC_CWD",
                    """static long oc_metadata(int fd,const char *path,OcMeta *m) {
    static int failed;
    const char *fault=getenv("OC_ALIAS_META_FAIL");
    if(path&&fault&&failed<2&&!strcmp(path,fault)) { ++failed; return -5; }
    long result=oc_metadata_raw(fd,path,m);
    if(result>=0&&path&&!strcmp(path,"boot-id")&&getenv("OC_BOOT_OWNER_FAIL")) ++m->uid;
    return result;
}
#else
#define OC_CWD""",
                    1,
                )
            if source.name == "boot-system.h":
                text = text.replace(
                    "static long oc_link(int from,const char *name,int to,const char *target) { return linkat(from,name,to,target,0)<0?-errno:0; }",
                    """static long oc_link(int from,const char *name,int to,const char *target) {
    const char *foreign=getenv("OC_ALIAS_FOREIGN"),*fault=getenv("OC_ALIAS_LINK_FAIL"),*after=getenv("OC_ALIAS_LINK_AFTER");
    if(foreign&&!strcmp(target,foreign)) {
        long fd=oc_openat(to,target,OC_WRITE|OC_CREATE|OC_EXCLUSIVE,0600);
        if(fd>=0) { (void)oc_write_all((int)fd,"foreign\\n",8); (void)oc_close((int)fd); }
        return -17;
    }
    if(fault&&!strcmp(target,fault)) return -5;
    if(linkat(from,name,to,target,0)<0) return -errno;
    return after&&!strcmp(target,after)?-5:0;
}""",
                    1,
                )
            (folder / source.name).write_text(text)
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-D_GNU_SOURCE",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                folder / "boot-select.c",
                "-o",
                cls.program,
            ],
            check=True,
        )

        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                ROOT / "cmu/startup/flush.c",
                "-o",
                Path(cls.build.name) / "flush",
            ],
            check=True,
        )
        if shutil.which("gstat"):
            (Path(cls.build.name) / "stat").symlink_to(shutil.which("gstat"))

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
            "ignition.sh",
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
        env = {**os.environ}
        env.update(extra_env or {})
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
            (self.ram / "ignition/state.sh").read_bytes(), (ASSETS / "state.sh").read_bytes()
        )
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
        partial = list(self.ram.glob(".ignition-*/state.sh"))
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
        self.assertTrue((self.ram / "ignition/ignition.sh").is_file())
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
        if stdout_path is not None:
            with Path(stdout_path).open("wb") as out:
                return subprocess.run(
                    [self.program, *args],
                    input=stdin,
                    stdout=out,
                    stderr=subprocess.PIPE,
                    env={**os.environ, **(env or {})},
                    timeout=5,
                )
        return subprocess.run(
            [self.program, *args],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **(env or {})},
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

    def test_boot_select_verified_trust_anchor_and_tamper_detection(self):
        # Build a complete 13-file RAM session manifest matching packages/<id>,
        # plus a sealed OC2 snapshot referencing that package.
        pkg_dir = self.data / "packages/.new-fullpkg"
        pkg_dir.mkdir(mode=0o700)
        for name in (
            "state.sh",
            "firmware.sh",
            "access.sh",
            "service.sh",
            "VERSION",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "ui-profile.awk",
            "ui-modules.tsv",
            "system-hook.js",
            "base-logging.js",
        ):
            (pkg_dir / name).write_bytes((ASSETS / name).read_bytes())
            (pkg_dir / name).chmod(0o600)
        shutil.copyfile(Path(self.build.name) / "flush", pkg_dir / "flush")
        (pkg_dir / "flush").chmod(0o700)
        (pkg_dir / "boot-select").write_bytes(self.program.read_bytes())
        (pkg_dir / "boot-select").chmod(0o700)
        pkg = self.publish(pkg_dir)

        snap_dir = self.data / "snapshots/.new-verify-snap"
        snap_dir.mkdir(mode=0o700)
        for p in sorted(self.snapshot.iterdir()):
            if p.name != "files.sha256":
                (snap_dir / p.name).write_bytes(p.read_bytes())
                (snap_dir / p.name).chmod(0o600)
        (snap_dir / "config").write_text(
            (snap_dir / "config")
            .read_text()
            .replace(self.package_id, pkg.name)
            .replace(
                "service-ids=android-auto,pandora\nservice.android-auto=1\nservice.pandora=1\n",
                "service-ids=android-auto,pandora,siriusxm\n"
                "service.android-auto=1\nservice.pandora=1\nservice.siriusxm=1\n",
            )
        )
        (snap_dir / "selector").write_text(
            f"{sha((pkg / 'boot-select').read_bytes())}|700:{os.getuid()}:{os.getgid()}|{pkg.name}\n"
        )
        snap = self.publish(snap_dir)

        ram_session = self.ram / "session-test"
        ram_session.mkdir(mode=0o700)
        for name in ("state.sh", "service.sh", "files.sha256"):
            (ram_session / name).write_bytes((pkg / name).read_bytes())
            (ram_session / name).chmod(0o600)
        shutil.copyfile(Path(self.build.name) / "flush", ram_session / "flush")
        (ram_session / "flush").chmod(0o700)

        env = {**os.environ, "PATH": self.build.name + os.pathsep + os.environ["PATH"]}

        def check(role="settings", cur=snap.name, backend=pkg.name, ram=ram_session):
            return subprocess.run(
                [
                    "sh",
                    "-c",
                    "set -eu; D=$1; P=$2; R_BACKEND=$3; R_CURRENT=$4; role=$5; "
                    'request_owner="$(id -u):$(id -g)"; '
                    '. "$P/state.sh"; . "$P/service.sh"; boot_select_verified',
                    "verify-helper",
                    str(self.data),
                    str(ram),
                    backend,
                    cur,
                    role,
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).returncode

        self.assertEqual(check(), 0)
        # Non-settings role returns compatibility code 2.
        self.assertEqual(check(role="usb"), 2)
        # Tampered or missing RAM session manifest with role=settings hard-fails (rc=1, NEVER rc=2).
        ram_mf = ram_session / "files.sha256"
        orig_ram_mf = ram_mf.read_bytes()
        ram_mf.write_bytes(orig_ram_mf + b"\n")
        self.assertEqual(check(), 1)
        ram_mf.unlink()
        self.assertEqual(check(), 1)
        ram_mf.write_bytes(orig_ram_mf)
        ram_mf.chmod(0o600)
        # Genuinely old package without boot-select in valid RAM manifest returns rc=2.
        old_pkg_dir = self.data / "packages/.new-oldpkg"
        old_pkg_dir.mkdir(mode=0o700)
        for name in ("state.sh", "service.sh"):
            (old_pkg_dir / name).write_bytes((ASSETS / name).read_bytes())
            (old_pkg_dir / name).chmod(0o600)
        shutil.copyfile(Path(self.build.name) / "flush", old_pkg_dir / "flush")
        (old_pkg_dir / "flush").chmod(0o700)
        old_pkg = self.publish(old_pkg_dir)
        old_ram = self.ram / "session-old"
        shutil.copytree(old_pkg, old_ram)
        self.assertEqual(check(backend=old_pkg.name, ram=old_ram), 2)
        # Missing declared boot.plan in authenticated manifest hard-fails (rc=1, NEVER rc=2).
        bp = snap / "boot.plan"
        orig_bp = bp.read_bytes()
        bp.unlink()
        self.assertEqual(check(), 1)
        bp.write_bytes(orig_bp)
        bp.chmod(0o600)
        # Genuinely unsealed snapshot (boot.plan absent from authenticated manifest) returns rc=2.
        unsealed_dir = self.data / "snapshots/.new-unsealed"
        unsealed_dir.mkdir(mode=0o700)
        for p in sorted(snap.iterdir()):
            if p.name not in ("files.sha256", "boot.plan"):
                (unsealed_dir / p.name).write_bytes(p.read_bytes())
                (unsealed_dir / p.name).chmod(0o600)
        unsealed_snap = self.publish(unsealed_dir)
        self.assertEqual(check(cur=unsealed_snap.name), 2)
        # Wrong mode on persistent boot-select hard-fails (rc=1).
        (pkg / "boot-select").chmod(0o600)
        self.assertEqual(check(), 1)
        (pkg / "boot-select").chmod(0o700)
        # Tampered persistent boot-select or script hard-fails (rc=1).
        orig_bs = (pkg / "boot-select").read_bytes()
        (pkg / "boot-select").write_bytes(orig_bs[:-1] + bytes([orig_bs[-1] ^ 1]))
        (pkg / "boot-select").chmod(0o700)
        self.assertEqual(check(), 1)
        (pkg / "boot-select").write_bytes(orig_bs)
        (pkg / "boot-select").chmod(0o700)
        orig_awk = (pkg / "sm-profile.awk").read_bytes()
        (pkg / "sm-profile.awk").write_bytes(orig_awk + b"\n")
        self.assertEqual(check(), 1)
        (pkg / "sm-profile.awk").write_bytes(orig_awk)
        self.assertEqual(check(), 0)

    def test_fast_set_publish_e2e_nvram_cuts_and_integrity_hard_refusal(self):
        # Run actual fast_set_publish shell function against the real host-compiled
        # boot-select (wrapped to pass self.root instead of '/') for:
        # 1) data-only save (carplay-autoshow 0->1), verifying S_VER="|$after|" cache format
        #    and exact byte equivalence of selectively rendered profiles vs full render
        # 2) NVRAM-changing touch 1->0->1, witnessing pending OC1 before nvram_change and
        #    verifying pre-NVRAM cut + pending-only audit behavior
        # 3) hard integrity refusals (extra package file, tampered originals/mmui.xml,
        #    predecessor symlink) returning state_changed without falling back.
        root_prefix = str(self.root).lstrip("/") + "/"
        wrapper = Path(self.build.name) / "boot-select-root"
        wrapper.write_text(
            "#!/bin/sh\nop=$1; shift; shift\n"
            f'if test "$op" = seal-publish; then c=$1; w=${{2#{shlex.quote(root_prefix)}}}; shift 2; '
            f'exec {shlex.quote(str(self.program))} "$op" {shlex.quote(str(self.root))} "$c" "$w" "$@"; fi\n'
            f'exec {shlex.quote(str(self.program))} "$op" {shlex.quote(str(self.root))} "$@"\n'
        )
        wrapper.chmod(0o700)
        env = {**os.environ, "PATH": self.build.name + os.pathsep + os.environ["PATH"]}
        nvram_file = self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction"
        witness_file = self.ram / "nvram-witness.txt"

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
        idx_tpl = (
            '<html><head><script src="common/js/logDefaults.js"></script></head>'
            "<body><script>/*@TOKEN@*/framework.init();</script></body></html>\n"
        )
        for nm in ("index-on.html", "index-off.html"):
            (new_comp / nm).write_text(idx_tpl)
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

        def run_fast(key, desired, cut_mode=""):
            script = r"""set -eu
D=$1; P=$2; BOOT_SELECT=$3; NV=$4; WIT=$5; KEY=$6; VAL=$7; CUT=$8
request_owner="$(id -u):$(id -g)"; S_CACHE=1; S_VER=; S_CUR=
. "$P/state.sh"; . "$P/firmware.sh"; . "$P/access.sh"; . "$P/transaction.sh"
uuid() { printf '%s\n' "0123456789abcdef0123456789abcdef"; }
fail() { printf '{"ok":false,"error":"%s"}\n' "$1"; exit 1; }
nvram_change() {
  cat "$D/record" > "$WIT"
  if test "$CUT" = before_nvram; then exit 99; fi
  if test "$2" = absent; then rm -f "$NV"; else printf '%s\n' "$2" > "$NV"; fi
  if test "$CUT" = after_nvram; then exit 98; fi
}
record_read
VERIFIED_PACKAGE=$R_BACKEND
snapshot_decode "$R_CURRENT"
package=$S_PACKAGE; prefs=$S_PREFS; schema=$S_SCHEMA; mode=$S_META
cur_nvram=$S_NVRAM; O_T2=0; test "$S_TOUCH" != 2 || O_T2=1
O_W=$S_WARNING; O_B=$S_BASE; O_WL=$S_WIRELESS; O_S=$S_SERVICES; O_AS=$S_AUTOSHOW
prefs=$(preferences_change "$prefs" "$package" "$KEY" "$VAL" "$schema")
touch=$(preference_value "$prefs" touch)
snapshot_decode "$R_BASE"
nvram=$S_NVRAM; test "$touch" != 1 || nvram=disable
fast_set_publish
printf '{"ok":true,"current":"%s","s_ver":"%s"}\n' "$R_CURRENT" "$S_VER"
"""
            return subprocess.run(
                [
                    "sh",
                    "-c",
                    script,
                    "fast-e2e",
                    str(self.data),
                    str(self.package),
                    str(wrapper),
                    str(nvram_file),
                    str(witness_file),
                    key,
                    desired,
                    cut_mode,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

        # 1) Data-only save: carplay-autoshow 0 -> 1.
        res = run_fast("carplay-autoshow", "1")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        data = json.loads(res.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["s_ver"], f"|{data['current']}|")
        self.assertEqual(self._run_helper("audit", str(self.root), data["current"]).returncode, 0)
        # Reused profiles (mmui.xml, sm-normal.conf, sm-wcp.conf, vui-plugins.list) were
        # copied in C identically to the predecessor while index.html includes carplay.js.
        new_snap = self.data / "snapshots" / data["current"]
        for unchanged in ("mmui.xml", "vui-plugins.list", "sm-normal.conf", "sm-wcp.conf"):
            self.assertEqual(
                (new_snap / unchanged).read_bytes(), (self.snapshot / unchanged).read_bytes()
            )
        self.assertIn("carplay.js", (new_snap / "index.html").read_text())

        # 2) NVRAM-changing save: touch 1 -> 0 -> 1, witnessing pending OC1 before nvram_change.
        res_off = run_fast("touch", "0")
        self.assertEqual(res_off.returncode, 0, res_off.stdout + res_off.stderr)
        off_cur = json.loads(res_off.stdout)["current"]
        witnessed = witness_file.read_text().strip().split("|")
        self.assertEqual(witnessed[1], "set")
        self.assertEqual(witnessed[5], data["current"])
        self.assertEqual(witnessed[6], data["current"])
        self.assertEqual(witnessed[7], off_cur)
        self.assertFalse(nvram_file.exists())
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur).returncode, 0)

        # Pre-NVRAM cut: touch 0 -> 1 stops right before NVRAM write; pending OC1 intact,
        # current-only audit refuses pending record, candidate audit refuses until NVRAM matches.
        cut_pre = run_fast("touch", "1", cut_mode="before_nvram")
        self.assertEqual(cut_pre.returncode, 99, cut_pre.stdout + cut_pre.stderr)
        rec = (self.data / "record").read_text().strip().split("|")
        self.assertEqual((rec[1], rec[5], rec[6]), ("set", off_cur, off_cur))
        self.assertNotEqual(self._run_helper("audit", str(self.root), off_cur).returncode, 0)
        self.assertNotEqual(
            self._run_helper("audit", str(self.root), off_cur, rec[7]).returncode, 0
        )
        nvram_file.write_text("disable\n")
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur, rec[7]).returncode, 0)
        # Restore active off_cur + absent NVRAM, then exercise post-NVRAM cut (after_nvram):
        # NVRAM already matches candidate, pending OC1 intact, current-only audit refuses,
        # and pending-set candidate audit succeeds immediately.
        nvram_file.unlink()
        rec[1] = "active"
        rec[6:8] = ["-", "-"]
        (self.data / "record").write_text("|".join(rec) + "\n")
        cut_post = run_fast("touch", "1", cut_mode="after_nvram")
        self.assertEqual(cut_post.returncode, 98, cut_post.stdout + cut_post.stderr)
        rec2 = (self.data / "record").read_text().strip().split("|")
        self.assertEqual((rec2[1], rec2[5], rec2[6]), ("set", off_cur, off_cur))
        self.assertEqual(nvram_file.read_text(), "disable\n")
        self.assertNotEqual(self._run_helper("audit", str(self.root), off_cur).returncode, 0)
        self.assertEqual(self._run_helper("audit", str(self.root), off_cur, rec2[7]).returncode, 0)
        # Restore active off_cur + absent NVRAM and complete touch 0 -> 1 cleanly.
        nvram_file.unlink()
        rec2[1] = "active"
        rec2[6:8] = ["-", "-"]
        (self.data / "record").write_text("|".join(rec2) + "\n")
        res_on = run_fast("touch", "1")
        self.assertEqual(res_on.returncode, 0, res_on.stdout + res_on.stderr)
        on_cur = json.loads(res_on.stdout)["current"]
        self.assertEqual(nvram_file.read_text(), "disable\n")
        self.assertEqual(self._run_helper("audit", str(self.root), on_cur).returncode, 0)

        # Real backend.sh entry-point check on this rooted native fixture:
        # exercises real backend.sh dispatch (boot_select_verified -> fast_set_publish ->
        # status_view, no-op audit, and hard state_changed refusal on extra package file).
        be_session = self.ram / "sessions/session-be0001"
        be_session.mkdir(parents=True, mode=0o700)
        for p in sorted(self.package.iterdir()):
            (be_session / p.name).write_bytes(p.read_bytes())
            (be_session / p.name).chmod(p.stat().st_mode & 0o777)
        be_script = (ASSETS / "backend.sh").read_text()
        be_script = (
            be_script.replace("/tmp/mnt/data_persist/open-connect", str(self.data))
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
                'transaction_prepare() { echo "UNEXPECTED_SLOW_PATH" >&2; exit 77; }\n',
            )
        )
        # Wrap persistent boot-select path inside fast_set_publish/no-op audit to supply self.root.
        (be_session / "service.sh").write_text(
            (be_session / "service.sh")
            .read_text()
            .replace(
                "BOOT_SELECT=$d/boot-select",
                f"BOOT_SELECT={shlex.quote(str(wrapper))}",
            )
        )
        (be_session / "firmware.sh").write_text(
            (be_session / "firmware.sh")
            .read_text()
            .replace("/proc/mounts", str(self.root / "proc/mounts"))
            .replace("/tmp/mnt/data_persist/open-connect", str(self.data))
            .replace("/tmp/open-connect", str(self.ram))
        )
        (be_session / "backend.sh").write_text(be_script)
        (be_session / "backend.sh").chmod(0o700)
        (self.ram / "lock").write_text("")
        (self.ram / "lock").chmod(0o600)
        (self.ram / "selected").write_text(on_cur + "\n")
        (self.ram / "selected").chmod(0o600)
        (self.ram / "boot-id").symlink_to(BOOT)
        (self.ram / "runtime").symlink_to(be_session)

        def call_backend(*args):
            return subprocess.run(
                ["sh", str(be_session / "backend.sh"), "api", *args],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

        # Data-only save through real backend.sh succeeds via fast path (never hits transaction_prepare).
        be_set = call_backend(on_cur, "set", "carplay-autoshow", "1", "0")
        self.assertEqual(be_set.returncode, 0, be_set.stdout + be_set.stderr)
        be_out = json.loads(be_set.stdout)
        self.assertTrue(be_out["ok"])
        self.assertEqual(be_out["carplayAutoshow"], 0)
        # No-op set through real backend.sh passes native audit.
        be_noop = call_backend(be_out["revision"], "set", "carplay-autoshow", "0", "0")
        self.assertEqual(be_noop.returncode, 0, be_noop.stdout + be_noop.stderr)
        # Extra package file causes real backend.sh to hard-fail state_changed on both no-op and set.
        pkg_extra = self.package / "be-extra"
        pkg_extra.write_text("bad\n")
        be_refuse_noop = call_backend(be_out["revision"], "set", "carplay-autoshow", "0", "0")
        be_refuse_set = call_backend(be_out["revision"], "set", "carplay-autoshow", "0", "1")
        pkg_extra.unlink()
        self.assertNotEqual(be_refuse_noop.returncode, 0)
        self.assertEqual(json.loads(be_refuse_noop.stdout)["error"], "state_changed")
        self.assertNotEqual(be_refuse_set.returncode, 0)
        self.assertEqual(json.loads(be_refuse_set.stdout)["error"], "state_changed")
        on_cur = be_out["revision"]

        # Extra package entry is also refused by shell fallback's boot_dependencies_match.
        extra_fb = self.package / "stray-fallback"
        extra_fb.write_text("stray\n")
        fb_rc = subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; D=$1; P=$2; R_BACKEND=$3; . "$P/state.sh"; . "$P/firmware.sh"; '
                '. "$P/transaction.sh"; boot_dependencies_match "$4"',
                "fb-member-check",
                str(self.data),
                str(self.package),
                self.package_id,
                on_cur,
            ],
            env=env,
            capture_output=True,
        ).returncode
        extra_fb.unlink()
        self.assertNotEqual(fb_rc, 0)

        # Oversized composed template (> 262144 B) is refused before awk renders.
        idx_on = self.composed / "index-on.html"
        orig_idx_on = idx_on.read_bytes()
        idx_on.write_bytes(b"a" * 262145)
        before_ov = (self.data / "record").read_bytes()
        ov_res = run_fast("carplay-autoshow", "1")
        idx_on.write_bytes(orig_idx_on)
        idx_on.chmod(0o600)
        self.assertNotEqual(ov_res.returncode, 0)
        self.assertEqual(json.loads(ov_res.stdout)["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_ov)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])

        # 3) Hard integrity refusals reach caller as state_changed and leave OC1/work clean.
        before_rec = (self.data / "record").read_bytes()
        extra = self.package / "unexpected-extra"
        extra.write_text("bad\n")
        refused = run_fast("carplay-autoshow", "0")
        extra.unlink()
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(json.loads(refused.stdout)["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_rec)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])

        # Symlink in predecessor snapshot (autostart) is refused by C O_NOFOLLOW without copying.
        cur_snap = self.data / "snapshots" / on_cur
        orig_auto = (cur_snap / "autostart").read_bytes()
        (cur_snap / "autostart").unlink()
        (cur_snap / "autostart").symlink_to("/etc/passwd")
        refused_link = run_fast("carplay-autoshow", "0")
        (cur_snap / "autostart").unlink()
        (cur_snap / "autostart").write_bytes(orig_auto)
        (cur_snap / "autostart").chmod(0o600)
        self.assertNotEqual(refused_link.returncode, 0)
        self.assertEqual(json.loads(refused_link.stdout)["error"], "state_changed")
        self.assertEqual((self.data / "record").read_bytes(), before_rec)
        self.assertEqual(list((self.data / "snapshots").glob(".new-*")), [])
