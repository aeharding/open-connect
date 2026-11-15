"""Developer workflow contracts; no hardware, credentials or OEM inputs."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from open_connect.device import feature_state as d
from open_connect.device import feature_workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.generation = "/tmp/mnt/data_persist/oc-boot-" + "a" * 32
        self.oldR, self.oldD = d.R, d.D
        d.R, d.D = self.root, self.generation
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.restore)
        d.save(
            "publication.json",
            dict(directory=self.generation, body=dict(md5="0" * 32, crc=1, bytes=4)),
        )
        d.save("code.json", dict(identity="45826:30:1:4:600:0:0:1", directory="45826:29:700:0:0"))
        self.sources = {"/jci/mmui/uia/libjciuiasystem.so": "64785:10:1:100:755:1018:3015:1"}
        d.save("source-identities.json", self.sources)
        d.save("artifact-identities.json", {"uia.so": "45826:20:1:100:600:0:0:1"})
        d.save(
            "runtime-baseline.json",
            dict(
                MMUI="/jci/sm/sm_svclauncher|-l|jciMMUI|/jci/mmui/svcjcimmui.so|-a|inputs|",
                OPERA="/jci/opera/opera|-u|/jci/gui/index.html|",
            ),
        )

    def restore(self):
        d.R, d.D = self.oldR, self.oldD

    def raw(self, selected=False, hook=True, health_boot=None):
        boot = "11111111-1111-1111-1111-111111111111"
        g = self.generation
        values = dict(
            SELECTOR="spent" if selected else "armed",
            BOOT=boot,
            UPTIME="80.00 100.00",
            SM="/jci/sm/sm|-f|"
            + (g + "/generation.conf" if selected else "/jci/sm/sm.conf")
            + "|-e|/tmp/smevents.txt|",
            MMUI="/jci/sm/sm_svclauncher|-l|jciMMUI|"
            + (g + "/mmui.so" if selected else "/jci/mmui/svcjcimmui.so")
            + "|-a|inputs|",
            OPERA="/jci/opera/opera|-u|"
            + (g + "/index.html" if selected else "/jci/gui/index.html")
            + "|",
            NATIVE_MAP="3:"
            + ("20:" + g + "/uia.so" if selected else "10:/jci/mmui/uia/libjciuiasystem.so")
            + ":1",
            HEALTH="ready|0" if selected else "absent",
            HEALTH_BOOT=health_boot or boot,
        )
        rows = ["OCSTATE|" + k + "|" + v for k, v in values.items()]
        rows += ["OCGEN_SOURCE|" + k + "|" + v for k, v in self.sources.items()]
        rows += [
            "OCLINK|VERIFY|"
            + ("C|candidate" if hook else "O|restored")
            + "|64785:99:1:100:775:1018:3015:2|ro,noatime|writes=0"
        ]
        return ("\n" + "\n".join(rows) + "\n").encode()

    def test_status_distinguishes_disk_hook_loaded_code_and_current_health(self):
        value = d.parse_status(0, self.raw(selected=False, hook=True))
        self.assertTrue(value["installed_hook"])
        self.assertEqual(value["loaded"], "baseline")
        self.assertFalse(value["home_acknowledged"])
        value = d.parse_status(0, self.raw(selected=True, hook=False))
        self.assertFalse(value["installed_hook"])
        self.assertEqual(value["loaded"], "selected")
        self.assertTrue(value["home_acknowledged"])
        value = d.parse_status(0, self.raw(selected=True, health_boot="old"))
        self.assertFalse(value["home_acknowledged"])
        value = d.parse_status(0, self.raw(selected=True).replace(b":20:", b":21:"))
        self.assertEqual(value["loaded"], "unknown")
        self.assertFalse(value["home_acknowledged"])

    def test_status_script_fits_actual_transport_and_undo_omits_optional_file_guards(self):
        from open_connect.session import wrap_command

        names = (
            "generation.conf",
            "mmui.so",
            "mmui.xml",
            "index.html",
            "system-app.js",
            "uia.so",
            "ready-receiver",
            "ready-watch.sh",
        )
        d.save(
            "run.json",
            dict(artifacts={n: dict(md5="0" * 32, crc=1, bytes=100) for n in (*names, "armed")}),
        )
        d.save("artifact-identities.json", {n: "45826:20:1:100:600:0:0:1" for n in names})
        full = d.status_script()
        wrap_command(full, "a" * 32)
        commands = d.status_commands()
        self.assertEqual(full, "\n".join(commands))
        self.assertLessEqual(len(commands), 24)
        for c in commands:
            self.assertLess(len(wrap_command(c, "a" * 32)), 3000)
        self.assertIn("test -f", full)
        recovery = d.status_script(check_artifacts=False)
        self.assertNotIn("p=" + self.generation + "/uia.so", recovery)
        self.assertIn("recovery.sh", recovery)
        wrap_command(recovery, "b" * 32)

    def test_cancellation_needs_no_candidate_or_local_build_files(self):
        with patch.object(d, "command") as command:
            w.cancel_watcher()
        script = command.call_args.args[0]
        self.assertNotIn("ready-watch.sh", script)
        self.assertNotIn("recovery.sh", script)
        self.assertIn("decision.lock", script)
        self.assertIn("reboot-requested", script)
        self.assertIn(': > "$w/cancelled"', script)

    def test_known_unsent_observer_failure_remains_retryable_but_missing_receipt_does_not(self):

        bundle = self.root / "failed"
        bundle.mkdir()
        (bundle / "manifest.json").write_text(json.dumps(dict(outcome="failed_before_request")))
        args = SimpleNamespace(action="disable", bundle=bundle)
        run = dict(phase="baseline_requested")
        w.record_observer_outcome(run, args, 2, "unused")
        self.assertEqual(run["phase"], "restored_pending_baseline")
        (bundle / "manifest.json").unlink()
        run = dict(phase="baseline_requested")
        w.record_observer_outcome(run, args, 2, "unused")
        self.assertEqual(run["phase"], "baseline_requested")

    def test_selected_request_refuses_spent_or_restored_state(self):

        args = SimpleNamespace(
            action="trial",
            bundle=self.root / "boot",
            credentials=Path("unused"),
            owner="test",
            camera_index=0,
        )
        for raw in (
            self.raw(hook=False),
            self.raw().replace(b"SELECTOR|armed", b"SELECTOR|spent"),
            self.raw().replace(b"SELECTOR|armed", b"SELECTOR|invalid"),
        ):

            def before_only(argv, **kwargs):
                kwargs["check_result"](0, raw)
                self.fail("invalid pre-request state accepted")

            with (
                patch.object(d, "status_commands", return_value=["synthetic read"]),
                patch.object(w.stock, "main", side_effect=before_only),
            ):
                with self.assertRaisesRegex(ValueError, "unused armed"):
                    w.observe(args, "selected")

    def test_status_rejects_duplicate_source_and_rw(self):
        for raw in (
            self.raw() + b"OCSTATE|BOOT|extra\n",
            self.raw() + b"OCGEN_SOURCE|/jci/mmui/uia/libjciuiasystem.so|extra\n",
            self.raw().replace(b"ro,noatime", b"rw,noatime"),
        ):
            with self.assertRaises(ValueError):
                d.parse_status(0, raw)

    def test_incomplete_prior_baseline_does_not_request_another_reboot(self):
        run = dict(phase="baseline_requested")
        args = [
            "disable",
            "--state",
            str(self.root),
            "--owner",
            "test",
            "--bundle",
            str(self.root / "observation"),
            "--credentials",
            "unused",
            "--camera-index",
            "0",
        ]
        with (
            patch.object(d, "status_script", return_value="synthetic read"),
            patch.object(d, "load_existing", return_value=run),
            patch.object(w.stock, "private_credentials"),
            patch.object(d, "command", return_value=self.raw(selected=True, hook=False)),
            patch.object(w, "observe") as observe,
            patch.object(d, "action") as action,
        ):
            with self.assertRaisesRegex(ValueError, "no reboot retry"):
                w.main(args)
            observe.assert_not_called()
            action.assert_not_called()

    def test_prior_baseline_reconciles_without_reboot_when_fresh_state_proves_it(self):
        run = dict(phase="baseline_requested")
        args = [
            "disable",
            "--state",
            str(self.root),
            "--owner",
            "test",
            "--bundle",
            str(self.root / "observation"),
            "--credentials",
            "unused",
            "--camera-index",
            "0",
        ]
        with (
            patch.object(d, "status_script", return_value="synthetic read"),
            patch.object(d, "load_existing", return_value=run),
            patch.object(w.stock, "private_credentials"),
            patch.object(d, "command", return_value=self.raw(selected=False, hook=False)),
            patch.object(w, "observe") as observe,
            patch.object(d, "action") as action,
        ):
            self.assertEqual(w.main(args), 0)
            observe.assert_not_called()
            self.assertEqual(action.call_args.args[0], "CLEAN")
            self.assertEqual(
                json.loads((self.root / "run.json").read_text())["phase"],
                "disabled_baseline_verified",
            )


if __name__ == "__main__":
    unittest.main()
