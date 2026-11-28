"""Private validation refuses unsupported inputs before creating any output."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import check_firmware as checker

ROOT = Path(__file__).resolve().parents[1]


class FirmwareCheck(unittest.TestCase):
    def test_missing_and_unknown_originals_leave_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = ROOT / "runs/firmware-check-must-not-be-created"
            self.assertFalse(output.exists())
            for unknown in (False, True):
                if unknown:
                    source = root / "usr/bin/autostart"
                    source.parent.mkdir(parents=True)
                    source.write_bytes(b"unknown firmware")
                result = subprocess.run(
                    [
                        sys.executable,
                        ROOT / "tests/check_firmware.py",
                        "--firmware",
                        root,
                        "--output",
                        output,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("checks not run", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_public_and_symlink_output_refused(self):
        with self.assertRaisesRegex(ValueError, "below"):
            checker.private_output(ROOT / "should-not-exist")
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            root = Path(directory)
            (root / "link").symlink_to(root / "destination")
            with self.assertRaisesRegex(ValueError, "symlink"):
                checker.private_output(root / "link")
            self.assertFalse((root / "destination").exists())
            fresh = root / "fresh-output"
            self.assertEqual(checker.private_output(fresh), fresh.resolve())

    def test_explicit_tools_and_linux_discovery_do_not_require_xcode(self):
        with (
            patch.object(checker.sys, "platform", "linux"),
            patch.object(checker.subprocess, "run") as run,
        ):
            self.assertTrue(Path(checker.tool("clang", sys.executable)).is_file())
            with patch.object(checker.shutil, "which", return_value=None):
                with self.assertRaisesRegex(ValueError, "missing executable"):
                    checker.tool("clang")
            run.assert_not_called()
