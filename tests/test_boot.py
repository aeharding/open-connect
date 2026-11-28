"""Exercise the maintained video capture with generated media, never a camera."""

import json
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from open_connect.device import boot as m
from open_connect.session import Bundle


class VideoTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required"
    )
    def test_streamable_video_stops_decodes_with_inherited_INT_ignored_NO_camera(self):
        actual_popen = subprocess.Popen

        def synthetic_input(argv, **kw):
            # Replace ONLY camera input with ffmpeg's generated test pattern.
            # Keep production exec wrapper, container, codec and stop/validation.
            argv = list(argv)
            if argv[0] != sys.executable:
                return actual_popen(argv, **kw)
            first = argv.index("-f")
            end = argv.index("-an")
            argv[first:end] = ["-f", "lavfi", "-re", "-i", "testsrc=size=128x96:rate=5"]
            return actual_popen(argv, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            b = Bundle(Path(tmp) / "bundle", "synthetic local video, no hardware", "unittest")
            v = m.Video(b, 0)
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                with patch.object(m.subprocess, "Popen", side_effect=synthetic_input):
                    try:
                        v.start()
                    except RuntimeError as exc:
                        self.fail(str(exc) + "\n" + (b.path / "camera.stderr.txt").read_text())
                    time.sleep(0.7)
                    v.stop()
                    v.stop()  # idempotent after first stop (e.g. caller finally after failed start)
                result = json.loads((b.path / "camera-result.json").read_text())
                self.assertTrue(result["video_verified"])
                self.assertEqual(result["ffprobe_rc"], 0)
                self.assertGreaterEqual(result["decoded_frames"], 2)
                self.assertGreater(result["actual_interval_fps"], 0)
                signals = [x["signal"] for x in result["stop_requests"]]
                self.assertEqual(signals[0], "SIGINT")
                self.assertTrue(set(signals).issubset({"SIGINT", "SIGTERM"}))
            finally:
                signal.signal(signal.SIGINT, previous)
                if v.proc and v.proc.poll() is None:
                    v.proc.terminate()
                    v.proc.wait(timeout=3)
                b.finish("synthetic_test_finished")

    def test_video_progress_ignores_non_numeric_frame_and_signals_ready(self):
        import io
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as tmp:
            b = Bundle(Path(tmp) / "bundle", "progress parser unit test", "unittest")
            v = m.Video(b, 0)
            v.proc = SimpleNamespace(
                stdout=io.BytesIO(b"frame=N/A\nframe=bad\nframe=0\nframe=2\nprogress=end\n")
            )
            v._progress()
            self.assertTrue(v.ready.is_set())
            self.assertEqual(len(v.rows), 5)
            b.finish("synthetic_test_finished")
