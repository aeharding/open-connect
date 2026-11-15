"""Installed package imports must not depend on a bench checkout or private runs."""

import subprocess
import sys
import tempfile
import unittest


class PackageImports(unittest.TestCase):
    def test_all_modules_import_outside_checkout_without_operations(self):
        script = """
from pathlib import Path
from unittest.mock import patch
import importlib
import pkgutil
import open_connect

def forbidden(*args, **kwargs):
    raise AssertionError("import attempted a private read, process or device operation")

with patch("pathlib.Path.read_bytes", forbidden), patch("pathlib.Path.read_text", forbidden), \\
     patch("subprocess.Popen", forbidden), patch("serial.Serial", forbidden):
    names = [m.name for m in pkgutil.walk_packages(open_connect.__path__, open_connect.__name__ + ".")
             if not m.name.endswith(".__main__")]
    for name in names:
        importlib.import_module(name)
assert not list(Path.cwd().iterdir())
print(len(names))
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(int(result.stdout.strip()), 20)


if __name__ == "__main__":
    unittest.main()
