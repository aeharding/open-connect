"""Native selector primitives: real file boundaries and independent SHA vectors."""

import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class NativeBootIO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name).resolve()
        cls.program = cls.folder / "boot-io"
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-std=c11",
                "-D_GNU_SOURCE",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-O2",
                "-I" + str(ASSETS),
                ROOT / "tests/fixtures/boot-io.c",
                "-o",
                cls.program,
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()

    def invoke(self, path="input", limit=2_000_000, output=None):
        command = [self.program, self.root, path, str(limit)]
        if output is not None:
            command.append(output)
        return subprocess.run(command, capture_output=True, text=True, timeout=3)

    def test_hash_vectors_padding_and_stream_boundaries(self):
        rows = [b"", b"abc", b"a" * 1_000_000]
        for length in (55, 56, 63, 64, 65, 127, 128, 4095, 4096, 4097, 8193):
            rows.append(bytes((i * 37 + 19) % 256 for i in range(length)))
        for data in rows:
            with self.subTest(length=len(data)):
                (self.root / "input").write_bytes(data)
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines()[0], hashlib.sha256(data).hexdigest())

    def test_copy_matches_digest_and_opened_file_metadata(self):
        data = bytes(range(256)) * 37
        path = self.root / "input"
        path.write_bytes(data)
        result = self.invoke(output="copy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "copy").read_bytes(), data)
        self.assertEqual(result.stdout.splitlines()[0], hashlib.sha256(data).hexdigest())
        stat = path.stat()
        fields = [int(v) for v in result.stdout.splitlines()[1].split()]
        self.assertEqual(
            fields,
            [
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mode,
                stat.st_uid,
                stat.st_gid,
                stat.st_mtime_ns // 1_000_000_000,
                stat.st_mtime_ns % 1_000_000_000,
                stat.st_ctime_ns // 1_000_000_000,
                stat.st_ctime_ns % 1_000_000_000,
            ],
        )

    def test_descriptor_walk_refuses_links_and_escapes(self):
        (self.root / "input").write_bytes(b"original")
        (self.root / "link").symlink_to("input")
        (self.root / "dir").mkdir()
        (self.root / "dir/file").write_bytes(b"nested")
        (self.root / "parent").symlink_to("dir", target_is_directory=True)
        for path in (
            "link",
            "parent/file",
            "../input",
            "./input",
            "/input",
            "dir//file",
            "dir/../input",
        ):
            with self.subTest(path=path):
                self.assertNotEqual(self.invoke(path).returncode, 0)
        self.assertEqual(self.invoke("dir/file").returncode, 0)

    def test_special_or_overlarge_input_refuses_without_blocking(self):
        os.mkfifo(self.root / "fifo")
        (self.root / "input").write_bytes(b"too long")
        self.assertNotEqual(self.invoke("fifo").returncode, 0)
        self.assertNotEqual(self.invoke("input", limit=7).returncode, 0)

    def test_copy_never_replaces_an_existing_file_or_directory(self):
        (self.root / "input").write_bytes(b"new")
        (self.root / "copy").write_bytes(b"old")
        self.assertNotEqual(self.invoke(output="copy").returncode, 0)
        self.assertEqual((self.root / "copy").read_bytes(), b"old")
        (self.root / "directory").mkdir()
        self.assertNotEqual(self.invoke(output="directory").returncode, 0)
        self.assertEqual(list((self.root / "directory").iterdir()), [])


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class NativeBootPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.program = Path(cls.temp.name).resolve() / "boot-select"
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
        cls.temp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.source = self.root / "input"
        (self.root / "snapshot").mkdir()
        self.source.write_bytes(b"verified original file\n")
        self.header = "OCBP1|" + "b" * 64 + "|" + "c" * 64 + "\n"
        self.row = "root/test|/input|" + hashlib.sha256(self.source.read_bytes()).hexdigest() + "\n"

    def seal(self, text=None, success=True):
        output = self.root / "plan"
        with output.open("wb") as target:
            result = subprocess.run(
                [self.program, "seal", self.root, "snapshot"],
                input=(text if text is not None else self.header + self.row).encode(),
                stdout=target,
                stderr=subprocess.PIPE,
                timeout=3,
            )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return output.read_bytes()

    def check(self, plan, success=True):
        result = subprocess.run(
            [self.program, "check", self.root, "snapshot"],
            input=plan,
            capture_output=True,
            timeout=3,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_sealed_plan_round_trip_and_deterministic_metadata(self):
        plan = self.seal()
        self.assertTrue(plan.startswith(self.header.encode()))
        self.assertEqual(len(plan.splitlines()[1].split(b"|")), 13)
        self.check(plan)
        self.assertEqual(self.seal(), plan)

    def test_snapshot_members_remain_valid_after_directory_publication(self):
        (self.root / "snapshot/config").write_bytes(b"saved configuration\n")
        row = (
            "current/config|@/config|" + hashlib.sha256(b"saved configuration\n").hexdigest() + "\n"
        )
        plan = self.seal(self.header + self.row + row)
        self.check(plan)
        (self.root / "snapshot").rename(self.root / "published")
        result = subprocess.run(
            [self.program, "check", self.root, "published"],
            input=plan,
            capture_output=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sealer_rehashes_all_bytes_before_attesting_metadata(self):
        self.source.write_bytes(b"foreign equal-length!\n")
        self.seal(success=False)

    def test_metadata_refuses_replacement_and_same_size_edits_with_restored_mtime(self):
        for operation in ("replace", "inplace", "chmod"):
            with self.subTest(operation=operation):
                self.source.write_bytes(b"verified original file\n")
                os.utime(self.source, ns=(1_600_000_000_000_000_000,) * 2)
                before = self.source.stat()
                plan = self.seal()
                if operation == "replace":
                    other = self.root / "replacement"
                    other.write_bytes(self.source.read_bytes())
                    os.utime(other, ns=(before.st_atime_ns, before.st_mtime_ns))
                    other.replace(self.source)
                elif operation == "inplace":
                    with self.source.open("r+b") as target:
                        target.write(b"changed!")
                    os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
                else:
                    self.source.chmod(0o400)
                self.check(plan, success=False)
                self.source.chmod(0o600)

    def test_rejects_empty_truncated_duplicate_or_noncanonical_source_lists(self):
        for text in (
            self.header,
            self.header + self.row.rstrip("\n"),
            self.header + self.row + self.row,
            self.header + self.row.replace("/input", "/../input"),
            self.header + self.row.replace("root/test", "root/../test"),
            self.header + self.row.replace("/input", "/input "),
            self.header + self.row.replace("/input", "/input\x00"),
        ):
            with self.subTest(text=text):
                self.seal(text, success=False)

    def test_rejects_malformed_or_missing_sealed_metadata(self):
        plan = self.seal()
        invalid = plan.splitlines()[1].split(b"|")
        invalid[-1] = b"zzzzzzzz"
        for changed in (
            plan[:-1],
            self.header.encode(),
            plan + plan.splitlines()[1] + b"\n",
            self.header.encode() + b"|".join(invalid) + b"\n",
            plan.split(b"\n", 1)[0] + b"\n" + self.row.encode(),
        ):
            if changed != plan:
                with self.subTest(plan=changed):
                    self.check(changed, success=False)

    def test_absence_requires_an_accessible_parent_and_rejects_any_new_leaf(self):
        plan = self.seal(self.header + self.row + "hold/test|@/missing|-\n")
        self.check(plan)
        path = self.root / "snapshot/missing"
        path.write_bytes(b"foreign")
        self.check(plan, success=False)
        path.unlink()
        path.symlink_to("dangling")
        self.check(plan, success=False)
        path.unlink()
        os.mkfifo(path)
        self.check(plan, success=False)
        self.seal(self.header + self.row + "hold/test|/no-parent/missing|-\n", success=False)

    def native_fixture(self):
        # Reuse the actual v74-map fixture, adding the real C capability. Import
        # locally so unittest does not discover that TestCase a second time.
        from tests.test_installer_boot import InstallerBoot

        fixture = InstallerBoot(
            "test_populated_fast_path_keeps_budget_and_original_dependency_guards"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        previous = fixture.package_id
        version = fixture.root / "version.ini"
        version.write_text("verified synthetic firmware identity\n")
        source = fixture.source / "firmware.sh"
        source.write_text(source.read_text().replace("/jci/version.ini", str(version)))
        shutil.copyfile(self.program, fixture.source / "boot-select")
        (fixture.source / "boot-select").chmod(0o700)
        (fixture.source / "INSTANCE").write_text("1" * 32 + "\n")
        manifest = "".join(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
            for path in sorted(fixture.source.iterdir())
            if path.name != "files.sha256"
        )
        (fixture.source / "files.sha256").write_text(manifest)
        fixture.package_id = hashlib.sha256(manifest.encode()).hexdigest()
        fixture.package = fixture.data / "packages" / fixture.package_id
        shutil.copytree(fixture.source, fixture.package)
        shutil.copytree(
            fixture.data / "composed" / previous,
            fixture.data / "composed" / fixture.package_id,
        )
        fixture.shell('record_read; R_BACKEND="$3"; record_write')
        fixture.select_wireless(1, base=1)
        return fixture

    def test_reconcile_publishes_plan_only_after_actual_after_state(self):
        fixture = self.native_fixture()
        before = fixture.record()[5]
        result = fixture.shell(r"""
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
AUTOSTART=$D-target
record_read
transaction_prepare set "$R_CURRENT" "$R_CURRENT"
transaction_reconcile
printf '%s\n' "$R_CURRENT"
""")
        current = result.stdout.strip()
        self.assertNotEqual(current, before)
        self.assertEqual(fixture.record()[1], "active")
        self.assertEqual(fixture.record()[5], current)
        snapshot = fixture.data / "snapshots" / current
        fixture.shell("snapshot_read " + shlex.quote(current))
        manifest = (snapshot / "files.sha256").read_bytes()
        self.assertEqual(hashlib.sha256(manifest).hexdigest(), current)
        plan = (snapshot / "boot.plan").read_bytes()
        self.assertIn(hashlib.sha256(plan).hexdigest() + "  boot.plan", manifest.decode())
        self.assertIn(b"base/settings.txt|", plan)
        for name in ("sm-normal.conf", "sm-wcp.conf", "index.html"):
            self.assertTrue((snapshot / name).is_file())
            self.assertIn(("current/" + name + "|@/" + name).encode(), plan)
        check = subprocess.run(
            [self.program, "check", "/", str(snapshot).lstrip("/")],
            input=plan,
            capture_output=True,
            timeout=3,
        )
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_cut_after_plan_sealing_preserves_pending_recovery(self):
        fixture = self.native_fixture()
        before = fixture.record()[5]
        driver = r"""
set -eu
umask 077
D=$1; P=$2; AUTOSTART=$D-target
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
record_read
if test "$3" = cut; then
    transaction_prepare set "$R_CURRENT" "$R_CURRENT"
    snapshot_finish() {
        test -s "$1/boot.plan" || exit 1
        kill -KILL "$$"
        exit 1
    }
fi
transaction_reconcile
"""
        cut = subprocess.run(
            ["sh", "-c", driver, "cut", fixture.data, fixture.package, "cut"],
            env=fixture.env,
            capture_output=True,
            timeout=15,
        )
        self.assertNotEqual(cut.returncode, 0)
        self.assertEqual(fixture.record()[1], "set")
        self.assertEqual(fixture.record()[5], before)
        self.assertFalse((fixture.data / "snapshots" / before / "boot.plan").exists())
        recovered = subprocess.run(
            ["sh", "-c", driver, "resume", fixture.data, fixture.package, "resume"],
            env=fixture.env,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(fixture.record()[1], "active")
        self.assertNotEqual(fixture.record()[5], before)
        self.assertTrue((fixture.data / "snapshots" / fixture.record()[5] / "boot.plan").is_file())

    def test_new_native_package_cannot_seal_an_empty_dependency_set(self):
        fixture = self.native_fixture()
        before = fixture.record()[5]
        driver = r"""
set -eu
umask 077
D=$1; P=$2; AUTOSTART=$D-target
. "$P/state.sh"
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
record_read; snapshot_read "$R_CURRENT"
after=$(snapshot_create "$AUTOSTART" "$R_BACKEND" "$S_TOUCH" "$S_WARNING" "$S_NVRAM" "$S_META" /dev/null - "$S_PANDORA" "$S_BASE" "$S_WIRELESS")
transaction_prepare set "$R_CURRENT" "$after"
transaction_reconcile
"""
        result = subprocess.run(
            ["sh", "-c", driver, "invalid", fixture.data, fixture.package],
            env=fixture.env,
            capture_output=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(fixture.record()[1], "set")
        self.assertEqual(fixture.record()[5], before)
        self.assertIn(b"boot_dependencies_changed", result.stderr)

    def test_prepared_factory_profiles_keep_policy_and_do_not_change_current_record(self):
        fixture = self.native_fixture()
        fixture.select_wireless(0)
        composed = fixture.data / "composed" / fixture.package_id
        (composed / "index-off.html").write_text("saved off @TOKEN@\n")
        for profile in ("normal", "wcp"):
            path = composed / f"sm-{profile}-off.conf"
            path.write_text(
                path.read_text().replace(
                    'name="jciMMUI"', 'name="jciMMUI" path="/jci/mmui/svcjcimmui.so"'
                )
            )
        fixture.populated_dependencies()
        fixture.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 0 disable "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" - 0 0 0); record_write'
        )
        before = (fixture.data / "record").read_bytes()
        result = fixture.shell(r"""
. "$P/firmware.sh"
. "$P/access.sh"
. "$P/transaction.sh"
AUTOSTART=$D-target
record_read
boot_snapshot_seal "$R_CURRENT"
""")
        self.assertEqual((fixture.data / "record").read_bytes(), before)
        snapshot = fixture.data / "snapshots" / result.stdout.strip()
        self.assertEqual((snapshot / "index.html").read_text(), "saved off @TOKEN@\n")
        self.assertNotIn(b"\nbase/", (snapshot / "boot.plan").read_bytes())
        for profile in ("normal", "wcp"):
            services = {
                node.attrib["name"]: node
                for node in ET.parse(snapshot / f"sm-{profile}.conf").iter("service")
            }
            self.assertNotIn("open_connect_wireless", services)
            self.assertEqual(services["jciMMUI"].attrib["path"], "/jci/mmui/svcjcimmui.so")
            self.assertEqual(services["blm_ira_pandora"].attrib["autorun"], "no")
            self.assertEqual(services["jciLDS"].attrib["args"], "actual-gps-provider")
            if profile == "wcp":
                self.assertEqual(services["jciCARPLAY"].attrib["args"], "wcp")

    @unittest.skipUnless(shutil.which("make") and shutil.which("ld.lld"), "Make/LLD required")
    def test_standard_make_builds_freestanding_arm_helper(self):
        output = self.root / "arm"
        result = subprocess.run(
            ["make", "OUT=" + str(output), str(output / "boot-select")],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        elf = (output / "boot-select").read_bytes()
        self.assertEqual(elf[:6], b"\x7fELF\x01\x01")
        self.assertEqual(int.from_bytes(elf[18:20], "little"), 40)
