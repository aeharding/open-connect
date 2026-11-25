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
        # These shell fixtures remap all OEM paths onto a private temporary
        # volume. Remap only the physical stock-root device reference as well;
        # the sealer still compares every selected source's actual device.
        for source in (*ASSETS.glob("boot-*.h"), ASSETS / "boot-select.c"):
            text = source.read_text()
            text = text.replace(
                "static int oc_stock_meta(int root,OcMeta *stock) { return oc_stat(root,stock)>=0; }",
                'static int oc_stock_meta(int root,OcMeta *stock) { (void)root; long fd=oc_openat(OC_CWD,"'
                + str(cls.program.parent)
                + '",OC_DIRECTORY,0); if(fd<0)return 0; int ok=oc_stat((int)fd,stock)>=0; return oc_close((int)fd)>=0&&ok; }',
            )
            (cls.program.parent / source.name).write_text(text)
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
                cls.program.parent / "boot-select.c",
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

    def test_recheck_allows_only_byte_identical_inode_and_timestamp_drift(self):
        plan = self.seal()
        original = self.source.read_bytes()
        self.source.write_bytes(original)
        for mode, success in (("recheck", True), ("verify", False)):
            result = subprocess.run(
                [self.program, mode, self.root, "snapshot"],
                input=plan,
                capture_output=True,
                timeout=3,
            )
            self.assertEqual(result.returncode == 0, success, result.stderr)
        self.source.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        result = subprocess.run(
            [self.program, "recheck", self.root, "snapshot"],
            input=plan,
            capture_output=True,
            timeout=3,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_recheck_preserves_old_mode_uid_and_gid(self):
        plan = self.seal()
        for index in (6, 7, 8):
            fields = plan.splitlines()[1].split(b"|")
            fields[index] = f"{int(fields[index], 16) ^ 1:08x}".encode()
            changed = plan.splitlines()[0] + b"\n" + b"|".join(fields) + b"\n"
            result = subprocess.run(
                [self.program, "recheck", self.root, "snapshot"],
                input=changed,
                capture_output=True,
                timeout=3,
            )
            self.assertNotEqual(result.returncode, 0)

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
        real_flush = fixture.root / "flush-real"
        shutil.copyfile(fixture.source / "flush", real_flush)
        real_flush.chmod(0o700)
        (fixture.source / "flush").write_text(
            "#!/bin/sh\nset -eu\n" + shlex.quote(str(real_flush)) + ' "$@"\n'
            'if test "$1" = f && test "${2##*/}" = boot.plan && test -f '
            + shlex.quote(str(fixture.root / "cut-seal"))
            + '; then kill -KILL "$PPID"; fi\n'
        )
        (fixture.source / "flush").chmod(0o700)
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

    def sealed_fixture(self):
        fixture = self.native_fixture()
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; transaction_prepare set "$R_CURRENT" "$R_CURRENT"; transaction_reconcile'
        )
        return fixture

    def test_sealed_shell_renders_base_index_with_disclaimer_off(self):
        fixture = self.native_fixture()
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 0 disable "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 1 1); '
            'record_write; transaction_prepare set "$R_CURRENT" "$R_CURRENT"; transaction_reconcile'
        )
        result = fixture.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        index = (fixture.runtime / "feature/index.html").read_text()
        self.assertIn('src="common/js/logDefaults.js"', index)
        self.assertIn('logDefaults.__global__ = "warn"', index)
        self.assertFalse((fixture.runtime / "feature/log-defaults.js").exists())
        self.assertTrue((fixture.runtime / "feature/mmui.so").exists())

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_logging_survives_compatible_dev13_purge_before_restart(self):
        fixture = self.sealed_fixture()
        result = fixture.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        index = fixture.runtime / "feature/index.html"
        replay = [
            "node",
            ROOT / "tests/fixtures/base-logging.js",
            index,
            fixture.root / "oem/log-defaults.js",
        ]
        subprocess.run(replay, check=True, capture_output=True, timeout=5)
        # Exercise the actual dev.13 purge body after restoration has reached
        # its committed purge phase. It knows nothing of dev.14 logging.
        fixture.shell(
            "record_read; R_PHASE=purge; record_write; "
            "P=" + shlex.quote(str(fixture.source)) + "; "
            ". " + shlex.quote(str(ROOT / "tests/fixtures/dev13-purge.sh")) + "; "
            "uninstall_cleanup"
        )
        self.assertFalse(fixture.data.exists())
        subprocess.run(replay, check=True, capture_output=True, timeout=5)

    def test_hinted_recovery_preserves_old_permissions_and_version_digest(self):
        for changed in ("permissions", "version"):
            with self.subTest(changed=changed):
                fixture = self.sealed_fixture()
                before = (fixture.data / "record").read_bytes()
                hint = fixture.data / "reseal"
                hint.write_text(fixture.record()[5] + "\n")
                hint.chmod(0o600)
                if changed == "permissions":
                    uia = fixture.data / "composed" / fixture.package_id / "uia.so"
                    uia.chmod((uia.stat().st_mode & 0o777) ^ 0o040)
                else:
                    version = fixture.root / "version.ini"
                    version.write_bytes(version.read_bytes().replace(b"identity", b"identitY"))
                result = fixture.boot(1)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("reseal_inputs_changed", result.stderr)
                self.assertEqual((fixture.data / "record").read_bytes(), before)
                self.assertTrue(hint.exists())
                self.assertFalse((fixture.runtime / "selected").exists())

    def test_hinted_recovery_reseals_identical_bytes_and_shell_links_resolve(self):
        fixture = self.sealed_fixture()
        old = fixture.record()[5]
        hint = fixture.data / "reseal"
        hint.write_text(old + "\n")
        hint.chmod(0o600)
        uia = fixture.data / "composed" / fixture.package_id / "uia.so"
        uia.write_bytes(uia.read_bytes())
        result = fixture.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(fixture.record()[5], old)
        self.assertFalse(hint.exists())
        self.assertEqual(fixture.record()[9], "2")
        for name in ("uia.so",):
            link = fixture.runtime / "feature" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), fixture.data / "composed" / fixture.package_id / name)
            self.assertEqual(link.read_bytes(), link.resolve().read_bytes())

    def test_unlisted_boot_plan_cannot_authorize_reseal_or_shell_links(self):
        fixture = self.native_fixture()
        snapshot = fixture.data / "snapshots" / fixture.record()[5]
        (snapshot / "boot.plan").write_text("unlisted plan\n")
        before = (fixture.data / "record").read_bytes()
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            fixture.shell('record_read; AUTOSTART=$D-target; boot_snapshot_seal "$R_CURRENT"')
        self.assertIn("invalid_boot_plan", caught.exception.stderr)
        hint = fixture.data / "reseal"
        hint.write_text(fixture.record()[5] + "\n")
        hint.chmod(0o600)
        result = fixture.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reseal_inputs_changed", result.stderr)
        self.assertEqual((fixture.data / "record").read_bytes(), before)
        self.assertFalse((fixture.runtime / "selected").exists())

    def test_sealer_rejects_a_copy_that_differs_from_prepared_named_digest(self):
        fixture = self.native_fixture()
        before = fixture.record()[5]
        cp = fixture.tools / "cp"
        cp.write_text(
            "#!/bin/sh\nset -eu\n" + shlex.quote(shutil.which("cp")) + ' "$@"\n'
            "for destination; do :; done\n"
            'case "$destination" in */snapshots/.new-*/sm-wcp.conf) printf "foreign copy\\n" >> "$destination";; esac\n'
        )
        cp.chmod(0o700)
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            fixture.shell(
                '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
                'record_read; transaction_prepare set "$R_CURRENT" "$R_CURRENT"; transaction_reconcile'
            )
        self.assertIn("boot_profiles_changed", caught.exception.stderr)
        self.assertEqual(fixture.record()[1], "set")
        self.assertEqual(fixture.record()[5], before)
        cp.unlink()
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; transaction_reconcile'
        )
        self.assertEqual(fixture.record()[1], "active")
        sealed = fixture.data / "snapshots" / fixture.record()[5]
        original = fixture.data / "snapshots" / before
        for name in ("sm-normal.conf", "sm-wcp.conf", "index.html"):
            self.assertEqual((sealed / name).read_bytes(), (original / name).read_bytes())

    def test_new_wcp_conflict_refuses_before_preparation_and_keeps_uninstall_usable(self):
        fixture = self.native_fixture()
        record = (fixture.data / "record").read_bytes()
        target = (fixture.root / "data-target").read_bytes()
        candidate = fixture.root / "candidate"
        shutil.copytree(fixture.package, candidate)
        (candidate / "INSTANCE").write_text("2" * 32 + "\n")
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(candidate.iterdir())
            if p.name != "files.sha256"
        )
        (candidate / "files.sha256").write_text(manifest)
        identity = hashlib.sha256(manifest.encode()).hexdigest()
        candidate.rename(fixture.data / "packages" / identity)
        composed = fixture.data / "composed" / identity
        shutil.copytree(fixture.data / "composed" / fixture.package_id, composed)
        bad = composed / "sm-wcp-on.conf"
        bad.write_text(bad.read_text().replace('name="jciAAPA"', 'name="foreign"'))
        fixture.composed_manifest(identity)
        result = fixture.shell(
            'AUTOSTART=$D-target; . "$P/access.sh"; . "$P/transaction.sh"; record_read; snapshot_read "$R_CURRENT"; '
            'deps=$(mktemp "$D/.candidate-deps-XXXXXX"); dependencies_capture '
            + identity
            + ' > "$deps"; '
            'if snapshot_create "$AUTOSTART" '
            + identity
            + ' "$S_NVRAM" "$S_META" "$deps" - "$S_PREFS"; then exit 99; fi; '
            'targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" && uninstall_owned "$R_CURRENT"'
        )
        self.assertIn("boot_profiles_failed", result.stderr)
        self.assertEqual((fixture.data / "record").read_bytes(), record)
        self.assertEqual((fixture.root / "data-target").read_bytes(), target)

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
        for profile in ("sm-normal.conf", "sm-wcp.conf"):
            services = list(ET.parse(snapshot / profile).iter("service"))
            worker = [s for s in services if s.attrib["name"] == "open_connect_settings"]
            self.assertEqual(len(worker), 1)
            self.assertEqual(worker[0].attrib["reset_board"], "no")
            self.assertEqual(worker[0].attrib["retry_count"], "0")
            self.assertEqual(worker[0].attrib["exit_allowed"], "yes")
            self.assertEqual(worker[0].find("dependency").attrib["value"], "stage_3")
            self.assertFalse(
                any(
                    dependency.attrib.get("value") == "open_connect_settings"
                    for service in services
                    for dependency in service.iter("dependency")
                )
            )
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

fi
transaction_reconcile
"""
        (fixture.root / "cut-seal").touch()
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
        (fixture.root / "cut-seal").unlink()
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
after=$(fixture_snapshot "$AUTOSTART" "$R_BACKEND" "$S_TOUCH" "$S_WARNING" "$S_NVRAM" "$S_META" /dev/null - "$S_PANDORA" "$S_BASE" "$S_WIRELESS")
transaction_prepare set "$R_CURRENT" "$after"
transaction_reconcile
"""
        driver = (ROOT / "tests/fixtures/installer-snapshots.sh").read_text() + driver
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
        (composed / "index-off.html").write_text("saved off @TOKEN@\nframework.init();\n")
        fixture.populated_dependencies()
        fixture.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 1 0 disable "$S_META" '
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
        index = (snapshot / "index.html").read_text()
        self.assertIn("saved off @TOKEN@\n", index)
        self.assertRegex(index, r'\}\(framework,\s*\[0,"pandora"\]\)\);')
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
