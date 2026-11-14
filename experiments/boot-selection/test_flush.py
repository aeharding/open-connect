"""Real filesystem checks for the selector's checked-flush helper (no device access)."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class FlushTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="oc-flush-host-")
        cls.root = Path(cls.temp.name)
        cls.binary = cls.root / "flush"
        subprocess.run([
            shutil.which("clang") or "cc", "-DOC_HOST", "-Wall", "-Wextra", "-Werror",
            str(Path(__file__).with_name("flush.c")), "-o", str(cls.binary),
        ], check=True)

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


if __name__ == "__main__":
    unittest.main()
