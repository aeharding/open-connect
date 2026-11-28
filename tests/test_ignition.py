"""Offline host ASan+UBSan execution tests for cmu/installer/ignition.c."""

import fcntl
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.host_bins import host_ignition

BOOT_ID = "12345678-1234-1234-1234-123456789abc"
REV = "a" * 32
PKG = "b" * 64
BASE = "c" * 64
CUR = "d" * 64
AFTER = "e" * 64
SLEEP_MS = 80


def _make_record(phase="active", before="-", after="-", off="-", boot=BOOT_ID):
    return f"OC1|{phase}|{REV}|{PKG}|{BASE}|{CUR}|{before}|{after}|-|2|{off}|{boot}|-\n"


def _write_atomic(path: Path, text: str, mode: int = 0o600):
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp.write_text(text)
    tmp.chmod(mode)
    os.replace(tmp, path)


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class IgnitionObserverTests(unittest.TestCase):
    def _setup_env(self, root: Path, *, phase="active", before="-", after="-"):
        ram = root / "tmp/open-connect"
        data = root / "tmp/mnt/data_persist/open-connect"
        gpio = root / "sys/class/gpio/ACC_Sense"
        dev_dir = root / "dev"
        ram.mkdir(parents=True, mode=0o700)
        data.mkdir(parents=True, mode=0o700)
        gpio.mkdir(parents=True, mode=0o755)
        dev_dir.mkdir(parents=True, mode=0o755)
        (dev_dir / "urandom").write_bytes(os.urandom(64))
        ram.chmod(0o700)
        data.chmod(0o700)
        (ram / "boot-id").symlink_to(BOOT_ID)
        (ram / "lock").touch(mode=0o600)
        (ram / "lock").chmod(0o600)
        rec = data / "record"
        _write_atomic(rec, _make_record(phase=phase, before=before, after=after), 0o600)
        acc = gpio / "value"
        _write_atomic(acc, "1\n", 0o644)
        env = {
            **os.environ,
            "OC_HOST_ROOT": str(root),
            "OC_HOST_NONROOT": "1",
            "OC_HOST_IGNITION_SLEEP_MS": str(SLEEP_MS),
        }
        return ram, data, acc, env

    def _wait_locked(self, lock_path: Path, proc: subprocess.Popen, timeout: float = 5.0):
        """Wait until the child holds an exclusive flock on ignition.lock."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                _, err = proc.communicate(timeout=1)
                self.fail(
                    f"ignition exited early ({proc.returncode}): {err.decode('utf-8', 'replace')}"
                )
            if lock_path.exists():
                with open(lock_path, "r+b") as lf:
                    try:
                        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return
                    else:
                        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            time.sleep(0.01)
        self.fail("ignition did not acquire ignition.lock before timeout")

    def _wait_off(self, rec_path: Path, expected: str, timeout: float = 3.0):
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            if rec_path.exists():
                last = rec_path.read_text()
                fields = last.strip().split("|")
                if len(fields) == 13 and fields[10] == expected:
                    return fields
            time.sleep(0.01)
        self.fail(f"record field[10] did not reach {expected!r}; last={last!r}")

    def test_acc_bounce_sustained_off_quickstart_resume_and_boot_id_exit(self):
        ig = host_ignition()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            ram, data, acc, env = self._setup_env(root)
            rec = data / "record"
            proc = subprocess.Popen(
                [str(ig), BOOT_ID], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
            )
            try:
                # Wait until observer holds ignition.lock and completes >=1 ACC=1 poll (seen_on=1).
                self._wait_locked(ram / "ignition.lock", proc)
                time.sleep(SLEEP_MS / 1000 * 2.5)
                self.assertEqual(rec.read_text().strip().split("|")[2], REV)
                # Brief ACC=0 bounce (<3 samples at 50 ms) must NOT rewrite the record or persist R_OFF.
                _write_atomic(acc, "0\n", 0o644)
                time.sleep(SLEEP_MS / 1000 * 0.7)
                _write_atomic(acc, "1\n", 0o644)
                time.sleep(SLEEP_MS / 1000 * 2.5)
                fields = rec.read_text().strip().split("|")
                self.assertEqual(
                    fields[2], REV, "bounce must not trigger any atomic record rewrite"
                )
                self.assertEqual(fields[10], "-")
                # Sustained ACC=0 (>=3 samples) persists R_OFF=BOOT_ID with fresh nonce.
                _write_atomic(acc, "0\n", 0o644)
                off_fields = self._wait_off(rec, BOOT_ID)
                self.assertNotEqual(off_fields[2], REV)
                self.assertEqual(rec.stat().st_mode & 0o777, 0o600)
                # QuickStart resume (ACC=1 in same kernel) clears R_OFF back to "-".
                _write_atomic(acc, "1\n", 0o644)
                self._wait_off(rec, "-")
                # Removing boot-id exits cleanly with code 0.
                (ram / "boot-id").unlink()
                _, err = proc.communicate(timeout=3)
                self.assertEqual(proc.returncode, 0, err.decode("utf-8", "replace"))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()

    def test_single_instance_lock_and_ram_lock_contention_retry(self):
        ig = host_ignition()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            ram, data, acc, env = self._setup_env(root)
            rec = data / "record"
            proc = subprocess.Popen(
                [str(ig), BOOT_ID], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
            )
            try:
                self._wait_locked(ram / "ignition.lock", proc)
                time.sleep(SLEEP_MS / 1000 * 2.5)
                # Second instance exits 0 immediately on EWOULDBLOCK.
                second = subprocess.run(
                    [str(ig), BOOT_ID], capture_output=True, text=True, timeout=3, env=env
                )
                self.assertEqual(second.returncode, 0, second.stderr)
                # Hold ram/lock while ACC drops to 0: observer must retry, not die!
                with open(ram / "lock", "r+b") as lf:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    _write_atomic(acc, "0\n", 0o644)
                    time.sleep(SLEEP_MS / 1000 * 5)
                    self.assertIsNone(proc.poll(), "observer died under ram/lock contention")
                    self.assertEqual(rec.read_text().strip().split("|")[10], "-")
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                self._wait_off(rec, BOOT_ID)
                (ram / "boot-id").unlink()
                _, err = proc.communicate(timeout=3)
                self.assertEqual(proc.returncode, 0, err.decode("utf-8", "replace"))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()

    def test_survives_transient_pending_record_and_exits_on_removed(self):
        ig = host_ignition()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            ram, data, acc, env = self._setup_env(root, phase="set", before=CUR, after=AFTER)
            rec = data / "record"
            proc = subprocess.Popen(
                [str(ig), BOOT_ID], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
            )
            try:
                self._wait_locked(ram / "ignition.lock", proc)
                time.sleep(SLEEP_MS / 1000 * 2.5)
                # ACC drops to 0 while record is transiently in "set" phase.
                _write_atomic(acc, "0\n", 0o644)
                time.sleep(SLEEP_MS / 1000 * 5)
                self.assertIsNone(proc.poll(), "observer permanently died on pending 'set' phase")
                self.assertEqual(rec.read_text().strip().split("|")[10], "-")
                # Once record settles back to "active", observer immediately persists R_OFF!
                _write_atomic(rec, _make_record(phase="active"), 0o600)
                self._wait_off(rec, BOOT_ID)
                # On uninstall ("removed"), next ACC transition exits non-zero cleanly.
                _write_atomic(rec, _make_record(phase="removed"), 0o600)
                _write_atomic(acc, "1\n", 0o644)
                _, err = proc.communicate(timeout=3)
                self.assertEqual(proc.returncode, 1, err.decode("utf-8", "replace"))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()


if __name__ == "__main__":
    unittest.main()
