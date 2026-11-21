"""Mutating experiment front door: refusal and uncertain relay TX with fake hardware."""

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from open_connect import startup_reference as m


class StartupReferenceTests(unittest.TestCase):
    def test_service_condition_requires_policy_state_and_startup_records(self):
        boot = "11111111-1111-1111-1111-111111111111"
        state = dict(
            ok=True,
            installed=True,
            conflict=False,
            restart=False,
            pending=False,
            touch=1,
            warning=1,
            uart=0,
            ssh=0,
            uartCurrent=0,
            sshCurrent=0,
            notice="-",
        )

        def output(enabled, current=None, starts=None, pid=None):
            current = current or ("RUNNING" if enabled else "STOPPED")
            starts = enabled if starts is None else starts
            pid = ('    pid="123"\n' if enabled else "") if pid is None else pid
            return (
                "CANDIDATE_STATUS|"
                + json.dumps({**state, "pandora": enabled})
                + '\nPANDORA_INFO_BEGIN\n<service\n    state="'
                + current
                + '"\n    autorun="'
                + ("yes" if enabled else "no")
                + '"\n'
                + pid
                + "/>\nPANDORA_INFO_END\nPANDORA_STARTS|"
                + str(starts)
                + "\nREFERENCE_BOOT|"
                + boot
                + "\n"
            ).encode()

        for enabled in (0, 1):
            self.assertEqual(m.validate_condition(output(enabled), "open-connect", enabled), boot)
            with self.assertRaises(ValueError):
                m.validate_condition(output(enabled), "open-connect", 1 - enabled)
            applied = output(enabled).replace(b'"notice": "-"', b'"notice": "restart"')
            self.assertEqual(m.validate_condition(applied, "open-connect", enabled), boot)
            with self.assertRaises(ValueError):
                m.validate_condition(applied, "open-connect")
        for bad in (
            output(0, starts=1),
            output(0, pid='    pid="123"\n'),
            output(0, current="RUNNING"),
            output(1, starts=2),
            output(1, pid=""),
            output(1).replace(b"PANDORA_INFO_BEGIN", b"OTHER_INFO_BEGIN"),
        ):
            with self.assertRaises(ValueError):
                m.validate_condition(
                    bad,
                    "open-connect",
                    json.loads(bad.split(b"|", 1)[1].splitlines()[0])["pandora"],
                )

    def test_candidate_condition_requires_selected_features_and_no_pending_restart(self):
        boot = "11111111-1111-1111-1111-111111111111"
        state = dict(
            ok=True,
            installed=True,
            conflict=False,
            restart=False,
            pending=False,
            touch=1,
            warning=1,
            uart=0,
            ssh=0,
            uartCurrent=0,
            sshCurrent=0,
            notice="-",
        )

        def output(state):
            return (
                "CANDIDATE_STATUS|" + json.dumps(state) + "\nREFERENCE_BOOT|" + boot + "\n"
            ).encode()

        self.assertEqual(m.validate_condition(output(state), "open-connect"), boot)
        for key, value in [
            ("restart", True),
            ("touch", 0),
            ("warning", 0),
            ("conflict", True),
            ("sshCurrent", 1),
            ("notice", "installed"),
        ]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "do not match"):
                m.validate_condition(output({**state, key: value}), "open-connect")
        with self.assertRaisesRegex(ValueError, "missing candidate"):
            m.validate_condition(("REFERENCE_BOOT|" + boot + "\n").encode(), "open-connect")

    def test_camera_identity_allows_continuity_camera_and_resolves_current_ffmpeg_index(self):
        devices = [
            {"_name": "Phone", "spcamera_unique-id": "phone"},
            {"_name": "USB Camera", "spcamera_unique-id": "bench"},
        ]
        enumeration = (
            b"[avf] AVFoundation video devices:\n[avf] [0] Phone\n[avf] [2] USB Camera\n"
            b"[avf] AVFoundation audio devices:\n[avf] [0] USB Camera\n"
        )
        self.assertEqual(m.camera_index(devices, enumeration, "bench"), 2)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            m.camera_index(devices + [devices[1]], enumeration, "bench")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            m.camera_index(
                devices,
                enumeration.replace(b"[2] USB Camera", b"[2] USB Camera\n[3] USB Camera"),
                "bench",
            )

    def test_boot_retrieval_requires_new_boot_complete_trace_and_matching_digest(self):
        boot = "22222222-2222-2222-2222-222222222222"
        token = boot.replace("-", "")
        prefix = "OCM1 " + token + " "
        trace = "\n" + prefix + "boot " + boot + "\n"
        trace += "\n" + prefix + "sample 0 2.00\n"
        for path in m.metrics.FILES:
            trace += "\n" + prefix + "file " + path + "\n"
            trace += "MemTotal: 1 kB\nMemFree: 1 kB\n" if path == "/proc/meminfo" else "example\n"
        trace += "\n" + prefix + "end 0 2.01\n\n" + prefix + "complete 1\n"

        def response(body):
            return (
                "banner\nBOOT_TRACE|"
                + boot
                + "\nBOOT_TRACE_SHA|(stdin)= "
                + hashlib.sha256(body.encode()).hexdigest()
                + "\n"
                + "START_UPTIME|1.99 0.00\n"
                + body
            ).encode()

        result = m.parse_boot_trace(response(trace), "11111111-1111-1111-1111-111111111111")
        self.assertEqual(result["samples"][0]["uptime_start_s"], 2.0)
        with self.assertRaisesRegex(ValueError, "stale"):
            m.parse_boot_trace(response(trace), boot)
        with self.assertRaisesRegex(ValueError, "digest"):
            m.parse_boot_trace(response(trace).replace(b"example", b"changed", 1), "old")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            m.parse_boot_trace(response(trace.rsplit("\n" + prefix + "complete", 1)[0]), "old")

    def test_dry_run_never_opens_devices_or_ssh(self):
        with (
            patch.object(sys, "argv", ["startup_reference"]),
            patch.object(m.subprocess, "run") as run,
            patch.object(m, "open_adapter") as adapter,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            m.main()
        run.assert_not_called()
        adapter.assert_not_called()

    def test_partial_off_and_camera_failure_preserve_errors_and_never_send_on(self):
        actual_run, actual_output = subprocess.run, subprocess.check_output
        frames = []
        uart = SimpleNamespace(is_open=True)
        uart.close = lambda: setattr(uart, "is_open", False)

        class Relay:
            is_open = False

            def open(self):
                self.is_open = True

            def close(self):
                self.is_open = False

            def write(self, value):
                frames.append(value)
                return 3

            def flush(self):
                pass

        relay = Relay()

        def run(argv, **kwargs):
            if argv[0] == "ssh":
                return subprocess.CompletedProcess(
                    argv, 0, b"\nREFERENCE_BOOT|11111111-1111-1111-1111-111111111111\n", b""
                )
            if argv[0] == "ffmpeg":
                return subprocess.CompletedProcess(
                    argv,
                    1,
                    b"",
                    b"[avf] AVFoundation video devices:\n[avf] [0] Fake\n[avf] AVFoundation audio devices:\n",
                )
            return actual_run(argv, **kwargs)

        def output(argv, **kwargs):
            if argv[0] == "system_profiler":
                return json.dumps(
                    {
                        "SPCameraDataType": [
                            {"_name": "Fake", "spcamera_unique-id": "synthetic-camera"}
                        ]
                    }
                ).encode()
            return actual_output(argv, **kwargs)

        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            bundle = Path(temporary) / "trial"
            stack.enter_context(
                patch.object(
                    sys,
                    "argv",
                    [
                        "startup_reference",
                        "--live",
                        "--bundle",
                        str(bundle),
                        "--camera-uid",
                        "synthetic-camera",
                    ],
                )
            )
            stack.enter_context(patch.object(m.subprocess, "run", side_effect=run))
            stack.enter_context(patch.object(m.subprocess, "check_output", side_effect=output))
            stack.enter_context(
                patch.object(m, "AdapterLock", return_value=contextlib.nullcontext())
            )
            stack.enter_context(patch.object(m, "open_adapter", return_value=uart))
            stack.enter_context(
                patch.object(
                    m, "Session", return_value=SimpleNamespace(receive=lambda _: time.sleep(0.001))
                )
            )
            stack.enter_context(patch.object(m.Video, "start"))
            stack.enter_context(
                patch.object(m.Video, "stop", side_effect=RuntimeError("synthetic camera failure"))
            )
            stack.enter_context(patch.object(m.serial, "Serial", return_value=relay))
            stack.enter_context(
                patch.object(
                    m.list_ports,
                    "comports",
                    return_value=[
                        SimpleNamespace(
                            vid=0x1A86, pid=0x7523, location="2-1", device="synthetic-relay"
                        )
                    ],
                )
            )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            with self.assertRaisesRegex(SystemExit, "partial relay transmission"):
                m.main()
            record = json.loads((bundle / "trial.json").read_text())
            self.assertEqual(frames, [bytes.fromhex("a00100a1")])
            self.assertTrue(record["uart_closed"])
            self.assertTrue(record["relay_closed"])
            self.assertIn("synthetic camera failure", record["camera_error"])
            self.assertEqual(record["outcome"], "incomplete_preserved")
