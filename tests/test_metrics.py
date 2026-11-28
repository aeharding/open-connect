"""Resource framing, PID races, missing RAM fields and the public dry-run boundary."""

import contextlib
import csv
import io
import json
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from open_connect import bench, metrics

TOKEN = "a" * 32
BOOT = "11111111-1111-1111-1111-111111111111"


def stat(pid=42, start=123):
    return f"{pid} (worker (test)) S " + " ".join(["0"] * 18 + [str(start)] + ["0"] * 8)


def trace(after=None):
    def marker(body):
        return f"\nOCM1 {TOKEN} {body}\n"

    result = "shell greeting without a newline" + marker("boot " + BOOT)
    result += marker("sample 0 12.50")
    for path in metrics.FILES:
        result += marker("file " + path)
        result += (
            "MemTotal: 1000 kB\nMemFree: 100 kB\nCached: 200 kB\n"
            if path.endswith("meminfo")
            else "UNAVAILABLE\n"
        )
    for path, body in (
        ("stat", stat()),
        ("status", "VmRSS: 20 kB"),
        ("io", "UNAVAILABLE"),
        ("stat", after or stat()),
    ):
        result += marker("file /proc/42/" + path) + body + "\n"
    return (result + marker("end 0 12.75") + marker("complete 1")).encode()


