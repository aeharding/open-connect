"""Private validation refuses unsupported inputs before creating any output."""

import re
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
            with self.assertRaisesRegex(ValueError, r"\.\."):
                checker.private_output(root / "nonexistent" / ".." / "link")
            self.assertFalse((root / "destination").exists())
            fresh = root / "fresh-output"
            self.assertEqual(checker.private_output(fresh), fresh.resolve())
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fake_root = base / "repo"
            (fake_root / "tests").mkdir(parents=True)
            real_runs = base / "elsewhere"
            real_runs.mkdir()
            (fake_root / "runs").symlink_to(real_runs)
            with patch.object(checker, "ROOT", fake_root):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    checker.private_output(fake_root / "runs" / "out")
            (fake_root / "runs").unlink()
            (fake_root / "runs").mkdir()
            alias = base / "repo-link"
            alias.symlink_to(fake_root)
            with (
                patch.object(checker, "ROOT", fake_root),
                patch.object(checker, "__file__", str(alias / "tests/check_firmware.py")),
            ):
                self.assertEqual(
                    checker.private_output(alias / "runs" / "fresh"),
                    fake_root / "runs" / "fresh",
                )

    def test_inputs_parses_all_19_root_pins_including_manager_and_lvds(self):
        guard = (ROOT / "cmu/installer/core/oc-guard.c").read_text()
        mgr_dig = re.search(r'oc_manager_digest\[\]="([a-f0-9]{64})"', guard)[1]
        self.assertEqual(
            mgr_dig,
            "1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29",
        )
        names = re.findall(
            r'"([^"]+)"', re.search(r"oc_root_names\[19\]=\{([^}]+)\}", guard, re.S)[1]
        )
        rpaths = re.findall(
            r'"([^"]+)"', re.search(r"oc_root_paths\[19\]=\{([^}]+)\}", guard, re.S)[1]
        )
        self.assertEqual(names[10], "manager.so")
        self.assertEqual(names[18], "lvds-service")
        self.assertEqual(rpaths[10], "/jci/lib/libjciuiamgr.so")
        self.assertEqual(rpaths[18], "/jci/lvds/lvds_service")

        rdig_body = re.search(r"oc_root_digests\[19\]=\{([^}]+)\}", guard, re.S)[1]
        rdigs = [
            lit or mgr_dig
            for lit, _ in re.findall(r'"([a-f0-9]{64})"|\b(oc_manager_digest)\b', rdig_body)
        ]
        self.assertEqual(len(rdigs), 19)
        self.assertEqual(rdigs[10], mgr_dig)
        self.assertEqual(
            rdigs[18],
            "19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb",
        )

        digests = {
            "usr/bin/autostart": re.search(r'oc_orig_autostart_digest="([a-f0-9]{64})"', guard)[1],
        }
        for rp, rd in zip(rpaths, rdigs, strict=True):
            digests[rp.lstrip("/")] = rd
        for _, rel, dig in re.findall(
            r'\{"([^"]+)","([^"]+)","([a-f0-9]{64})"',
            re.search(r"oc_base_pins\[5\]=\{([^;]+)\};", guard, re.S)[1],
        ):
            digests[rel.lstrip("/")] = dig
        for row in (ROOT / "cmu/installer/ui-modules.tsv").read_text().splitlines():
            if row.startswith("vui\t"):
                _, name, _, dig = row.split("\t")
                digests[f"jci/vui/plugins/{name}"] = dig

        with tempfile.TemporaryDirectory() as td:
            fw = Path(td)
            (fw / "jci/gui/framework/js").mkdir(parents=True)
            (fw / "jci/gui/framework/js/Websockets.js").write_bytes(b"ws\n")
            with patch.object(
                checker, "sha", side_effect=lambda p: digests[p.relative_to(fw).as_posix()]
            ):
                paths = checker.inputs(fw)
            self.assertEqual(paths["manager.so"], fw / "jci/lib/libjciuiamgr.so")
            self.assertEqual(paths["lvds-service"], fw / "jci/lvds/lvds_service")
            self.assertEqual(paths["display"], fw / "jci/lvds/lvds_service")
            self.assertEqual(paths["framework"], fw / "jci/gui/framework/js/GuiFramework.js")

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
