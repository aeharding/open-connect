"""Reject coherent-looking edits that the old numeric exporter trusted."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from open_connect.clock_reference import bounds
from open_connect.startup_analysis import verified_annotations, verified_clock


class StartupEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.trial = self.root / "trial-1"
        self.clock = self.root / "clock-1"
        self.trial.mkdir()
        self.clock.mkdir()
        self.boot = "12345678-1234-1234-1234-123456789abc"
        exchanges = [
            {"before_s": 1210 + n, "after_s": 1210.002 + n, "uptime_s": 210 + n} for n in range(7)
        ]
        self.saved = {"boot": self.boot, "exchanges": exchanges, **bounds(exchanges)}
        self.write(self.clock / "clock-bounds.json", self.saved)
        self.raw = "\nBOOT_CLOCK_READY|" + self.boot + "\n"
        self.raw += "".join(
            f"\nBOOT_CLOCK_REPLY|{n:032x}|{210 + n:.2f} {300 + n:.2f}\n" for n in range(7)
        )
        (self.clock / "ssh.stdout").write_text(self.raw)
        self.write(
            self.trial / "trial.json", {"events": [{"kind": "ACC_ON", "monotonic_s": 1000.5}]}
        )
        (self.trial / "camera.stderr.txt").write_text("Duration: N/A, start: 1000.0, bitrate:\n")
        self.write(
            self.trial / "video-clock-origin.json",
            dict(
                avfoundation_input_start_host_s=1000.0, acc_on_host_s=1000.5, acc_on_video_pts_s=0.5
            ),
        )
        self.pts = [1.0, 1.2, 1.4, 1.6, 1.8]
        self.write(
            self.trial / "camera-result.json",
            {"ffprobe": {"frames": [{"best_effort_timestamp_time": str(v)} for v in self.pts]}},
        )
        self.annotations = [self.annotation(0, 1), self.annotation(3, 4)]
        self.annotations[0]["definition"] = "Home carousel fully spaced"
        self.annotations[1]["definition"] = "CarPlay dashboard fully rendered; map still loading"
        self.write(self.trial / "annotations.json", self.annotations)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value))

    def annotation(self, before, after):
        host = [1000.0 + self.pts[before], 1000.0 + self.pts[after]]
        return dict(
            before_frame=before,
            first_frame=after,
            video_pts_bounds_s=[self.pts[before], self.pts[after]],
            relative_acc_command_s=[v - 1000.5 for v in host],
            relative_kernel_s=[
                host[0] - self.saved["kernel_zero_host_upper_s"],
                host[1] - self.saved["kernel_zero_host_lower_s"],
            ],
            sensor_and_relay_latency_qualified=False,
        )

    def test_clock_rejects_changed_bounds_raw_reply_boot_and_duplicate_nonce(self):
        self.assertEqual(verified_clock(self.trial, self.boot), self.saved)
        changed = copy.deepcopy(self.saved)
        changed["kernel_zero_host_lower_s"] += 1
        self.write(self.clock / "clock-bounds.json", changed)
        with self.assertRaises(AssertionError):
            verified_clock(self.trial, self.boot)
        self.write(self.clock / "clock-bounds.json", self.saved)
        for raw in (
            self.raw.replace("210.00", "209.00"),
            self.raw.replace(self.boot, "87654321-1234-1234-1234-123456789abc"),
            self.raw.replace(f"{1:032x}", f"{0:032x}"),
        ):
            with self.subTest(raw=raw):
                (self.clock / "ssh.stdout").write_text(raw)
                with self.assertRaises(AssertionError):
                    verified_clock(self.trial, self.boot)

    def test_annotations_reject_nonadjacent_frames_bad_definition_and_changed_arithmetic(self):
        self.assertEqual(verified_annotations(self.trial, self.saved), self.annotations)
        skipped = self.annotation(0, 2)
        skipped["definition"] = self.annotations[0]["definition"]
        mutations = [[skipped, self.annotations[1]]]
        for field in ("definition", "relative_acc_command_s", "relative_kernel_s"):
            rows = copy.deepcopy(self.annotations)
            if field == "definition":
                rows[0][field] = "first usable input"
            else:
                rows[0][field][0] += 0.1
            mutations.append(rows)
        for rows in mutations:
            with self.subTest(rows=rows):
                self.write(self.trial / "annotations.json", rows)
                with self.assertRaises(AssertionError):
                    verified_annotations(self.trial, self.saved)
