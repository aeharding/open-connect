"""Playground: five serial starts using the qualified finite observer."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--ssh-config", type=Path)
    parser.add_argument("--condition", choices=["stock", "open-connect"], required=True)
    parser.add_argument("--package")
    parser.add_argument("--pandora", type=int, choices=[0, 1])
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument("--log-level", choices=["Info", "Warn"])
    logging.add_argument("--base", type=int, choices=[0, 1])
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"outcome": "dry_run", "starts": 5, "device_opened": False}))
        return
    args.bundle.mkdir(mode=0o700)
    (args.bundle / "batch.json").write_text(json.dumps(vars(args), default=str, indent=2) + "\n")
    common = ["--live", "--host", args.host]
    if args.ssh_config:
        common += ["--ssh-config", str(args.ssh_config)]
    condition = ["--condition", args.condition]
    if args.package:
        condition += ["--package", args.package]
    if args.pandora is not None:
        condition += ["--pandora", str(args.pandora)]
    if args.log_level is not None:
        condition += ["--log-level", args.log_level]
    if args.base is not None:
        condition += ["--base", str(args.base)]
    for number in range(1, 6):
        trial = args.bundle / f"trial-{number}"
        print(json.dumps({"start": number, "condition": args.condition}), flush=True)
        with (args.bundle / f"trial-{number}.log").open("xb") as output:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "open_connect.startup_reference",
                    *common,
                    *condition,
                    "--bundle",
                    str(trial),
                    "--label",
                    "Declared BASE-COMPARISON.md batch"
                    if args.base is not None
                    else "Declared LOGGING-PREFILTER.md batch"
                    if args.log_level is not None
                    else (
                        "Declared SERVICES-COMPARISON.md batch"
                        if args.pandora is not None
                        else "Declared STARTUP-COMPARISON.md batch"
                    ),
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                check=True,
            )
        trace = json.loads((trial / "trace.json").read_text())
        with (args.bundle / f"clock-{number}.log").open("xb") as output:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "open_connect.clock_reference",
                    *common,
                    "--expect-boot",
                    trace["boot_id"],
                    "--bundle",
                    str(args.bundle / f"clock-{number}"),
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                check=True,
            )
        print(json.dumps({"completed": number, "boot": trace["boot_id"]}), flush=True)


if __name__ == "__main__":
    main()
