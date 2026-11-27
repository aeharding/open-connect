"""Public-key intake and access restoration using real files and SSH key parsers."""

import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(
    shutil.which("ssh-keygen") and shutil.which("clang"), "SSH keygen and Clang required"
)
class InstallerAccess(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.tools = self.root / "tools"
        self.volume = self.root / "sd1"
        self.bin = self.root / "bin"
        self.ssh = self.root / "ssh"
        for path in (self.data, self.tools, self.volume, self.bin, self.ssh):
            path.mkdir(mode=0o700)
        for name in ("keys", "snapshots", "plan"):
            (self.data / name).mkdir(mode=0o700)
        self.mounts = self.root / "mounts"
        self.mounts.write_text(f"/dev/sda1 {self.volume} vfat rw 0 0\n")
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        from tests.host_bins import copy_host_flush

        copy_host_flush(self.tools / "flush")
        self.key = self.root / "owner"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ecdsa", "-b", "256", "-N", "", "-f", self.key],
            check=True,
        )
        self.public = self.key.with_suffix(".pub").read_bytes()
        self.target = self.volume / "open-connect.pub"
        (self.bin / "autostart").write_text("stock startup\n")
        (self.bin / "runlogin").write_text("stock authenticated login\n")
        self.original = b"Port 36000\nAuthorizedKeysFile /config-mfg/authorized_keys /owner/keys.%u\nPasswordAuthentication no\n"
        (self.ssh / "sshd_config").write_bytes(self.original)
        (self.root / "passwd").write_text(
            "cmu:x:0:0:owner:/root:/bin/sh\nuser:x:1000:1000::/:/bin/sh\n"
        )
        # Host fixture substitutes the firmware's parser (qualified separately on
        # the CMU); key validation still runs the real installed ssh-keygen.
        (self.tools / "sshd-check").write_text(
            '#!/bin/sh\ntest "$1" = -t && test "$2" = -f && test -f "$3"\n'
        )
        (self.tools / "sshd-check").chmod(0o700)
        access = (ASSETS / "access.sh").read_text()
        for before, after in {
            "/usr/bin/ssh-keygen": shutil.which("ssh-keygen"),
            "/usr/sbin/sshd": str(self.tools / "sshd-check"),
            "/usr/bin/runlogin": str(self.bin / "runlogin"),
            "/etc/ssh/sshd_config": str(self.ssh / "sshd_config"),
            "/etc/passwd": str(self.root / "passwd"),
            "/proc/mounts": str(self.mounts),
            "/tmp/mnt/sda1": str(self.volume),
        }.items():
            access = access.replace(before, after)
        access = access.replace("/usr/bin", str(self.bin))
        (self.bin / "ssh-keygen").symlink_to(shutil.which("ssh-keygen"))
        (self.tools / "access.sh").write_text(access)
        shutil.copyfile(ASSETS / "console.sh", self.tools / "console.sh")
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}

    def run_shell(self, body):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; . "$3/state.sh"; . "$P/access.sh"\n'
                "uuid() { openssl rand -hex 16; }\n"
                + (ROOT / "tests/fixtures/installer-snapshots.sh").read_text()
                + body,
                "test",
                self.data,
                self.tools,
                ASSETS,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def import_key(self, data):
        self.target.write_bytes(data)
        return self.run_shell("access_key_import")

    def test_import_canonicalizes_crlf_and_comments_and_reuses_verified_key(self):
        parts = self.public.split()
        canonical = b" ".join(parts[:2]) + b"\n"
        result = self.import_key(b" ".join(parts[:2]) + b" a comment\r\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = result.stdout.strip()
        self.assertEqual(identity, hashlib.sha256(canonical).hexdigest())
        self.assertEqual((self.data / "keys" / (identity + ".cmu")).read_bytes(), canonical)
        self.assertEqual(self.import_key(self.public).stdout, result.stdout)
        self.assertEqual(list((self.data / "keys").glob(".new-*")), [])

    def test_private_multiple_optioned_unsupported_and_malformed_keys_are_rejected(self):
        for data in (
            self.key.read_bytes(),
            self.public + self.public,
            b'command="id" ' + self.public,
            b"ssh-ed25519 AAAA\n",
            b"ssh-rsa AAAA\n",
            b"",
            b"x" * 8193,
        ):
            with self.subTest(prefix=data[:30]):
                self.assertNotEqual(self.import_key(data).returncode, 0)
                self.assertEqual(list((self.data / "keys").iterdir()), [])

    def test_reusing_a_key_does_not_accept_a_failed_durability_check(self):
        imported = self.import_key(self.public)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        key = self.data / "keys" / (imported.stdout.strip() + ".cmu")
        original = key.read_bytes()
        real = self.tools / "flush-real"
        (self.tools / "flush").rename(real)
        (self.tools / "flush").write_text(
            '#!/bin/sh\nif test "$1:$2" = '
            + shlex.quote("f:" + str(key))
            + "; then exit 9; fi\nexec "
            + shlex.quote(str(real))
            + ' "$@"\n'
        )
        (self.tools / "flush").chmod(0o700)
        failed = self.import_key(self.public)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("flush_failed", failed.stderr)
        self.assertEqual(key.read_bytes(), original)
        self.assertEqual(list((self.data / "keys").glob(".new-*")), [])

    def test_symlink_and_unmounted_source_are_rejected(self):
        self.target.symlink_to(self.key.with_suffix(".pub"))
        self.assertNotEqual(self.run_shell("access_key_import").returncode, 0)
        self.target.unlink()
        self.target.write_bytes(self.public)
        self.mounts.write_text("")
        self.assertNotEqual(self.run_shell("access_key_import").returncode, 0)

    def test_login_restoration_refuses_one_read_hash_fault_before_publication(self):
        # Keep real access decisions and hashes; isolate the publication boundary
        # from unrelated snapshot validation and physical root operations.
        for fault in ("none", "baseline", "live", "malformed", "failed-valid"):
            with self.subTest(fault=fault):
                result = self.run_shell(
                    r"""
mkdir -p "$D/snapshots/base" "$D/snapshots/before" "$D/snapshots/after"
cp @LOGIN@ "$D/snapshots/base/runlogin"
cp @LOGIN@ "$D/snapshots/before/runlogin"
cp @LOGIN@ "$D/snapshots/after/runlogin"
: > "$D/snapshots/after/access"
R_BASE=base
inode=$(stat -c %i @LOGIN@)
hold=@BIN@/.open-connect-runlogin-$inode
test -e "$hold" || ln @LOGIN@ "$hold"
snapshot_read() { S_LOGIN_INODE=$inode; S_LOGIN_META=$(stat -c '%a:%u:%g' @LOGIN@); }
access_pair_check() { :; }
root_publish() { printf 'published|%s\n' "$7"; return 1; }
snapshot_read base
fault=@FAULT@
sha() {
    if test "$fault" != none && test ! -e "$D/fault-read"; then
        case "$fault:$1" in
            baseline:"$D/snapshots/base/runlogin"|live:@LOGIN@|malformed:"$D/snapshots/base/runlogin"|failed-valid:"$D/snapshots/base/runlogin")
                : > "$D/fault-read"
                case "$fault" in
                    malformed) printf 'invalid\n'; return 0;;
                    failed-valid) "$P/flush" h "$1";;
                esac
                return 19;;
        esac
    fi
    "$P/flush" h "$1"
}
if test "$fault" = live; then
    access_login_check_loaded
else
    access_pair_apply before after
fi
""".replace("@LOGIN@", shlex.quote(str(self.bin / "runlogin")))
                    .replace("@BIN@", shlex.quote(str(self.bin)))
                    .replace("@FAULT@", shlex.quote(fault))
                )
                self.assertNotEqual(result.returncode, 0)
                if fault == "none":
                    self.assertEqual(result.stdout, "published|restore\n")
                else:
                    self.assertEqual(result.stdout, "")
                    self.assertTrue((self.data / "fault-read").exists())
                (self.data / "fault-read").unlink(missing_ok=True)

    def test_snapshot_preserves_existing_authorization_and_rejects_later_edits(self):
        self.target.write_bytes(self.public)
        script = r"""
key=$(access_key_import)
access_capture "$D/plan" 0 0 -
: > "$D/dependencies"
R_BASE=$(fixture_snapshot "$4" - 0 0 absent "755:$(id -u):$(id -g)" "$D/dependencies" "$D/plan")
access_compose "$D/plan" 1 1 "$key"
snapshot=$(fixture_snapshot "$4" - 0 0 absent "755:$(id -u):$(id -g)" "$D/dependencies" "$D/plan")
snapshot_read "$snapshot"
test "$S_SSH:$S_KEY" = "1:$key"
printf '%s\n' "$snapshot"
"""
        # The fourth argument to this one driver is the startup input.
        script = script.replace('"$4"', '"' + str(self.bin / "autostart") + '"')
        result = self.run_shell(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshot = self.data / "snapshots" / result.stdout.strip()
        candidate = (snapshot / "sshd.conf").read_bytes()
        self.assertIn(
            b"/config-mfg/authorized_keys /owner/keys.%u /data_persist/open-connect/keys/",
            candidate,
        )
        self.assertTrue(candidate.endswith(b"PasswordAuthentication no\n"))
        self.assertEqual((snapshot / "runlogin").read_bytes(), (ASSETS / "console.sh").read_bytes())
        self.assertEqual((self.ssh / "sshd_config").read_bytes(), self.original)
        (snapshot / "runlogin").write_text("later edit\n")
        self.assertNotEqual(self.run_shell(f'snapshot_read "{snapshot.name}"').returncode, 0)

    def test_interrupted_ssh_change_recovers_and_uninstall_restores_originals(self):
        self.target.write_bytes(self.public)
        opened_login = (self.bin / "runlogin").open("rb")
        self.addCleanup(opened_login.close)
        original_inode = os.fstat(opened_login.fileno()).st_ino
        firmware = (ASSETS / "firmware.sh").read_text()
        firmware = firmware.replace("/usr/bin", str(self.bin)).replace("/etc/ssh", str(self.ssh))
        firmware = firmware.replace("root_publish() (", "root_publish_real() (")
        (self.tools / "firmware.sh").write_text(firmware)
        prefix = r"""
AUTOSTART=STARTUP
. "$P/firmware.sh"
. "$3/transaction.sh"
root_mode() { cat "$D/mount"; }
remount() { printf '%s,noatime\n' "$1" > "$D/mount"; }
nvram_read() { cat "$D/nvram"; }
nvram_change() { test "$(nvram_read)" = "$1"; printf '%s\n' "$2" > "$D/nvram"; }
root_publish() {
    root_publish_real "$@"
    if test "${CUT:-}:$1" = "ssh:SSHD"; then kill -KILL $$; fi
}
""".replace("STARTUP", str(self.bin / "autostart")).replace("SSHD", str(self.ssh / "sshd_config"))
        from tests.test_installer_transaction import fixture_package

        fixture_package(self.data, self.tools)
        for name in ("preferences.awk", "services.tsv"):
            shutil.copyfile(ASSETS / name, self.tools / name)
        initialize = r"""
printf 'ro,noatime\n' > "$D/mount"; printf 'absent\n' > "$D/nvram"
key=$(access_key_import)
access_capture "$D/plan" 0 0 -
: > "$D/dependencies"
R_BASE=$(fixture_snapshot "$AUTOSTART" - 0 0 absent "$(stat -c '%a:%u:%g' "$AUTOSTART")" "$D/dependencies" "$D/plan")
R_BACKEND=$(cat "$D/package-id")
R_PHASE=removed; R_CURRENT=$R_BASE; R_BEFORE=-; R_AFTER=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-
record_write
access_compose "$D/plan" 1 1 "$key"
printf 'installed startup\n' > "$D/installed"
mkdir -p "$D/composed/$R_BACKEND"
cp "$D/installed" "$D/composed/$R_BACKEND/autostart"
after=$(fixture_snapshot "$D/installed" "$R_BACKEND" 0 0 absent "$(stat -c '%a:%u:%g' "$AUTOSTART")" "$D/dependencies" "$D/plan")
transaction_prepare install "$R_CURRENT" "$after"
CUT=ssh
transaction_reconcile
"""
        interrupted = self.run_shell(prefix + initialize)
        self.assertNotEqual(interrupted.returncode, 0, interrupted.stderr)
        self.assertNotEqual((self.ssh / "sshd_config").read_bytes(), self.original)
        # Linux 3.x refuses a read-only remount while an open file has no
        # pathname. Preserve the reader's inode throughout the change.
        self.assertGreater(os.fstat(opened_login.fileno()).st_nlink, 0)
        recovered = self.run_shell(
            prefix + 'record_read; transaction_reconcile; targets_match "$R_CURRENT"'
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual((self.data / "record").read_text().split("|")[1], "active")
        # A later edit must be preserved, even when the other targets still match.
        self.assertEqual((self.data / "mount").read_text(), "ro,noatime\n")
        enabled = (self.ssh / "sshd_config").read_bytes()
        (self.ssh / "sshd_config").write_bytes(enabled + b"# owner's later edit\n")
        refused = self.run_shell(
            prefix + 'record_read; transaction_prepare uninstall "$R_CURRENT" "$R_BASE"'
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertTrue((self.ssh / "sshd_config").read_bytes().endswith(b"# owner's later edit\n"))
        (self.ssh / "sshd_config").write_bytes(enabled)
        restored = self.run_shell(
            prefix
            + r"""
record_read
transaction_prepare uninstall "$R_CURRENT" "$R_BASE"
transaction_reconcile
targets_match "$R_CURRENT"
"""
        )
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual((self.ssh / "sshd_config").read_bytes(), self.original)
        self.assertEqual((self.bin / "runlogin").read_text(), "stock authenticated login\n")
        self.assertEqual((self.bin / "runlogin").stat().st_ino, original_inode)
        self.assertGreater(os.fstat(opened_login.fileno()).st_nlink, 0)
        self.assertEqual(list(self.bin.glob(".open-connect-runlogin-*")), [])
        self.assertEqual((self.bin / "autostart").read_text(), "stock startup\n")
