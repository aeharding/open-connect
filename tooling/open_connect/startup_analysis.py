# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only analysis of completed STARTUP-COMPARISON.md trials."""


def verified_clock(path, boot):
    """Recompute saved bounds and match all seven exchanges to raw replies."""
    import json
    import re

    from open_connect.clock_reference import bounds

    directory = path.parent / path.name.replace("trial-", "clock-")
    saved = json.loads((directory / "clock-bounds.json").read_text())
    raw = (directory / "ssh.stdout").read_text()
    assert saved["boot"] == boot
    assert re.findall(r"^BOOT_CLOCK_READY\|([a-f0-9-]{36})$", raw, re.M) == [boot]
    replies = re.findall(
        r"^BOOT_CLOCK_REPLY\|([a-f0-9]{32})\|([0-9]+\.[0-9]+) ([0-9]+\.[0-9]+)$",
        raw,
        re.M,
    )
    exchanges = saved["exchanges"]
    assert len(replies) == len(exchanges) == len({r[0] for r in replies}) == 7
    assert [float(r[1]) for r in replies] == [r["uptime_s"] for r in exchanges]
    assert all(a["after_s"] <= b["before_s"] for a, b in zip(exchanges, exchanges[1:]))
    for key, value in bounds(exchanges).items():
        assert saved[key] == value, key
    return saved


def verified_annotations(path, clocks):
    """Check definitions, adjacent saved video PTS and all timing arithmetic."""
    import json
    import math
    import re

    meta = json.loads((path / "trial.json").read_text())
    on = [e["monotonic_s"] for e in meta["events"] if e["kind"] == "ACC_ON"]
    starts = re.findall(
        r"Duration: N/A, start: ([0-9.]+), bitrate:",
        (path / "camera.stderr.txt").read_text(),
    )
    assert len(on) == len(starts) == 1
    start = float(starts[0])
    assert math.isfinite(start) and math.isfinite(on[0])
    origin = json.loads((path / "video-clock-origin.json").read_text())
    assert origin == {
        "avfoundation_input_start_host_s": start,
        "acc_on_host_s": on[0],
        "acc_on_video_pts_s": on[0] - start,
    }
    frames = json.loads((path / "camera-result.json").read_text())["ffprobe"]["frames"]
    pts = [float(f["best_effort_timestamp_time"]) for f in frames]
    assert pts and all(math.isfinite(v) for v in pts)
    assert all(a < b for a, b in zip(pts, pts[1:]))
    rows = json.loads((path / "annotations.json").read_text())
    assert [r["definition"] for r in rows] == [
        "Home carousel fully spaced",
        "CarPlay dashboard fully rendered; map still loading",
    ]
    for row in rows:
        a, b = row["before_frame"], row["first_frame"]
        assert type(a) is int and type(b) is int and 0 <= a < b < len(pts) and b == a + 1
        assert row["video_pts_bounds_s"] == [pts[a], pts[b]]
        host = [start + pts[a], start + pts[b]]
        assert row["relative_acc_command_s"] == [v - on[0] for v in host]
        assert row["relative_kernel_s"] == [
            host[0] - clocks["kernel_zero_host_upper_s"],
            host[1] - clocks["kernel_zero_host_lower_s"],
        ]
        assert row["sensor_and_relay_latency_qualified"] is False
    return rows


def main():
    import hashlib
    import json
    import re
    import sys
    from pathlib import Path

    from open_connect import metrics

    def memory(sample):
        return {
            m[1]: int(m[2])
            for m in re.finditer(
                r"^([A-Za-z_()]+):\s+(\d+) kB$", sample["files"]["/proc/meminfo"][0], re.M
            )
        }

    def cpu(sample):
        lines = [
            line.split()[1:]
            for line in sample["files"]["/proc/stat"][0].splitlines()
            if line.startswith("cpu ")
        ]
        assert len(lines) == 1 and len(lines[0]) >= 8
        return list(map(int, lines[0][:8]))

    def disks(sample):
        rows = {}
        for line in sample["files"]["/proc/diskstats"][0].splitlines():
            fields = line.split()
            # Full eleven-counter rows only; do not guess a different partition format.
            if len(fields) != 14:
                continue
            identity = tuple(fields[:3])
            assert identity not in rows
            rows[identity] = [int(value) for value in fields[3:]]
        return rows

    for argument in sys.argv[1:]:
        path = Path(argument)
        meta = json.loads((path / "trial.json").read_text())
        assert meta["outcome"] == "observed" and meta["error"] is None
        raw = (path / "fetch.out").read_bytes()
        boot = re.findall(rb"^BOOT_TRACE\|([a-f0-9-]{36})$", raw, re.M)
        assert len(boot) == 1
        token = boot[0].decode().replace("-", "")
        raw = raw[raw.index(b"\nOCM1 " + token.encode() + b" boot ") :]
        trace = metrics.parse(raw, token, [])
        assert trace == json.loads((path / "trace.json").read_text())
        assert metrics.memory_csv(trace).encode() == (path / "memory.csv").read_bytes()
        samples = trace["samples"]
        window = [s for s in samples if s["uptime_start_s"] >= 20 and s["uptime_end_s"] <= 170]
        assert len(window) >= 2
        first, last = window[0], window[-1]
        delta = [b - a for a, b in zip(cpu(first), cpu(last))]
        assert all(value >= 0 for value in delta) and sum(delta) > 0
        before, after = disks(first), disks(last)
        disk_rows = []
        for identity in sorted(before.keys() | after.keys()):
            if identity not in before or identity not in after:
                disk_rows.append(
                    dict(
                        major=identity[0],
                        minor=identity[1],
                        name=identity[2],
                        endpoint_state="appeared" if identity not in before else "disappeared",
                        reads="",
                        sectors_read="",
                        writes="",
                        sectors_written="",
                    )
                )
                continue
            values = [b - a for a, b in zip(before[identity], after[identity])]
            # In-flight I/O is a gauge; completed counts and sectors are cumulative.
            assert all(values[index] >= 0 for index in (0, 2, 4, 6))
            disk_rows.append(
                dict(
                    major=identity[0],
                    minor=identity[1],
                    name=identity[2],
                    endpoint_state="both",
                    reads=values[0],
                    sectors_read=values[2],
                    writes=values[4],
                    sectors_written=values[6],
                )
            )
        clocks = verified_clock(path, trace["boot_id"])
        values = [memory(sample) for sample in samples]
        result = dict(
            trial=str(path),
            condition=meta["condition"],
            revision=meta["revision"],
            boot=trace["boot_id"],
            trace_sha256=hashlib.sha256(raw).hexdigest(),
            trace_bytes=len(raw),
            samples=len(samples),
            first_uptime_s=samples[0]["uptime_start_s"],
            last_uptime_s=samples[-1]["uptime_end_s"],
            window_first_uptime_s=first["uptime_start_s"],
            window_last_uptime_s=last["uptime_end_s"],
            cpu_busy_percent=100 * (sum(delta) - delta[3] - delta[4]) / sum(delta),
            cpu_delta_ticks=delta,
            memory_kB={
                name: dict(
                    first=values[0][name],
                    last=values[-1][name],
                    min=min(row[name] for row in values),
                    max=max(row[name] for row in values),
                )
                for name in ("MemFree", "Buffers", "Cached", "Shmem", "Slab")
            },
            disk_deltas=disk_rows,
            kernel_zero_host_bounds=[
                clocks["kernel_zero_host_lower_s"],
                clocks["kernel_zero_host_upper_s"],
            ],
        )
        print(json.dumps(result))


if __name__ == "__main__":
    main()
