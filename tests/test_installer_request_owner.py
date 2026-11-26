"""Interpreter identity is local to an include; filesystem authority stays fresh."""

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


class RequestOwner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "state"
        self.data.mkdir(mode=0o700)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.stat = shlex.quote(shutil.which("gstat") or shutil.which("stat"))
        self.id = shlex.quote(shutil.which("id"))
        self.owner = f"{os.geteuid()}:{os.getegid()}"
        self.calls = self.root / "id-calls"
        self.command("stat", f'exec {self.stat} "$@"\n')
        self.command("id", 'printf "%s\\n" "$*" >> "$ID_CALLS"\n' + f'exec {self.id} "$@"\n')
        # Only physical paths change. The includes and owner checks stay intact.
        (self.root / "state.sh").write_text(
            (ASSETS / "state.sh")
            .read_text()
            .replace("/tmp/open-connect/boot-id", str(self.root / "boot-id"))
        )
        (self.root / "firmware.sh").write_text(
            (ASSETS / "firmware.sh")
            .read_text()
            .replace("/sys/devices/virtual/block/ffx01", str(self.root / "block"))
        )
        self.boot = "12345678-1234-1234-1234-123456789abc"
        (self.root / "boot-id").symlink_to(self.boot)
        block = self.root / "block"
        (block / "queue").mkdir(parents=True)
        (block / "dev").write_text("253:16\n")
        self.read_ahead = block / "queue/read_ahead_kb"
        self.read_ahead.write_text("4\n")
        self.read_ahead.chmod(0o644)

    def command(self, name, body):
        path = self.tools / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o700)

    def run_shell(self, script, *args, **env):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; P=$1; D=$2; . "$P/state.sh"; . "$P/firmware.sh"\n' + script,
                "owner-test",
                self.root,
                self.data,
                *args,
            ],
            env={
                **os.environ,
                "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
                "ID_CALLS": str(self.calls),
                "request_owner": "0:0",
                **env,
            },
            capture_output=True,
            text=True,
            timeout=5,
        )

    def hashed_folder(self, parent, members):
        manifest = "".join(
            hashlib.sha256(data).hexdigest() + "  " + name + "\n"
            for name, data in sorted(members.items())
        ).encode()
        identity = hashlib.sha256(manifest).hexdigest()
        folder = parent / identity
        folder.mkdir(parents=True, mode=0o700)
        for name, data in {**members, "files.sha256": manifest}.items():
            (folder / name).write_bytes(data)
        return identity

    def selector_snapshot(self, owner):
        selector = b"synthetic selector\n"
        package = self.hashed_folder(self.data / "packages", {"boot-select": selector})
        digest = hashlib.sha256(selector).hexdigest()
        descriptor = f"{digest}|700:{owner}|{package}\n"
        snapshot = self.hashed_folder(
            self.data / "snapshots",
            {
                "autostart": b"synthetic startup\n",
                "config": f"{package}|1|1|disable|755:{self.owner}|1|0|0\n".encode(),
                "dependencies": b"",
                "selector": descriptor.encode(),
            },
        )
        return package, snapshot, descriptor

    @unittest.skipIf(os.geteuid() == 0, "actual nonroot interpreter required")
    def test_nonroot_checks_and_selector_serialization_use_actual_owner(self):
        package, snapshot, descriptor = self.selector_snapshot(self.owner)
        result = self.run_shell(
            'private_dir "$D"; private_dir "$D"\n'
            'test "$(current_boot_id)" = "$3"\n'
            'base_read_ahead; selector_compose "$D" "$4"\n'
            'snapshot_read "$5"; test "$S_SELECTOR_META" = "$6"\n'
            'cat "$D/selector"',
            self.boot,
            package,
            snapshot,
            "700:" + self.owner,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, descriptor)
        self.assertEqual(self.read_ahead.read_text(), "4\n")
        self.assertEqual(self.calls.read_text().splitlines(), ["-u", "-g"])

    def test_wrong_metadata_cannot_be_authorized_by_an_imported_owner(self):
        # Nonroot hosts cannot chown to another owner. Preserve real mode/size
        # and inject only stat's UID:GID, with matching poisoned input.
        self.command(
            "stat",
            f'actual=$({self.stat} "$@") || exit\n'
            'case "$2" in "%a:%u:%g"|"%s:%u:%g")\n'
            'printf "%s:%s\\n" "${actual%%:*}" "$WRONG_OWNER";;\n'
            '*) printf "%s\\n" "$actual";; esac\n',
        )
        for owner in (f"{os.geteuid() + 1}:{os.getegid()}", f"{os.geteuid()}:{os.getegid() + 1}"):
            for script in ('private_dir "$D"', "current_boot_id", "base_read_ahead"):
                with self.subTest(owner=owner, script=script):
                    result = self.run_shell(script, request_owner=owner, WRONG_OWNER=owner)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stdout, "")
        self.assertEqual(self.read_ahead.read_text(), "4\n")

    def test_private_directory_mode_is_reread_after_an_accepted_check(self):
        result = self.run_shell('private_dir "$D"; chmod 755 "$D"; private_dir "$D"')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.data.stat().st_mode & 0o777, 0o755)

    def test_authenticated_selector_with_foreign_owner_is_refused(self):
        owner = f"{os.geteuid() + 1}:{os.getegid()}"
        _, snapshot, descriptor = self.selector_snapshot(owner)
        result = self.run_shell('snapshot_read "$3"', snapshot, request_owner=owner)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((self.data / "snapshots" / snapshot / "selector").read_text(), descriptor)

    def test_reinclude_replaces_tampered_owner_and_recaptures_once(self):
        result = self.run_shell(
            'private_dir "$D"; request_owner=99999:99999\n'
            '. "$P/state.sh"; private_dir "$D"; private_dir "$D"'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text().splitlines(), ["-u", "-g", "-u", "-g"])

    def test_failing_or_malformed_identity_exits_before_caller_continues(self):
        for flag in ("-u", "-g"):
            for output, status in (
                ("", 1),
                ("123", 1),
                ("", 0),
                ("name", 0),
                ("1:2", 0),
                ("12\n34", 0),
                (" 123", 0),
                ("-1", 0),
            ):
                with self.subTest(flag=flag, output=output, status=status):
                    self.command(
                        "id",
                        f'if test "$1" = {shlex.quote(flag)}; then\n'
                        f"printf '%s\\n' {shlex.quote(output)}\n"
                        f'exit {status}\nfi\nexec {self.id} "$@"\n',
                    )
                    result = self.run_shell('printf "caller_continued\\n"')
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stdout, "")

    def test_backend_identity_failure_exits_before_json_error_handler(self):
        self.command("id", 'printf "123\\n"\nexit 1\n')
        result = subprocess.run(
            ["sh", ASSETS / "backend.sh"],
            env={
                **os.environ,
                "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
                "request_owner": self.owner,
            },
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    @unittest.skipIf(os.geteuid() == 0, "actual nonroot interpreter required")
    def test_firmware_root_guard_still_queries_actual_uid(self):
        result = self.run_shell("firmware_guard")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "root_required\n")
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.calls.read_text().splitlines(), ["-u", "-g", "-u"])
