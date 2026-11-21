# SPDX-License-Identifier: AGPL-3.0-or-later
"""Retain manually reviewed adjacent-frame bounds; never infer usability."""


def main():
    import hashlib
    import json
    import re
    import sys
    from pathlib import Path

    p = Path(sys.argv[1])
    requested = list(map(float, sys.argv[2:]))
    assert len(requested) == 4
    pts = [
        float(f["best_effort_timestamp_time"])
        for f in json.loads((p / "camera-result.json").read_text())["ffprobe"]["frames"]
    ]
    start = re.findall(
        r"Duration: N/A, start: ([0-9.]+), bitrate:", (p / "camera.stderr.txt").read_text()
    )
    assert len(start) == 1
    on = [
        e["monotonic_s"]
        for e in json.loads((p / "trial.json").read_text())["events"]
        if e["kind"] == "ACC_ON"
    ][0]
    origin = {
        "avfoundation_input_start_host_s": float(start[0]),
        "acc_on_host_s": on,
        "acc_on_video_pts_s": on - float(start[0]),
    }
    (p / "video-clock-origin.json").write_text(json.dumps(origin, indent=2) + "\n")
    clock = json.loads(
        (p.parent / p.name.replace("trial-", "clock-") / "clock-bounds.json").read_text()
    )
    rows = []
    for index, name in enumerate(
        ["Home carousel fully spaced", "CarPlay dashboard fully rendered; map still loading"]
    ):
        before, after = requested[2 * index : 2 * index + 2]
        a, b = pts.index(before), pts.index(after)
        assert b == a + 1
        host = [float(start[0]) + v for v in [before, after]]
        rows.append(
            {
                "definition": name,
                "before_frame": a,
                "first_frame": b,
                "video_pts_bounds_s": [before, after],
                "relative_acc_command_s": [v - on for v in host],
                "relative_kernel_s": [
                    host[0] - clock["kernel_zero_host_upper_s"],
                    host[1] - clock["kernel_zero_host_lower_s"],
                ],
                "sensor_and_relay_latency_qualified": False,
            }
        )
    (p / "annotations.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(
        json.dumps(
            {
                "trial": str(p),
                "video_sha256": hashlib.sha256((p / "camera.mkv").read_bytes()).hexdigest(),
                "observations": rows,
            }
        )
    )


if __name__ == "__main__":
    main()