class MetricsTests(unittest.TestCase):
    def test_framed_trace_preserves_kernel_units_and_missing_fields(self):
        parsed = metrics.parse(trace(), TOKEN)
        self.assertEqual(parsed["boot_id"], BOOT)
        sample = parsed["samples"][0]
        self.assertEqual(
            sample["processes"]["42"],
            {"identity": {"pid": 42, "start_ticks": 123, "comm": "worker (test)"}, "stable": True},
        )
        self.assertEqual(sample["files"]["/proc/42/io"], ["UNAVAILABLE\n"])
        rows = list(csv.DictReader(io.StringIO(metrics.memory_csv(parsed))))
        self.assertEqual(rows[0]["MemFree_kB"], "100")
        self.assertEqual(rows[0]["MemAvailable_kB"], "")
        self.assertEqual(rows[0]["Slab_kB"], "")

    def test_pid_reuse_or_disappearance_never_qualifies_process_read(self):
        for after in (stat(start=456), stat(pid=43), "READ_FAILED"):
            parsed = metrics.parse(trace(after), TOKEN)
            self.assertFalse(parsed["samples"][0]["processes"]["42"]["stable"])

    def test_reuse_before_first_stat_cannot_select_an_unrequested_process(self):
        replacement = trace().replace(b"worker (test)", b"unrelated")
        parsed = metrics.parse(replacement, TOKEN, ["jci"])
        self.assertEqual(parsed["requested_processes"], ["jci"])
        self.assertFalse(parsed["samples"][0]["processes"]["42"]["stable"])
        parsed = metrics.parse(trace(), TOKEN, ["worker (test)"])
        self.assertTrue(parsed["samples"][0]["processes"]["42"]["stable"])
        parsed = metrics.parse(trace(), TOKEN, [])
        self.assertFalse(parsed["samples"][0]["processes"]["42"]["stable"])

    def test_partial_duplicate_reordered_and_foreign_frames_are_rejected(self):
        original = trace()
        cases = [
            original.rsplit(b"OCM1", 1)[0],
            original.replace(b"complete 1", b"complete 2"),
            original.replace(b"end 0", b"end 1"),
            original.replace(b"sample 0 12.50", b"sample 0 nan"),
            original + f"OCM1 {TOKEN} complete 1\n".encode(),
            original.replace(b"file /proc/stat", b"file /proc/other"),
            original.replace(b"boot " + BOOT.encode(), b"boot invalid"),
            original.replace(b"end 0 12.75", b"end 0 12.25"),
        ]
        for raw in cases:
            with self.subTest(raw=raw[-100:]), self.assertRaises(ValueError):
                metrics.parse(raw, TOKEN)
        with self.assertRaises(ValueError):
            metrics.parse(original, "b" * 32)

    def test_memory_read_failure_cannot_be_reported_as_zero(self):
        for raw in (
            trace().replace(b"MemTotal: 1000 kB", b"READ_FAILED"),
            trace().replace(b"Cached: 200 kB", b"Cached: 200 kB\nREAD_FAILED"),
        ):
            with self.assertRaises(ValueError):
                metrics.parse(raw, TOKEN)

    def test_front_door_dry_run_opens_no_transport(self):
        with (
            patch.object(metrics.subprocess, "Popen") as opener,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(bench.main(["sample", "--seconds", "5"]), 0)
        opener.assert_not_called()
        self.assertIn('"opens_ssh": false', output.getvalue())

    def test_alias_and_process_names_cannot_inject_commands(self):
        for args in (
            ["--host", "-oProxyCommand=bad"],
            ["--host", "$(bad)"],
            ["--process", "opera;bad"],
            ["--seconds", "601"],
        ):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                metrics.main(args)

    def test_live_front_door_preserves_sources_raw_failures_and_closes_ssh(self):
        real_popen = subprocess.Popen

        def fake_ssh(argv, **kwargs):
            words = shlex.split(argv[-1])
            token = words[words.index("--") + 3]
            body = trace().replace(TOKEN.encode(), token.encode())
            return real_popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdin.buffer.read(); "
                    "sys.stdout.buffer.write(bytes.fromhex(sys.argv[1])); sys.exit(int(sys.argv[2]))",
                    body.hex(),
                    str(exit_code),
                ],
                **kwargs,
            )

        for exit_code in (0, 7):
            with (
                tempfile.TemporaryDirectory() as tmp,
                patch.object(metrics.subprocess, "Popen", side_effect=fake_ssh),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                path = Path(tmp) / "trace"
                result = bench.main(["sample", "--live", "--seconds", "1", "--bundle", str(path)])
                manifest = json.loads((path / "manifest.json").read_text())
                self.assertEqual(result, 0 if exit_code == 0 else 1)
                self.assertEqual(
                    manifest["outcome"], "recorded" if exit_code == 0 else "incomplete_preserved"
                )
                self.assertTrue(manifest["ssh_closed"])
                self.assertEqual(
                    (path / "metrics.sh").read_bytes(),
                    (metrics.ROOT / "cmu/bench/metrics.sh").read_bytes(),
                )
                self.assertIn(b"complete 1", (path / "ssh.stdout").read_bytes())
                self.assertEqual((path / "memory.csv").exists(), exit_code == 0)

    def test_interrupt_keeps_partial_output_and_terminates_only_owned_ssh(self):
        real_popen = subprocess.Popen
        children = []
        stdout_path = None

        class Interrupted:
            def __init__(self, process):
                self.process = process

            def __getattr__(self, name):
                return getattr(self.process, name)

            def communicate(self, data=None, timeout=None):
                if data is not None:
                    self.process.stdin.write(data)
                    self.process.stdin.close()
                    self.process.stdin = None
                    deadline = time.monotonic() + 5.0
                    while time.monotonic() < deadline:
                        if stdout_path.exists() and stdout_path.stat().st_size >= len(
                            b"partial raw evidence"
                        ):
                            raise KeyboardInterrupt
                        if self.process.poll() is not None:
                            raise AssertionError("fixture child unexpectedly ended")
                        time.sleep(0.01)
                    raise AssertionError(
                        "fixture child did not flush partial output before timeout"
                    )
                return self.process.communicate(timeout=timeout)

        def fake_ssh(argv, **kwargs):
            process = real_popen(
                [
                    sys.executable,
                    "-c",
                    "import sys,time; sys.stdin.buffer.read(); "
                    "sys.stdout.buffer.write(b'partial raw evidence'); sys.stdout.buffer.flush(); time.sleep(60)",
                ],
                **kwargs,
            )
            children.append(process)
            return Interrupted(process)

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(metrics.subprocess, "Popen", side_effect=fake_ssh),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            path = Path(tmp) / "trace"
            stdout_path = path / "ssh.stdout"
            self.assertEqual(bench.main(["sample", "--live", "--bundle", str(path)]), 1)
            self.assertEqual(stdout_path.read_bytes(), b"partial raw evidence")
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual(manifest["outcome"], "incomplete_preserved")
            self.assertTrue(manifest["ssh_closed"])
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_collector_script_rejects_missing_empty_and_colon_args(self):
        script = metrics.ROOT / "cmu/bench/metrics.sh"
        for argv in (
            [],
            ["10", "1"],
            ["", "1", TOKEN],
            ["10", "", TOKEN],
            ["1:2", "1", TOKEN],
            ["10", "1:2", TOKEN],
        ):
            with self.subTest(argv=argv):
                res = subprocess.run(
                    ["/bin/sh", str(script), *argv],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(res.returncode, 64, res.stderr)
                self.assertEqual(res.stderr, "")

    def test_parse_tolerates_utf8_banner_before_boot_marker(self):
        raw = "Welcome — Mazda bench\n".encode() + trace()
        parsed = metrics.parse(raw, TOKEN)
        self.assertEqual(len(parsed["samples"]), 1)

    def test_main_records_system_exit_error_in_manifest(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(metrics.subprocess, "Popen", side_effect=SystemExit(7)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            path = Path(tmp) / "trace"
            self.assertEqual(bench.main(["sample", "--live", "--bundle", str(path)]), 1)
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual(manifest["outcome"], "incomplete_preserved")
            self.assertEqual(manifest["error"], "SystemExit: 7")
