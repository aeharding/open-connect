#!/usr/bin/env python3
"""Run an explicit command in the already authenticated bench UART shell."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import time

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True)
    parser.add_argument("--label", default="console-command")
    parser.add_argument("--wait", type=float, default=5)
    args = parser.parse_args()
    if not 0 < args.wait <= 30:
        parser.error("--wait must be between 0 and 30 seconds")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label):
        parser.error("--label must contain letters, numbers, hyphens or underscores")
    found = [p for p in list_ports.comports()
             if p.vid == 0x0403 and p.pid == 0x6001 and p.serial_number == "A9048JM0"]
    if len(found) != 1:
        parser.error("The known FTDI adapter is not uniquely enumerated")
    token = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S.%f%z")
    prefix = str(ROOT / "logs" / f"{token}-{args.label}")
    report = {"started_at": datetime.now().astimezone().isoformat(), "port": found[0].device,
              "command": args.command, "command_sent": False, "raw_log": prefix + ".bin"}
    received = bytearray()
    connection = serial.Serial(port=None, baudrate=115200, bytesize=8, parity="N", stopbits=1,
                               timeout=0.2, write_timeout=1, xonxoff=False, rtscts=False,
                               dsrdtr=False, exclusive=True)
    connection.dtr = False
    connection.rts = False
    result = 0
    try:
        with open(prefix + ".bin", "xb") as raw, open(prefix + ".jsonl", "x") as events:
            def record(direction, data):
                events.write(json.dumps({"at": datetime.now().astimezone().isoformat(),
                                         "direction": direction, "hex": data.hex()}) + "\n")
                events.flush()
                if direction == "rx":
                    received.extend(data)
                    raw.write(data)
                    raw.flush()

            def send(data):
                count = connection.write(data)
                connection.flush()
                if count != len(data):
                    raise OSError("Incomplete serial write")
                record("tx", data)

            def read_for(seconds):
                data = bytearray()
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    chunk = connection.read(min(max(connection.in_waiting, 1), 4096))
                    if chunk:
                        record("rx", chunk)
                        data.extend(chunk)
                return bytes(data)

            connection.port = found[0].device
            connection.open()
            send(b"\r")
            initial = read_for(1.5)
            if b"cmu login:" in initial or not re.search(rb"(?:^|[\r\n])[^\r\n]{0,60}[#$] ", initial):
                raise ValueError("No authenticated shell prompt; command was not sent")
            send(args.command.encode("ascii") + b"\r")
            report["command_sent"] = True
            read_for(args.wait)
            report["status"] = "command capture finished"
    except (OSError, ValueError, serial.SerialException) as exc:
        report.update(status="failed", error=str(exc))
        result = 1
    finally:
        connection.close()
        report.update(ended_at=datetime.now().astimezone().isoformat(), bytes_received=len(received))
        Path(prefix + ".json").write_text(json.dumps(report, indent=2) + "\n")
        Path(prefix + ".txt").write_bytes(received)
    text = bytes(received).decode("utf-8", errors="replace")
    print(json.dumps(report, indent=2))
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    visible = "\n".join(line for line in clean.splitlines()
                        if not re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3} ", line))
    print("Escaped response (runtime log lines omitted):", repr(visible[:18000]))
    if len(visible) > 18000:
        print("Response display truncated; complete bytes are in the saved log.")
    print(prefix + ".txt")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
