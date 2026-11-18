"""Durable record and immutable backup checks on real local files."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "state"
        self.data.mkdir(mode=0o700)
        (self.data / "snapshots").mkdir(mode=0o700)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                str(ROOT / "cmu/startup/flush.c"),
                "-o",
                str(self.tools / "flush"),
            ],
            check=True,
        )
        (self.root / "autostart").write_text("original startup\n")
        self.driver = self.root / "driver.sh"
        self.driver.write_text(
            "set -eu\numask 077\n"
            'D=$1; P=$2; . "$3"\n'
            "uuid() { openssl rand -hex 16; }\n"
            'case "$4" in\n'
            'create) base=$(snapshot_create "$5" - 0 0 absent "755:$(id -u):$(id -g)")\n'
            'R_PHASE=removed; R_BACKEND=$(printf "%064d" 0); R_BASE=$base; R_CURRENT=$base\n'
            "R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-\n"
            "record_write;;\n"
            'read) record_read && snapshot_read "$R_CURRENT";;\n'
            "change) record_read; R_BUDGET=3; record_write;;\n"
            "esac\n"
        )
        self.assertEqual(self.run_command("create").returncode, 0)

    def run_command(self, action):
        return subprocess.run(
            [
                "sh",
                self.driver,
                self.data,
                self.tools,
                ROOT / "cmu/installer/state.sh",
                action,
                self.root / "autostart",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )

    def test_original_backup_changes_are_rejected(self):
        self.assertEqual(self.run_command("read").returncode, 0)
        snapshot = next((self.data / "snapshots").iterdir())
        (snapshot / "autostart").write_text("later change\n")
        self.assertNotEqual(self.run_command("read").returncode, 0)
        self.assertEqual((snapshot / "autostart").read_text(), "later change\n")

    def test_missing_or_invalid_record_never_selects_state(self):
        record = self.data / "record"
        original = record.read_bytes()
        for invalid in (
            b"",
            original[:-5],
            original + original,
            original.replace(b"|removed|", b"|unknown|"),
        ):
            record.write_bytes(invalid)
            self.assertNotEqual(self.run_command("read").returncode, 0)
            self.assertEqual(record.read_bytes(), invalid)

    def test_flush_failure_preserves_an_entire_old_or_new_record(self):
        record = self.data / "record"
        old = record.read_bytes()
        real_flush = self.tools / "real-flush"
        (self.tools / "flush").rename(real_flush)
        for failure, expected_budget in (("f", "0"), ("d", "3")):
            record.write_bytes(old)
            (self.tools / "flush").write_text(
                '#!/bin/sh\nif [ "$1" = '
                + failure
                + " ]; then exit 5; fi\n"
                + 'exec "'
                + str(real_flush)
                + '" "$@"\n'
            )
            (self.tools / "flush").chmod(0o700)
            result = self.run_command("change")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("flush_failed", result.stderr)
            self.assertEqual(self.run_command("read").returncode, 0)
            self.assertEqual(record.read_text().split("|")[9], expected_budget)
