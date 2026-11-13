"""Parse startup persistence records; no profile files, device access or side effects."""

import re

FIELDS = {"META", "HASH", "CRC", "ROOT", "UPTIME", "BOOT_ID"}

FIELD_SHAPES = {
    "META": rb"[0-9]+(?::[0-9]+){7}",
    "HASH": rb"[0-9a-f]{32}[ \t]+-",
    "CRC": rb"[0-9]+[ \t]+[0-9]+",
    "ROOT": rb"[^ \t|]+(?:[ \t]+[^ \t|]+){5}",
    "UPTIME": rb"[0-9]+(?:\.[0-9]+)?[ \t]+[0-9]+(?:\.[0-9]+)?",
    "BOOT_ID": rb"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
}


def persistence_fields(raw):
    found = {}
    lines = raw.split(b"\n")
    for index, line in enumerate(lines):
        count = line.count(b"SWST|")
        if not count:
            continue
        if index == len(lines) - 1:
            raise ValueError("unterminated candidate persistence record")
        if count != 1:
            raise ValueError("interleaved candidate persistence markers")
        line = line.removesuffix(b"\r")
        record = line[line.index(b"SWST|") :]
        match = re.fullmatch(rb"SWST\|([A-Z_]+)\|([^|\r\n]*)", record)
        if match is None:
            raise ValueError("malformed candidate persistence record")
        key = match[1].decode("ascii")
        if key not in FIELDS or key in found:
            raise ValueError("unexpected/duplicate candidate persistence field")
        value = match[2].strip(b" \t")
        if any((c < 32 and c != 9) or c == 127 for c in value):
            raise ValueError("control byte in candidate persistence value")
        if re.fullmatch(FIELD_SHAPES[key], value) is None:
            raise ValueError("malformed/partial candidate persistence value")
        found[key] = value.decode("ascii")
    if set(found) != FIELDS:
        raise ValueError("missing/unexpected candidate persistence field")
    return found
