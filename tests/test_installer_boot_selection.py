"""Exercise the real native decision and durable writer against complete files."""

import hashlib
import os
import re
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
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.program = Path(cls.build.name).resolve() / "boot-select"
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
                ASSETS / "boot-select.c",
                "-o",
                cls.program,
            ],
            check=True,
        )

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
        for name in ("snapshots", "packages", "composed", "keys"):
            (self.data / name).mkdir(mode=0o700)
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
            "VERSION",
        ]
        for name in mandatory:
            (package / name).write_bytes((ASSETS / name).read_bytes())
        for name in ("flush", "api", "wireless.sh", "wireless-device.awk"):
            (package / name).write_text("fixture " + name + "\n")
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
            "config": f"-|0|0|absent|{self.mode}|1|0|0\n",
            "dependencies": "",
            "access": access,
            "runlogin": login.read_text(),
            "sshd.conf": ssh.read_text(),
            "selector": "-\n",
        }.items():
            (baseline / name).write_text(content)
        self.baseline = self.publish(baseline)

        composed = self.data / "composed" / self.package_id
        composed.mkdir(mode=0o700)
        names = [
            "autostart",
            "uia.so",
            "mmui.so",
            "mmui.xml",
            "system-app.js",
            "index-on.html",
            "index-off.html",
            "sm-normal-on.conf",
            "sm-normal-off.conf",
            "sm-wcp-on.conf",
            "sm-wcp-off.conf",
        ]
        for name in names:
            (composed / name).write_text("composed " + name + "\n")
        (composed / "autostart").write_text("installed autostart\n")
        self.manifest(composed)
        self.composed = composed
        self.put("usr/bin/autostart", "installed autostart\n", 0o755)
        # Use firmware.sh's real complete map, including sm_WCP's underscore.
        firmware = (ASSETS / "firmware.sh").read_text()
        mapping = re.findall(r"\b([a-f0-9]{64}) ([a-zA-Z0-9_.-]+) (/[^\s'\n]+)", firmware)
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
            "config": f"{self.package_id}|1|1|disable|{self.mode}|1|0|1\n",
            "access": access,
            "runlogin": login.read_text(),
            "sshd.conf": ssh.read_text(),
            "selector": f"{sha(self.program.read_bytes())}|700:{os.getuid()}:{os.getgid()}|{self.package_id}\n",
            "sm-normal.conf": "prepared normal\n",
            "sm-wcp.conf": "prepared WCP\n",
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

    def invoke(self, cut=None, term=None):
        # A regular fixture models urandom's bytes, refreshing them per entry.
        self.put("dev/urandom", os.urandom(1024))
        env = {**os.environ}
        if cut:
            env["OC_BOOT_CUT"] = cut
        if term:
            env["OC_BOOT_TERM"] = term
        return subprocess.run(
            [self.program, "select", self.root], env=env, capture_output=True, timeout=5
        )

    def test_selects_complete_policy_and_debits_once(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        record = (self.data / "record").read_text().split("|")
        self.assertEqual(record[9:12], ["2", "-", BOOT])
        self.assertEqual((self.ram / "selected").read_text(), self.snapshot.name + "\n")
        self.assertEqual(
            (self.ram / "feature/uia.so").read_bytes(), (self.composed / "uia.so").read_bytes()
        )
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
        config = (self.snapshot / "config").read_text().split("|")
        config[1] = "0"
        config[3] = "absent"
        self.change_current("config", "|".join(config))
        (self.root / "sys/class/nvram/nv-config/keys/lvds_speed_restriction").unlink()
        self.record[9] = "0"
        self.save_record()
        self.assertEqual(self.invoke().returncode, 2)
        self.assertTrue((self.ram / "ignition/ignition.sh").is_file())
        self.assertTrue((self.ram / "access-selected").is_file())
        self.assertFalse((self.ram / "selected").exists())
        self.assertFalse((self.ram / "feature").exists())
        self.assertEqual((self.data / "record").read_text().split("|")[9:12], ["0", "-", BOOT])

    def test_only_off_from_a_different_kernel_renews_budget(self):
        self.record[9] = "0"
        self.record[10] = "87654321-1234-1234-1234-123456789abc"
        self.save_record()
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual((self.data / "record").read_text().split("|")[9:12], ["2", "-", BOOT])

    def test_same_kernel_off_requires_factory_nvram_restore_in_full_verifier(self):
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
