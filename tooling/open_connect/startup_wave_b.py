# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export the Wave B complete-preset captures; retain unmatched attempts.

Usage: python -m open_connect.startup_wave_b PRIVATE_CAPTURE_ROOT OUTPUT_DIR
Only rows with included_in_matched=True belong in the matched comparison.
The supplementary clock/SM/RAM files must be collected in the same boot.
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
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
rows = {
    name: []
    for name in (
        "attempts",
        "summary",
        "samples",
        "timings",
        "io",
        "io-windows",
        "selector-phases",
        "native-services",
        "service-states",
        "native-wireless",
        "cpu-windows",
        "own-ram",
    )
}


def mem(s):
    return {
        m[1]: int(m[2])
        for m in re.finditer(r"^([A-Za-z_()]+):\s+(\d+) kB$", s["files"]["/proc/meminfo"][0], re.M)
    }


def cpu(s, key="cpu"):
    return list(
        map(
            int,
            next(
                x for x in s["files"]["/proc/stat"][0].splitlines() if x.startswith(key + " ")
            ).split()[1:9],
        )
    )


def busy(a, b, key="cpu"):
    d = [y - x for x, y in zip(cpu(a, key), cpu(b, key))]
    assert min(d) >= 0 and sum(d) > 0
    return 100 * (sum(d) - d[3] - d[4]) / sum(d)


def ram_fields(ram):
    assert ram.endswith("RAM_READ_ONLY_PROBE_COMPLETE\n")
    files = {}
    for line in ram.splitlines():
        if line.startswith("RAM_FILE|"):
            _, path, size, blocks, dev, ino = line.split("|")
            files[(dev, ino)] = (int(size), int(blocks))
    own = {
        "snapshot_uptime_s": float(re.search(r"^RAM_UPTIME[|]([0-9.]+)", ram, re.M)[1]),
        "regular_files": len(files),
        "regular_file_bytes": sum(x[0] for x in files.values()),
        "allocated_tmpfs_KiB": sum(x[1] for x in files.values()) // 2,
    }
    for role in ("listener", "ignition"):
        totals = {
            field: int(value)
            for r, pid, field, value in re.findall(
                r"^RAM_PROCESS_TOTAL[|]([^|]+)[|]([^|]+)[|]([^|]+)[|]([0-9]+)$", ram, re.M
            )
            if r == role
        }
        assert totals, role
        own[role + "_private_KiB"] = totals["Private_Clean:"] + totals["Private_Dirty:"]
        own[role + "_PSS_KiB"] = totals["Pss:"]
    return own


