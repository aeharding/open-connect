"""Finite camera capture and frame validation for bench startup observations."""

import json
import signal
import subprocess
import sys
import threading
import time


class Video:
    def __init__(self, bundle, index):
        self.bundle, self.index = bundle, index
        self.proc = None
        self.ready = threading.Event()
        self.rows = []
        self.stop_requests = []

    def start(self):
        self.path = self.bundle.path / "camera.mkv"
        self.stderr = (self.bundle.path / "camera.stderr.txt").open("xb")
        self.argv = [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-n",
            "-f",
            "avfoundation",
            "-framerate",
            "5",
            "-video_size",
            "1280x720",
            "-pixel_format",
            "uyvy422",
            "-i",
            str(self.index) + ":none",
            "-an",
            "-c:v",
            "mjpeg",
            "-q:v",
            "4",
            "-t",
            "260",
            "-f",
            "matroska",
            "-cluster_time_limit",
            "1000",
            "-flush_packets",
            "1",
            "-progress",
            "pipe:1",
            "-nostats",
            str(self.path),
        ]
        self.started = time.monotonic()
        # Explicit child defaults avoid inherited ignored INT/TERM. exec keeps the
        # exact owned Popen PID; no fork-time Python callback or shell is involved.
        self.launch_argv = [
            sys.executable,
            "-c",
            "import os,signal,sys; signal.signal(signal.SIGINT,signal.SIG_DFL); "
            "signal.signal(signal.SIGTERM,signal.SIG_DFL); os.execvp(sys.argv[1],sys.argv[1:])",
            *self.argv,
        ]
        self.proc = subprocess.Popen(self.launch_argv, stdout=subprocess.PIPE, stderr=self.stderr)
        self.bundle.event(
            "camera_started",
            pid=self.proc.pid,
            argv=self.argv,
            launch_argv=self.launch_argv,
            child_signal_defaults=["SIGINT", "SIGTERM"],
        )
        self.worker = threading.Thread(target=self._progress, daemon=True)
        self.worker.start()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.ready.wait(0.05):
                return
            if self.proc.poll() is not None:
                break
        raise RuntimeError("camera produced no confirmed frame before request; no reboot")

    def _progress(self):
        for line in iter(self.proc.stdout.readline, b""):
            row = dict(
                monotonic_ns=time.monotonic_ns(), line=line.decode("utf8", "replace").strip()
            )
            self.rows.append(row)
            if row["line"].startswith("frame=") and int(row["line"].split("=")[1].strip()) >= 1:
                self.ready.set()

    def stop(self):
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.stop_requests.append(dict(signal="SIGINT", monotonic_ns=time.monotonic_ns()))
            self.proc.send_signal(signal.SIGINT)  # exact owned child; streamable container
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.stop_requests.append(dict(signal="SIGTERM", monotonic_ns=time.monotonic_ns()))
                self.proc.terminate()
                self.proc.wait(timeout=3)
        self.worker.join(timeout=2)
        self.stderr.close()
        self.bundle.save("camera-progress.json", (json.dumps(self.rows, indent=2) + "\n").encode())
        report = dict(
            pid=self.proc.pid,
            argv=self.argv,
            launch_argv=self.launch_argv,
            stop_requests=self.stop_requests,
            returncode=self.proc.returncode,
            host_elapsed_s=time.monotonic() - self.started,
        )
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-count_frames",
                    "-show_frames",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "frame=best_effort_timestamp_time:stream=nb_read_frames,avg_frame_rate,duration:format=duration",
                    "-of",
                    "json",
                    str(self.path),
                ],
                capture_output=True,
                timeout=12,
            )
            report.update(
                ffprobe_rc=result.returncode, ffprobe_stderr=result.stderr.decode("utf8", "replace")
            )
            report["ffprobe"] = json.loads(result.stdout)
            stream = report["ffprobe"]["streams"][0]
            duration = float(stream.get("duration") or report["ffprobe"]["format"]["duration"])
            report["decoded_frames"] = int(stream["nb_read_frames"])
            report["actual_frames_per_video_second"] = report["decoded_frames"] / duration
            report["video_duration_s"] = duration
            pts = [float(f["best_effort_timestamp_time"]) for f in report["ffprobe"]["frames"]]
            if (
                result.returncode != 0
                or report["decoded_frames"] != len(pts)
                or len(pts) < 2
                or duration <= 0
                or any(b <= a for a, b in zip(pts, pts[1:]))
            ):
                raise RuntimeError("video lacks verified frames/increasing timestamps/duration")
            report.update(
                first_frame_pts_s=pts[0],
                last_frame_pts_s=pts[-1],
                actual_interval_fps=(len(pts) - 1) / (pts[-1] - pts[0]),
                video_verified=True,
            )
        except Exception as exc:
            report["probe_error"] = str(exc)
        self.bundle.save("camera-result.json", (json.dumps(report, indent=2) + "\n").encode())
        if report.get("video_verified") is not True:
            raise RuntimeError("camera final validation failed; see camera-result.json")
