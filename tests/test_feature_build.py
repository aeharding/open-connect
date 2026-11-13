"""Public build entry points: no OEM inputs, toolchain or hardware required."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "experiments/disclaimer-native"
INTRO = ROOT / "experiments/intro-handoff"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FeatureBuild(unittest.TestCase):
    def test_missing_inputs_are_actionable_and_write_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            absent = Path(directory) / "missing"
            output = ROOT / "runs" / "must-not-be-created-by-missing-input"
            self.assertFalse(output.exists())
            commands = [
                [NATIVE / "build.py", "--original", absent],
                [NATIVE / "check.py", "--original", absent],
                [INTRO / "patch.py", "--original", absent],
                [
                    INTRO / "check.py",
                    "--native-original",
                    absent,
                    "--system-app",
                    absent,
                    "--base-app",
                    absent,
                ],
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, *map(str, command), "--output", str(output)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("missing", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(output.exists())

    def test_tool_override_and_linux_discovery_do_not_require_xcode(self):
        builder = load("_test_native_builder", NATIVE / "build.py")
        with (
            patch.object(builder.sys, "platform", "linux"),
            patch.object(builder.subprocess, "run") as run,
        ):
            self.assertEqual(
                builder.tool("clang", sys.executable), str(Path(sys.executable).absolute())
            )
            with patch.object(builder.shutil, "which", return_value=None):
                with self.assertRaisesRegex(builder.Rejected, "missing executable"):
                    builder.tool("clang")
            with tempfile.TemporaryDirectory() as directory:
                shim = Path(directory) / "node"
                shim.symlink_to(sys.executable)
                self.assertEqual(builder.tool("node", shim), str(shim))
            run.assert_not_called()

    def test_unknown_js_input_and_public_output_refused_before_writes(self):
        builder = load("_test_intro_builder", INTRO / "patch.py")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "systemApp.js"
            source.write_bytes(b"unknown firmware")
            output = ROOT / "runs" / "must-not-be-created-by-unknown-input"
            with self.assertRaisesRegex(ValueError, "unsupported exact"):
                builder.build(output, source)
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, "private output"):
                builder.build(ROOT / "candidate", source)
            self.assertFalse((ROOT / "candidate").exists())


if __name__ == "__main__":
    unittest.main()
