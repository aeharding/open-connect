"""UART extraction excludes prior boots, ambiguous captures and identity data."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_connect import startup_annotate, startup_export
from open_connect.startup_analysis import verified_annotations
from open_connect.startup_wireless import BOOT_MARKER, native_events, trial_rows


class WirelessEvents(unittest.TestCase):
    def test_partial_export_rejects_unverified_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for base, condition in [(0, "wireless-base-off"), (1, "wireless-base-on")]:
                for number in range(1, 6):
                    path = root / condition / f"trial-{number}"
                    path.mkdir(parents=True)
                    (path / "trial.json").write_text(
                        json.dumps(
                            {
                                "outcome": "incomplete_preserved",
                                "condition": "open-connect",
                                "base": base,
                                "wireless": 1,
                                "pandora": 1,
                            }
                        )
                    )
                    (path / "preflight.out").write_bytes(b"unverified policy\n")
            with (
                patch("sys.argv", ["export", str(root), str(root / "public"), "--wireless"]),
                self.assertRaisesRegex(ValueError, "missing"),
            ):
                startup_export.main()

    def test_camera_only_keeps_missing_kernel_time_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial-4"
            path.mkdir()
            (path / "trial.json").write_text(
                json.dumps({"events": [{"kind": "ACC_ON", "monotonic_s": 1001.0}]})
            )
            (path / "camera-result.json").write_text(
                json.dumps(
                    {
                        "ffprobe": {
                            "frames": [
                                {"best_effort_timestamp_time": str(t)}
                                for t in (10.0, 10.2, 20.0, 20.2)
                            ]
                        }
                    }
                )
            )
            (path / "camera.stderr.txt").write_text("Duration: N/A, start: 1000.000, bitrate:")
            (path / "camera.mkv").write_bytes(b"synthetic fixture")
            with (
                patch(
                    "sys.argv", ["annotate", str(path), "10", "10.2", "20", "20.2", "--camera-only"]
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                startup_annotate.main()
            rows = verified_annotations(path, None)
            self.assertEqual(rows[0]["relative_acc_command_s"][0], 9.0)
            self.assertAlmostEqual(rows[0]["relative_acc_command_s"][1], 9.2)
            self.assertTrue(all(row["relative_kernel_s"] is None for row in rows))
            rows[0]["relative_kernel_s"] = [0, 0]
            (path / "annotations.json").write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):
                verified_annotations(path, None)

    def test_boot_scope_repeats_and_missing_events(self):
        raw = (
            b"00:12:34.567 hostapd[] Info: IEEE 802.11: associated\n"
            + b"00:00:01.000 syslog-ng[] Info: "
            + BOOT_MARKER
            + b"\n00:00:51.123 hostapd[] Info: IEEE 802.11: associated\r\n"
            + b"00:00:51.125 hostapd[] Info: IEEE 802.11: associated\n"
        )
        count, events = native_events(raw)
        self.assertEqual(count, 1)
        self.assertEqual(events["wifi_associated"], [51.123, 51.125])
        self.assertEqual(events["carplay_session_started"], [])
        for bad in (raw.replace(BOOT_MARKER, b"other"), raw + b"\n" + BOOT_MARKER):
            count, events = native_events(bad)
            self.assertNotEqual(count, 1)
            self.assertTrue(all(not values for values in events.values()))

    def test_export_whitelist_and_finished_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            meta = {"base": 0, "outcome": "observed", "events": [], "label": "private label"}
            (path / "trial.json").write_text(json.dumps(meta))
            (path / "rx.bin").write_bytes(
                BOOT_MARKER
                + b"\n00:00:58.034 Std[] Error: Unique Device ID in "
                + b"_CarPlayHandleSessionStartedAsync is 987654321\n"
                + b"00:00:55.702 hostapd[] Info: STA 02:00:00:00:00:01 "
                + b"IEEE 802.11: associated\n"
            )
            rows = list(trial_rows(path, 1))
            exported = json.dumps(rows)
            for private in ("987654321", "02:00:00:00:00:01", "private label", "Unique Device"):
                self.assertNotIn(private, exported)
            session = next(r for r in rows if r["event"] == "carplay_session_started")
            self.assertEqual(session["native_logged_s"], "58.034")
            missing = next(r for r in rows if r["event"] == "wifi_authenticated")
            self.assertEqual(missing["native_logged_s"], "")
            del meta["outcome"]
            (path / "trial.json").write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "not finished"):
                list(trial_rows(path, 1))
