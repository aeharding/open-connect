# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only analysis of completed STARTUP-COMPARISON.md trials."""


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
        clocks = json.loads(
            (path.parent / path.name.replace("trial-", "clock-") / "clock-bounds.json").read_text()
        )
        assert clocks["boot"] == trace["boot_id"]
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
