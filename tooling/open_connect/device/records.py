"""Strict device records shared by preparation and independent recovery."""

import hashlib
import re

from open_connect.files import posix_cksum


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fp(b):
    return dict(bytes=len(b), md5=hashlib.md5(b).hexdigest(), crc=posix_cksum(b), sha256=sha(b))


def typed_records(raw, prefix):
    out = []
    for line in raw.splitlines(keepends=True):
        n = line.count(prefix)
        if not n:
            continue
        if n != 1 or not line.endswith(b"\n"):
            raise ValueError("partial/duplicate native record")
        r = line[line.index(prefix) :].removesuffix(b"\n").removesuffix(b"\r")
        if any(c < 32 and c != 9 for c in r):
            raise ValueError("record control")
        out.append(r[len(prefix) :].decode("ascii"))
    return out


def code_identity(value, body):
    f = value.split(":")
    if (
        len(f) != 8
        or any(not re.fullmatch("[0-9]+", x) for x in f)
        or f[0] != "45826"
        or int(f[1]) < 1
        or f[3:] != [str(len(body)), "600", "0", "0", "1"]
    ):
        raise ValueError("actual code identity")
    return value
