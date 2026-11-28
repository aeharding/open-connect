"""Offline shell execution tests for cmu/installer/startup-hook.sh and startup-join.sh."""

import os
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


class StartupHookAndJoinTests(unittest.TestCase):
    def _run_hook(
        self,
        selector_body: str,
        *,
        with_ignition: bool = False,
        with_startup_times: bool = False,
        recover_marker: bool = False,
    ):
        busybox = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
        shell = [busybox, "sh"] if busybox else ["/bin/bash"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            ram = root / "ram"
            ram.mkdir(mode=0o700)
            tools = root / "tools"
            tools.mkdir(mode=0o700)
            uptime = root / "uptime"
            uptime.write_text("100.00 50.00\n")

            if with_ignition:
                ig_dir = ram / "ignition"
                ig_dir.mkdir(mode=0o700)
                ig_bin = ig_dir / "ignition"
                ig_bin.write_text(f"#!/bin/sh\n: > {shlex.quote(str(root / 'ignition-ran'))}\n")
                ig_bin.chmod(0o700)

            if with_startup_times:
                (ram / "startup-times").write_text("")

            sel_bin = tools / "open-connect-boot-select"
            sel_bin.write_text("#!/bin/sh\n" + selector_body + "\n")
            sel_bin.chmod(0o700)

            # Minimal BusyBox-style `timeout -t SEC CMD...` shim for host macOS/Linux parity.
            timeout_bin = tools / "timeout"
            timeout_bin.write_text('#!/bin/sh\nif [ "$1" = -t ]; then shift 2; fi\nexec "$@"\n')
            timeout_bin.chmod(0o700)
            bb_shim = tools / "busybox"
            bb_shim.write_text(
                f'#!/bin/sh\nif [ "$1" = timeout ]; then shift; exec {shlex.quote(str(timeout_bin))} "$@"; fi\n'
                'exec "$@"\n'
            )
            bb_shim.chmod(0o700)

            hook = (ASSETS / "startup-hook.sh").read_text()
            join = (ASSETS / "startup-join.sh").read_text()
            for text_name, src in (("hook", hook), ("join", join)):
                src = src.replace("/proc/uptime", str(uptime))
                src = src.replace("/usr/bin/open-connect-boot-select", str(sel_bin))
                src = src.replace("/bin/busybox", str(bb_shim))
                # Standalone BusyBox builds run built-in timeout without searching PATH.
                src = src.replace("if timeout -t ", f"if {shlex.quote(str(timeout_bin))} -t ")
                src = src.replace("/tmp/open-connect", str(ram))
                src = src.replace("/tmp/.open-connect-gate-XXXXXX", str(root / "gate-XXXXXX"))
                if recover_marker and text_name == "hook":
                    # Replace the inner root-mount recovery subshell with a deterministic marker.
                    start = src.index(
                        f'if {shlex.quote(str(timeout_bin))} -t "$oc_wait" sh -c \'set -eu'
                    )
                    end = src.index("'; then", start) + len("'; then")
                    src = (
                        src[:start]
                        + f'if sh -c ": > {shlex.quote(str(root / "recover-ran"))}"; then'
                        + src[end:]
                    )
                if text_name == "hook":
                    hook = src
                else:
                    join = src

            driver = root / "driver.sh"
            driver.write_text(
                "set -u\n"
                f'export PATH={shlex.quote(str(tools))}:"$PATH"\n'
                "SMCFG_NORMALMODE=stock-normal\n"
                "SMCFG_WCPMODE=stock-wcp\n"
                + hook
                + "\n"
                + join
                + "\n"
                + 'printf "NORMAL=%s\\nWCP=%s\\nRES=%s\\nREL=%s\\n" '
                '"$SMCFG_NORMALMODE" "$SMCFG_WCPMODE" "$oc_result" "$oc_released"\n'
            )
            env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
            res = subprocess.run(
                [*shell, str(driver)], capture_output=True, text=True, timeout=10, env=env
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stderr, "")
            self.assertEqual(list(root.glob("gate-*")), [])
            out = dict(line.split("=", 1) for line in res.stdout.strip().splitlines())
            times = (ram / "startup-times").read_text() if with_startup_times else ""
            # Brief settle for backgrounded ignition marker if expected.
            ig_ran = False
            if with_ignition:
                for _ in range(50):
                    if (root / "ignition-ran").exists():
                        ig_ran = True
                        break
                    time.sleep(0.01)
            return out, times, ig_ran, (root / "recover-ran").exists()

    def test_gated_overlap_joins_sets_sm_confs_starts_ignition_and_logs_times(self):
        out, times, ig_ran, rec_ran = self._run_hook(
            'printf "G"; sleep 0.05; exit 0',
            with_ignition=True,
            with_startup_times=True,
        )
        self.assertEqual(out["REL"], "true")
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
        self.assertTrue(out["WCP"].endswith("/feature/sm_WCP.conf"))
        self.assertTrue(ig_ran)
        self.assertFalse(rec_ran)
        self.assertIn("oem_window_start|100.00", times)
        self.assertIn("join_entered|100.00", times)
        self.assertIn("join_returned|100.00", times)

    def test_fast_j_frame_selects_synchronously_without_overlap(self):
        out, _, ig_ran, rec_ran = self._run_hook(
            'printf "J"; exit 0',
            with_ignition=True,
        )
        self.assertEqual(out["REL"], "false")
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
        self.assertTrue(ig_ran)
        self.assertFalse(rec_ran)

    def test_gated_worker_failure_preserves_stock_sm_confs_and_skips_ignition(self):
        out, _, ig_ran, _ = self._run_hook(
            'printf "G"; sleep 0.05; exit 1',
            with_ignition=True,
        )
        self.assertEqual(out["REL"], "true")
        self.assertEqual(out["RES"], "1")
        self.assertEqual(out["NORMAL"], "stock-normal")
        self.assertEqual(out["WCP"], "stock-wcp")
        self.assertFalse(ig_ran)

    def test_legacy_exit_64_falls_back_to_boot_recover_and_reselects(self):
        # First invocation (select-gated) exits 64 with no frame -> oc_result=95 ->
        # boot-recover runs -> second invocation (select) exits 0!
        out, _, _, rec_ran = self._run_hook(
            'if [ "$1" = select-gated ]; then exit 64; fi\nexit 0',
            recover_marker=True,
        )
        self.assertTrue(rec_ran)
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))


if __name__ == "__main__":
    unittest.main()