for cohort in ("control", "active"):
    matched_run = 0
    for n in sorted(int(p.name.removeprefix("trial-")) for p in (base / cohort).glob("trial-*")):
        qualification = base / cohort / f"trial-{n}" / "workload-qualification.json"
        matched = (
            not qualification.exists()
            or json.loads(qualification.read_text())["qualified_for_matched_comparison"]
        )
        if matched:
            matched_run += 1
        run = matched_run if matched else 0
        p = base / cohort / f"trial-{n}"
        meta = json.loads((p / "trial.json").read_text())
        prefix = {
            "cohort": cohort,
            "run": run,
            "capture_attempt": n,
            "included_in_matched": matched,
            "version": "dev14" if cohort == "control" else "dev15",
        }
        assert (
            meta["condition"] == "open-connect"
            and meta["base"] == meta["wireless"] == meta["pandora"] == 1
        )
        assert meta["uart_closed"] and meta["relay_closed"] and meta.get("ui_inputs_sent") is False
        raw = (p / "rx.bin").read_bytes()
        banners = raw.count(b"Uncompressing Linux... done, booting the kernel.")
        markers, events = native_events(raw)
        camera = json.loads((p / "camera-result.json").read_text())
        assert camera["video_verified"]
        attempt = {
            **prefix,
            "acquisition_order": n + (0 if cohort == "control" else 3),
            "workload_qualification": "matched_light_maps"
            if matched
            else "operator_wrong_foreground_app",
            "outcome": meta["outcome"],
            "camera_verified": True,
            "kernel_boot_banners": banners,
            "uart_boot_markers": markers,
            "resource_samples": "",
            "trace_sha256": "",
        }
        if meta["outcome"] != "observed":
            rows["attempts"].append(attempt)
            continue
        proof = json.loads(
            subprocess.check_output(
                [sys.executable, "-m", "open_connect.startup_analysis", str(p)], text=True
            )
        )
        t = json.loads((p / "trace.json").read_text())
        assert (
            validate_condition((p / "postflight.out").read_bytes(), "open-connect", 1, None, 1, 1)
            == t["boot_id"]
        )
        assert (
            validate_condition((p / "preflight.out").read_bytes(), "open-connect", 1, None, 1, 1)
            != t["boot_id"]
        )
        attempt.update(resource_samples=len(t["samples"]), trace_sha256=proof["trace_sha256"])
        rows["attempts"].append(attempt)
        clocks = verified_clock(p, t["boot_id"])
        rows["timings"].extend({**prefix, **row} for row in timing_rows(p, cohort, run, clocks))
        w = [s for s in t["samples"] if s["uptime_start_s"] >= 20 and s["uptime_end_s"] <= 170]
        assert len(w) > 100
        row = {
            **prefix,
            "first_sample_uptime_s": t["samples"][0]["uptime_start_s"],
            "last_sample_uptime_s": t["samples"][-1]["uptime_end_s"],
            "window_first_uptime_s": w[0]["uptime_start_s"],
            "window_last_uptime_s": w[-1]["uptime_end_s"],
            "window_samples": len(w),
        }
        for key in ("cpu", "cpu0", "cpu1"):
            row[key + "_busy_pct"] = busy(w[0], w[-1], key)
        for key in ("MemFree", "Cached", "Shmem", "AnonPages", "Slab", "Buffers"):
            row["min_" + key + "_KiB"] = min(mem(s)[key] for s in w)
            row["last_" + key + "_KiB"] = mem(w[-1])[key]
        rows["summary"].append(row)
        for lo, hi in ((20, 60), (60, 170)):
            split = [
                s for s in t["samples"] if s["uptime_start_s"] >= lo and s["uptime_end_s"] <= hi
            ]
            rows["cpu-windows"].append(
                {
                    **prefix,
                    "analysis": "post_hoc",
                    "nominal_start_s": lo,
                    "nominal_end_s": hi,
                    "first_uptime_s": split[0]["uptime_start_s"],
                    "last_uptime_s": split[-1]["uptime_end_s"],
                    "cpu_busy_pct": busy(split[0], split[-1]),
                }
            )
        previous = None
        for i, s in enumerate(t["samples"]):
            rows["samples"].append(
                {
                    **prefix,
                    "sample": i,
                    "uptime_start_s": s["uptime_start_s"],
                    "uptime_end_s": s["uptime_end_s"],
                    "in_window": s in w,
                    "cpu_interval_busy_pct": "" if previous is None else busy(previous, s),
                    **{
                        key + "_KiB": value
                        for key, value in mem(s).items()
                        if key in ("MemFree", "Cached", "Shmem", "AnonPages", "Slab", "Buffers")
                    },
                }
            )
            previous = s
        rows["io"].extend({**prefix, **r} for r in proof["disk_deltas"])
        extra = base / cohort / f"extra-{n}.out"
        text = extra.read_text()
        native_prefix = {**prefix, "extra_receipt": "same_boot_verified"}
        assert f"EXTRA_VERIFIED|{t['boot_id']}" in text
        phases = text.split("NATIVE_SELECTOR_PHASES_BEGIN\n")[1].split(
            "NATIVE_SELECTOR_PHASES_END"
        )[0]
        rows["selector-phases"].extend(
            {**native_prefix, "phase": line.split("|")[0], "kernel_uptime_s": line.split("|")[1]}
            for line in phases.splitlines()
        )
        sm = text.split("SM_EVENTS_BEGIN\n")[1].split("SM_EVENTS_END")[0]
        names = {
            "open_connect_gap2",
            "stage_gap2",
            "jciVBS",
            "system_mazda_my14",
            "jciEem",
            "jciVwm",
            "jciDriverid",
            "jciblmVdt",
            "jciIdm",
            "jciVdtcon",
            "jciUpdateS",
            "jciUpdatea",
            "jcifav",
            "jciTestDiag",
            "jciUSBM",
            "jcinavi",
            "JVMM",
            "jciusbdtc",
            "stage_1",
            "stage_3",
            "settings",
            "jciMMUI",
            "jciUSBMGR",
            "bds",
            "dmserver",
            "start_network",
            "start_wifi",
            "jciCARPLAY",
            "open_connect_settings",
            "blm_ira_aha",
            "offboard_service",
            "irs_server",
            "blm_ira_pandora",
            "jcidvd",
            "jciSXMS",
            "jciXMMGR",
        }
        rows["native-services"].extend(
            {
                **native_prefix,
                "service": r["Component"],
                "event": r["Event"],
                "native_logged_s": r["Timestamp"],
            }
            for r in csv.DictReader(sm.splitlines())
            if r["Component"] in names and r["Event"] in ("SM_SVC_CMD_START", "SM_SVC_CMD_STARTED")
        )
        for match in re.finditer(r"^SERVICE[|]([^|]+)[|]([^|]+)[|]expected=([^\n]+)$", text, re.M):
            assert match[2] == match[3]
            rows["service-states"].append({**prefix, "service": match[1], "state": match[2]})
        ram = (base / cohort / f"ram-{n}.out").read_text()
        assert ram.endswith("RAM_READ_ONLY_PROBE_COMPLETE\n")
        own = {**prefix, "base": 1, **ram_fields(ram)}
        rows["own-ram"].append(own)
        for lo, hi in ((20, 60), (60, 170)):
            split = [
                s for s in t["samples"] if s["uptime_start_s"] >= lo and s["uptime_end_s"] <= hi
            ]

            def disks(sample):
                return {
                    r.split()[2]: list(map(int, r.split()[3:]))
                    for r in sample["files"]["/proc/diskstats"][0].splitlines()
                    if len(r.split()) >= 14
                }

            first, last = disks(split[0]), disks(split[-1])
            for device in ("ffx01", "ffx01p1", "ffx01p4"):
                before, after = first[device], last[device]
                rows["io-windows"].append(
                    {
                        **prefix,
                        "analysis": "post_hoc",
                        "nominal_start_s": lo,
                        "nominal_end_s": hi,
                        "first_uptime_s": split[0]["uptime_start_s"],
                        "last_uptime_s": split[-1]["uptime_end_s"],
                        "device": device,
                        "read_requests": after[0] - before[0],
                        "read_sectors": after[2] - before[2],
                        "read_MiB": (after[2] - before[2]) / 2048,
                        "write_sectors": after[6] - before[6],
                    }
                )
        for name, times in events.items():
            for occurrence, at in enumerate(times or [None], 1):
                rows["native-wireless"].append(
                    {
                        **prefix,
                        "clock_scope": "single_boot"
                        if banners == markers == 1
                        else "ambiguous_discard",
                        "event": name,
                        "occurrence": occurrence if at is not None else "",
                        "native_logged_s": f"{at:.3f}"
                        if at is not None and banners == markers == 1
                        else "",
                    }
                )
sanity = base / "base0-final-ram.out"
if sanity.exists():
    rows["own-ram"].append(
        {
            "cohort": "base0_sanity",
            "run": 1,
            "capture_attempt": "not_timed",
            "included_in_matched": False,
            "version": "dev15",
            "base": 0,
            **ram_fields(sanity.read_text()),
        }
    )

for name, data in rows.items():
    assert data, name
    with (output / (name + ".csv")).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
print(json.dumps({name: len(data) for name, data in rows.items()}))
