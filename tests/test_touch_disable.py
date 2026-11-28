"""Release ARM layout and host ABI/refcount/fault behavior of the touch shim."""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READELF = shutil.which("llvm-readelf") or (
    "/opt/homebrew/opt/llvm/bin/llvm-readelf"
    if Path("/opt/homebrew/opt/llvm/bin/llvm-readelf").exists()
    else None
)


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class TouchDisable(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()

    @unittest.skipUnless(READELF and shutil.which("ld.lld"), "LLVM tools required")
    def test_release_elf_dependencies_layout_unwind_and_page_budgets(self):
        subprocess.run(
            ["make", "release", "OUT=" + str(self.folder / "build")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=45,
        )
        folder = self.folder / "build"
        shim = folder / "touch-disable.so"
        self.assertLessEqual(shim.stat().st_size, 4096)
        self.assertLessEqual((folder / "api").stat().st_size, 81920)
        self.assertLessEqual((folder / "install").stat().st_size, 81920)
        self.assertLessEqual((folder / "boot-select").stat().st_size, 36864)
        self.assertLessEqual((folder / "ignition").stat().st_size, 4096)
        for native_bin in ("api", "install", "boot-select", "ignition"):
            bin_report = subprocess.check_output(
                [READELF, "-l", "-r", folder / native_bin], text=True
            )
            self.assertIn("There are no relocations in this file.", bin_report)
            self.assertNotIn("RWE", bin_report)
        report = subprocess.check_output(
            [READELF, "-l", "-S", "-d", "--dyn-syms", "--unwind", shim],
            text=True,
        )
        loads = re.findall(r"^\s+LOAD\s+.*$", report, re.M)
        self.assertEqual(len(loads), 2)
        self.assertRegex(loads[0], r"R E 0x1000$")
        self.assertRegex(loads[1], r"RW  0x1000$")
        self.assertIn("BIND_NOW", report)
        self.assertNotIn("GNU_RELRO", report)
        for forbidden in (".init_array", ".rel.dyn", "(RUNPATH)", "touch-stubs", "real-devices"):
            self.assertNotIn(forbidden, report)
        self.assertEqual(
            re.findall(r"\(NEEDED\).*\[(.*?)\]", report),
            ["svc-com-jci-cpp-devices.so", "libdl.so.2"],
        )
        self.assertIn("Library rpath: [/jci/devices:/jci/lib]", report)
        # The linker adds a CantUnwind sentinel AFTER both functions. Check each
        # exported function's own entry, rather than rejecting the valid sentinel.
        for name in ("getDevice", "4send"):
            address = re.search(r"\d+: ([0-9a-f]+)\s+\d+ FUNC .*\S*" + name + r"\S*", report)[1]
            entry = re.search(
                r"FunctionAddress: 0x"
                + f"{int(address, 16):X}"
                + r"\n(.*?)(?=\n      Entry|\n    \])",
                report,
                re.S,
            )[1]
            self.assertIn("Model: Compact", entry)
            self.assertNotIn("CantUnwind", entry)
        version = (ROOT / "cmu/installer/VERSION").read_text().strip()
        packaged = folder / f"usb/open-connect-{version}-usb/open-connect"
        self.assertEqual((packaged / "touch-disable.so").read_bytes(), shim.read_bytes())
        self.assertLessEqual(
            sum((p.stat().st_size + 4095) // 4096 for p in packaged.iterdir()), 123
        )
        self.assertFalse((packaged / "svc-com-jci-cpp-devices.so").exists())
        self.assertFalse((packaged / "libdl.so.2").exists())
        # Packaging must reject an oversized artifact even when make skips linking.
        shim.write_bytes(b"x" * 4097)
        result = subprocess.run(
            ["sh", "tooling/package-usb.sh", folder],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("touch-disable.so exceeds its RAM page budget", result.stderr)

    def test_host_dl_passthrough_refcount_and_missing_lookup_traps(self):
        shim = self.folder / "touch.so"
        program = self.folder / "fixture"
        extra = ["-Wl,-undefined,dynamic_lookup"] if sys.platform == "darwin" else []
        subprocess.run(
            [
                "clang",
                "-shared",
                "-fPIC",
                "-Ddlsym=touch_lookup",
                ROOT / "cmu/features/touch/disable.c",
                *extra,
                "-o",
                shim,
            ],
            check=True,
        )
        export = ["-Wl,-export_dynamic"] if sys.platform == "darwin" else ["-rdynamic", "-ldl"]
        subprocess.run(
            [
                "clang",
                "-Wall",
                "-Wextra",
                "-Werror",
                ROOT / "tests/fixtures/touch-disable.c",
                *export,
                "-o",
                program,
            ],
            check=True,
        )
        result = subprocess.run([program, shim], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Clang emits brk on AArch64 and an illegal instruction on x86/ARM32.
        trap = signal.SIGTRAP if os.uname().machine in ("arm64", "aarch64") else signal.SIGILL
        for missing in ("get", "deref", "send"):
            with self.subTest(missing=missing):
                result = subprocess.run(
                    [program, shim],
                    capture_output=True,
                    timeout=5,
                    env={**os.environ, "TOUCH_MISSING": missing},
                )
                self.assertEqual(result.returncode, -trap)
