"""Strict device records shared by preparation and independent recovery."""

import hashlib

from open_connect.files import posix_cksum


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fp(b):
    return dict(bytes=len(b), md5=hashlib.md5(b).hexdigest(), crc=posix_cksum(b), sha256=sha(b))
