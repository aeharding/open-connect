# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export reviewed numeric fields only, requiring complete verified cohorts."""


def main():
    import argparse
    import csv
    import json
    import subprocess
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("output", type=Path)
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--services", action="store_true")
    comparison.add_argument("--logging", action="store_true")
    args = parser.parse_args()
    base = args.base.resolve()
    output = args.output
    output.mkdir(mode=0o700)
    if args.logging:
        cohorts = [
            ("logging-info", base / "logging-info", "stock", None, "Info"),
            ("logging-warn", base / "logging-warn", "stock", None, "Warn"),
        ]
    elif args.services:
        cohorts = [
            ("pandora-on", base / "pandora-on", "open-connect", 1, None),
            ("pandora-off", base / "pandora-off", "open-connect", 0, None),
        ]
    else:
        cohorts = [
            ("stock", base / "stock", "stock", None, None),
            ("open-connect", base / "open-connect-matched", "open-connect", None, None),
        ]
    paths = [root / f"trial-{n}" for _, root, _, _, _ in cohorts for n in range(1, 6)]
    # The existing analysis independently parses raw retrieval, checks the saved
    # trace/CSV and boot clock, and rejects incomplete or changed evidence.
    raw = subprocess.check_output(
        [sys.executable, "-m", "open_connect.startup_analysis", *[str(p) for p in paths]], text=True
    )
    verified = {row["trial"]: row for row in map(json.loads, raw.splitlines())}
    summary = []
    samples = []
    io = []
    timings = []
    for condition, root, recorded_condition, pandora, log_level in cohorts:
        for run in range(1, 6):
            path = root / f"trial-{run}"
            proof = verified[str(path)]
            assert proof["condition"] == recorded_condition
            trace = json.loads((path / "trace.json").read_text())
            if pandora is not None or log_level is not None:
                from open_connect.startup_reference import validate_condition

                meta = json.loads((path / "trial.json").read_text())
                if pandora is not None:
                    assert meta["pandora"] == pandora
                if log_level is not None:
                    assert meta["log_level"] == log_level
                before = validate_condition(
                    (path / "preflight.out").read_bytes(), recorded_condition, pandora, log_level
                )
                after = validate_condition(
                    (path / "postflight.out").read_bytes(), recorded_condition, pandora, log_level
                )
                assert before != after and after == trace["boot_id"]
            window = [
                s
                for s in trace["samples"]
                if s["uptime_start_s"] >= 20 and s["uptime_end_s"] <= 170
            ]
            assert len(window) > 100
            memory = []
            previous = None
            for sample in trace["samples"]:
                row = dict(
                    condition=condition,
                    run=run,
                    sample=sample["index"],
                    uptime_start_s=sample["uptime_start_s"],
                    uptime_end_s=sample["uptime_end_s"],
                )
                counters = {}
                for line in sample["files"]["/proc/meminfo"][0].splitlines():
                    parts = line.split()
                    if len(parts) == 3 and parts[2] == "kB":
                        counters[parts[0].rstrip(":")] = int(parts[1])
                for name in [
                    "MemTotal",
                    "MemFree",
                    "MemAvailable",
                    "Buffers",
                    "Cached",
                    "Shmem",
                    "Slab",
                ]:
                    row[name + "_kB"] = counters.get(name, "")
                cpu = [
                    line.split()[1:]
                    for line in sample["files"]["/proc/stat"][0].splitlines()
                    if line.startswith("cpu ")
                ]
                assert len(cpu) == 1 and len(cpu[0]) >= 8
                ticks = list(map(int, cpu[0][:8]))
                for name, value in zip(
                    ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"], ticks
                ):
                    row["cpu_" + name + "_ticks"] = value
                row["cpu_interval_busy_pct"] = ""
                if previous is not None:
                    delta = [b - a for a, b in zip(previous, ticks)]
                    if min(delta) >= 0 and sum(delta) > 0:
                        row["cpu_interval_busy_pct"] = (
                            100 * (sum(delta) - delta[3] - delta[4]) / sum(delta)
                        )
                previous = ticks
                samples.append(row)
                if sample in window:
                    memory.append(row)
            entry = dict(
                condition=condition,
                run=run,
                host_revision=proof["revision"],
                samples=proof["samples"],
                first_sample_uptime_s=proof["first_uptime_s"],
                last_sample_uptime_s=proof["last_uptime_s"],
                window_first_sample_s=proof["window_first_uptime_s"],
                window_last_sample_end_s=proof["window_last_uptime_s"],
                cpu_busy_pct=proof["cpu_busy_percent"],
                trace_output_bytes=proof["trace_bytes"],
                clock_bound_width_s=proof["kernel_zero_host_bounds"][1]
                - proof["kernel_zero_host_bounds"][0],
            )
            for field in ["MemFree", "Cached", "Shmem", "Slab", "Buffers"]:
                values = [r[field + "_kB"] for r in memory]
                entry[field + "_first_kB"] = values[0]
                entry[field + "_last_kB"] = values[-1]
                entry[field + "_min_kB"] = min(values)
                entry[field + "_max_kB"] = max(values)
            summary.append(entry)
            for disk in proof["disk_deltas"]:
                io.append(
                    dict(
                        condition=condition,
                        run=run,
                        window_first_sample_s=proof["window_first_uptime_s"],
                        window_last_sample_end_s=proof["window_last_uptime_s"],
                        **disk,
                    )
                )
            from open_connect.startup_analysis import verified_annotations, verified_clock

            clocks = verified_clock(path, trace["boot_id"])
            for annotation in verified_annotations(path, clocks):
                label = (
                    "home_spaced"
                    if annotation["definition"] == "Home carousel fully spaced"
                    else "carplay_dashboard"
                )
                timings.append(
                    dict(
                        condition=condition,
                        run=run,
                        milestone=label,
                        before_frame=annotation["before_frame"],
                        first_frame=annotation["first_frame"],
                        video_before_s=annotation["video_pts_bounds_s"][0],
                        video_first_s=annotation["video_pts_bounds_s"][1],
                        acc_lower_s=annotation["relative_acc_command_s"][0],
                        acc_upper_s=annotation["relative_acc_command_s"][1],
                        kernel_lower_s=annotation["relative_kernel_s"][0],
                        kernel_upper_s=annotation["relative_kernel_s"][1],
                    )
                )
    for name, rows in [
        ("startup-samples.csv", samples),
        ("startup-runs.csv", summary),
        ("startup-io.csv", io),
        ("startup-timings.csv", timings),
    ]:
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(name, len(rows))


if __name__ == "__main__":
    main()
