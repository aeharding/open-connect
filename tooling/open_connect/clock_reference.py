"""Playground: bound one CMU boot epoch in the host monotonic clock, read-only."""

import argparse
import json
import math
import re
import secrets
import shlex
import signal
import subprocess
import time
from pathlib import Path

from open_connect.paths import ROOT
from open_connect.session import Bundle


def bounds(exchanges):
    """Allow ±10 ms for the hundredth-second /proc/uptime representation."""
    intervals = []
    for row in exchanges:
        before, after, uptime = row["before_s"], row["after_s"], row["uptime_s"]
        if not all(math.isfinite(v) for v in (before, after, uptime)) or not (
            after >= before and uptime >= 0
        ):
            raise ValueError("invalid exchange")
        intervals.append((before - uptime - 0.01, after - uptime + 0.01))
    if not intervals:
        raise ValueError("no exchanges")
    lower, upper = max(v[0] for v in intervals), min(v[1] for v in intervals)
    if lower > upper:
        raise ValueError("clock bounds disagree")
    return {
        "kernel_zero_host_lower_s": lower,
        "kernel_zero_host_upper_s": upper,
        "width_s": upper - lower,
        "uptime_quantization_allowance_s": 0.01,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="my-cmu")
    parser.add_argument("--ssh-config", type=Path)
    parser.add_argument("--expect-boot", required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host) or not re.fullmatch(
        r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", args.expect_boot
    ):
        parser.error("expected a trusted alias and a complete boot UUID")
    if not args.live:
        print(json.dumps({"outcome": "dry_run", "ssh_opened": False}))
        return
    if args.bundle is None:
        parser.error("live requires a fresh --bundle")
    bundle = Bundle(args.bundle, "read-only kernel/host clock bridge", "primary", mode="live")
    source = (ROOT / "cmu/bench/clock-reference.sh").read_bytes()
    bundle.save("clock-reference.sh", source)
    bundle.save("clock_reference.py", Path(__file__).read_bytes())
    command = [
        "ssh",
        "-T",
        "-oBatchMode=yes",
        "-oStrictHostKeyChecking=yes",
        "-oConnectTimeout=2",
        "-oControlMaster=no",
        "-oControlPath=none",
    ]
    if args.ssh_config:
        command += ["-F", str(args.ssh_config)]
    command += [
        args.host,
        "timeout -t 12 sh -c "
        + shlex.quote(source.decode())
        + " clock-reference "
        + shlex.quote(args.expect_boot),
    ]
    process, exchanges, raw = None, [], bytearray()
    error = None

    def alarm(*_):
        raise TimeoutError("clock query deadline")

    previous = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(18)
    try:
        bundle.save("ssh.stderr", b"")
        with (bundle.path / "ssh.stderr").open("wb") as stderr:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, bufsize=0
            )

            def line():
                value = process.stdout.readline()
                raw.extend(value)
                if not value:
                    raise RuntimeError("clock stream ended early")
                return value.strip()

            while line() != b"BOOT_CLOCK_READY|" + args.expect_boot.encode():
                pass
            for _ in range(7):
                token = secrets.token_hex(16)
                before = time.monotonic()
                process.stdin.write(token.encode() + b"\n")
                process.stdin.flush()
                reply = line()
                if reply == b"":
                    reply = line()
                after = time.monotonic()
                match = re.fullmatch(
                    rb"BOOT_CLOCK_REPLY\|" + token.encode() + rb"\|([0-9.]+) ([0-9.]+)", reply
                )
                if not match:
                    raise RuntimeError("unexpected clock reply")
                exchanges.append(
                    {"before_s": before, "after_s": after, "uptime_s": float(match[1])}
                )
            process.stdin.close()
            process.wait(timeout=3)
            raw.extend(process.stdout.read())
            if process.returncode:
                raise RuntimeError("clock command failed")
        result = {"boot": args.expect_boot, "exchanges": exchanges, **bounds(exchanges)}
        bundle.save("clock-bounds.json", (json.dumps(result, indent=2) + "\n").encode())
    except BaseException as exc:
        error = repr(exc)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        bundle.save("ssh.stdout", bytes(raw))
        bundle.meta["ssh_closed"] = process is None or process.poll() is not None
        bundle.finish("bounded" if error is None else "incomplete_preserved", error)
    if error:
        raise SystemExit(error)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
