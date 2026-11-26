"""Cut the real first-Install backend around its initial state publication.

All files are authored fixtures. Only firmware composition/rendering, physical
root/NVRAM and native sealing are adapted; OC1, originals, packages, snapshots,
dependencies, lock admission and the USB metadata/JS contract run unchanged.
"""

import fcntl
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import unittest

from tests import test_installer_transaction as transaction

ROOT = transaction.ROOT
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang") and shutil.which("node"), "Clang and Node.js required")
class InitialInstall(unittest.TestCase):
    def setUp(self):
        self.f = transaction.InstallerTransaction()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root, self.tools = self.f.root, self.f.tools
        self.data = self.root / "data"
        self.f.backend_fixture(self.data)
        self.f.real_flock()
        self.runtime = self.root / "runtime"
        (self.runtime / "runtime").unlink()
        (self.runtime / "usb-runtime").symlink_to(self.tools)
        self.target = self.root / "data-target"
        self.target.write_text("authored stock startup\n")
        self.target.chmod(0o755)
        self.nvram = self.root / "nvram"
        self.nvram.write_text("absent\n")
        self.login = self.root / "login"
        self.login.write_text("authored stock login\n")
        self.login.chmod(0o755)
        self.ssh = self.root / "sshd.conf"
        self.ssh.write_text("authored stock SSH configuration\n")
        self.ssh.chmod(0o600)
        self.dependency = self.root / "dependency"
        self.dependency.write_text("authored stock dependency\n")
        self.originals = {
            "autostart": self.target.read_bytes(),
            "dependency": self.dependency.read_bytes(),
        }
        self.physical = (self.target, self.nvram, self.login, self.ssh)
        self.stock = self.fingerprint()
        self.operations = self.root / "operations"
        self.validator = self.root / "sshd-validator"
        self.validator.write_text("#!/bin/sh\nexit 0\n")
        self.validator.chmod(0o700)
        for name in ("sm-profile.awk", "boot.sh", "startup-hook.sh", "startup-join.sh"):
            shutil.copyfile(ASSETS / name, self.tools / name)
        (self.tools / "boot-select").write_text("authored native selector fixture\n")
        mapping = {
            "/usr/bin/runlogin": str(self.login),
            "/usr/bin/.open-connect-runlogin-": str(self.root / ".login-"),
            "/etc/ssh/sshd_config": str(self.ssh),
            "/usr/sbin/sshd": str(self.validator),
            "/usr/bin/open-connect-boot-select": str(self.root / "selector"),
            "b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8": hashlib.sha256(
                self.login.read_bytes()
            ).hexdigest(),
        }
        firmware = (ASSETS / "firmware.sh").read_text()
        firmware += "\n" + self.adapters()
        (self.tools / "firmware.sh").write_text(firmware)
        for name in ("backend.sh", "firmware.sh", "access.sh"):
            path = self.tools / name
            source = path.read_text()
            for old, new in mapping.items():
                source = source.replace(old, new)
            path.write_text(source)
        self.manifest(self.tools)

    def adapters(self):
        rows = "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()} {name} {path}\n"
            for name, path in (("autostart", self.target), ("dependency", self.dependency))
        )
        return (
            "TEST_ROOT=" + shlex.quote(str(self.root)) + "\n"
            "CANONICAL=" + shlex.quote(str(self.data)) + "\n"
            "BACKEND_PID=$$\n"
            "original_files() { cat <<'FIXTURE_ORIGINALS'\n"
            + rows
            + "FIXTURE_ORIGINALS\n}\n"
            + r"""
firmware_dependencies() { original_files; }
firmware_guard() { :; }
root_mode() { printf 'ro,noatime\n'; }
factory_wireless() { return 1; }
cleanup_mount_guard() { test ! -f "$TEST_ROOT/overmount"; }
startup_staging_guard() { :; }
nvram_read() { cat "$TEST_ROOT/nvram"; }
nvram_change() {
    test "$(cat "$TEST_ROOT/nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$TEST_ROOT/nvram"
}
boot_snapshot_seal() { printf '%s\n' "$1"; }
boot_render_profiles() {
    config_decode "$2" || return 1
    for name in sm-normal.conf sm-wcp.conf index.html mmui.xml vui-plugins.list; do
        printf '%s\n' "$S_SERVICES" > "$1/$name" || return 1
    done
}
compose() (
    set -eu
    local work
    verify_manifest "$D/packages/$1" && originals_verify || fail composition_inputs
    work=$(mktemp -d "$D/composed/.new-XXXXXX")
    # Physical firmware composition is synthetic. Persist a canonical boot path
    # so the fixture catches composing before the initial namespace is published.
    printf 'installed from %s/packages/%s\n' "$D" "$1" > "$work/autostart"
    printf '%s  autostart\n' "$(sha "$work/autostart")" > "$work/files.sha256"
    flush f "$work/autostart"; flush f "$work/files.sha256"; flush d "$work"
    mv "$work" "$D/composed/$1"; flush d "$D/composed"
)
root_publish() {
    # All target writes require the real prepared OC1 at the canonical location.
    test "$D" = "$CANONICAL" && record_read && test "$R_PHASE" = install || return 1
    local target=$1 source=$2 mode=$3 expected=$4 expected_mode=$5
    printf 'effect %s\n' "$target" >> "$TEST_ROOT/operations"
    if test "$expected" = -; then absent "$target" || return 1
    else
        test "$(sha "$target")" = "$expected" &&
            test "$(stat -c '%a:%u:%g' "$target")" = "$expected_mode" || return 1
    fi
    if test "$expected:$expected_mode" != "$(sha "$source"):$mode"; then
        cp "$source" "$target.next"; metadata "$mode"; chmod "$S_MODE" "$target.next"
        mv "$target.next" "$target"
    fi
}
startup_publish() { root_publish "$AUTOSTART" "$@"; }
fault() {
    printf 'fault %s\n' "$1" >> "$TEST_ROOT/operations"
    if test "${INITIAL_FAULT:-}" = "$1"; then
        if test "${INITIAL_MODE:-kill}" = fail; then return 1; fi
        kill -KILL "$BACKEND_PID"; exit 1
    fi
    return 0
}
mkdir() {
    local path
    for path in "$@"; do :; done
    command mkdir "$@" || return
    if test "$path" = "$D/snapshots"; then
        "$P/flush" d "$D" || return
        fault child || return 1
    fi
}
cp() {
    printf 'copy %s\n' "$*" >> "$TEST_ROOT/operations"
    case "$2" in
        "$D"/.originals-*/dependency) head -c 3 "$1" > "$2"; fault originals || return 1;;
        "$D"/packages/.new-*/state.sh) head -c 3 "$1" > "$2"; fault package || return 1;;
    esac
    command cp "$@"
}
mv() {
    local destination
    for destination in "$@"; do :; done
    if test "$destination" = "$CANONICAL"; then fault before-publish || return 1; fi
    command mv "$@" || return
    if test "$destination" = "$CANONICAL"; then fault after-publish || return 1; fi
    if test "$destination" = "$D/record" && test "$(cut -d '|' -f 2 "$destination")" = removed; then
        fault record-renamed || return 1
    fi
}
flush() {
    printf 'flush %s %s\n' "$1" "$2" >> "$TEST_ROOT/operations"
    case "$1:$2" in
        f:"$D"/record.*) fault record-file || fail flush_failed;;
        d:"$CANONICAL"/composed) fault composed || fail flush_failed;;
    esac
    if test "$1:$2" = "d:${CANONICAL%/*}" && test -f "$CANONICAL/record"; then fault parent || fail flush_failed; fi
    if test "$1:$2" = "d:$D" && test -f "$D/record" &&
        test "$(cut -d '|' -f 2 "$D/record")" = install; then fault pending-flush || fail flush_failed; fi
    "$P/flush" "$1" "$2" || fail flush_failed
    if test "$1:$2" = "d:$D"; then
        if test -f "$D/record"; then
            case "$(cut -d '|' -f 2 "$D/record")" in
                removed) fault baseline-record || fail flush_failed;;
                install) fault prepared || fail flush_failed;;
            esac
        elif test -d "$D/keys" && test ! -d "$D/originals"; then fault directories || fail flush_failed; fi
    fi
}
"""
        )

    def manifest(self, folder):
        (folder / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(folder.iterdir())
                if p.is_file() and not p.is_symlink() and p.name != "files.sha256"
            )
        )

    def fingerprint(self):
        return {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_ino) for p in self.physical}

    def api(self, operation, revision="-", *, fault="", mode="kill", media=None):
        result = subprocess.run(
            [
                "sh",
                (media or self.tools) / "backend.sh",
                "api",
                revision,
                operation,
                "settings" if operation == "status" else "-",
                "-",
                "-",
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
                "INITIAL_FAULT": fault,
                "INITIAL_MODE": mode,
            },
            timeout=20,
        )
        reply = None
        if result.stdout:
            try:
                reply = json.loads(result.stdout)
            except json.JSONDecodeError:
                # The existing originals pipeline can emit both its child and
                # parent error. Preserve raw stdout; metadata must parse exactly.
                if result.returncode == 0:
                    raise
        return result, reply

    def metadata(self):
        result, reply = self.api("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return reply

    def popup(self, reply, expected="fresh"):
        result = subprocess.run(
            ["node", ROOT / "tests/fixtures/usb-metadata.js", ASSETS, expected],
            input=json.dumps(reply),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_child_cut_keeps_install_actionable(self):
        self.popup(self.metadata())
        result, _ = self.api("install", fault="child")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.data.exists(), "initial preparation must remain private")
        self.assertEqual(self.fingerprint(), self.stock)
        self.popup(self.metadata())

    def independent(self):
        fixture = InitialInstall("test_first_child_cut_keeps_install_actionable")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def record(self):
        return (self.data / "record").read_text().strip().split("|")

    def tree(self, folder):
        return {
            str(p.relative_to(folder)): (
                p.read_bytes() if p.is_file() and not p.is_symlink() else None,
                p.lstat().st_mode,
                p.lstat().st_ino,
                p.lstat().st_ctime_ns,
                os.readlink(p) if p.is_symlink() else None,
            )
            for p in folder.rglob("*")
        }

    def replacement(self):
        old = self.tools
        media = self.root / "replacement"
        shutil.copytree(old, media, symlinks=True)
        pointer = self.runtime / "usb-runtime"
        pointer.unlink()
        pointer.symlink_to(media)
        self.tools = media
        shutil.rmtree(old)

    def check_installed(self, baseline=None):
        fields = self.record()
        self.assertEqual(fields[1], "active")
        if baseline:
            self.assertEqual(fields[4], baseline)
        for name, content in self.originals.items():
            self.assertEqual((self.data / "originals" / name).read_bytes(), content)
        self.assertEqual(self.nvram.read_text(), "disable\n")
        self.assertIn(str(self.data / "packages") + "/", self.target.read_text())
        self.assertNotIn(".open-connect-initial-", self.target.read_text())

    def test_initial_cuts_retry_with_replacement_media(self):
        cuts = (
            "child",
            "directories",
            "originals",
            "package",
            "record-file",
            "record-renamed",
            "baseline-record",
            "before-publish",
            "after-publish",
            "composed",
        )
        for cut in cuts:
            with self.subTest(cut=cut):
                f = self.independent()
                result, _ = f.api("install", fault=cut)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(f.fingerprint(), f.stock)
                self.assertNotIn("effect ", f.operations.read_text())
                published = cut in ("after-publish", "composed")
                self.assertEqual(f.data.exists(), published)
                baseline = f.record()[4] if published else None
                saved = f.tree(f.data / "snapshots" / baseline) if baseline else None
                access = set(f.data.glob(".access-*"))
                orphans = {p.name: f.tree(p) for p in f.root.glob(".open-connect-initial-*")}
                self.assertEqual(bool(orphans), not published)
                f.replacement()
                metadata = f.metadata()
                f.popup(metadata)
                self.assertEqual(metadata["retained"], published)
                result, _ = f.api("install", metadata["revision"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                f.check_installed(baseline)
                self.assertEqual(
                    set(f.data.glob(".access-*")), access, "clean only live access work"
                )
                if baseline:
                    self.assertEqual(f.tree(f.data / "snapshots" / baseline), saved)
                for name, tree in orphans.items():
                    self.assertEqual(
                        f.tree(f.root / name), tree, "orphans are never adopted or swept"
                    )

    def test_handled_private_failures_clean_only_this_attempt(self):
        unknown = self.root / ".open-connect-initial-unknown"
        unknown.mkdir(mode=0o700)
        (unknown / "foreign").write_text("preserve this unexplained work\n")
        original = self.tree(unknown)
        for cut in (
            "child",
            "directories",
            "originals",
            "package",
            "record-file",
            "record-renamed",
            "before-publish",
        ):
            with self.subTest(cut=cut):
                result, _ = self.api("install", fault=cut, mode="fail")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.fingerprint(), self.stock)
                self.assertFalse(self.data.exists())
                self.assertEqual(list(self.root.glob(".open-connect-initial-*")), [unknown])
                self.assertEqual(self.tree(unknown), original)
                self.popup(self.metadata())

    def test_parent_flush_failure_requires_a_successful_barrier_on_retry(self):
        result, _ = self.api("install", fault="parent", mode="fail")
        self.assertNotEqual(result.returncode, 0)
        baseline = self.record()[4]
        self.assertEqual(self.fingerprint(), self.stock)
        self.replacement()
        metadata = self.metadata()
        self.popup(metadata)
        result, _ = self.api("install", metadata["revision"], fault="parent", mode="fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.fingerprint(), self.stock)
        self.assertEqual(self.record()[1], "removed")
        self.assertNotIn("effect ", self.operations.read_text())
        result, _ = self.api("install", metadata["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.check_installed(baseline)

    def test_fresh_pending_recovery_requires_durable_record_before_effects(self):
        result, _ = self.api("install", fault="pending-flush", mode="fail")
        self.assertNotEqual(result.returncode, 0)
        fields = self.record()
        self.assertEqual(fields[1], "install")
        self.assertEqual(self.fingerprint(), self.stock)
        self.replacement()
        metadata = self.metadata()
        self.popup(metadata, "pending")
        result, _ = self.api("recover", metadata["revision"], fault="pending-flush", mode="fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), fields)
        self.assertEqual(self.fingerprint(), self.stock)
        self.assertNotIn("effect ", self.operations.read_text())
        result, _ = self.api("recover", metadata["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.check_installed(fields[4])

    def test_retained_baseline_refuses_drift_and_damaged_saved_inputs(self):
        for damage in (
            "nvram",
            "startup",
            "login",
            "login-inode",
            "ssh",
            "selector",
            "snapshot",
            "originals",
            "missing-originals",
        ):
            with self.subTest(damage=damage):
                f = self.independent()
                result, _ = f.api("install", fault="after-publish")
                self.assertNotEqual(result.returncode, 0)
                fields = f.record()
                if damage == "nvram":
                    f.nvram.write_text("enable\n")
                elif damage == "startup":
                    f.target.write_text("unexplained startup\n")
                elif damage == "login":
                    f.login.write_text("unexplained login\n")
                elif damage == "login-inode":
                    moved = f.login.with_suffix(".original")
                    f.login.rename(moved)
                    shutil.copyfile(moved, f.login)
                    f.login.chmod(0o755)
                elif damage == "ssh":
                    f.ssh.write_text("unexplained SSH config\n")
                elif damage == "selector":
                    (f.root / "selector").write_text("unexplained selector\n")
                elif damage == "snapshot":
                    (f.data / "snapshots" / fields[4] / "config").write_text("damaged\n")
                elif damage == "originals":
                    (f.data / "originals/autostart").write_text("damaged original\n")
                else:
                    shutil.rmtree(f.data / "originals")
                physical, saved = f.fingerprint(), f.tree(f.data)
                f.replacement()
                if damage == "snapshot":
                    result, reply = f.api("status")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(reply["error"], "invalid_snapshot")
                    revision = fields[5]
                else:
                    metadata = f.metadata()
                    f.popup(metadata)
                    revision = metadata["revision"]
                result, reply = f.api("install", revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reply["error"], ("state_changed", "originals_changed"))
                self.assertEqual(f.fingerprint(), physical)
                self.assertEqual(f.tree(f.data), saved)
                self.assertNotIn("effect ", f.operations.read_text())

    def test_foreign_canonical_or_damaged_record_is_never_cleaned(self):
        self.data.mkdir(mode=0o700)
        (self.data / "snapshots").mkdir(mode=0o700)
        (self.data / "foreign").write_text("unexplained contents\n")
        (self.data / "link").symlink_to(self.login)
        for record in (None, "damaged OC1\n"):
            if record:
                (self.data / "record").write_text(record)
            saved = self.tree(self.data)
            for operation in ("status", "install", "recover"):
                result, _ = self.api(operation)
                self.assertNotEqual(result.returncode, 0, operation)
                self.assertEqual(self.tree(self.data), saved)
                self.assertEqual(self.fingerprint(), self.stock)

    def test_writer_lock_refuses_parallel_initial_preparation(self):
        with (self.runtime / "lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result, reply = self.api("install")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(reply["error"], "busy")
        self.assertFalse(self.data.exists())
        self.assertFalse(list(self.root.glob(".open-connect-initial-*")))
        self.assertEqual(self.fingerprint(), self.stock)

    def test_mount_guard_preserves_private_tree_including_nested_access_work(self):
        (self.root / "overmount").touch()
        result, _ = self.api("install", fault="record-file", mode="fail")
        self.assertNotEqual(result.returncode, 0)
        private = list(self.root.glob(".open-connect-initial-*"))
        self.assertEqual(len(private), 1)
        self.assertTrue(list(private[0].glob(".access-*/access")))
        saved = self.tree(private[0])
        self.assertFalse(self.data.exists())
        self.assertEqual(self.fingerprint(), self.stock)
        (self.root / "overmount").unlink()
        self.replacement()
        self.popup(self.metadata())
        result, _ = self.api("install")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.check_installed()
        self.assertEqual(self.tree(private[0]), saved)

    def test_distinct_legacy_removed_snapshots_keep_saved_baseline(self):
        result, _ = self.api("install", fault="composed")
        self.assertNotEqual(result.returncode, 0)
        baseline = self.record()[4]
        # A predecessor's removed current can pin more dependencies than base.
        # Remove access fields to exercise its existing verified conversion.
        result = subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; . "$P/state.sh"; . "$P/firmware.sh"; '
                'record_read; snapshot_read "$R_BASE"; '
                'deps=$(mktemp "$D/.legacy-XXXXXX"); dependencies_capture "$R_BACKEND" > "$deps"; '
                'R_CURRENT=$(snapshot_create "$D/snapshots/$R_BASE/autostart" - "$S_NVRAM" "$S_META" "$deps" - ""); '
                'rm "$deps"; record_write',
                "legacy",
                self.data,
                self.tools,
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(self.record()[4], self.record()[5])
        saved = self.tree(self.data / "snapshots" / baseline)
        self.replacement()
        metadata = self.metadata()
        self.popup(metadata)
        result, _ = self.api("install", metadata["revision"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.check_installed(baseline)
        self.assertEqual(self.tree(self.data / "snapshots" / baseline), saved)
