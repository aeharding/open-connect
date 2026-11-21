"""Real filesystem checks for the selector's checked-flush helper (no device access)."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from open_connect.paths import ROOT


class FlushTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="oc-flush-host-")
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / "flush"
        subprocess.run(
            [
                shutil.which("clang") or "cc",
                "-DOC_HOST",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(ROOT / "cmu/startup/flush.c"),
                "-o",
                str(cls.binary),
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def call(self, *args):
        return subprocess.run([str(self.binary), *map(str, args)], capture_output=True, timeout=2)

    def test_file_and_directory_flush_leave_contents_unchanged(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            p = Path(directory) / "state"
            p.write_bytes(b"consumed\n")
            before = p.stat()
            for args in [("f", p), ("d", directory)]:
                result = self.call(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(p.read_bytes(), b"consumed\n")
            self.assertEqual(p.stat().st_ino, before.st_ino)
            self.assertEqual(p.stat().st_mtime_ns, before.st_mtime_ns)

    def test_refusals_and_fifo_do_not_block_or_create_files(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            d = Path(directory)
            p = d / "state"
            p.write_bytes(b"unchanged\n")
            (d / "link").symlink_to(p)
            os.mkfifo(d / "fifo")
            for args in [("f", d / "missing"), ("f", d / "link"), ("d", p)]:
                result = self.call(*args)
                self.assertNotEqual(result.returncode, 0, args)
            # Darwin may accept fsync on a FIFO; only nonblocking open is promised here.
            self.call("f", d / "fifo")
            self.assertEqual(p.read_bytes(), b"unchanged\n")
            self.assertFalse((d / "missing").exists())

    def test_usage_refuses_without_work(self):
        for args in [(), ("x", "/tmp"), ("d", "relative"), ("file", "/tmp")]:
            result = self.call(*args)
            self.assertEqual(result.returncode, 64)
            self.assertTrue(result.stderr.endswith(b"\n"))

    def test_atomic_link_refuses_existing_files_directories_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            source = root / "stage"
            source.write_bytes(b"selected configuration\n")
            target = root / "selected"
            result = self.call("l", source, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.stat().st_ino, target.stat().st_ino)
            target.unlink()
            target.write_bytes(b"another provider\n")
            folder = root / "folder"
            folder.mkdir()
            link = root / "link"
            link.symlink_to(target)
            for destination in (target, folder, link):
                result = self.call("l", source, destination)
                self.assertNotEqual(result.returncode, 0, destination)
            self.assertEqual(target.read_bytes(), b"another provider\n")
            self.assertEqual(source.read_bytes(), b"selected configuration\n")
            self.assertEqual(list(folder.iterdir()), [])
            self.assertTrue(link.is_symlink())


if __name__ == "__main__":
    unittest.main()
