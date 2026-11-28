"""Offline shell execution tests for cmu/installer/startup-hook.sh and startup-join.sh."""

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
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
        fail_mktemp: bool = False,
        real_recover: dict | None = None,
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

            mktemp_bin = None
            if fail_mktemp:
                mktemp_bin = tools / "mktemp"
                mktemp_bin.write_text("#!/bin/sh\nexit 1\n")
                mktemp_bin.chmod(0o700)

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

            data = None
            mounts_file = None
            if real_recover is not None:
                data = root / "data"
                data.mkdir(mode=0o700)
                mounts_file = root / "mounts"
                mounts_text = real_recover.get(
                    "mounts",
                    "rootfs / rootfs rw 0 0\n"
                    "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
                    "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n",
                )
                mounts_file.write_text(
                    mounts_text.replace("@DATA@", str(data)).replace("@RAM@", str(ram))
                )
                inst_bytes = (
                    f'#!/bin/sh\nprintf \'%s|%s|%s\\n\' "$1" "$2" "$3" > '
                    f"{shlex.quote(str(root / 'recover-ran'))}\nexit 0\n"
                ).encode()
                inst_sha = hashlib.sha256(inst_bytes).hexdigest()
                if real_recover.get("tamper_install_digest"):
                    mf_text = f"{'0' * 64}  install\n"
                else:
                    mf_text = f"{inst_sha}  install\n"
                pkg_id = hashlib.sha256(mf_text.encode()).hexdigest()
                pkg_dir = data / "packages" / pkg_id
                pkg_dir.mkdir(parents=True, mode=0o700)
                (data / "packages").chmod(0o700)
                pkg_dir.chmod(0o700)
                (pkg_dir / "install").write_bytes(inst_bytes)
                (pkg_dir / "install").chmod(0o700)
                (pkg_dir / "files.sha256").write_text(mf_text)
                (pkg_dir / "files.sha256").chmod(0o600)
                (data / "record").write_text(
                    f"OC1|active|{'a' * 32}|{pkg_id}|{'b' * 64}|{'c' * 64}|-|-|-|3|-|-|-\n"
                )
                (data / "record").chmod(0o600)
                (tools / "id").write_text("#!/bin/sh\necho 0\n")
                (tools / "id").chmod(0o700)
                (tools / "stat").write_text(
                    f"#!{sys.executable}\n"
                    "import os, sys\n"
                    "from pathlib import Path\n"
                    "a = sys.argv[1:]\n"
                    "fmt = a[0][2:] if a[0].startswith('-c') and a[0] != '-c' else a[1]\n"
                    "st = Path(a[-1]).lstat()\n"
                    "vals = {'a': format(st.st_mode & 0o777, 'o'), 'u': 0, 'g': 0}\n"
                    "for k, v in vals.items(): fmt = fmt.replace('%' + k, str(v))\n"
                    "print(fmt)\n"
                )
                (tools / "stat").chmod(0o700)

            hook = (ASSETS / "startup-hook.sh").read_text()
            join = (ASSETS / "startup-join.sh").read_text()
            for text_name, src in (("hook", hook), ("join", join)):
                src = src.replace("/proc/uptime", str(uptime))
                src = src.replace("/usr/bin/open-connect-boot-select", str(sel_bin))
                src = src.replace("/bin/busybox", str(bb_shim))
                # Standalone BusyBox builds run built-in timeout without searching PATH.
                src = src.replace("if timeout -t ", f"if {shlex.quote(str(timeout_bin))} -t ")
                if mktemp_bin is not None and text_name == "hook":
                    # Standalone BusyBox builds also bypass PATH for built-in mktemp.
                    src = src.replace(
                        "oc_directory=$(mktemp -d ",
                        f"oc_directory=$({shlex.quote(str(mktemp_bin))} -d ",
                    )
                if real_recover is not None:
                    src = src.replace("/proc/self/mounts", str(mounts_file))
                    src = src.replace("/tmp/mnt/data_persist/open-connect", str(data))
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
            self.assertEqual(list(ram.glob(".recover-*")), [])
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
            rec_text = (root / "recover-ran").read_text() if (root / "recover-ran").exists() else ""
            return out, times, ig_ran, (root / "recover-ran").exists(), rec_text

    def test_gated_overlap_joins_sets_sm_confs_starts_ignition_and_logs_times(self):
        out, times, ig_ran, rec_ran, _ = self._run_hook(
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
        out, _, ig_ran, rec_ran, _ = self._run_hook(
            'printf "J"; exit 0',
            with_ignition=True,
        )
        self.assertEqual(out["REL"], "false")
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
        self.assertTrue(ig_ran)
        self.assertFalse(rec_ran)

    def test_gated_worker_failure_preserves_stock_sm_confs_and_skips_ignition(self):
        out, _, ig_ran, _, _ = self._run_hook(
            'printf "G"; sleep 0.05; exit 1',
            with_ignition=True,
        )
        self.assertEqual(out["REL"], "true")
        self.assertEqual(out["RES"], "1")
        self.assertEqual(out["NORMAL"], "stock-normal")
        self.assertEqual(out["WCP"], "stock-wcp")
        self.assertFalse(ig_ran)

    def test_oc_stock_exit_2_preserves_stock_sm_confs_and_starts_ignition(self):
        out, _, ig_ran, rec_ran, _ = self._run_hook(
            'printf "J"; exit 2',
            with_ignition=True,
        )
        self.assertEqual(out["REL"], "false")
        self.assertEqual(out["RES"], "2")
        self.assertEqual(out["NORMAL"], "stock-normal")
        self.assertEqual(out["WCP"], "stock-wcp")
        self.assertTrue(ig_ran)
        self.assertFalse(rec_ran)

    def test_delayed_frame_after_initial_read_timeout_recovers_result(self):
        for frame in ("J", "G"):
            with self.subTest(frame=frame):
                out, _, ig_ran, rec_ran, _ = self._run_hook(
                    f'sleep 1.2; printf "{frame}"; exit 0',
                    with_ignition=True,
                )
                self.assertEqual(out["REL"], "false")
                self.assertEqual(out["RES"], "0")
                self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
                self.assertTrue(ig_ran)
                self.assertFalse(rec_ran)

    def test_gate_setup_failure_falls_back_to_synchronous_select(self):
        out, _, ig_ran, rec_ran, _ = self._run_hook(
            'if [ "$1" = select ]; then exit 0; fi\nexit 1',
            with_ignition=True,
            fail_mktemp=True,
        )
        self.assertEqual(out["REL"], "false")
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
        self.assertTrue(ig_ran)
        self.assertFalse(rec_ran)

    def test_legacy_exit_64_falls_back_to_boot_recover_and_reselects(self):
        # First invocation (select-gated) exits 64 with no frame -> oc_result=95 ->
        # boot-recover runs -> second invocation (select) exits 0!
        out, _, _, rec_ran, _ = self._run_hook(
            'if [ "$1" = select-gated ]; then exit 64; fi\nexit 0',
            recover_marker=True,
        )
        self.assertTrue(rec_ran)
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))

    def test_real_boot_recover_bootstrap_verifies_digest_and_runs_install(self):
        out, _, ig_ran, rec_ran, rec_text = self._run_hook(
            'if [ "$1" = select-gated ]; then printf "J"; exit 95; fi\nexit 0',
            with_ignition=True,
            real_recover={},
        )
        self.assertTrue(rec_ran)
        parts = rec_text.strip().split("|")
        self.assertEqual(len(parts), 3, rec_text)
        self.assertEqual(parts[0], "--boot-recover")
        self.assertIn("/packages/", parts[1])
        self.assertIn("/.recover-", parts[2])
        self.assertEqual(out["RES"], "0")
        self.assertTrue(out["NORMAL"].endswith("/feature/sm.conf"))
        self.assertTrue(ig_ran)

    def test_real_boot_recover_bootstrap_fails_closed_on_tampered_digest_or_bad_mount(self):
        for label, cfg in (
            ("tampered_install_digest", {"tamper_install_digest": True}),
            (
                "unexpected_data_mount",
                {
                    "mounts": (
                        "rootfs / rootfs rw 0 0\n"
                        "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
                        "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
                        "tmpfs @DATA@/packages tmpfs rw 0 0\n"
                    )
                },
            ),
        ):
            with self.subTest(case=label):
                out, _, ig_ran, rec_ran, _ = self._run_hook(
                    'if [ "$1" = select-gated ]; then printf "J"; exit 95; fi\nexit 0',
                    with_ignition=True,
                    real_recover=cfg,
                )
                self.assertFalse(rec_ran)
                self.assertEqual(out["RES"], "1")
                self.assertEqual(out["NORMAL"], "stock-normal")
                self.assertEqual(out["WCP"], "stock-wcp")
                self.assertFalse(ig_ran)


if __name__ == "__main__":
    unittest.main()
