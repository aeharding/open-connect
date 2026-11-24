# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export the declared Wave C cohorts, retaining failed and supplemental attempts.

Usage: python -m open_connect.startup_wave_c PRIVATE_CAPTURE_ROOT OUTPUT_DIR
Primary Home runs are control 2/3/4 and active 3/4/5; control 5 is supplemental.
Reviewed achieved foregrounds differ, so projection_workload_matched is False
throughout. CPU and whole-system RAM rows are descriptive, not an isolated gain.
Raw metrics, clocks and frame arithmetic use the existing independent verifiers.
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from open_connect.startup_analysis import verified_clock
from open_connect.startup_export import timing_rows
from open_connect.startup_reference import validate_condition
from open_connect.startup_wireless import native_events

base = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
tables = {
    k: []
    for k in (
        "attempts",
        "timings",
        "summary",
        "samples",
        "io",
        "own-ram",
        "app-pss",
        "native-services",
        "selector-phases",
        "native-wireless",
    )
}


def mem(s):
    return {
        m[1]: int(m[2])
        for m in re.finditer(r"^([A-Za-z_()]+):\s+(\d+) kB$", s["files"]["/proc/meminfo"][0], re.M)
    }


def busy(a, b, key="cpu"):
    def counters(s):
        return list(
            map(
                int,
                next(
                    x for x in s["files"]["/proc/stat"][0].splitlines() if x.startswith(key + " ")
                ).split()[1:9],
            )
        )

    d = [y - x for x, y in zip(counters(a), counters(b))]
    assert min(d) >= 0 and sum(d) > 0
    return 100 * (sum(d) - d[3] - d[4]) / sum(d)


