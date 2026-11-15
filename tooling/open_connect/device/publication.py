"""Render linked-file publication and its independently guarded entry."""

import re
import shlex
import subprocess

from open_connect.paths import ROOT


def render(target, d, hold_o, hold_c, stage, oid, parents, original, candidate):
    o = original
    c = candidate
    vals = {
        "TARGET": target,
        "DIRECTORY": d,
        "HOLD_O": hold_o,
        "HOLD_C": hold_c,
        "STAGE": stage,
        "ORIGINAL_ID": oid,
        "ORIGINAL_HASH": o["md5"],
        "CANDIDATE_HASH": c["md5"],
        "ORIGINAL_CRC": str(o["crc"]),
        "CANDIDATE_CRC": str(c["crc"]),
        "ORIGINAL_SIZE": str(o["bytes"]),
        "CANDIDATE_SIZE": str(c["bytes"]),
    }
    guards = []
    for path, sid in parents.items():
        guards.extend(
            [
                f'test -d {path} && test ! -L {path} && test "$(readlink -f {path})" = {path} || die parent',
                f'test "$(stat -c "%d:%i:%a:%u:%g" {path})" = "{sid}" || die parent_identity',
            ]
        )
    vals["PARENT_GUARDS"] = "\n".join(guards)
    s = (ROOT / "cmu/startup/publication.sh.in").read_text()
    s = re.sub(
        r"@([A-Z_]+)@",
        lambda m: vals[m[1]] if m[1] == "PARENT_GUARDS" else shlex.quote(vals[m[1]]),
        s,
    )
    subprocess.run(["/bin/sh", "-n"], input=s.encode(), check=True)
    if len(s.encode()) > 16384:
        raise ValueError("staging bound")
    return s


def bound_entry(p, code, mode):
    return f"""d={p["directory"]}
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = '{code["directory"]}' || exit 71
p="$d/recovery.sh"
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{code["identity"]}' || exit 73
test "$(md5sum < "$p")" = '{p["body"]["md5"]}  -' || exit 74
test "$(cksum < "$p")" = '{p["body"]["crc"]} {p["body"]["bytes"]}' || exit 75
/bin/sh "$p" {mode} </dev/null
"""
