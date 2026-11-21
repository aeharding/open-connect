# SPDX-License-Identifier: AGPL-3.0-or-later
"""Inspect numeric brightness of the same border region in both private videos."""


def main():
    import csv
    import json
    import re
    import subprocess
    import sys
    from pathlib import Path

    import numpy as np

    base = Path(sys.argv[1]).resolve()
    for condition in ("stock", "open-connect"):
        p = base / ("response-" + condition)
        frames = json.loads((p / "camera-result.json").read_text())["ffprobe"]["frames"]
        pts = [float(f["best_effort_timestamp_time"]) for f in frames]
        raw = subprocess.check_output(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(p / "camera.mkv"),
                "-vf",
                "crop=400:35:180:425",
                "-vsync",
                "0",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            timeout=30,
        )
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((-1, 35, 400, 3))
        assert len(pixels) == len(pts)
        counts = (pixels.min(axis=3) > 160).sum(axis=(1, 2))
        with (p / "focus-counts.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["frame", "video_pts_s", "border_white_pixels"])
            writer.writerows(zip(range(len(pts)), pts, counts))
        start = float(
            re.findall(
                r"Duration: N/A, start: ([0-9.]+), bitrate:", (p / "camera.stderr.txt").read_text()
            )[0]
        )
        clock = json.loads(
            (base / ("response-clock-" + condition) / "clock-bounds.json").read_text()
        )
        zero = (clock["kernel_zero_host_lower_s"] + clock["kernel_zero_host_upper_s"]) / 2
        print(condition, "counts percentiles", np.percentile(counts, [0, 25, 50, 75, 100]).tolist())
        for event in (p / "action.out").read_text().splitlines():
            _, pair, direction, before, after = event.split("|")
            target = zero + float(before) - start
            near = [
                (i, t, int(n))
                for i, (t, n) in enumerate(zip(pts, counts))
                if target - 0.25 <= t <= target + 0.8
            ]
            print(pair, direction, "input_pts", round(target, 4), near)


if __name__ == "__main__":
    main()
