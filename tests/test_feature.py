"""Public feature command: local build semantics and failure preservation."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_connect import cli, feature


class FeatureCLI(unittest.TestCase):
    def fixture(self, root):
        for name in ("pyproject.toml", *feature.SOURCE_FILES):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("fixture")
        firmware = root / "private"
        for name in feature.INPUTS.values():
            p = firmware / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"synthetic")
        return firmware

    def invoke(self, *args):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(["feature", *map(str, args)])
        return rc, json.loads(stdout.getvalue())

    def test_dry_run_no_output_or_device_and_explicit_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            firmware = self.fixture(root)
            out = root / "runs/build"
            with patch.object(feature.subprocess, "run") as run:
                rc, result = self.invoke(
                    "build",
                    "--workspace",
                    root,
                    "--firmware",
                    firmware,
                    "--output",
                    out,
                    "--dry-run",
                )
            self.assertEqual(rc, 0)
            self.assertFalse(out.exists())
            run.assert_not_called()
            self.assertFalse(result["device_operations"])
            self.assertEqual(result["device_state"], "not_observed")
            commands = result["commands"]
            self.assertEqual(
                list(commands), ["pair", "flush", "receiver", "selection", "readiness"]
            )
            self.assertNotIn("--recover-on-timeout", commands["readiness"])

    def test_failed_builder_stops_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            firmware = self.fixture(root)
            out = root / "runs/build"
            with patch.object(
                feature.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 9, b"details", b"actual error"),
            ) as run:
                rc, result = self.invoke(
                    "build", "--workspace", root, "--firmware", firmware, "--output", out
                )
            self.assertEqual(rc, 1)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(result["outcome"], "build_failed")
            self.assertEqual((out / "pair.stderr").read_bytes(), b"actual error")
            self.assertEqual(
                json.loads((out / "build.json").read_text())["stages"][0]["returncode"], 9
            )

    def test_complete_frontdoor_and_changed_artifact_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            firmware = self.fixture(root)
            out = root / "runs/build"
            generation = None

            def run(command, **kwargs):
                nonlocal generation
                folder = Path(command[command.index("--output") + 1])
                folder.mkdir()
                if "--directory" in command:
                    generation = command[command.index("--directory") + 1]
                if folder.name == "payload":
                    (folder / "plan.json").write_text(
                        json.dumps(dict(directory=generation, health=dict(recover_on_timeout=True)))
                    )
                else:
                    (folder / "artifact").write_bytes(b"candidate")
                return subprocess.CompletedProcess(command, 0, b"ok", b"")

            with patch.object(feature.subprocess, "run", side_effect=run) as execute:
                rc, result = self.invoke(
                    "build",
                    "--workspace",
                    root,
                    "--firmware",
                    firmware,
                    "--output",
                    out,
                    "--recover-on-timeout",
                )
            self.assertEqual(rc, 0)
            self.assertEqual(execute.call_count, 5)
            self.assertEqual(result["outcome"], "built_not_installed")
            rc, result = self.invoke("inspect", "--build", out)
            self.assertEqual(rc, 0)
            self.assertEqual(result["device_state"], "not_observed")
            (out / "pair/artifact").write_bytes(b"changed")
            rc, result = self.invoke("inspect", "--build", out)
            self.assertEqual(rc, 2)
            self.assertIn("artifact changed", result["error"])

    def test_prepare_defaults_to_dry_run_and_stale_build_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.fixture(root)
            out = root / "runs/build"
            payload = out / "payload"
            payload.mkdir(parents=True)
            (payload / "plan.json").write_text("{}")
            record = dict(
                schema=1,
                outcome="built_not_installed",
                workspace=str(root),
                payload=str(payload),
                feature="disclaimer",
                firmware=feature.FIRMWARE,
                generation="synthetic",
                recover_on_timeout=False,
                artifacts={"payload/plan.json": feature.sha(payload / "plan.json")},
                source_sha256=feature.sources(root),
            )
            (out / "build.json").write_text(json.dumps(record))
            with patch.object(feature.subprocess, "run") as run:
                rc, result = self.invoke("prepare", "--build", out, "--state", root / "runs/state")
            self.assertEqual(rc, 0)
            self.assertEqual(result["outcome"], "dry_run_not_prepared")
            self.assertFalse((root / "runs/state").exists())
            run.assert_not_called()
            (root / "cmu/startup/ready-receiver.c").write_text("changed")
            with patch.object(feature.subprocess, "run") as run:
                rc, result = self.invoke(
                    "prepare", "--build", out, "--state", root / "runs/state", "--live"
                )
            self.assertEqual(rc, 2)
            self.assertIn("payload producer changed", result["error"])
            run.assert_not_called()

    def test_post_launch_json_or_receipt_error_never_claims_no_device_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.fixture(root)
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "after.json").write_text("not json")
            with patch.object(
                feature.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "operation completed", ""),
            ):
                result, rc = feature.run_device(["synthetic"], root, bundle, "trial", "completed")
            self.assertEqual(rc, 2)
            self.assertEqual(result["outcome"], "incomplete_preserved")
            self.assertTrue(result["device_operations"])
            self.assertEqual(result["device_state"], "unknown")
            bundle = root / "second"
            bundle.mkdir()
            with (
                patch.object(
                    feature.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "operation completed", ""),
                ),
                patch.object(Path, "write_text", side_effect=OSError("disk full")),
                patch.object(feature, "execution_snapshot"),
            ):
                result, rc = feature.run_device(["synthetic"], root, bundle, "disable", "completed")
            self.assertEqual(rc, 2)
            self.assertTrue(result["device_operations"])
            self.assertIn("disk full", result["error"])

    def test_missing_inputs_public_output_and_symlink_refused_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            firmware = self.fixture(root)
            (root / "runs").mkdir()
            (root / "runs/alias").symlink_to(root / "runs", target_is_directory=True)
            for out in (root / "public", root / "runs/alias/output"):
                with patch.object(feature.subprocess, "run") as run:
                    rc, _ = self.invoke(
                        "build", "--workspace", root, "--firmware", firmware, "--output", out
                    )
                self.assertEqual(rc, 2)
                run.assert_not_called()
            (firmware / feature.INPUTS["native"]).unlink()
            with patch.object(feature.subprocess, "run") as run:
                rc, result = self.invoke(
                    "build",
                    "--workspace",
                    root,
                    "--firmware",
                    firmware,
                    "--output",
                    root / "runs/new",
                )
            self.assertEqual(rc, 2)
            self.assertIn("missing private originals", result["error"])
            run.assert_not_called()
            self.assertFalse((root / "runs/new").exists())


if __name__ == "__main__":
    unittest.main()
