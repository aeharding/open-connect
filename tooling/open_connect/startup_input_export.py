# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export checked input/frame intervals; camera bounds are not physical latency."""


def main():
    import csv
    import hashlib
    import json
    import re
    import sys
    from pathlib import Path

    from open_connect import metrics

    base = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2])
    rows = []
    summaries = []
    for condition in ("stock", "open-connect"):
        p = base / ("response-" + condition)
        trace = json.loads((p / "resources/trace.json").read_text())
        raw = (p / "resources/ssh.stdout").read_bytes()
        token = re.findall(rb"^OCM1 ([a-f0-9]{32}) boot ", raw, re.M)
        assert len(token) == 1
        assert metrics.parse(raw, token[0].decode(), []) == trace
        assert metrics.memory_csv(trace).encode() == (p / "resources/memory.csv").read_bytes()
        clock = json.loads(
            (base / ("response-clock-" + condition) / "clock-bounds.json").read_text()
        )
        assert clock["boot"] == trace["boot_id"]
        start = float(
            re.findall(
                r"Duration: N/A, start: ([0-9.]+), bitrate:", (p / "camera.stderr.txt").read_text()
            )[0]
        )
        frames = list(csv.DictReader((p / "focus-counts.csv").open()))
        points = [float(f["video_pts_s"]) for f in frames]
        counts = [int(f["border_white_pixels"]) for f in frames]
        expected_pts = [
            float(f["best_effort_timestamp_time"])
            for f in json.loads((p / "camera-result.json").read_text())["ffprobe"]["frames"]
        ]
        assert points == expected_pts
        events = [line.split("|") for line in (p / "action.out").read_text().splitlines()]
        assert len(events) == 10
        for index, (_, pair, direction, before, after) in enumerate(events):
            before, after = float(before), float(after)
            assert direction == ("right" if index % 2 == 0 else "left")
            assert int(pair) == index // 2 + 1
            assert (
                trace["samples"][0]["uptime_start_s"]
                < before
                < after
                < trace["samples"][-1]["uptime_end_s"]
            )
            lower = clock["kernel_zero_host_lower_s"] + before - start
            upper = clock["kernel_zero_host_upper_s"] + after - start
            focused = direction == "right"
            # Same region/threshold in both conditions; transitions have a large
            # separation (unfocused <=19 pixels, focused >=479 near these inputs).
            candidates = [
                i
                for i in range(1, len(points))
                if lower - 0.25 <= points[i] <= upper + 0.8
                and (counts[i] >= 100) == focused
                and (counts[i - 1] >= 100) != focused
            ]
            assert len(candidates) == 1, (condition, pair, direction, candidates)
            i = candidates[0]
            rows.append(
                dict(
                    condition=condition,
                    pair=pair,
                    direction=direction,
                    input_before_uptime_s=before,
                    input_after_uptime_s=after,
                    before_frame=i - 1,
                    first_frame=i,
                    video_before_s=points[i - 1],
                    video_first_s=points[i],
                    response_lower_s=points[i - 1] - upper,
                    response_upper_s=points[i] - lower,
                    before_white_pixels=counts[i - 1],
                    first_white_pixels=counts[i],
                )
            )
        first, last = trace["samples"][0], trace["samples"][-1]

        def cpu(sample):
            return list(
                map(
                    int,
                    next(
                        line.split()[1:9]
                        for line in sample["files"]["/proc/stat"][0].splitlines()
                        if line.startswith("cpu ")
                    ),
                )
            )

        delta = [b - a for a, b in zip(cpu(first), cpu(last))]
        assert min(delta) >= 0 and sum(delta) > 0
        memory = [
            {
                m[1]: int(m[2])
                for m in re.finditer(
                    r"^([A-Za-z_()]+):\s+(\d+) kB$", s["files"]["/proc/meminfo"][0], re.M
                )
            }
            for s in trace["samples"]
        ]
        summaries.append(
            dict(
                condition=condition,
                samples=len(memory),
                first_uptime_s=first["uptime_start_s"],
                last_uptime_s=last["uptime_end_s"],
                cpu_busy_pct=100 * (sum(delta) - delta[3] - delta[4]) / sum(delta),
                MemFree_min_kB=min(s["MemFree"] for s in memory),
                MemFree_last_kB=memory[-1]["MemFree"],
                Cached_last_kB=memory[-1]["Cached"],
                input_probe_sha256=hashlib.sha256((p / "response.sh").read_bytes()).hexdigest(),
            )
        )
    for name, data in (("input-response.csv", rows), ("input-workload.csv", summaries)):
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(data[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
        print(name, len(data))


if __name__ == "__main__":
    main()
