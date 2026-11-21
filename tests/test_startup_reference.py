"""Mutating experiment front door: refusal and uncertain relay TX with fake hardware."""

import contextlib
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
                    argv, 0, b"\nSTOCK_BOOT|11111111-1111-1111-1111-111111111111\n", b""
                )
            return actual_run(argv, **kwargs)

        def output(argv, **kwargs):
            if argv[0] == "system_profiler":
                return json.dumps(
                    {"SPCameraDataType": [{"spcamera_unique-id": "synthetic-camera"}]}
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
