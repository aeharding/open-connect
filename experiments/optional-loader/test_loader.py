"""Public checks: real compiler/loader fixtures, no OEM inputs or device access."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import build


class LoaderProbe(unittest.TestCase):
    def test_arm_calls_are_position_independent_and_fit(self):
        with tempfile.TemporaryDirectory() as td:
            obj = build.compile_stub(build.elf.tool("clang"), Path(td) / "loader.o")
            blob, relocs = build.link(obj)
        self.assertLessEqual(len(blob), 200)
        self.assertIn(b"/data/open-connect/bootstrap-v1.so\0", blob)
        for base in (0, 0x2B000000, 0x71234000):
            for r in relocs:
                word = int.from_bytes(blob[r["place"]-build.START:r["place"]-build.START+4], "little")
                self.assertEqual(build.elf.branch_target(word, base+r["place"]), base+r["target"])

    def test_unknown_original_refused(self):
        with self.assertRaisesRegex(ValueError, "unsupported exact"):
            build.patch(bytes(22952), b"")

    def test_real_noop_library_entry_and_missing_library(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "noop.so"
            cc = build.elf.tool("clang")
            subprocess.run([cc, "-shared", "-fPIC", "-fvisibility=hidden",
                            str(build.HERE/"noop.c"), "-o", str(path)],
                           check=True, capture_output=True)
            lib = ctypes.CDLL(str(path), mode=os.RTLD_LOCAL | os.RTLD_NOW)
            count = ctypes.c_uint.in_dll(lib, "oc_noop_calls")
            self.assertEqual(count.value, 0)
            self.assertEqual(lib.oc_bootstrap_v1(), 0)
            self.assertEqual(count.value, 1)
            with self.assertRaises(AttributeError):
                getattr(lib, "nonexistent_entry")
            with self.assertRaises(OSError):
                ctypes.CDLL(str(Path(td)/"missing.so"), mode=os.RTLD_NOW)

    def test_arm_shared_noop_has_no_dependencies_or_constructor(self):
        linker = os.environ.get("OC_LLD")
        if not linker:
            self.skipTest("set OC_LLD to build ARM shared probe; Linux CI supplies it")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run([build.elf.tool("clang"), "--target=armv7-none-eabi",
                            "-march=armv7-a", "-marm", "-mfloat-abi=hard", "-mfpu=vfpv3",
                            "-fPIC", "-ffreestanding", "-fno-unwind-tables",
                            "-fno-stack-protector", "-c", str(build.HERE/"noop.c"),
                            "-o", str(td/"noop.o")], check=True, capture_output=True)
            subprocess.run([linker, "-shared", "-z", "defs", "-soname", "bootstrap-v1.so",
                            str(td/"noop.o"), "-o", str(td/"bootstrap-v1.so")],
                           check=True, capture_output=True)
            parsed = build.elf.ELF((td/"bootstrap-v1.so").read_bytes())
            dynamic = parsed.section_data(".dynamic")
            tags = [int.from_bytes(dynamic[i:i+4], "little") for i in range(0,len(dynamic),8)]
            self.assertNotIn(1,tags)   # DT_NEEDED
            self.assertNotIn(12,tags)  # DT_INIT
            self.assertNotIn(25,tags)  # DT_INIT_ARRAY
            self.assertNotEqual(parsed.symbols["oc_bootstrap_v1"]["section"],0)


if __name__ == "__main__":
    unittest.main()
