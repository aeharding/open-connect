"""Public import and hardware-boundary regression checks; no device access."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import bench
import boot
import linked

ROOT = Path(__file__).resolve().parents[2]


class ImportBoundaries(unittest.TestCase):
    def test_public_modules_import_without_private_inputs_or_historical_profiles(self):
        code = """
import sys
from pathlib import Path
from unittest.mock import patch
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "experiments" / sys.argv[2]))
read_bytes = Path.read_bytes
def guarded_read(path):
    if path.is_relative_to(root / "runs") or path.name.endswith(".json"):
        raise AssertionError("import read a private input or execution profile: " + str(path))
    return read_bytes(path)
with patch.object(Path, "read_bytes", guarded_read):
    import boot
    print("imported without profile/input reads")
"""
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, OC_NATIVE_PROFILE=tmp + "/absent.json", OC_RUN=tmp + "/absent")
            for directory in ("mapped-publication", "intro-handoff"):
                with self.subTest(directory=directory):
                    result = subprocess.run(
                        [sys.executable, "-I", "-c", code, str(ROOT), directory],
                        cwd=tmp, env=env, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_command_rejects_unqualified_profile_before_bundle_or_hardware(self):
        with patch.object(bench.rt, "verify_dependencies", side_effect=ValueError("stale")) as gate, \
             patch.object(bench, "Bundle") as bundle, \
             patch.object(bench, "AdapterLock") as lock, \
             patch.object(bench, "open_adapter") as adapter:
            with self.assertRaisesRegex(ValueError, "not qualified"):
                bench.command("true", "unused")
            gate.assert_called_once_with()
            bundle.assert_not_called()
            lock.assert_not_called()
            adapter.assert_not_called()

    def test_restart_rejects_unqualified_profile_before_credentials_or_hardware(self):
        with patch.object(bench.rt, "verify_dependencies", side_effect=ValueError("stale")) as gate, \
             patch.object(boot.stock, "private_credentials") as credentials, \
             patch.object(boot.stock, "Bundle") as bundle, \
             patch.object(boot.stock, "Video") as video, \
             patch.object(boot.stock, "open_adapter") as adapter:
            with self.assertRaisesRegex(ValueError, "not qualified"):
                boot.observe(None, None, None)
            gate.assert_called_once_with()
            credentials.assert_not_called()
            bundle.assert_not_called()
            video.assert_not_called()
            adapter.assert_not_called()

    def test_feature_inputs_are_validated_only_when_requested(self):
        with patch.object(linked, "SOURCE", Path("/nonexistent/oc-profile.json")):
            with self.assertRaises(ValueError):
                linked.feature()


if __name__ == "__main__":
    unittest.main()
