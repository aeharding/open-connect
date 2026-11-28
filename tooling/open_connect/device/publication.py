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
        q = shlex.quote(path)
        qsid = shlex.quote(sid)
        guards.extend(
            [
                f'test -d {q} && test ! -L {q} && test "$(readlink -f {q})" = {q} || die parent',
                f'test "$(stat -c "%d:%i:%a:%u:%g" {q})" = {qsid} || die parent_identity',
            ]
        )
    vals["PARENT_GUARDS"] = "\n".join(guards)
    s = (ROOT / "cmu/startup/publication.sh.in").read_text()
    s = re.sub(
        r"@([A-Z_]+)@",
        lambda m: vals[m[1]] if m[1] == "PARENT_GUARDS" else shlex.quote(vals[m[1]]),
        s,
    )
    subprocess.run(["/bin/sh", "-n"], input=s.encode(), check=True, timeout=10)
    if len(s.encode()) > 16384:
        raise ValueError("staging bound")
    return s
