"""Run the actual USB entry against local files before its session handoff."""

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "cmu/installer/run.sh"


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL required")
class InstallerUSBEntry(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "media/open-connect"
        self.source.mkdir(parents=True)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        stat = shutil.which("gstat") or shutil.which("stat")
        if not stat:
            self.skipTest("GNU stat required")
        if subprocess.run([stat, "--version"], capture_output=True, timeout=3).returncode:
            self.skipTest("GNU stat required")
        (self.tools / "stat").symlink_to(stat)
        # A local descriptor lock: the entry, not this child, retains the open
        # description. No bench process, mount or global lock is touched.
        (self.tools / "flock").write_text(
            "#!" + sys.executable + "\nimport fcntl,sys\n"
            "fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
        )
        (self.tools / "flock").chmod(0o700)
        (self.tools / "logger").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >&2\n')
        (self.tools / "logger").chmod(0o700)
        (self.root / "version.ini").write_text(
            'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
        )
        self.members = {
            "session.sh": b"authored session fixture\n",
            "api": b"authored API fixture\n",
            "flush": b"authored flush fixture\n",
            "install-only.bin": bytes(range(256)) * 31,
        }
        for name, content in self.members.items():
            (self.source / name).write_bytes(content)
        self.manifest()
        entry = ENTRY.read_text()
        entry = entry.replace("PATH=/sbin:/bin:/usr/sbin:/usr/bin", ": # host PATH")
        entry = entry.replace("= 0 || refuse privileges", f"= {os.getuid()} || refuse privileges")
        entry = entry.replace("/jci/version.ini", str(self.root / "version.ini"))
        entry = entry.replace("/tmp/mnt/sd[a-d]1/open-connect", str(self.source))
        entry = entry.replace("/tmp/open-connect-usb.lock", str(self.root / "lock"))
        entry = entry.replace("/tmp/oc-usb-XXXXXX", str(self.root / "oc-usb-XXXXXX"))
        launch = 'sh "$work/session.sh" "$work" "$source" </dev/null >/dev/null 2>&1 &'
        self.assertEqual(entry.count(launch), 1)
        entry = entry.replace(launch, 'printf "%s\\n" "$work" > "$FIXTURE_STAGE"')
        self.driver = self.source / "entry-fixture.sh"
        self.driver.write_text(entry)
        self.stage = self.root / "stage"
        self.env = {
            **os.environ,
            "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
            "FIXTURE_STAGE": str(self.stage),
        }

    def manifest(self):
        (self.source / "files.sha256").write_text(
            "".join(
                hashlib.sha256((self.source / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in sorted(self.members)
            )
        )

    def entry(self):
        return subprocess.run(
            ["sh", self.driver], capture_output=True, text=True, env=self.env, timeout=15
        )

    def refused(self):
        result = self.entry()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.stage.exists(), "refusal must precede the session handoff")
        self.assertEqual(list(self.root.glob("oc-usb-*")), [], "owned partial staging must retire")
        return result

    def test_complete_verified_packet_survives_media_removal(self):
        (self.source / "install-only.bin").chmod(0o777)
        self.manifest()
        result = self.entry()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        staged = Path(self.stage.read_text().strip())
        self.assertEqual(staged.stat().st_mode & 0o777, 0o700)
        expected = dict(self.members)
        expected["files.sha256"] = (self.source / "files.sha256").read_bytes()
        shutil.rmtree(self.source)
        self.assertEqual({path.name for path in staged.iterdir()}, set(expected))
        for name, content in expected.items():
            self.assertEqual((staged / name).read_bytes(), content)
            self.assertEqual(
                (staged / name).stat().st_mode & 0o777, 0o700 if name in ("api", "flush") else 0o600
            )

    def test_changed_install_only_bytes_never_launch(self):
        (self.source / "install-only.bin").write_bytes(b"changed after manifest\n")
        self.refused()

    def test_dot_members_never_reach_consumers_that_cannot_retire_them(self):
        for name in (".hidden", "..hidden"):
            with self.subTest(name=name):
                self.members[name] = b"unsupported hidden member\n"
                (self.source / name).write_bytes(self.members[name])
                self.manifest()
                self.refused()
                del self.members[name]
                (self.source / name).unlink()

    def test_unreadable_or_missing_member_never_launches(self):
        (self.source / "install-only.bin").unlink()
        self.refused()

    def test_symlink_member_and_manifest_never_launch(self):
        member = self.source / "install-only.bin"
        member.rename(self.root / "external")
        member.symlink_to(self.root / "external")
        self.refused()
        member.unlink()
        shutil.copyfile(self.root / "external", member)
        manifest = self.source / "files.sha256"
        manifest.rename(self.root / "manifest")
        manifest.symlink_to(self.root / "manifest")
        self.refused()

    def test_duplicate_unsafe_and_self_manifest_names_never_launch(self):
        manifest = self.source / "files.sha256"
        original = manifest.read_text()
        for line in (
            original.splitlines()[0],
            "a" * 64 + "  ../external",
            "a" * 64 + "  files.sha256",
            "g" * 64 + "  extra.bin",
            "a" * 64 + "  extra.bin unexpected",
        ):
            with self.subTest(line=line):
                manifest.write_text(original + line + "\n")
                self.refused()

    def test_size_and_count_limits_precede_handoff(self):
        member = self.source / "install-only.bin"
        member.write_bytes(b"x" * 2097152)
        self.manifest()
        self.refused()
        member.write_bytes(self.members[member.name])
        for number in range(61):
            name = f"extra-{number}.bin"
            self.members[name] = b"extra\n"
            (self.source / name).write_bytes(self.members[name])
        self.manifest()
        self.refused()

    def test_absent_required_session_program_never_launches(self):
        del self.members["session.sh"]
        (self.source / "session.sh").unlink()
        self.manifest()
        self.refused()

    def test_failed_or_incomplete_size_pass_never_launches(self):
        stat = self.tools / "stat"
        stat.unlink()
        for command in (
            "exit 1",
            "printf '1\\n'",
            "printf '1\\n1\\ninvalid\\n1\\n'",
            "printf '1\\n1\\n1\\n1\\n'; exit 1",
        ):
            with self.subTest(command=command):
                stat.write_text("#!/bin/sh\n" + command + "\n")
                stat.chmod(0o700)
                self.refused()

    def test_failed_or_mismatched_digest_pass_never_launches(self):
        openssl = self.tools / "openssl"
        real = shlex.quote(shutil.which("openssl"))
        for command in (
            "exit 1",
            "printf 'incomplete digest output\\n'",
            real + ' "$@"; exit 1',
            real + " \"$@\" | awk '{line[NR]=$0} END{for(i=NR;i>0;i--)print line[i]}'",
        ):
            with self.subTest(command=command):
                openssl.write_text("#!/bin/sh\n" + command + "\n")
                openssl.chmod(0o700)
                self.refused()

    def test_unterminated_manifest_never_reaches_newline_only_consumers(self):
        name = "z-last.bin"
        self.members[name] = b"last row without newline\n"
        (self.source / name).write_bytes(self.members[name])
        self.manifest()
        manifest = self.source / "files.sha256"
        manifest.write_bytes(manifest.read_bytes().rstrip(b"\n"))
        self.refused()

    def test_bad_unterminated_last_row_never_launches(self):
        manifest = self.source / "files.sha256"
        original = manifest.read_text()
        for row in ("a" * 64 + "  z-last.bin", "invalid final record"):
            with self.subTest(row=row):
                (self.source / "z-last.bin").write_bytes(b"mismatched digest\n")
                manifest.write_text(original + row)
                self.refused()

    def test_partial_copy_failure_retires_only_owned_stage(self):
        sentinel = self.root / "oc-usb-unowned"
        sentinel.mkdir()
        (sentinel / "keep").write_bytes(b"unrelated\n")
        real = shlex.quote(shutil.which("cp"))
        (self.tools / "cp").write_text(
            "#!/bin/sh\n"
            'case "$1" in *files.sha256) exec ' + real + ' "$@";; esac\n'
            'for destination in "$@"; do :; done\n'
            'if test -d "$destination"; then destination="$destination/.partial"; fi\n'
            'printf partial > "$destination"\nexit 1\n'
        )
        (self.tools / "cp").chmod(0o700)
        result = self.entry()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.stage.exists())
        self.assertEqual(list(self.root.glob("oc-usb-*")), [sentinel])
        self.assertEqual((sentinel / "keep").read_bytes(), b"unrelated\n")
