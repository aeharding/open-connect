"""Real package writer: independent installs with shared immutable member inodes."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"

DRIVER = r"""
set -eu
umask 077
D=$1; P=$2; R_BACKEND=$3; FAULT=$4
. "$5/state.sh"; . "$5/firmware.sh"
uuid() { openssl rand -hex 16; }
cp() { printf 'copy\n' >> "$D-operations"; command cp "$@"; }
ln() {
    printf 'link\n' >> "$D-operations"
    test "$FAULT" != no-links || return 1
    command ln "$@" || return
    test "$FAULT" != uncertain-link
}
flush() {
    "$P/flush" "$1" "$2" || fail flush_failed
    case "$FAULT:$1:$2" in
        member:f:*/payload.bin|directory:d:*/.new-*) fail interrupted;;
        published:d:*/packages) fail interrupted;;
    esac
}
package=$(package_save) || fail package_failed
printf '%s\n' "$package"
"""


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.source = self.root / "source"
        self.tools = self.root / "tools"
        for folder in (self.data, self.source, self.tools):
            folder.mkdir(mode=0o700)
        for name in ("packages", "snapshots", "composed"):
            (self.data / name).mkdir(mode=0o700)
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.source / "flush"],
            check=True,
            capture_output=True,
            timeout=20,
        )
        for name in ("state.sh", "preferences.awk", "services.tsv", "sm-profile.awk", "VERSION"):
            shutil.copyfile(ASSETS / name, self.source / name)
        state = (
            (self.source / "state.sh")
            .read_text()
            .replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
        )
        (self.source / "state.sh").write_text(state)
        # Only profile rendering is synthetic in the transaction check. Package,
        # manifest, snapshot and OC1 writers/readers remain the maintained code.
        (self.source / "firmware.sh").write_text(
            "boot_render_profiles() {\n"
            " for name in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do\n"
            '  printf "fixture profile\\n" > "$1/$name" || return 1\n'
            " done\n}\n"
        )
        (self.source / "api").write_text("authored API fixture\n")
        (self.source / "payload.bin").write_bytes(bytes(range(256)) * 16384)
        self.manifest(self.source)
        self.members = [p.name for p in self.source.iterdir() if p.name != "files.sha256"]

    def manifest(self, folder):
        (folder / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(folder.iterdir())
                if p.name != "files.sha256"
            )
        )

    def save(self, previous="-", fault="none", ok=True):
        log = self.data.with_name("data-operations")
        log.write_text("")
        start = time.monotonic()
        result = subprocess.run(
            ["sh", "-c", DRIVER, "package-test", self.data, self.source, previous, fault, ASSETS],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.elapsed = time.monotonic() - start
        self.operations = log.read_text().splitlines()
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            identity = result.stdout.strip()
            folder = self.data / "packages" / identity
            self.assertEqual(
                hashlib.sha256((folder / "files.sha256").read_bytes()).hexdigest(), identity
            )
            return folder
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def fingerprint(self, folder):
        return {
            p.name: (
                hashlib.sha256(p.read_bytes()).hexdigest(),
                p.stat().st_ino,
                p.stat().st_mode,
                p.stat().st_uid,
                p.stat().st_gid,
            )
            for p in folder.iterdir()
        }

    def test_identical_repeats_share_members_with_independent_install_identities(self):
        first = self.save()
        copied = self.operations.count("copy")
        first_seconds = self.elapsed
        original = self.fingerprint(first)
        hold = (first / "payload.bin").open("rb")
        self.addCleanup(hold.close)
        second = self.save(first.name)
        second_seconds = self.elapsed
        self.assertEqual(self.operations.count("copy"), 0)
        self.assertEqual(self.operations.count("link"), copied)
        third = self.save(second.name)
        self.assertEqual(self.operations.count("copy"), 0)
        self.assertEqual(len({first.name, second.name, third.name}), 3)
        self.assertEqual(self.fingerprint(first), original)
        for name in self.members:
            self.assertEqual((first / name).stat().st_ino, (second / name).stat().st_ino)
            self.assertEqual((first / name).stat().st_ino, (third / name).stat().st_ino)
        for name in ("INSTANCE", "files.sha256"):
            self.assertEqual(len({(p / name).stat().st_ino for p in (first, second, third)}), 3)
            self.assertEqual(len({(p / name).read_bytes() for p in (first, second, third)}), 3)
        files = [p for generation in (first, second, third) for p in generation.iterdir()]
        unique = {(p.stat().st_dev, p.stat().st_ino): p for p in files}
        report = {
            "generations": 3,
            "member_copies_first": copied,
            "member_copies_repeat": self.operations.count("copy"),
            "member_links_repeat": self.operations.count("link"),
            "logical_bytes_all_paths": sum(p.stat().st_size for p in files),
            "logical_bytes_unique_inodes": sum(p.stat().st_size for p in unique.values()),
            "allocated_bytes_unique_inodes": sum(p.stat().st_blocks * 512 for p in unique.values()),
            "first_seconds": round(first_seconds, 4),
            "repeat_seconds": [round(second_seconds, 4), round(self.elapsed, 4)],
        }
        print("IDENTICAL_REINSTALL_HOST_COST " + json.dumps(report, sort_keys=True))
        # Removal of either new generation releases names, never old data/metadata.
        shutil.rmtree(second)
        shutil.rmtree(third)
        self.assertEqual(self.fingerprint(first), original)
        self.assertEqual(hold.read(), (first / "payload.bin").read_bytes())

    def test_changed_payload_uses_verified_copy_path(self):
        first = self.save()
        original = self.fingerprint(first)
        (self.source / "payload.bin").write_bytes(b"different authored payload\n")
        self.manifest(self.source)
        second = self.save(first.name)
        self.assertEqual(self.operations.count("copy"), len(self.members))
        self.assertNotIn("link", self.operations)
        self.assertEqual((second / "payload.bin").read_bytes(), b"different authored payload\n")
        self.assertEqual(self.fingerprint(first), original)

    def test_untrusted_candidates_use_fresh_verified_source(self):
        for damage in ("bytes", "manifest", "symlink", "directory-mode", "unknown-id"):
            with self.subTest(damage=damage):
                first = self.save()
                candidate_id = first.name
                if damage == "bytes":
                    (first / "payload.bin").write_bytes(b"corruption\n")
                elif damage == "manifest":
                    (first / "files.sha256").write_text("not authenticated\n")
                elif damage == "symlink":
                    (first / "payload.bin").unlink()
                    (first / "payload.bin").symlink_to(self.source / "payload.bin")
                elif damage == "directory-mode":
                    first.chmod(0o755)
                else:
                    candidate_id = "f" * 64
                second = self.save(candidate_id)
                self.assertEqual(self.operations.count("copy"), len(self.members))
                self.assertNotIn("link", self.operations)
                self.assertEqual(
                    (second / "payload.bin").read_bytes(),
                    (self.source / "payload.bin").read_bytes(),
                )

    def test_metadata_mismatch_copies_without_changing_old_inode(self):
        (self.source / "boot-select").write_text("authored selector fixture\n")
        self.manifest(self.source)
        first = self.save()
        (first / "payload.bin").chmod(0o400)
        old = self.fingerprint(first)
        second = self.save(first.name)
        self.assertEqual(self.operations.count("copy"), 1)
        self.assertNotEqual(
            (first / "payload.bin").stat().st_ino, (second / "payload.bin").stat().st_ino
        )
        self.assertEqual((second / "payload.bin").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.fingerprint(first), old)
        for name in ("api", "flush", "boot-select"):
            self.assertEqual((second / name).stat().st_mode & 0o777, 0o700)

    def test_damaged_source_refuses_before_linking_even_with_good_old_package(self):
        first = self.save()
        old = self.fingerprint(first)
        (self.source / "payload.bin").write_bytes(b"unmanifested change\n")
        self.save(first.name, ok=False)
        self.assertEqual(self.operations, [])
        self.assertEqual(self.fingerprint(first), old)
        self.assertEqual(list((self.data / "packages").iterdir()), [first])

    def test_unavailable_hardlinks_fall_back_without_touching_old_members(self):
        first = self.save()
        old = self.fingerprint(first)
        second = self.save(first.name, "no-links")
        self.assertEqual(self.operations.count("copy"), len(self.members))
        self.assertEqual(self.fingerprint(first), old)
        for name in self.members:
            self.assertNotEqual((first / name).stat().st_ino, (second / name).stat().st_ino)

    def test_reused_package_does_not_bypass_originals_verification(self):
        first = self.save()
        second = self.save(first.name)
        old = self.fingerprint(first)
        originals = self.data / "originals"
        originals.mkdir(mode=0o700)
        original = originals / "uia.so"
        original.write_bytes(b"synthetic verified original\n")
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        original.write_bytes(b"changed original\n")
        result = subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; D=$1; P=$2; expected=$5; . "$4/state.sh"; . "$4/firmware.sh"; '
                'original_files() { printf "%s uia.so /unused\\n" "$expected"; }; compose "$3"',
                "originals-test",
                self.data,
                self.source,
                second.name,
                ASSETS,
                digest,
            ],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compose_inputs_invalid", result.stderr)
        self.assertFalse((self.data / "composed" / second.name).exists())
        self.assertEqual(self.fingerprint(first), old)

    def test_interrupted_staging_and_uncertain_link_never_overwrite_shared_bytes(self):
        first = self.save()
        old = self.fingerprint(first)
        for fault in ("uncertain-link", "member", "directory", "published"):
            with self.subTest(fault=fault):
                self.save(first.name, fault, ok=False)
                self.assertEqual(self.fingerprint(first), old)
                self.assertFalse(list((self.data / "packages").glob(".new-*")))
                if fault == "uncertain-link":
                    self.assertNotIn("copy", self.operations)
                for path in (self.data / "packages").iterdir():
                    if path != first:
                        shutil.rmtree(path)
                self.assertTrue(all(p.stat().st_nlink == 1 for p in first.iterdir()))

    def test_reinstall_cuts_preserve_old_record_or_recover_the_exact_new_instance(self):
        driver = r"""
