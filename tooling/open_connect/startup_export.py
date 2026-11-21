# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export reviewed numeric fields; wireless attempts retain partial observations."""


def timing_rows(path, condition, run, clocks, postflight_verified=None):
    from open_connect.startup_analysis import verified_annotations

    for annotation in verified_annotations(path, clocks):
        kernel = annotation["relative_kernel_s"]
        row = dict(
            condition=condition,
            run=run,
            milestone="home_spaced"
            if annotation["definition"] == "Home carousel fully spaced"
            else "carplay_dashboard",
            before_frame=annotation["before_frame"],
            first_frame=annotation["first_frame"],
            video_before_s=annotation["video_pts_bounds_s"][0],
            video_first_s=annotation["video_pts_bounds_s"][1],
            acc_lower_s=annotation["relative_acc_command_s"][0],
            acc_upper_s=annotation["relative_acc_command_s"][1],
            kernel_lower_s="" if kernel is None else kernel[0],
            kernel_upper_s="" if kernel is None else kernel[1],
        )
        if postflight_verified is not None:
            row["condition_postflight_verified"] = postflight_verified
        yield row


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
    comparison.add_argument("--base-optimizations", action="store_true")
    comparison.add_argument("--wireless", action="store_true")
    args = parser.parse_args()
    base = args.base.resolve()
    output = args.output
    output.mkdir(mode=0o700)
    if args.wireless:
        cohorts = [
            ("wireless-base-off", base / "wireless-base-off", "open-connect", 1, None, 0),
            ("wireless-base-on", base / "wireless-base-on", "open-connect", 1, None, 1),
        ]
    elif args.base_optimizations:
        cohorts = [
            ("base-on", base / "base-on", "open-connect", 1, None, 1),
            ("base-off", base / "base-off", "open-connect", 1, None, 0),
        ]
    elif args.logging:
        cohorts = [
            ("logging-info", base / "logging-info", "stock", None, "Info", None),
            ("logging-warn", base / "logging-warn", "stock", None, "Warn", None),
        ]
    elif args.services:
        cohorts = [
            ("pandora-on", base / "pandora-on", "open-connect", 1, None, None),
            ("pandora-off", base / "pandora-off", "open-connect", 0, None, None),
        ]
    else:
        cohorts = [
            ("stock", base / "stock", "stock", None, None, None),
            ("open-connect", base / "open-connect-matched", "open-connect", None, None, None),
        ]
    paths = [root / f"trial-{n}" for _, root, _, _, _, _ in cohorts for n in range(1, 6)]
    metadata = {p: json.loads((p / "trial.json").read_text()) for p in paths}
    assert all(
        meta.get("outcome") in ("observed", "incomplete_preserved") for meta in metadata.values()
    )
    complete = [p for p in paths if metadata[p]["outcome"] == "observed"]
    if not args.wireless:
        assert complete == paths
    # The existing analysis independently parses raw retrieval, checks the saved
    # trace/CSV and boot clock, and rejects incomplete or changed evidence.
    raw = subprocess.check_output(
        [sys.executable, "-m", "open_connect.startup_analysis", *[str(p) for p in complete]],
        text=True,
    )
    verified = {row["trial"]: row for row in map(json.loads, raw.splitlines())}
    summary = []
    samples = []
    io = []
    timings = []
    attempts = []
    for condition, root, recorded_condition, pandora, log_level, base_choice in cohorts:
        for run in range(1, 6):
            path = root / f"trial-{run}"
            if args.wireless:
                from open_connect.startup_reference import validate_condition

                meta = metadata[path]
                assert meta["condition"] == recorded_condition and meta["base"] == base_choice
                assert meta["wireless"] == 1 and meta["pandora"] == 1
                # A failed fetch still needs independent evidence that the
                # declared policy was applied before its ACC attempt.
                validate_condition(
                    (path / "preflight.out").read_bytes(),
                    recorded_condition,
                    pandora,
                    None,
                    base_choice,
                    1,
                )
                camera = json.loads((path / "camera-result.json").read_text())
                assert camera["video_verified"] is True
                attempts.append(
                    dict(
                        condition=condition,
                        run=run,
                        host_revision=meta["revision"],
                        observer_outcome=meta["outcome"],
                        resource_trace_present=(path / "trace.json").exists(),
                        resource_postflight_verified=str(path) in verified,
                        camera_verified=True,
                    )
                )
                if str(path) not in verified:
                    # Keep valid camera/ACC observations from an incomplete
                    # retrieval without inventing RAM, clock or postflight data.
                    timings.extend(timing_rows(path, condition, run, None, False))
                    continue
            proof = verified[str(path)]
            assert proof["condition"] == recorded_condition
            trace = json.loads((path / "trace.json").read_text())
            if pandora is not None or log_level is not None or base_choice is not None:
                from open_connect.startup_reference import validate_condition

                meta = json.loads((path / "trial.json").read_text())
                if pandora is not None:
                    assert meta["pandora"] == pandora
                if log_level is not None:
                    assert meta["log_level"] == log_level
                if base_choice is not None:
                    assert meta["base"] == base_choice
                before = validate_condition(
                    (path / "preflight.out").read_bytes(),
                    recorded_condition,
                    pandora,
                    log_level,
                    base_choice,
                    1 if args.wireless else None,
                )
                after = validate_condition(
                    (path / "postflight.out").read_bytes(),
                    recorded_condition,
                    pandora,
                    log_level,
                    base_choice,
                    1 if args.wireless else None,
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
            from open_connect.startup_analysis import verified_clock

            clocks = verified_clock(path, trace["boot_id"])
            timings.extend(
                timing_rows(path, condition, run, clocks, True if args.wireless else None)
            )
    exports = [
        ("startup-samples.csv", samples),
        ("startup-runs.csv", summary),
        ("startup-io.csv", io),
        ("startup-timings.csv", timings),
    ]
    if args.wireless:
        exports.append(("startup-attempts.csv", attempts))
    for name, rows in exports:
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(name, len(rows))


if __name__ == "__main__":
    main()
