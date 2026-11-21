"""UART extraction excludes prior boots, ambiguous captures and identity data."""

import json
import tempfile
import unittest
from pathlib import Path

from open_connect.startup_wireless import BOOT_MARKER, native_events, trial_rows


class WirelessEvents(unittest.TestCase):
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
