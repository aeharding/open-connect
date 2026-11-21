# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export numeric native UART events from completed wireless startup trials.

Times retain the native logger's origin. They are not camera/ACC timestamps or
proof of usable projection. Log bodies and phone identifiers are never exported.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

BOOT_MARKER = b"syslog-ng starting up;"
EVENTS = {
    "dhcp_server_started": b"udhcpd (v1.19.2) started",
    "wifi_authenticated": b"IEEE 802.11: authenticated",
    "wifi_associated": b"IEEE 802.11: associated",
    "wifi_key_handshake": b"WPA: pairwise key handshake completed",
    "carplay_control_started": b"CarPlayControlClientStart: 0/0x0 noErr",
    "carplay_control_connected": b"CarPlayControlClientConnect succeeded: 0/0x0 noErr",
    "carplay_session_started": b"_CarPlayHandleSessionStartedAsync",
    "mmui_session_active_event": b"SessionActiveCP",
}
STAMP = re.compile(rb"^([0-9]{2}):([0-5][0-9]):([0-5][0-9])\.([0-9]{3})\s+(.*)$")


def native_events(raw):
    """Keep repeats; absent or ambiguous boot boundaries yield no event times."""
    count = raw.count(BOOT_MARKER)
    events = {name: [] for name in EVENTS}
    if count != 1:
        return count, events
    anchor = raw.index(BOOT_MARKER)
    start = raw.rfind(b"\n", 0, anchor) + 1
    for line in raw[start:].splitlines():
        match = STAMP.fullmatch(line.strip(b"\r"))
        if not match:
            continue
        hours, minutes, seconds, millis, message = match.groups()
        at = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
        for name, marker in EVENTS.items():
            if marker in message:
                events[name].append(at)
    return count, events


def trial_rows(path, number):
    meta = json.loads((path / "trial.json").read_text())
    outcome = meta.get("outcome")
    if outcome not in ("observed", "incomplete_preserved"):
        raise ValueError("trial is not finished")
    boots = {
        event.get("boot_id")
        for event in meta.get("events", [])
        if event.get("kind") == "trace_retrieved"
        and re.fullmatch(r"[a-f0-9-]{36}", str(event.get("boot_id")))
    }
    count, events = native_events((path / "rx.bin").read_bytes())
    scope = (
        "single_boot" if count == 1 else "missing_boot_marker" if count == 0 else "ambiguous_boots"
    )
    condition = (
        "base_off" if meta.get("base") == 0 else "base_on" if meta.get("base") == 1 else "unknown"
    )
    for name, times in events.items():
        for occurrence, at in enumerate(times or [None], 1):
            yield {
                "condition": condition,
                "trial": number,
                "boot_id": next(iter(boots)) if len(boots) == 1 else "",
                "observer_outcome": outcome,
                "uart_boot_markers": count,
                "capture_scope": scope,
                "event": name,
                "native_logged_s": "" if at is None else f"{at:.3f}",
                "occurrence": "" if at is None else occurrence,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trials", type=Path, nargs="+")
    args = parser.parse_args()
    writer = None
    for number, path in enumerate(args.trials, 1):
        trial = re.fullmatch(r"trial-([1-9][0-9]*)", path.name)
        for row in trial_rows(path, int(trial[1]) if trial else number):
            if writer is None:
                writer = csv.DictWriter(sys.stdout, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)


if __name__ == "__main__":
    main()
