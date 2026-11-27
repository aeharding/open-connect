"""Native selector primitives: real file boundaries and independent SHA vectors."""

import hashlib
import json
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

    def native_fixture(self, *, resources=False, publisher=False, wireless=True):
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
            "#!/bin/sh\nset -eu\n"
            'if test "$1:$2" = '
            + shlex.quote("d:" + str(fixture.data / "snapshots"))
            + " && test -f "
            + shlex.quote(str(fixture.root / "fail-snapshots"))
            + "; then printf x >> "
            + shlex.quote(str(fixture.root / "snapshot-flushes"))
            + "; exit 1; fi\n"
            'if test "$1" = d && test -f '
            + shlex.quote(str(fixture.root / "fail-retire-dir"))
            + ' && test "$2" = '
            + shlex.quote(str(fixture.root))
            + "; then exit 1; fi\n"
            + shlex.quote(str(real_flush))
            + ' "$@"\n'
            'case "$1:$*" in f:*/boot.plan|F:*/boot.plan*) if test -f '
            + shlex.quote(str(fixture.root / "cut-seal"))
            + '; then kill -KILL "$PPID"; fi;; esac\n'
            'case "$1:$2" in f:*/.open-connect-*-root-login) if test -f '
            + shlex.quote(str(fixture.root / "cut-publisher"))
            + '; then kill -KILL "$PPID"; fi;; esac\n'
        )
        (fixture.source / "flush").chmod(0o700)
        (fixture.source / "INSTANCE").write_text("1" * 32 + "\n")
        if resources:
            # Keep real access/selector pair checks and writes on private targets.
            for name in ("firmware.sh", "access.sh"):
                path = fixture.source / name
                text = path.read_text()
                for original, leaf in (
                    ("/usr/bin/autostart", "data-target"),
                    ("/usr/bin/open-connect-boot-select", "root-selector"),
                    ("/usr/bin/runlogin", "root-login"),
                    ("/etc/ssh/sshd_config", "root-sshd"),
                ):
                    text = text.replace(original, str(fixture.root / leaf))
                path.write_text(text)
            if publisher:
                validator = fixture.tools / "sshd-validator"
                validator.write_text("#!/bin/sh\nexit 0\n")
                validator.chmod(0o700)
                text = source.read_text().replace("startup_staging_guard() { :; }\n", "")
                text = text.replace("startup_staging_retire() { :; }\n", "")
                start = text.index("startup_publish() {\n")
                end = text.index("\n}\n", start) + 3
                text = text[:start] + text[end:]
                source.write_text(
                    text.replace(
                        "/usr/bin/.open-connect-", str(fixture.root / ".open-connect-")
                    ).replace("/etc/ssh/.open-connect-", str(fixture.root / ".open-connect-"))
                    + '\nstartup_publish() { root_publish "$AUTOSTART" "$@"; }\n'
                    "remount() { :; }\n"
                )
                access = fixture.source / "access.sh"
                access.write_text(
                    access.read_text()
                    .replace("/usr/bin/.open-connect-", str(fixture.root / ".open-connect-"))
                    .replace("/usr/sbin/sshd", str(validator))
                )
            else:
                with source.open("a") as stream:
                    stream.write(
                        "\nroot_publish() {\n"
                        ' if test "$2" = -; then rm -f "$1"; return; fi\n'
                        ' cp "$2" "$1.next" && metadata "$3" &&\n'
                        ' chmod "$S_MODE" "$1.next" && mv "$1.next" "$1"\n'
                        "}\n"
                    )
        if resources:
            shutil.copyfile(ASSETS / "console.sh", fixture.source / "console.sh")
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
        if wireless:
            fixture.select_wireless(1, base=1)
        else:
            fixture.write_profiles()
            fixture.populated_dependencies()
        if resources:
            fixture.shell(
                '. "$P/access.sh"; record_read; root=${D%/*}; work=$D-resources; mkdir -m 700 "$work"; '
                'printf "stock login\\n" > "$work/runlogin"; '
                'printf "stock sshd\\n" > "$work/sshd.conf"; '
                'cp "$work/runlogin" "$root/root-login"; chmod 755 "$root/root-login"; '
                + ('inode=$(stat -c %i "$root/root-login"); ' if publisher else "inode=-; ")
                + 'printf "0|0|-|755:%s:%s|644:%s:%s|%s\\n" '
                '"$(id -u)" "$(id -g)" "$(id -u)" "$(id -g)" "$inode" > "$work/access"; '
                'printf "%s\\n" - > "$work/selector"; '
                'snapshot_read "$R_BASE"; '
                'R_BASE=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" '
                '"$S_META" "$D/snapshots/$R_BASE/dependencies" "$work" ""); '
                'cp "$work/sshd.conf" "$root/root-sshd"; chmod 644 "$root/root-sshd"; '
                'selector_compose "$work" "$R_BACKEND"; '
                'cp "$P/boot-select" "$root/root-selector"; chmod 700 "$root/root-selector"; '
                'snapshot_read "$R_CURRENT"; '
                'R_CURRENT=$(snapshot_create "$D/snapshots/$R_CURRENT/autostart" "$S_PACKAGE" '
                '"$S_NVRAM" "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$work" "$S_PREFS"); '
                "record_write"
            )
        return fixture

    def sealed_fixture(self):
        fixture = self.native_fixture()
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; transaction_prepare set "$R_CURRENT" "$R_CURRENT"; transaction_reconcile'
        )
        return fixture

    def touch_fixture(self, *, resources=False, publisher=False):
        fixture = self.native_fixture(resources=resources, publisher=publisher, wireless=False)
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(fixture_snapshot "$D-target" "$R_BACKEND" 2 0 absent "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0); '
            'printf "absent\\n" > "$D-nvram"; record_write; '
            'transaction_prepare set "$R_CURRENT" "$R_CURRENT"; transaction_reconcile'
        )
        return fixture

    def test_touch_pins_guard_prepare_but_not_exit_or_uninstall_dependencies(self):
        fixture = self.touch_fixture()
        before = (fixture.data / "record").read_bytes()
        snapshot = fixture.data / "snapshots" / fixture.record()[5]
        dependencies = (snapshot / "dependencies").read_text()
        self.assertNotIn("touch/devices/", dependencies)
        self.assertNotIn(str(fixture.root / "touch-svc"), dependencies)
        (fixture.root / "touch-svc").write_bytes(b"changed OEM service\n")
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            fixture.shell(
                'record_read; snapshot_read "$R_CURRENT"; '
                'fixture_snapshot "$D-target" "$R_BACKEND" 2 0 absent "$S_META" '
                '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0'
            )
        self.assertIn("boot_profiles_failed", caught.exception.stderr)
        self.assertEqual((fixture.data / "record").read_bytes(), before)
        # The same changed input does not block a 2->0 snapshot or the actual
        # uninstall transaction, because conditional pins are boot inputs only.
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; snapshot_read "$R_CURRENT"; '
            'after=$(fixture_snapshot "$AUTOSTART" "$R_BACKEND" 0 0 absent "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0); '
            'transaction_prepare set "$R_CURRENT" "$after"; transaction_reconcile; '
            'targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" && uninstall_owned "$R_CURRENT"; '
            'before=$R_CURRENT; snapshot_read "$R_BASE"; '
            'after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" "$S_META" '
            '"$D/snapshots/$before/dependencies" "$D/snapshots/$R_BASE" ""); '
            'transaction_prepare uninstall "$before" "$after"; transaction_reconcile'
        )
        self.assertEqual(fixture.record()[1], "removed")

    def test_touch_changed_pin_does_not_block_direct_disabled_uninstall(self):
        fixture = self.touch_fixture()
        (fixture.root / "touch-lib").write_bytes(b"changed OEM devices library\n")
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" && uninstall_owned "$R_CURRENT"; '
            'before=$R_CURRENT; snapshot_read "$R_BASE"; '
            'after=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" "$S_META" '
            '"$D/snapshots/$before/dependencies" "$D/snapshots/$R_BASE" ""); '
            'transaction_prepare uninstall "$before" "$after"; transaction_reconcile'
        )
        self.assertEqual(fixture.record()[1], "removed")
        self.assertEqual((fixture.root / "data-target").read_text(), "stock\n")

    def retained_touch_pending(self, operation, cut):
        fixture = self.touch_fixture(resources=True)
        setup = '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; '
        if operation == "set":
            # Use the actual Settings Set entry, cutting after its durable prepare.
            client = fixture.runtime / "client"
            shutil.copytree(fixture.package, client)
            (fixture.runtime / "runtime").symlink_to(client)
            (fixture.runtime / "selected").write_text(fixture.record()[5] + "\n")
            transaction = client / "transaction.sh"
            original = transaction.read_text()
            transaction.write_text(
                original.replace(
                    "  PREPARED_REV=$R_REV", "  kill -KILL $$\n  PREPARED_REV=$R_REV"
                )
            )
            result = self.touch_api(
                fixture, "set", fixture.record()[5], "carplay-autoshow", "0", "1"
            )
            self.assertEqual(result.returncode, -9, result.stdout + result.stderr)
            transaction.write_text(original)
        else:
            # Reinstall captures current physical state, then creates an unsealed
            # after snapshot retaining the same preferences and package.
            fixture.shell(
                setup + 'snapshot_read "$R_CURRENT"; '
                'before=$(state_capture "$S_PACKAGE" "$D/snapshots/$R_CURRENT" "$S_PREFS"); '
                'after=$(snapshot_create "$AUTOSTART" "$S_PACKAGE" "$S_NVRAM" "$S_META" '
                '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$S_PREFS"); '
                'transaction_prepare install "$before" "$after"'
            )
            client = fixture.runtime / "client"
            shutil.copytree(fixture.package, client)
            (fixture.runtime / "runtime").symlink_to(client)
            (fixture.runtime / "selected").write_text(fixture.record()[5] + "\n")
        pending = fixture.record()
        self.assertEqual(pending[1], operation)
        snapshots = fixture.data / "snapshots"
        configs = [
            dict(
                line.split("=", 1)
                for line in (snapshots / value / "config").read_text().splitlines()[1:]
            )
            for value in pending[6:8]
        ]
        self.assertEqual([config["touch"] for config in configs], ["2", "2"])
        self.assertEqual(
            {key for key in configs[0] if configs[0][key] != configs[1][key]},
            {"carplay-autoshow"} if operation == "set" else set(),
        )
        self.assertEqual((snapshots / pending[7] / "boot.plan").exists(), operation == "set")
        if cut == "startup":
            # Exit immediately after a real physical target publication, before sealing.
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                fixture.shell(
                    setup + 'startup_publish() { root_publish "$AUTOSTART" "$@"; kill -KILL $$; }; '
                    "transaction_reconcile"
                )
            self.assertEqual(caught.exception.returncode, -9)
            self.assertEqual(fixture.record(), pending)
        (fixture.root / "touch-lib").write_bytes(b"changed OEM devices library\n")
        return fixture, client, pending

    def touch_api(self, fixture, operation, revision, *args):
        return subprocess.run(
            [
                "sh",
                fixture.runtime / "client/backend.sh",
                "api",
                revision,
                operation,
                *(args or ("-", "-", "-")),
            ],
            capture_output=True,
            text=True,
            env=fixture.env,
            timeout=20,
        )

    def staged_touch_pending(self, *, reversal=False):
        fixture = self.touch_fixture(resources=True, publisher=True)
        setup = '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; '
        if reversal:
            fixture.shell(
                setup + 'snapshot_read "$R_CURRENT"; '
                'prefs=$(preferences_change "$S_PREFS" "$S_PACKAGE" touch 1 "$S_SCHEMA"); '
                'after=$(snapshot_create "$AUTOSTART" "$S_PACKAGE" disable "$S_META" '
                '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" "$prefs"); '
                'transaction_prepare set "$R_CURRENT" "$after"; transaction_reconcile'
            )
        client = fixture.runtime / "client"
        shutil.copytree(fixture.package, client)
        (fixture.runtime / "runtime").symlink_to(client)
        (fixture.runtime / "selected").write_text(fixture.record()[5] + "\n")
        # The flush adapter kills the publisher subshell immediately after
        # fsync, bypassing its EXIT trap and preventing the target rename.
        cut = fixture.root / "cut-publisher"
        cut.touch()
        if reversal:
            # Also change UART in the real prepared 1->2 transaction so the
            # reversal has a physical pre-rename stage to retire.
            fixture.shell(
                setup + 'snapshot_read "$R_CURRENT"; '
                "package=$S_PACKAGE; prefs=$S_PREFS; mode=$S_META; schema=$S_SCHEMA; "
                'work=$(mktemp -d "$D/access.XXXXXX"); access_compose "$work" 1 0 -; '
                'selector_keep "$D/snapshots/$R_CURRENT" "$work"; '
                'prefs=$(preferences_change "$prefs" "$package" touch 2 "$schema"); '
                'after=$(snapshot_create "$AUTOSTART" "$package" absent "$mode" '
                '"$D/snapshots/$R_CURRENT/dependencies" "$work" "$prefs"); '
                'rm -rf "$work"; transaction_prepare set "$R_CURRENT" "$after"'
            )
            result = self.touch_api(fixture, "recover", fixture.record()[2])
        else:
            result = self.touch_api(fixture, "set", fixture.record()[5], "uart", "0", "1")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"], "access_apply_failed")
        cut.unlink()
        pending = fixture.record()
        self.assertEqual(pending[1], "set")
        stage = fixture.root / (".open-connect-" + pending[2] + "-root-login")
        self.assertEqual(
            stage.read_bytes(),
            (fixture.data / "snapshots" / pending[7] / "runlogin").read_bytes(),
        )
        self.assertEqual((fixture.root / "root-login").read_bytes(), b"stock login\n")
        # Other owned physical-stage names share the same retirement boundary.
        for source, suffix in (
            (fixture.data / "snapshots" / pending[7] / "autostart", ""),
            (fixture.data / "snapshots" / pending[7] / "sshd.conf", "-root-sshd"),
            (fixture.package / "boot-select", "-root-selector"),
        ):
            (fixture.root / (".open-connect-" + pending[2] + suffix)).write_bytes(
                source.read_bytes()
            )
        (fixture.root / "touch-lib").write_bytes(b"changed OEM devices library\n")
        (fixture.runtime / "runtime").unlink()
        (fixture.runtime / "usb-runtime").symlink_to(client)
        return fixture, client, pending, stage

    def test_touch_recovery_retires_real_publisher_stages_across_policy_cuts(self):
        for reversal in (False, True):
            for cut in ("before", "after", "policy"):
                with self.subTest(reversal=reversal, cut=cut):
                    fixture, client, pending, stage = self.staged_touch_pending(reversal=reversal)
                    transaction = client / "transaction.sh"
                    original = transaction.read_text()
                    retire = '      startup_staging_retire "$R_AFTER" || fail startup_stage_changed\n'
                    if cut == "before":
                        changed = original.replace(retire, "      kill -KILL $$\n" + retire)
                    elif cut == "after":
                        changed = original.replace(retire, retire + "      kill -KILL $$\n")
                    else:
                        changed = original.replace(
                            "      record_write\n      transaction_reconcile; return",
                            "      record_write\n      kill -KILL $$\n      transaction_reconcile; return",
                        )
                    self.assertNotEqual(changed, original)
                    transaction.write_text(changed)
                    result = self.touch_api(fixture, "recover", pending[2])
                    self.assertEqual(result.returncode, -9, result.stdout + result.stderr)
                    self.assertEqual(stage.exists(), cut == "before")
                    if cut != "policy":
                        self.assertEqual(fixture.record(), pending)
                    else:
                        self.assertNotEqual(fixture.record()[2], pending[2])
                    transaction.write_text(original)
                    result = self.touch_api(fixture, "recover", fixture.record()[2])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    recovered = json.loads(result.stdout)
                    self.assertEqual(recovered["touch"], 1 if reversal else 0)
                    self.assertEqual(recovered["uart"], 0 if reversal else 1)
                    self.assertEqual(list(fixture.root.glob(".open-connect-" + "?" * 32 + "*")), [])
                    result = self.touch_api(fixture, "uninstall", recovered["revision"])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertFalse(fixture.data.exists())
                    self.assertEqual(list(fixture.root.glob(".open-connect-*")), [])
                    self.assertEqual((fixture.root / "root-login").read_bytes(), b"stock login\n")

    def test_touch_recovery_keeps_foreign_stage_and_cleanup_refuses_it(self):
        fixture, _, pending, stage = self.staged_touch_pending()
        foreign = fixture.root / (".open-connect-" + "f" * 32 + "-root-login")
        foreign.write_bytes(stage.read_bytes())
        result = self.touch_api(fixture, "recover", pending[2])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(stage.exists())
        saved = foreign.read_bytes()
        result = self.touch_api(fixture, "uninstall", fixture.record()[5])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"], "startup_stage_changed")
        self.assertEqual(foreign.read_bytes(), saved)
        foreign.unlink()
        result = self.touch_api(fixture, "uninstall", fixture.record()[5])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(fixture.data.exists())

    def test_touch_recovery_refuses_changed_owned_stage_before_retiring_revision(self):
        fixture, _, pending, stage = self.staged_touch_pending()
        stage.write_bytes(b"foreign stage bytes\n")
        result = self.touch_api(fixture, "recover", pending[2])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"], "startup_stage_changed")
        self.assertEqual(fixture.record(), pending)
        self.assertEqual(stage.read_bytes(), b"foreign stage bytes\n")

    def test_touch_recovery_checks_restore_stage_inode_identity(self):
        for replace_inode in (True, False):
            with self.subTest(replace_inode=replace_inode):
                fixture = self.touch_fixture(resources=True, publisher=True)
                client = fixture.runtime / "client"
                shutil.copytree(fixture.package, client)
                (fixture.runtime / "runtime").symlink_to(client)
                (fixture.runtime / "selected").write_text(fixture.record()[5] + "\n")
                original_inode = (fixture.root / "root-login").stat().st_ino
                enabled = self.touch_api(fixture, "set", fixture.record()[5], "uart", "0", "1")
                self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
                hold = fixture.root / (".open-connect-runlogin-" + str(original_inode))
                self.assertEqual(hold.stat().st_ino, original_inode)
                # Interrupt disabling UART immediately after the restore stage is flushed.
                cut = fixture.root / "cut-publisher"
                cut.touch()
                interrupted = self.touch_api(fixture, "set", fixture.record()[5], "uart", "1", "0")
                self.assertNotEqual(
                    interrupted.returncode, 0, interrupted.stdout + interrupted.stderr
                )
                cut.unlink()
                pending = fixture.record()
                self.assertEqual(pending[1], "set")
                stage = fixture.root / (".open-connect-" + pending[2] + "-root-login")
                self.assertEqual(stage.stat().st_ino, original_inode)
                if replace_inode:
                    stat_before = stage.stat()
                    replacement = fixture.root / "replacement-stage"
                    replacement.write_bytes(stage.read_bytes())
                    replacement.chmod(stat_before.st_mode & 0o7777)
                    os.utime(replacement, ns=(stat_before.st_atime_ns, stat_before.st_mtime_ns))
                    stage.unlink()
                    replacement.rename(stage)
                    self.assertNotEqual(stage.stat().st_ino, original_inode)
                    replacement_inode = stage.stat().st_ino
                (fixture.root / "touch-lib").write_bytes(b"changed OEM devices library\n")
                (fixture.runtime / "runtime").unlink()
                (fixture.runtime / "usb-runtime").symlink_to(client)
                result = self.touch_api(fixture, "recover", pending[2])
                if replace_inode:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(json.loads(result.stdout)["error"], "startup_stage_changed")
                    self.assertEqual(fixture.record(), pending)
                    self.assertTrue(stage.exists())
                    self.assertEqual(stage.stat().st_ino, replacement_inode)
                    self.assertEqual(hold.stat().st_ino, original_inode)
                else:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    recovered = json.loads(result.stdout)
                    self.assertEqual((recovered["touch"], recovered["uart"]), (0, 0))
                    self.assertFalse(stage.exists())
                    self.assertEqual((fixture.root / "root-login").stat().st_ino, original_inode)
                    uninstall = self.touch_api(fixture, "uninstall", recovered["revision"])
                    self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
                    self.assertFalse(fixture.data.exists())
                    self.assertEqual(list(fixture.root.glob(".open-connect-*")), [])
                    self.assertEqual((fixture.root / "root-login").stat().st_ino, original_inode)

    def test_factory_snapshot_reuse_retries_failed_parent_flush_before_oc1(self):
        fixture, _, pending, _ = self.staged_touch_pending()
        record = (fixture.data / "record").read_bytes()
        failure = fixture.root / "fail-snapshots"
        failure.touch()
        before = set((fixture.data / "snapshots").iterdir())
        for attempt in (1, 2):
            result = self.touch_api(fixture, "recover", pending[2])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["error"], "plan_failed")
            self.assertEqual((fixture.data / "record").read_bytes(), record)
            self.assertEqual((fixture.root / "snapshot-flushes").read_bytes(), b"x" * attempt)
            created = set((fixture.data / "snapshots").iterdir()) - before
            self.assertEqual(len(created), 1)
            self.assertFalse(next(iter(created)).name.startswith(".new-"))
        failure.unlink()
        result = self.touch_api(fixture, "recover", pending[2])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["touch"], 0)
        result = self.touch_api(fixture, "uninstall", fixture.record()[5])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(fixture.data.exists())

    def test_touch_stage_retirement_flush_failure_keeps_old_oc1_across_retries(self):
        for reversal in (False, True):
            with self.subTest(reversal=reversal):
                fixture, _, pending, _ = self.staged_touch_pending(reversal=reversal)
                failure = fixture.root / "fail-retire-dir"
                failure.touch()
                for _ in range(2):
                    result = self.touch_api(fixture, "recover", pending[2])
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(json.loads(result.stdout)["error"], "startup_stage_changed")
                    self.assertEqual(fixture.record(), pending)
                failure.unlink()
                result = self.touch_api(fixture, "recover", pending[2])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = self.touch_api(fixture, "uninstall", fixture.record()[5])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(fixture.data.exists())
                self.assertEqual(list(fixture.root.glob(".open-connect-*")), [])

    def test_touch_oem_pin_hash_refuses_valid_output_from_failed_process(self):
        fixture = self.native_fixture()
        fixture.shell("touch_inputs_verify")
        for pin in ("touch-svc", "touch-lib"):
            with self.subTest(pin=pin):
                target = shlex.quote(str(fixture.root / pin))
                with self.assertRaises(subprocess.CalledProcessError):
                    fixture.shell(
                        'sha() { "$P/flush" h "$1" || return 1; '
                        'test "$1" != ' + target + "; }; touch_inputs_verify"
                    )

    def test_retained_touch_changed_pin_recovers_and_usb_uninstalls_across_cuts(self):
        for operation in ("set", "install"):
            for cut in ("prepared", "startup", "policy"):
                with self.subTest(operation=operation, cut=cut):
                    fixture, client, pending = self.retained_touch_pending(operation, cut)
                    # Changed pins still prevent selecting or resealing mode 2.
                    for attempt in range(3):
                        with self.assertRaises(subprocess.CalledProcessError) as caught:
                            fixture.shell(
                                'AUTOSTART=$D-target; record_read; boot_snapshot_seal "$R_AFTER"'
                            )
                        self.assertIn("boot_inputs_failed", caught.exception.stderr)
                        self.assertEqual(
                            list((fixture.data / "snapshots").glob(".new-*")), [], attempt
                        )
                    if cut == "policy":
                        (fixture.runtime / "runtime").unlink()
                        (fixture.runtime / "usb-runtime").symlink_to(client)
                        transaction = client / "transaction.sh"
                        original = transaction.read_text()
                        transaction.write_text(
                            original.replace(
                                "      record_write\n      transaction_reconcile; return",
                                "      record_write\n      kill -KILL $$\n      transaction_reconcile; return",
                            )
                        )
                        interrupted = self.touch_api(fixture, "recover", pending[2])
                        self.assertEqual(interrupted.returncode, -9, interrupted.stderr)
                        safe = fixture.record()
                        self.assertEqual(safe[6], pending[6])
                        self.assertNotEqual(safe[7], pending[7])
                        transaction.write_text(original)
                    result = self.touch_api(fixture, "recover", fixture.record()[2])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    recovered = json.loads(result.stdout)
                    self.assertEqual((recovered["touch"], recovered["pending"]), (0, False))
                    snapshot = fixture.data / "snapshots" / fixture.record()[5]
                    config = (snapshot / "config").read_text()
                    original_config = (
                        fixture.data / "snapshots" / pending[7] / "config"
                    ).read_text()
                    self.assertEqual(config, original_config.replace("touch=2\n", "touch=0\n"))
                    self.assertNotIn("touch/devices/", (snapshot / "boot.plan").read_text())
                    fixture.shell(
                        '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
                        'record_read; targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT"'
                    )
                    settled_record = (fixture.data / "record").read_bytes()
                    result = self.touch_api(fixture, "recover", recovered["revision"])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual((fixture.data / "record").read_bytes(), settled_record)
                    # A fresh compatible USB consumes the recovered durable state.
                    if cut != "policy":
                        result = self.touch_api(
                            fixture, "set", recovered["revision"], "touch", "0", "2"
                        )
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(json.loads(result.stdout)["error"], "touch_inputs_changed")
                        self.assertEqual((fixture.data / "record").read_bytes(), settled_record)
                        (fixture.runtime / "runtime").unlink()
                        (fixture.runtime / "usb-runtime").symlink_to(client)
                    result = self.touch_api(fixture, "uninstall", recovered["revision"])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertFalse(fixture.data.exists())
                    self.assertEqual(
                        (fixture.root / "touch-lib").read_bytes(), b"changed OEM devices library\n"
                    )
                    self.assertEqual((fixture.root / "data-target").read_text(), "stock\n")
                    self.assertEqual((fixture.root / "data-nvram").read_text(), "absent\n")
                    self.assertEqual((fixture.root / "root-login").read_text(), "stock login\n")
                    self.assertEqual((fixture.root / "root-sshd").read_text(), "stock sshd\n")
                    self.assertFalse((fixture.root / "root-selector").exists())

    def test_retained_touch_changed_pin_recovery_refuses_every_third_target(self):
        for operation in ("set", "install"):
            for cut in ("prepared", "startup"):
                with self.subTest(operation=operation, cut=cut):
                    fixture, _, pending = self.retained_touch_pending(operation, cut)
                    record = (fixture.data / "record").read_bytes()
                    targets = (
                        "data-nvram",
                        "data-target",
                        "root-login",
                        "root-sshd",
                        "root-selector",
                    )
                    expected = (
                        "nvram_changed",
                        "startup_changed",
                        "access_changed",
                        "access_changed",
                        "selector_changed",
                    )
                    for leaf, error in zip(targets, expected, strict=True):
                        with self.subTest(target=leaf):
                            target = fixture.root / leaf
                            saved = target.read_bytes()
                            target.write_bytes(
                                b"enable\n"
                                if leaf == "data-nvram"
                                else b"unexpected third target\n"
                            )
                            physical = {
                                name: (fixture.root / name).read_bytes() for name in targets
                            }
                            result = self.touch_api(fixture, "recover", pending[2])
                            self.assertNotEqual(result.returncode, 0)
                            self.assertEqual(json.loads(result.stdout)["error"], error)
                            self.assertEqual((fixture.data / "record").read_bytes(), record)
                            self.assertEqual(
                                {name: (fixture.root / name).read_bytes() for name in targets},
                                physical,
                            )
                            self.assertEqual(list((fixture.data / "snapshots").glob(".new-*")), [])
                            target.write_bytes(saved)

    def test_interrupted_touch_disable_changed_pin_recovers_then_uninstalls(self):
        for previous in (0, 1):
            for cut in ("prepared", "nvram", "rollback"):
                with self.subTest(previous=previous, cut=cut):
                    self.interrupted_touch_recovery(cut, previous)

    def interrupted_touch_recovery(self, cut, previous):
        fixture = self.touch_fixture()
        previous_nvram = "disable" if previous == 1 else "absent"
        setup = '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; '
        fixture.shell(
            setup + 'snapshot_read "$R_CURRENT"; '
            f'after=$(fixture_snapshot "$AUTOSTART" "$R_BACKEND" {previous} 0 {previous_nvram} "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0); '
            'transaction_prepare set "$R_CURRENT" "$after"; transaction_reconcile; '
            'snapshot_read "$R_CURRENT"; '
            'after=$(fixture_snapshot "$AUTOSTART" "$R_BACKEND" 2 0 absent "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0); '
            'transaction_prepare set "$R_CURRENT" "$after"'
        )
        pending = fixture.record()
        self.assertEqual(pending[1], "set")
        snapshots = fixture.data / "snapshots"
        before = dict(
            line.split("=", 1)
            for line in (snapshots / pending[6] / "config").read_text().splitlines()[1:]
        )
        after = dict(
            line.split("=", 1)
            for line in (snapshots / pending[7] / "config").read_text().splitlines()[1:]
        )
        self.assertEqual(
            {key for key in before if before[key] != after[key]},
            {"touch", "nvram"} if previous == 1 else {"touch"},
        )
        # The preparing process has exited before the OEM input changes.
        pin = fixture.root / "touch-lib"
        pin.write_bytes(b"changed OEM devices library\n")
        client = fixture.runtime / "client"
        shutil.copytree(fixture.package, client)
        (fixture.runtime / "runtime").symlink_to(client)
        (fixture.runtime / "selected").write_text(pending[5] + "\n")
        if cut == "nvram":
            # A previous recovery could reach NVRAM before failing to seal.
            (fixture.root / "data-nvram").write_text("absent\n")
        if cut == "rollback":
            transaction = client / "transaction.sh"
            original = transaction.read_text()
            transaction.write_text(
                original.replace(
                    "      record_write\n      transaction_reconcile; return",
                    "      record_write\n      kill -KILL $$\n      transaction_reconcile; return",
                )
            )
            interrupted = subprocess.run(
                ["sh", client / "backend.sh", "api", pending[2], "recover", "-", "-", "-"],
                capture_output=True,
                text=True,
                env=fixture.env,
                timeout=15,
            )
            self.assertEqual(interrupted.returncode, -9)
            self.assertEqual(fixture.record()[6:8], [pending[7], pending[6]])
            self.assertEqual((fixture.root / "data-nvram").read_text(), previous_nvram + "\n")
            transaction.write_text(original)

        def api(operation, revision):
            result = subprocess.run(
                ["sh", client / "backend.sh", "api", revision, operation, "-", "-", "-"],
                capture_output=True,
                text=True,
                env=fixture.env,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        recovered = api("recover", fixture.record()[2])
        self.assertFalse(recovered["pending"])
        self.assertEqual(recovered["touch"], previous)
        self.assertEqual(fixture.record()[1], "active")
        self.assertEqual(fixture.record()[6:8], ["-", "-"])
        self.assertEqual(
            (snapshots / fixture.record()[5] / "config").read_text(),
            (snapshots / pending[6] / "config").read_text(),
        )
        self.assertEqual((fixture.root / "data-nvram").read_text(), previous_nvram + "\n")
        fixture.shell(
            setup
            + f'snapshot_read "$R_CURRENT"; test "$S_TOUCH" = {previous}; targets_match "$R_CURRENT"'
        )
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            fixture.shell(
                setup
                + 'snapshot_read "$R_CURRENT"; fixture_snapshot "$AUTOSTART" "$R_BACKEND" 2 0 absent "$S_META" "$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 0 0'
            )
        self.assertIn("boot_profiles_failed", caught.exception.stderr)
        removed = api("uninstall", recovered["revision"])
        self.assertFalse(removed["installed"])
        self.assertFalse(fixture.data.exists())
        self.assertEqual(pin.read_bytes(), b"changed OEM devices library\n")
        self.assertEqual((fixture.root / "data-target").read_text(), "stock\n")
        self.assertEqual((fixture.root / "data-nvram").read_text(), "absent\n")

    def test_touch_shell_unselected_modes_have_no_feature_copy(self):
        fixture = self.sealed_fixture()
        result = fixture.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((fixture.runtime / "feature/touch-disable.so").exists())
        fixture.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
            'record_read; snapshot_read "$R_CURRENT"; '
            'after=$(fixture_snapshot "$AUTOSTART" "$R_BACKEND" 0 1 absent "$S_META" '
            '"$D/snapshots/$R_CURRENT/dependencies" "$D/snapshots/$R_CURRENT" 1 1 1); '
            'transaction_prepare set "$R_CURRENT" "$after"; transaction_reconcile'
        )
        result = fixture.boot(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((fixture.runtime / "feature/touch-disable.so").exists())

    def test_touch_shell_stages_only_disabled_and_fallback_keeps_stock(self):
        fixture = self.touch_fixture()
        result = fixture.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        shim = fixture.runtime / "feature/touch-disable.so"
        self.assertEqual(shim.read_bytes(), (fixture.package / "touch-disable.so").read_bytes())
        self.assertEqual(shim.stat().st_mode & 0o777, 0o755)
        self.assertFalse((fixture.runtime / "feature/mmui.so").exists())
        self.assertIn("touch-disable.so", (fixture.runtime / "feature/sm.conf").read_text())
        record = fixture.record()
        record[9] = "0"
        (fixture.data / "record").write_text("|".join(record) + "\n")
        result = fixture.boot(2)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((fixture.runtime / "feature").exists())
        self.assertEqual((fixture.data.with_name("data-nvram")).read_text(), "absent\n")

    def test_touch_shell_requires_both_pins_once_and_root_fs_without_other_features(self):
        fixture = self.touch_fixture()
        snapshot = fixture.data / "snapshots" / fixture.record()[5]
        plan = (snapshot / "boot.plan").read_text()
        # Call the real shell verifier directly: boot normally reseals under its
        # lock, which is a separate defense against a damaged plan.
        script = (fixture.package / "boot.sh").read_text().split("boot_select() {")[0]
        verifier = fixture.root / "verify-touch.sh"
        verifier.write_text(script)

        def verify():
            return subprocess.run(
                [
                    "sh",
                    "-c",
                    'set -eu; D=$1; P=$2; . "$P/state.sh"; . "$P/firmware.sh"; '
                    '. "$3"; record_read; snapshot_read "$R_CURRENT"; boot_plan_verify "$R_CURRENT" verify',
                    "test",
                    fixture.data,
                    fixture.package,
                    verifier,
                ],
                env=fixture.env,
                capture_output=True,
                timeout=5,
            )

        def publish(text):
            nonlocal snapshot
            # Rename preserves every sealed @/ member's inode and metadata.
            (snapshot / "boot.plan").write_text(text)
            manifest = "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(snapshot.iterdir())
                if p.name != "files.sha256"
            )
            (snapshot / "files.sha256").write_text(manifest)
            digest = hashlib.sha256(manifest.encode()).hexdigest()
            target = fixture.data / "snapshots" / digest
            snapshot.rename(target)
            snapshot = target
            fields = fixture.record()
            fields[5] = digest
            (fixture.data / "record").write_text("|".join(fields) + "\n")

        publish(plan)
        positive = verify()
        self.assertEqual(positive.returncode, 0, positive.stderr)
        for key in ("svc", "lib"):
            row = next(
                line
                for line in plan.splitlines(True)
                if line.startswith("touch/devices/" + key + "|")
            )
            for bad in (
                plan.replace(row, ""),
                plan + row,
                plan.replace(row, row.replace(row.split("|")[2], "0" * 64)),
                plan.replace(row, row.replace("touch-" + key, "touch-wrong")),
            ):
                with self.subTest(key=key, bad=bad[-80:]):
                    # Authenticate through the same path as the intact control.
                    publish(bad)
                    before = (fixture.data / "record").read_bytes()
                    self.assertNotEqual(verify().returncode, 0)
                    self.assertEqual((fixture.data / "record").read_bytes(), before)
        publish(plan)
        positive = verify()
        self.assertEqual(positive.returncode, 0, positive.stderr)
        selected = fixture.boot(1)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual((fixture.runtime / "selected").read_text().strip(), fixture.record()[5])
        self.assertIn(
            "package=" + fixture.package_id + "\n",
            (fixture.data / "snapshots" / fixture.record()[5] / "config").read_text(),
        )
        self.assertEqual(
            (fixture.runtime / "feature/touch-disable.so").read_bytes(),
            (fixture.package / "touch-disable.so").read_bytes(),
        )
        # Exact byte-identical sources are rejected when the physical root
        # adapter reports a different device. No OEM content is required.
        text = verifier.read_text() + "\nvui_stock_device() { printf '999999\\n'; }\n"
        verifier.write_text(text)
        self.assertNotEqual(verify().returncode, 0)

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
