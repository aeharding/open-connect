"""Strict small-file transfer: allowlisted regular paths, no remote staging writes."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import shlex

from .session import ProtocolError, check_nonce, digest, nonce, wrap_command

ALLOWLIST = ("/jci/version.ini", "/etc/version")
MAX_BYTES = 16384
CHUNK_BYTES = 1024


def posix_cksum(data):
    """POSIX cksum polynomial, byte-length suffix and final complement (not zlib)."""
    table = []
    for byte in range(256):
        value = byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
        table.append(value)
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ byte) & 255]
    length = len(data)
    while length:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ length) & 255]
        length >>= 8
    return (~crc) & 0xFFFFFFFF


def export_command(path, token, encoder="base64", checksum="md5"):
    if path not in ALLOWLIST or encoder not in ("base64", "hex") or checksum not in ("md5", "sha256"):
        raise ValueError("unsupported path, encoder or checksum")
    check_nonce(token)
    tool = {"md5": "md5sum", "sha256": "sha256sum"}[checksum]
    encode = {"base64": "base64", "hex": "od -An -tx1 -v"}[encoder]
    # Real newlines keep EACH physical input line short, including shell quoting.
    # All variables and positional arguments belong to an isolated sh -c process.
    script = f'''set -f
_p={shlex.quote(path)}
_t={token}
[ -f "$_p" ] && [ ! -L "$_p" ] || exit 70
_n=$(wc -c < "$_p") || exit 71
_n=$((_n + 0))
[ "$_n" -ge 0 ] && [ "$_n" -le {MAX_BYTES} ] || exit 71
_h=$({tool} "$_p") || exit 72
_h=${{_h%% *}}
_c=$(cksum "$_p") || exit 72
set -- $_c
_crc=$1
[ "$2" -eq "$_n" ] || exit 72
printf 'CMUF1 %s BEGIN %s %s {encoder} {checksum} %s %s\\n' "$_t" "$_p" "$_n" "$_h" "$_crc"
_i=0
_o=0
while [ "$_o" -lt "$_n" ]; do
_w=$((_n - _o))
[ "$_w" -le {CHUNK_BYTES} ] || _w={CHUNK_BYTES}
_e=$(dd if="$_p" bs={CHUNK_BYTES} skip="$_i" count=1 2>/dev/null | {encode}) || exit 73
printf 'CMUF1 %s DATA %s %s %s ' "$_t" "$_i" "$_o" "$_w"
set -- $_e
printf '%s' "$@"
printf '\\n'
_i=$((_i + 1))
_o=$((_o + _w))
done
_n2=$(wc -c < "$_p") || exit 74
_n2=$((_n2 + 0))
_h2=$({tool} "$_p") || exit 74
_h2=${{_h2%% *}}
_c2=$(cksum "$_p") || exit 74
set -- $_c2
_crc2=$1
[ "$2" -eq "$_n2" ] || exit 74
printf 'CMUF1 %s END %s %s %s %s\\n' "$_t" "$_n2" "$_h2" "$_crc2" "$_i"
[ "$_n" -eq "$_n2" ] && [ "$_h" = "$_h2" ] && [ "$_crc" = "$_crc2" ]'''
    # BusyBox 1.19.2 syntax VERIFIED by operator t14; never GNU timeout syntax.
    command = "timeout -t 20 -s 9 /bin/sh -c " + shlex.quote(script)
    wrap_command(command, "0" * 32)  # Validate the final nested wire quoting overhead.
    return command


def _number(value, maximum=MAX_BYTES):
    if not re.fullmatch(rb"0|[1-9][0-9]*", value):
        raise ProtocolError("noncanonical numeric field")
    number = int(value)
    if number > maximum:
        raise ProtocolError("numeric field exceeds bound")
    return number


def decode_file(output, token, path, encoder="base64", checksum="md5"):
    if path not in ALLOWLIST or encoder not in ("base64", "hex") or checksum not in ("md5", "sha256"):
        raise ValueError("unsupported capture profile")
    prefix = b"CMUF1 " + check_nonce(token).encode() + b" "
    pre, post = None, None
    decoded = bytearray()
    sequence = 0
    hash_pattern = rb"[0-9a-f]{32}" if checksum == "md5" else rb"[0-9a-f]{64}"
    for raw in output.split(b"\n"):
        line = raw.removesuffix(b"\r")
        if not line.startswith(prefix):
            continue  # Raw noise remains intact in the command/bundle evidence.
        fields = line[len(prefix):].split(b" ")
        kind = fields[0]
        if kind == b"BEGIN" and len(fields) == 7 and pre is None and post is None:
            _, source, length, encoding, algorithm, value, crc = fields
            if (source != path.encode() or encoding != encoder.encode() or algorithm != checksum.encode()
                    or not re.fullmatch(hash_pattern, value)):
                raise ProtocolError("unexpected source/encoding/checksum metadata")
            pre = dict(bytes=_number(length), checksum=value.decode(), cksum=_number(crc, 0xFFFFFFFF))
        elif kind == b"DATA" and len(fields) == 5 and pre is not None and post is None:
            _, seq, offset, length, payload = fields
            count = _number(length, CHUNK_BYTES)
            if (_number(seq) != sequence or _number(offset) != len(decoded) or count == 0
                    or count != min(CHUNK_BYTES, pre["bytes"] - len(decoded))):
                raise ProtocolError("missing/reordered/duplicate frame or incorrect chunk length")
            try:
                if encoder == "base64":
                    chunk = base64.b64decode(payload, validate=True)
                    if base64.b64encode(chunk) != payload:
                        raise ValueError("noncanonical base64")
                else:
                    if not re.fullmatch(rb"[0-9a-f]+", payload):
                        raise ValueError("noncanonical hex")
                    chunk = bytes.fromhex(payload.decode("ascii"))
            except (ValueError, binascii.Error) as exc:
                raise ProtocolError("corrupted/interleaved encoded payload") from exc
            if len(chunk) != count:
                raise ProtocolError("decoded chunk length mismatch")
            decoded.extend(chunk)
            sequence += 1
        elif kind == b"END" and len(fields) == 5 and pre is not None and post is None:
            _, length, value, crc, count = fields
            if not re.fullmatch(hash_pattern, value):
                raise ProtocolError("invalid end checksum")
            if _number(count) != sequence:
                raise ProtocolError("wrong final chunk count")
            post = dict(bytes=_number(length), checksum=value.decode(), cksum=_number(crc, 0xFFFFFFFF))
        else:
            raise ProtocolError("duplicate/malformed/out-of-order file record")
    if pre is None or post is None:
        raise ProtocolError("missing/truncated BEGIN/END file record")
    if pre != post or len(decoded) != pre["bytes"]:
        raise ProtocolError("source changed, length mismatch or truncated transfer")
    data = bytes(decoded)
    actual_hash = hashlib.new(checksum, data).hexdigest()
    crc = posix_cksum(data)
    if actual_hash != pre["checksum"] or crc != pre["cksum"]:
        raise ProtocolError("host/target checksum mismatch")
    metadata = dict(source_path=path, encoding=encoder, target_algorithm=checksum,
                    target_pre=pre, target_post=post, host_bytes=len(data),
                    host_checksum=actual_hash, host_cksum=crc, host_sha256=digest(data),
                    exact_bytes_verified=True, target_sha256=(checksum == "sha256"),
                    consistency="matching pre/post size and checksums; no atomic snapshot claim",
                    chunk_checksums=False, resumable=False)
    return data, metadata


def capture_file(session, path, encoder="base64", checksum="md5"):
    token = nonce()
    command = export_command(path, token, encoder, checksum)
    attempt = dict(source_path=path, file_nonce=token, encoder=encoder, checksum=checksum,
                   outcome="in_progress")
    session.bundle.meta.setdefault("file_captures", []).append(attempt)
    try:
        status, output = session.execute(command)
        if status != 0:
            raise ProtocolError("file command exited " + str(status))
        data, metadata = decode_file(output, token, path, encoder, checksum)
        name = path.strip("/").replace("/", "-") + ".exact.bin"
        session.bundle.save(name, data)
        attempt.update(metadata, outcome="verified", artifact=name,
                       command_nonce=session.bundle.meta["operations"][-1]["nonce"])
        session.bundle.event("file_verified", **attempt)
        return data, metadata
    except BaseException as exc:
        attempt.update(outcome="rejected", error=str(exc))
        session.bundle.event("file_rejected", **attempt)
        raise