set -eu
umask 077
D=$1; P=$2; package=$3; action=$4; CUT=$5
AUTOSTART=$D-target
. "$P/state.sh"; . "$6/firmware.sh"; . "$6/transaction.sh"
firmware_dependencies() { :; }
nvram_read() { cat "$D-nvram"; }
nvram_change() {
    test "$(cat "$D-nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D-nvram"
    test "$CUT" != nvram || kill -KILL $$
}
startup_publish() {
    test "$(sha "$AUTOSTART")" = "$3" || return 1
    cp "$1" "$AUTOSTART.next"; chmod 755 "$AUTOSTART.next"
    mv "$AUTOSTART.next" "$AUTOSTART"
    test "$CUT" != startup || kill -KILL $$
}
if test "$action" = init; then
    printf 'stock\n' > "$AUTOSTART"; chmod 755 "$AUTOSTART"
    printf 'absent\n' > "$D-nvram"
    R_BASE=$(state_capture - - ""); R_CURRENT=$R_BASE
    R_BACKEND=$(printf '%064d' 0); R_PHASE=removed
    R_BEFORE=-; R_AFTER=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
    record_write; exit
fi
record_read
if test "$action" = recover; then transaction_reconcile; exit; fi
mkdir -m 700 "$D/composed/$package"
printf 'installed\n' > "$D/composed/$package/autostart"
deps=$(mktemp "$D/.deps-XXXXXX")
dependencies_capture "$package" > "$deps"
after=$(snapshot_create "$D/composed/$package/autostart" "$package" disable "755:$(id -u):$(id -g)" "$deps" - "")
rm "$deps"
test "$CUT" != before-record || kill -KILL $$
R_BACKEND=$package
transaction_prepare install "$R_CURRENT" "$after"
test "$CUT" != prepared || kill -KILL $$
transaction_reconcile
"""

        def transaction(package, action, cut="none", ok=True):
            result = subprocess.run(
                [
                    "sh",
                    "-c",
                    driver,
                    "transaction-test",
                    self.data,
                    self.source,
                    package.name,
                    action,
                    cut,
                    ASSETS,
                ],
                capture_output=True,
                text=True,
                env=self.env,
                timeout=15,
            )
            self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)

        first = self.save()
        transaction(first, "init")
        transaction(first, "install")
        old = self.fingerprint(first)
        initial_snapshot = (self.data / "record").read_text().split("|")[5]
        previous = first
        for cut in ("before-record", "prepared", "startup", "nvram"):
            with self.subTest(cut=cut):
                candidate = self.save(previous.name)
                record = (self.data / "record").read_bytes()
                transaction(candidate, "install", cut, ok=False)
                self.assertEqual(self.fingerprint(first), old)
                if cut == "before-record":
                    self.assertEqual((self.data / "record").read_bytes(), record)
                    # Roll back an unpublished attempt by releasing its names.
                    shutil.rmtree(candidate)
                    self.assertEqual(self.fingerprint(first), old)
                else:
                    fields = (self.data / "record").read_text().strip().split("|")
                    self.assertEqual(fields[1], "install")
                    self.assertEqual(fields[3], candidate.name)
                    transaction(candidate, "recover")
                    fields = (self.data / "record").read_text().strip().split("|")
                    self.assertEqual(fields[1], "active")
                    self.assertEqual(fields[3], candidate.name)
                    self.assertNotEqual(fields[5], initial_snapshot)
                    self.assertEqual(fields[6:9], ["-", "-", "-"])
                    self.assertEqual(fields[12], "installed")
                    config = self.data / "snapshots" / fields[5] / "config"
                    self.assertIn("package=" + candidate.name + "\n", config.read_text())
                    previous = candidate
        self.assertEqual(self.fingerprint(first), old)
