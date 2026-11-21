"""Finite, read-only CMU resource traces using an existing trusted SSH alias."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import secrets
import shlex
import subprocess
import time
from pathlib import Path

from open_connect.paths import ROOT, verify_package
from open_connect.session import Bundle, digest

UUID = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"
FILES = ("/proc/meminfo", "/proc/stat", "/proc/vmstat", "/proc/diskstats", "/proc/net/dev")


def process_identity(raw):
    """PID and start ticks, allowing spaces/parentheses in the kernel comm field."""
    match = re.fullmatch(r"([1-9][0-9]*) \((.*)\) (\S) (.*)\n?", raw.strip())
    if not match:
        return None
    fields = match[4].split()  # starts at field 4 (ppid)
    if len(fields) < 19 or not fields[18].isdigit():
        return None
    return {"pid": int(match[1]), "start_ticks": int(fields[18]), "comm": match[2]}


def parse(raw, token, processes=()):
    """Require complete ordered frames; keep unsupported/raced reads explicit."""
    prefix = "OCM1 " + token + " "
    boot, samples, sample, current, complete = None, [], None, None, False
    for line in raw.decode("ascii").splitlines():
        if not line.startswith(prefix):
            if current is not None:
                current.append(line)
            elif boot is not None and line.strip():
                raise ValueError("unexpected output outside a sample")
            continue
        fields = line[len(prefix) :].split()
        if not fields:
            raise ValueError("empty metrics marker")
        kind = fields[0]
        if kind == "boot" and len(fields) == 2 and boot is None:
            if not re.fullmatch(UUID, fields[1]):
                raise ValueError("invalid boot identity")
            boot = fields[1]
        elif kind == "sample" and len(fields) == 3 and boot and sample is None and not complete:
            if int(fields[1]) != len(samples):
                raise ValueError("missing/duplicate sample")
            sample = {"index": int(fields[1]), "uptime_start_s": float(fields[2]), "files": {}}
            current = None
        elif kind == "file" and len(fields) == 2 and sample is not None:
            path = fields[1]
            if path not in FILES and not re.fullmatch(r"/proc/[1-9][0-9]*/(stat|status|io)", path):
                raise ValueError("unexpected proc file")
            current = []
            sample["files"].setdefault(path, []).append(current)
        elif kind == "end" and len(fields) == 3 and sample is not None:
            if int(fields[1]) != sample["index"]:
                raise ValueError("wrong sample end")
            sample["uptime_end_s"] = float(fields[2])
            if not all(
                math.isfinite(sample[k]) for k in ("uptime_start_s", "uptime_end_s")
            ) or not (0 <= sample["uptime_start_s"] <= sample["uptime_end_s"]):
                raise ValueError("invalid uptime bounds")
            if samples and sample["uptime_start_s"] < samples[-1]["uptime_end_s"]:
                raise ValueError("uptime moved backwards")
            for path in FILES:
                blocks = sample["files"].get(path, [])
                if len(blocks) != 1:
                    raise ValueError("missing/duplicate system counter file")
                if "READ_FAILED" in blocks[0]:
                    raise ValueError("system counter read failed; raw evidence retained")
            sample["files"] = {
                path: ["\n".join(block).strip() + "\n" for block in blocks]
                for path, blocks in sample["files"].items()
            }
            identities = {}
            for path, blocks in sample["files"].items():
                if re.fullmatch(r"/proc/[1-9][0-9]*/stat", path):
                    before = process_identity(blocks[0])
                    after = process_identity(blocks[-1])
                    identities[path.split("/")[2]] = {
                        "identity": before,
                        "stable": len(blocks) == 2
                        and before is not None
                        and before == after
                        and before["pid"] == int(path.split("/")[2])
                        and (not processes or before["comm"] in processes),
                    }
            sample["processes"] = identities
            samples.append(sample)
            sample = current = None
        elif kind == "complete" and len(fields) == 2 and sample is None and not complete:
            if int(fields[1]) != len(samples) or not samples:
                raise ValueError("wrong completed sample count")
            complete = True
        else:
            raise ValueError("unexpected metrics frame")
    if not complete or sample is not None:
        raise ValueError("incomplete trace; raw evidence retained")
    return {
        "schema": 1,
        "boot_id": boot,
        "requested_processes": list(processes),
        "samples": samples,
    }


def memory_csv(trace):
    """Preserve kernel units. Missing fields stay empty, never zero."""
    fields = ("MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "Shmem", "Slab")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sample", "uptime_start_s", "uptime_end_s", *(f + "_kB" for f in fields)])
    for sample in trace["samples"]:
        values = {}
        for line in sample["files"]["/proc/meminfo"][0].splitlines():
            match = re.fullmatch(r"([A-Za-z_()]+):\s+([0-9]+) kB", line)
            if match:
                if match[1] in values:
                    raise ValueError("duplicate memory counter")
                values[match[1]] = int(match[2])
        if "MemTotal" not in values or "MemFree" not in values:
            raise ValueError("required memory counters unavailable")
        writer.writerow(
            [
                sample["index"],
                sample["uptime_start_s"],
                sample["uptime_end_s"],
                *(values.get(f, "") for f in fields),
            ]
        )
    return output.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="my-cmu", help="existing SSH host alias")
    parser.add_argument("--ssh-config", type=Path)
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--interval", type=int, default=1, help="minimum pause between samples")
    parser.add_argument("--process", action="append", default=None, help="exact /proc comm name")
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    processes = args.process or ["jci", "opera", "carplayd"]
    if not 1 <= args.seconds <= 600 or not 1 <= args.interval <= 30:
        parser.error("seconds must be 1..600; interval must be 1..30")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host) or any(
        not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,14}", name) for name in processes
    ):
        parser.error("use a plain SSH alias and exact kernel process names")
    if not args.live:
        print(
            json.dumps(
                {
                    "outcome": "dry_run_not_executed",
                    "opens_ssh": False,
                    "seconds": args.seconds,
                    "interval": args.interval,
                    "processes": processes,
                }
            )
        )
        return 0
    if args.bundle is None:
        parser.error("live sampling requires a fresh --bundle")
    verify_package(args.workspace)
    source = (args.workspace / "cmu/bench/metrics.sh").read_bytes()
    bundle = Bundle(args.bundle, "read-only CMU resource trace", "primary", mode="live")
    bundle.save("metrics.sh", source)
    bundle.save("metrics.py", Path(__file__).read_bytes())
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
        + str(args.seconds + 40)
        + " sh -s -- "
        + shlex.join([str(args.seconds), str(args.interval), token, *processes]),
    ]
    bundle.meta.update(
        collector_sha256=digest(source),
        seconds=args.seconds,
        interval=args.interval,
        processes=processes,
        firmware_scope="74.00.324A NA/cmu150_NA",
        startup_hook_installed=False,
        transport="ssh",
        port_closed=True,
    )
    outcome, error, code = "incomplete_preserved", None, 1
    started = time.monotonic()
    try:
        bundle.save("ssh.stdout", b"")
        bundle.save("ssh.stderr", b"")
        with (
            (bundle.path / "ssh.stdout").open("wb") as stdout,
            (bundle.path / "ssh.stderr").open("wb") as stderr,
        ):
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            try:
                process.communicate(source, timeout=args.seconds + 50)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=3)
                bundle.meta["ssh_closed"] = process.poll() is not None
        if process.returncode:
            raise RuntimeError("SSH/collector returned " + str(process.returncode))
        trace = parse((bundle.path / "ssh.stdout").read_bytes(), token, processes)
        csv_data = memory_csv(trace)
        bundle.save("trace.json", (json.dumps(trace, indent=2) + "\n").encode())
        bundle.save("memory.csv", csv_data.encode())
        bundle.meta.update(
            boot_id=trace["boot_id"],
            samples=len(trace["samples"]),
            first_sample_uptime_s=trace["samples"][0]["uptime_start_s"],
            last_sample_uptime_s=trace["samples"][-1]["uptime_end_s"],
        )
        outcome, code = "recorded", 0
    except subprocess.TimeoutExpired:
        error = "Collector deadline exceeded; no retry."
    except (Exception, KeyboardInterrupt) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        bundle.meta["host_elapsed_s"] = time.monotonic() - started
        bundle.finish(outcome, error)
    print(json.dumps({"outcome": outcome, "error": error, "bundle": str(bundle.path)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
