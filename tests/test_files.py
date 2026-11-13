import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from cmu_bench.files import (ALLOWLIST, CHUNK_BYTES, MAX_BYTES, capture_file, decode_file,
                             export_command, posix_cksum)
from cmu_bench.session import ProtocolError, wrap_command

TOKEN = "b" * 32
ROOT = Path(__file__).resolve().parents[1]
KNOWN = b"201506101650\njci-cmu_01.00.110\n"


def frames(data, encoder="base64", checksum="md5", path="/etc/version"):
    value = hashlib.new(checksum, data).hexdigest()
    crc = posix_cksum(data)
    lines = [f"CMUF1 {TOKEN} BEGIN {path} {len(data)} {encoder} {checksum} {value} {crc}"]
    count = 0
    for offset in range(0, len(data), CHUNK_BYTES):
        chunk = data[offset:offset+CHUNK_BYTES]
        encoded = base64.b64encode(chunk).decode() if encoder == "base64" else chunk.hex()
        lines.append(f"CMUF1 {TOKEN} DATA {count} {offset} {len(chunk)} {encoded}")
        count += 1
    lines.append(f"CMUF1 {TOKEN} END {len(data)} {value} {crc} {count}")
    return ("\n".join(lines) + "\n").encode()


class FileTests(unittest.TestCase):
    def test_posix_crc_known_operator_and_host_vectors(self):
        # Independent live observation, NOT a computed expectation: operator t14 report.
        self.assertEqual(len(KNOWN), 31)
        self.assertEqual(hashlib.md5(KNOWN).hexdigest(), "10cac4792dbca7d886eb2d9ee80d0647")
        self.assertEqual(posix_cksum(KNOWN), 2910742528)
        for data in (b"", b"a", b"123456789", KNOWN, bytes(range(256)) * 64):
            result = subprocess.run(["/usr/bin/cksum"], input=data, capture_output=True, timeout=2, check=True)
            fields = result.stdout.split()
            self.assertEqual(posix_cksum(data), int(fields[0]))
            self.assertEqual(len(data), int(fields[1]))

    def test_exact_binary_roundtrip_profiles_and_noise(self):
        for encoder in ("base64", "hex"):
            for algorithm in ("md5", "sha256"):
                for data in (b"", KNOWN, bytes(range(256)) * 50):
                    output = b"noise\x00\xff\n" + frames(data, encoder, algorithm) + b"runtime noise\n"
                    actual, metadata = decode_file(output, TOKEN, "/etc/version", encoder, algorithm)
                    self.assertEqual(actual, data)
                    self.assertEqual(metadata["host_sha256"], hashlib.sha256(data).hexdigest())
                    self.assertEqual(metadata["target_sha256"], algorithm == "sha256")
                    self.assertEqual(metadata["target_pre"], metadata["target_post"])

    def test_corrupted_interleaved_truncated_checksum_and_lengths_fail(self):
        good = frames(KNOWN)
        lines = good.splitlines(keepends=True)
        crc = str(posix_cksum(KNOWN)).encode()
        cases = [good[:-20], b"".join(lines[:-1]), b"".join(lines[1:]),
                 lines[0] + lines[1] + lines[1] + lines[2],
                 good + lines[-1], lines[1] + lines[0] + lines[2],
                 good.replace(b" DATA 0 0 31 ", b" DATA 0 1 31 "),
                 good.replace(b" DATA 0 0 31 ", b" DATA 0 0 30 "),
                 good.replace(b" DATA 0 0 31 ", b" DATA 1 0 31 "),
                 good.replace(b" BEGIN /etc/version 31 ", b" BEGIN /etc/version 32 "),
                 good.replace(b"10cac479", b"20cac479"),
                 good.replace(crc, b"12345"),
                 good.replace(b"MjAx", b"MjAxLOG NOISE"),
                 good.replace(b"MjAx", b"MjAx\nbackground\n"),
                 good.replace(b"Cg==", b"Cg="),
                 good.replace(b" END 31 ", b" END 32 "),
                 good.replace(b" BEGIN /etc/version ", b" BEGIN /jci/version.ini ")]
        for index, bad in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(ProtocolError):
                    decode_file(bad, TOKEN, "/etc/version")

    def test_missing_chunk_reordered_and_wrong_final_count_fail(self):
        lines = frames(b"x" * 3000).splitlines(keepends=True)
        for bad in (b"".join(lines[:1] + lines[2:]),
                    b"".join([lines[0], lines[2], lines[1]] + lines[3:]),
                    b"".join(lines).replace(b" 3\n", b" 2\n")):
            with self.assertRaises(ProtocolError):
                decode_file(bad, TOKEN, "/etc/version")

    def test_echoed_payload_and_lookalikes_do_not_verify(self):
        command = export_command("/etc/version", TOKEN)
        wire = wrap_command(command, "c" * 32)
        self.assertNotIn(b"CMUF1 " + TOKEN.encode() + b" BEGIN", wire)
        self.assertTrue(all(len(line) <= 600 for line in wire.splitlines()))
        for fake in (wire, frames(KNOWN).replace(b"CMUF1 ", b"echo CMUF1 ")):
            with self.assertRaises(ProtocolError):
                decode_file(fake, TOKEN, "/etc/version")

    def test_allowlist_size_hash_source_stability(self):
        for path in ("/etc/passwd", "/proc/meminfo", "/dev/mtd0", "/etc/../etc/version"):
            with self.assertRaises(ValueError):
                export_command(path, TOKEN)
        oversized = frames(b"a" * (MAX_BYTES + 1))
        with self.assertRaises(ProtocolError):
            decode_file(oversized, TOKEN, "/etc/version")
        good = frames(KNOWN)
        bad = good.replace(b" END 31 10cac479", b" END 31 20cac479")
        with self.assertRaises(ProtocolError):
            decode_file(bad, TOKEN, "/etc/version")

    def test_fresh_identity_to_verified_artifact_and_reject_bad_export(self):
        import re
        from cmu_bench.session import Bundle, Session
        from test_session import FakeTransport, IDENTITY_OUTPUT, response
        for corrupted in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                bundle = Bundle(Path(temp) / "run", "offline full export", "unittest")
                def callback(wire):
                    command_token = re.search(rb"\x27 ([a-f0-9]{32}); sh -c", wire).group(1).decode()
                    file_token = re.search(rb"_t=([a-f0-9]{32})", wire)
                    if file_token:
                        payload = frames(KNOWN).replace(TOKEN.encode(), file_token.group(1))
                        if corrupted:
                            payload = payload.replace(b"10cac479", b"20cac479")
                    else:
                        payload = IDENTITY_OUTPUT
                    raw = wire + response(command_token, payload)
                    return [raw[index:index+11] for index in range(0, len(raw), 11)]
                transport = FakeTransport([b"/tmp/root # "], callback)
                session = Session(transport, bundle, timeout=1)
                try:
                    session.observe_prompt()
                    session.identify()
                    if corrupted:
                        with self.assertRaises(ProtocolError):
                            capture_file(session, "/etc/version")
                        self.assertFalse((bundle.path / "etc-version.exact.bin").exists())
                    else:
                        actual, metadata = capture_file(session, "/etc/version")
                        self.assertEqual(actual, KNOWN)
                        self.assertEqual((bundle.path / "etc-version.exact.bin").read_bytes(), KNOWN)
                        self.assertFalse(metadata["target_sha256"])
                        self.assertEqual(len(bundle.meta["operations"]), 2)
                        self.assertTrue(all(op["exit_status"] == 0 for op in bundle.meta["operations"]))
                finally:
                    bundle.finish("offline test")
                events = [json.loads(row) for row in (bundle.path / "events.jsonl").read_text().splitlines()]
                for direction in ("rx", "tx"):
                    rebuilt = b"".join(bytes.fromhex(e["hex"]) for e in events if e.get("direction") == direction)
                    self.assertEqual(rebuilt, (bundle.path / (direction + ".bin")).read_bytes())

    def test_execute_generated_remote_script_offline_real_tools(self):
        # Only tests substitute temp paths/tool functions. Production retains exact allowlist.
        data = bytes(range(256)) * 57 + b"\x00\r\n\xff"
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic-source.bin"
            source.write_bytes(data)
            for encoder in ("base64", "hex"):
                command = export_command("/etc/version", TOKEN, encoder, "md5")
                argv = shlex.split(command)
                self.assertEqual(argv[:5], ["timeout", "-t", "20", "-s", "9"])
                self.assertEqual(argv[5:7], ["/bin/sh", "-c"])
                script = argv[7].replace("_p=/etc/version", "_p=" + shlex.quote(str(source)))
                helper = ("md5sum() { " + shlex.quote(sys.executable) + " -B -c "
                          + shlex.quote("import hashlib,sys; print(hashlib.md5(open(sys.argv[1],'rb').read()).hexdigest()+'  '+sys.argv[1])")
                          + ' "$1"; }\n')
                result = subprocess.run(["/bin/sh", "-c", helper + script], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                decoded, _ = decode_file(result.stdout.replace(str(source).encode(), b"/etc/version"),
                                         TOKEN, "/etc/version", encoder)
                self.assertEqual(decoded, data)
                # Verify generated script rejects a symlink rather than reading its target.
                link = Path(temp) / "symlink.bin"
                link.symlink_to(source)
                linked = script.replace(shlex.quote(str(source)), shlex.quote(str(link)))
                result = subprocess.run(["/bin/sh", "-c", helper + linked], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 70)
                link.unlink()


if __name__ == "__main__":
    unittest.main()
