"""Exercise the real native decision and durable writer against complete files."""

import hashlib
import os
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
    )

    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        folder = Path(cls.build.name).resolve()
        cls.program = folder / "boot-select"
        # Only the three physical Base input digests are adapted to authored
        # fixtures. The selector, metadata, commit and publication logic is real.
        for source in (*ASSETS.glob("boot-*.h"), ASSETS / "boot-select.c"):
            text = source.read_text()
            for _, _, data, original in cls.BASE_INPUTS:
                text = text.replace(original, sha(data.encode()))
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
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "VERSION",
        ]
        for name in mandatory:
            (package / name).write_bytes((ASSETS / name).read_bytes())
        for name in ("flush", "api", "wireless.sh", "wireless-device.awk", "defer-gap2.sh"):
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

    def invoke(self, cut=None, term=None, output_limit=None, mode="select", stderr_fd=None):
        # A regular fixture models urandom's bytes, refreshing them per entry.
        self.put("dev/urandom", os.urandom(1024))
        env = {**os.environ}
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
        self.change_current(
            "config", (self.snapshot / "config").read_text().replace("base=0", "base=1")
        )
        self.put("sys/devices/virtual/block/ffx01/dev", "253:16\n")
        return self.put("sys/devices/virtual/block/ffx01/queue/read_ahead_kb", "128\n", 0o644)

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
        self.assertIn(b"base_read_ahead_unavailable\n", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.ram / "selected").is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[9], "2")

    def test_missing_queue_does_not_turn_success_into_stock_or_a_second_debit(self):
        queue = self.base_fixture()
        queue.unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"base_read_ahead_unavailable\n", result.stderr)
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
        self.assertFalse((self.ram / "feature/mmui.so").exists())

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
        self.assertEqual(record[9:12], ["2", "-", BOOT])
        self.assertEqual((self.ram / "selected").read_text(), self.snapshot.name + "\n")
        self.assertEqual(
            (self.ram / "feature/uia.so").read_bytes(), (self.composed / "uia.so").read_bytes()
        )
        for name in ("uia.so", "system-app.js"):
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
