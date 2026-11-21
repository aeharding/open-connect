"""Playground experiment: matched control/collector windows on one idle workload."""

import argparse
import csv
import json
import re
import secrets
import shlex
import subprocess
import sys
import time
from pathlib import Path

from open_connect import metrics
from open_connect.paths import ROOT
from open_connect.session import digest


def summarize(argv):
    parser = argparse.ArgumentParser(description="Export paired CPU results; opens no device.")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = json.loads((args.bundle / "plan.json").read_text())
    windows = json.loads((args.bundle / "windows.json").read_text())
    if len(windows) != 2 * plan["pairs"] or [w["mode"] for w in windows] != plan["order"]:
        raise ValueError("incomplete or reordered batch")
    rows = []
    boot = windows[0]["before"]["boot"]
    for index in range(0, len(windows), 2):
        pair = {}
        for window in windows[index : index + 2]:
            before, after = window["before"], window["after"]
            if before["boot"] != boot or after["boot"] != boot:
                raise ValueError("mixed boot identities")
            delta = [b - a for a, b in zip(before["cpu"], after["cpu"])]
            if len(delta) != 8 or min(delta) < 0 or sum(delta) <= 0:
                raise ValueError("invalid CPU endpoints")
            busy = 100 * (sum(delta) - delta[3] - delta[4]) / sum(delta)
            if abs(busy - window["cpu_busy_pct_excluding_iowait"]) > 1e-9:
                raise ValueError("stored result differs from original counters")
            duration = after["uptime_s"] - before["uptime_s"]
            if duration <= 0:
                raise ValueError("invalid reference duration")
            pair[window["mode"]] = (busy, duration)
        if set(pair) != {"control", "sample"}:
            raise ValueError("incomplete control/sampling pair")
        off, on = pair["control"], pair["sample"]
        rows.append([index // 2, off[0], on[0], on[0] - off[0], off[1], on[1]])
    with args.output.open("x") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "pair",
                "control_cpu_busy_pct",
                "sampling_cpu_busy_pct",
                "difference_pp",
                "control_duration_s",
                "sampling_duration_s",
            ]
        )
        writer.writerows(rows)


def endpoints(raw, token):
    lines = raw.decode("ascii").splitlines()
    result = []
    for kind in ("START", "END"):
        matches = [i for i, line in enumerate(lines) if line.startswith(f"REF {token} {kind} ")]
        if len(matches) != 1:
            raise ValueError("missing/duplicate reference endpoint")
        i = matches[0]
        cpu = [int(v) for v in lines[i + 2].split()[1:9]]
        if len(cpu) != 8 or not lines[i + 2].startswith("cpu "):
            raise ValueError("invalid CPU endpoint")
        result.append(
            {
                "boot": lines[i].split()[-1],
                "uptime_s": float(lines[i + 1].split()[0]),
                "cpu": cpu,
                "MemFree_kB": int(lines[i + 3].split()[1]),
            }
        )
    before, after = result
    if before["boot"] != after["boot"] or not after["uptime_s"] > before["uptime_s"]:
        raise ValueError("boot/clock changed during reference")
    delta = [b - a for a, b in zip(before["cpu"], after["cpu"])]
    if min(delta) < 0 or sum(delta) <= 0:
        raise ValueError("invalid CPU deltas")
    busy = 100 * (sum(delta) - delta[3] - delta[4]) / sum(delta)
    return {"before": before, "after": after, "cpu_busy_pct_excluding_iowait": busy}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--ssh-config", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--interval", type=int, default=1)
    parser.add_argument("--process", action="append", default=[])
    parser.add_argument("--label", required=True, help="fixed workload/configuration")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host):
        parser.error("use an existing SSH alias")
    if not 15 <= args.seconds <= 120 or not 1 <= args.pairs <= 5 or not 1 <= args.interval <= 30:
        parser.error("seconds 15..120, pairs 1..5, interval 1..30")
    args.bundle.mkdir(parents=True, mode=0o700)
    reference = (ROOT / "cmu/bench/metrics-reference.sh").read_bytes()
    plan = {
        "question": "Incremental CPU cost of the complete SSH collector at a fixed idle workload",
        "label": args.label,
        "seconds": args.seconds,
        "pairs": args.pairs,
        "interval": args.interval,
        "processes": args.process,
        "reference_sha256": digest(reference),
        "collector_sha256": digest((ROOT / "cmu/bench/metrics.sh").read_bytes()),
        "order": [
            mode
            for pair in range(args.pairs)
            for mode in (("control", "sample") if pair % 2 == 0 else ("sample", "control"))
        ],
    }
    (args.bundle / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    windows, boot = [], None
    for index, mode in enumerate(plan["order"]):
        path = args.bundle / f"{index}-{mode}"
        path.mkdir(mode=0o700)
        token = secrets.token_hex(16)
        command = [
            "ssh",
            "-T",
            "-oBatchMode=yes",
            "-oStrictHostKeyChecking=yes",
            "-oConnectTimeout=8",
            "-oControlMaster=no",
            "-oControlPath=none",
        ]
        if args.ssh_config:
            command += ["-F", str(args.ssh_config)]
        command += [
            args.host,
            "timeout -t "
            + str(args.seconds + 15)
            + " sh -s -- "
            + shlex.join([token, str(args.seconds)]),
        ]
        print(json.dumps({"window": index, "mode": mode, "status": "started"}), flush=True)
        with (path / "reference.out").open("xb") as out, (path / "reference.err").open("xb") as err:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err)
            try:
                process.stdin.write(reference)
                process.stdin.close()
                deadline = time.monotonic() + 10
                while f"REF {token} START ".encode() not in (path / "reference.out").read_bytes():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("reference did not start; no retry")
                    time.sleep(0.1)
                if mode == "sample":
                    time.sleep(2)
                    options = [
                        "--live",
                        "--host",
                        args.host,
                        "--seconds",
                        str(args.seconds - 5),
                        "--interval",
                        str(args.interval),
                        "--bundle",
                        str(path / "trace"),
                    ]
                    if args.ssh_config:
                        options += ["--ssh-config", str(args.ssh_config)]
                    for name in args.process:
                        options += ["--process", name]
                    if metrics.main(options) != 0:
                        raise RuntimeError("collector did not finish; no retry")
                process.wait(timeout=args.seconds + 15)
                if process.returncode:
                    raise RuntimeError("reference failed; raw data retained")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
        row = endpoints((path / "reference.out").read_bytes(), token)
        boot = boot or row["before"]["boot"]
        if row["before"]["boot"] != boot:
            raise RuntimeError("boot changed across windows")
        if mode == "sample":
            trace = json.loads((path / "trace/trace.json").read_text())
            if not (
                row["before"]["uptime_s"] <= trace["samples"][0]["uptime_start_s"]
                and trace["samples"][-1]["uptime_end_s"] <= row["after"]["uptime_s"]
            ):
                raise RuntimeError("collector escaped reference window")
        row.update(window=index, mode=mode)
        windows.append(row)
        (args.bundle / "windows.json").write_text(json.dumps(windows, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "window": index,
                    "mode": mode,
                    "cpu_busy_pct": row["cpu_busy_pct_excluding_iowait"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    if sys.argv[1:2] == ["summarize"]:
        summarize(sys.argv[2:])
    else:
        main()