for cohort in ("control", "active"):
    for p in sorted(
        (p for p in (base / cohort).glob("trial-*") if p.is_dir()),
        key=lambda p: int(p.name.split("-")[-1]),
    ):
        n = int(p.name.split("-")[-1])
        m = json.loads((p / "trial.json").read_text())
        assert m["uart_closed"] and m["relay_closed"] and not m["ui_inputs_sent"]
        hardware = any(e["kind"] == "ACC_ON" for e in m["events"])
        complete = m["outcome"] == "observed"
        primary = (cohort == "control" and n in (2, 3, 4)) or (
            cohort == "active" and n in (3, 4, 5)
        )
        workload = (
            (
                "maps_visible"
                if cohort == "active"
                else ("protocol_active_native_home" if n == 4 else "no_session")
            )
            if complete
            else ("hardware_reset_failure" if hardware else "pre_hardware_tooling_refusal")
        )
        prefix = dict(
            cohort=cohort,
            capture_attempt=n,
            version="dev15" if cohort == "control" else "dev16",
            primary_timing_cohort=primary,
            projection_workload_matched=False,
            achieved_workload=workload,
        )
        markers, events = (
            native_events((p / "rx.bin").read_bytes()) if (p / "rx.bin").exists() else (0, {})
        )
        banners = (
            (p / "rx.bin").read_bytes().count(b"Uncompressing Linux... done, booting the kernel.")
            if (p / "rx.bin").exists()
            else 0
        )
        attempt = dict(
            prefix,
            hardware_attempt=hardware,
            outcome=m["outcome"],
            error=m["error"] or "",
            kernel_boot_banners=banners,
            uart_boot_markers=markers,
            resource_samples=0,
            trace_sha256="",
        )
        if not complete:
            tables["attempts"].append(attempt)
            continue
        proof = json.loads(
            subprocess.check_output(
                [sys.executable, "-m", "open_connect.startup_analysis", str(p)], text=True
            )
        )
        t = json.loads((p / "trace.json").read_text())
        assert proof["trace_sha256"]
        assert (
            validate_condition((p / "postflight.out").read_bytes(), "open-connect", 1, None, 1, 1)
            == t["boot_id"]
        )
        assert (
            validate_condition((p / "preflight.out").read_bytes(), "open-connect", 1, None, 1, 1)
            != t["boot_id"]
        )
        attempt.update(resource_samples=len(t["samples"]), trace_sha256=proof["trace_sha256"])
        tables["attempts"].append(attempt)
        tables["timings"].extend(
            {**prefix, **r} for r in timing_rows(p, cohort, n, verified_clock(p, t["boot_id"]))
        )
        w = [s for s in t["samples"] if s["uptime_start_s"] >= 20 and s["uptime_end_s"] <= 170]
        assert len(w) > 100
        row = dict(
            prefix,
            first_sample_uptime_s=t["samples"][0]["uptime_start_s"],
            last_sample_uptime_s=t["samples"][-1]["uptime_end_s"],
            window_first_uptime_s=w[0]["uptime_start_s"],
            window_last_uptime_s=w[-1]["uptime_end_s"],
            window_samples=len(w),
        )
        row.update({k + "_busy_pct": busy(w[0], w[-1], k) for k in ("cpu", "cpu0", "cpu1")})
        for k in ("MemFree", "Cached", "Shmem", "AnonPages", "Slab", "Buffers"):
            row["min_" + k + "_KiB"] = min(mem(s)[k] for s in w)
            row["last_" + k + "_KiB"] = mem(w[-1])[k]
        tables["summary"].append(row)
        previous = None
        for i, s in enumerate(t["samples"]):
            tables["samples"].append(
                dict(
                    prefix,
                    sample=i,
                    uptime_start_s=s["uptime_start_s"],
                    uptime_end_s=s["uptime_end_s"],
                    in_window=s in w,
                    cpu_interval_busy_pct="" if previous is None else busy(previous, s),
                    **{
                        k + "_KiB": v
                        for k, v in mem(s).items()
                        if k in ("MemFree", "Cached", "Shmem", "AnonPages", "Slab", "Buffers")
                    },
                )
            )
            previous = s
        tables["io"].extend({**prefix, **r} for r in proof["disk_deltas"])
        text = (base / cohort / f"extra-{n}.out").read_text()
        assert f"EXTRA_VERIFIED|{t['boot_id']}" in text
        sm = text.split("SM_EVENTS_BEGIN\n")[1].split("SM_EVENTS_END")[0]
        tables["native-services"].extend(
            dict(prefix, service=r["Component"], event=r["Event"], native_logged_s=r["Timestamp"])
            for r in csv.DictReader(sm.splitlines())
            if r["Event"] in ("SM_SVC_CMD_START", "SM_SVC_CMD_STARTED")
        )
        phases = text.split("NATIVE_SELECTOR_PHASES_BEGIN\n")[1].split(
            "NATIVE_SELECTOR_PHASES_END"
        )[0]
        tables["selector-phases"].extend(
            dict(prefix, phase=line.split("|")[0], kernel_uptime_s=line.split("|")[1])
            for line in phases.splitlines()
        )
        ram = (base / cohort / f"ram-{n}.out").read_text()
        assert ram.endswith("MMUI_VUI_MATCHED_AGE_PSS_COMPLETE\n")
        files = {}
        for line in ram.splitlines():
            if line.startswith("RAM_FILE|"):
                _, path, size, blocks, dev, ino = line.split("|")
                files[dev, ino] = (int(size), int(blocks))
        own = dict(
            prefix,
            snapshot_uptime_s=float(re.search(r"^RAM_UPTIME[|]([0-9.]+)", ram, re.M)[1]),
            regular_files=len(files),
            regular_file_bytes=sum(v[0] for v in files.values()),
            allocated_tmpfs_KiB=sum(v[1] for v in files.values()) // 2,
        )
        for role in ("listener", "ignition"):
            vals = {
                field: int(v)
                for r, pid, field, v in re.findall(
                    r"^RAM_PROCESS_TOTAL[|]([^|]+)[|]([^|]+)[|]([^|]+)[|]([0-9]+)$", ram, re.M
                )
                if r == role
            }
            assert vals
            own[role + "_private_KiB"] = vals["Private_Clean:"] + vals["Private_Dirty:"]
            own[role + "_private_dirty_KiB"] = vals["Private_Dirty:"]
            own[role + "_PSS_KiB"] = vals["Pss:"]
        tables["own-ram"].append(own)
        for app in ("L_jciMMUI", "L_jciVUI", "opera"):
            vals = {
                field: int(v)
                for a, pid, field, v in re.findall(
                    r"^APP_PSS_TOTAL[|]([^|]+)[|]([^|]+)[|]([^|]+)[|]([0-9]+)$", ram, re.M
                )
                if a == app
            }
            assert vals
            at = float(
                re.search(r"^APP_PSS_BEGIN[|]" + app + r"[|][^|]+[|][^|]+[|]([0-9.]+)", ram, re.M)[
                    1
                ]
            )
            tables["app-pss"].append(
                dict(
                    prefix,
                    app=app,
                    snapshot_uptime_s=at,
                    **{k.rstrip(":") + "_KiB": v for k, v in sorted(vals.items())},
                )
            )
        for name, times in events.items():
            for i, at in enumerate(times or [None], 1):
                tables["native-wireless"].append(
                    dict(
                        prefix,
                        event=name,
                        occurrence=i if at is not None else "",
                        native_logged_s=f"{at:.3f}"
                        if at is not None and banners == markers == 1
                        else "",
                        clock_scope="single_boot"
                        if banners == markers == 1
                        else "ambiguous_discard",
                    )
                )
for name, rows in tables.items():
    assert rows, name
    with (out / (name + ".csv")).open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
print(json.dumps({k: len(v) for k, v in tables.items()}))
