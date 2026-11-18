"""Check the authored browser client against its actual POST contract."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerRuntime(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_requests_recovery_and_unknown_acknowledgements(self):
        subprocess.run(
            [
                "node",
                ROOT / "tests/fixtures/installer-runtime.js",
                ROOT / "cmu/installer/runtime.js",
            ],
            check=True,
        )
