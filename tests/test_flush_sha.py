"""Streaming scalar hashes, failed-I/O refusals and the ARM allocation gate."""

import errno
import hashlib
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class FlushSha(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="oc-flush-sha-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve()
        cls.binary = cls.root / "flush"
        cls.fault_binary = cls.root / "flush-fault"
        for source, target in (
            (ROOT / "cmu/startup/flush.c", cls.binary),
            (ROOT / "tests/fixtures/flush-sha.c", cls.fault_binary),
        ):
            subprocess.run(
                ["clang", "-DOC_HOST", "-Wall", "-Wextra", "-Werror", source, "-o", target],
                check=True,
                capture_output=True,
                timeout=20,
            )

    def call(self, path, fault=None, **kwargs):
        return subprocess.run(
            [self.fault_binary if fault else self.binary, "h", path],
            capture_output=True,
            timeout=3,
            env={**os.environ, "OC_FLUSH_FAULT": fault or ""},
            **kwargs,
        )

    def test_known_answers_padding_boundaries_and_multiblock_binary(self):
        vectors = [b"", b"abc", *(b"a" * n for n in (55, 56, 64, 128)), bytes(range(256)) * 257]
        for data in vectors:
            with self.subTest(bytes=len(data)):
                path = self.root / "input with spaces"
                path.write_bytes(data)
                result = self.call(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, hashlib.sha256(data).hexdigest().encode() + b"\n")
                self.assertEqual(result.stderr, b"")
                self.assertEqual(path.read_bytes(), data)
        # sha() callers that construct manifests may supply relative paths.
        result = self.call(path.name, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, hashlib.sha256(data).hexdigest().encode() + b"\n")

    def test_eintr_and_short_io_preserve_complete_digest(self):
        data = bytes(range(256)) * 9
        path = self.root / "interrupted"
        path.write_bytes(data)
        for fault in (
            "open-eintr",
            "stat-eintr",
            "read-eintr",
            "write-eintr",
            "short-read",
            "short-write",
        ):
            with self.subTest(fault=fault):
                result = self.call(path, fault)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, hashlib.sha256(data).hexdigest().encode() + b"\n")

    def test_stat_read_close_and_output_errors_refuse_without_a_digest(self):
        path = self.root / "failed"
        path.write_bytes(b"a" * 1024)
        for fault in ("stat-error", "read-error", "close-error", "write-error", "write-zero"):
            with self.subTest(fault=fault):
                result = self.call(path, fault)
                self.assertEqual(result.returncode, errno.EIO, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"failed\n", result.stderr)

    def test_missing_symlink_directory_fifo_and_device_are_refused(self):
        path = self.root / "regular"
        path.write_bytes(b"unchanged")
        link = self.root / "link"
        link.symlink_to(path)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        for refused in (self.root / "missing", link, self.root, fifo, Path("/dev/null")):
            with self.subTest(path=refused):
                result = self.call(refused)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
        self.assertEqual(path.read_bytes(), b"unchanged")
        self.assertFalse((self.root / "missing").exists())

    def test_arm_helper_fits_one_file_page_and_two_readonly_load_pages(self):
        output = self.root / "arm"
        subprocess.run(
            ["make", "CLANG=clang -fstack-usage", "OUT=" + str(output), str(output / "flush")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=30,
        )
        elf = (output / "flush").read_bytes()
        self.assertLessEqual(len(elf), 4096)
        self.assertEqual(elf[:7], b"\x7fELF\x01\x01\x01")
        self.assertEqual(struct.unpack_from("<H", elf, 18)[0], 40)  # EM_ARM
        phoff, shoff = struct.unpack_from("<II", elf, 28)
        phsize, phnum, shsize, shnum = struct.unpack_from("<HHHH", elf, 42)
        loads = [
            p
            for i in range(phnum)
            if (p := struct.unpack_from("<8I", elf, phoff + i * phsize))[0] == 1
        ]
        self.assertEqual([p[6] for p in loads], [4, 5])  # PF_R, PF_R|PF_X
        for _, _, address, _, filesz, memsz, _, alignment in loads:
            self.assertEqual(filesz, memsz, "no zero-filled/BSS tail")
            self.assertEqual(alignment, 4096)
            self.assertLessEqual((address % 4096) + memsz, 4096)
        for i in range(shnum):
            section = struct.unpack_from("<10I", elf, shoff + i * shsize)
            self.assertFalse(section[2] & 1, "no writable section")
            self.assertFalse(section[1] == 8 and section[5], "no BSS/NOBITS section")
        # Conservatively add every static frame, even disjoint call paths.
        # This bounds scratch; native peak/PSS still needs matched evidence.
        frames = [line.split("\t")[1:] for line in (output / "flush.su").read_text().splitlines()]
        self.assertTrue(frames)
        self.assertTrue(all(kind == "static" for _, kind in frames))
        self.assertLess(sum(int(size) for size, _ in frames), 4096)
