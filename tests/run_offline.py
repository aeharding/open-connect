"""Run offline tests; preserve exact source bytes BEFORE execution under runs/tests/."""

import datetime
import hashlib
import io
import json
import os
import platform
import sys
import unittest
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
path = ROOT / "runs/tests" / stamp
path.mkdir(parents=True, mode=0o700)
source = {}
copies = {}
for pattern in ("src/open_connect/*.py", "tests/*.py"):
    for p in ROOT.glob(pattern):
        data = p.read_bytes()
        name = str(p.relative_to(ROOT))
        h = hashlib.sha256(data).hexdigest()
        target = path / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        source[name] = h
        copies[name] = dict(bytes=len(data), sha256=h, snapshot=str(target.relative_to(path)))
log = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
(path / "tests.txt").write_text(log.getvalue())
stable = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in source.items())
manifest = dict(
    question="Do the host CLI, bench profile and UART/file operations pass offline?",
    firmware_scope="55.00.750B cmu150_NA; no real device used",
    mode="offline_only",
    hardware_opened=False,
    camera_opened=False,
    synthetic_pty_only=True,
    command="python tests/run_offline.py",
    started_at=stamp,
    ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    tests=result.testsRun,
    failures=len(result.failures),
    errors=len(result.errors),
    passed=result.wasSuccessful(),
    python=sys.version,
    pyserial=serial.VERSION,
    platform=platform.platform(),
    source_sha256=source,
    source_copies=copies,
    source_bytes_stable_during_tests=stable,
    test_log_sha256=hashlib.sha256((path / "tests.txt").read_bytes()).hexdigest(),
    cleanup="Owned PTY children terminated/reaped and temp bundles/locks removed; no real UART/camera",
    interpretation="Host/PTY evidence only; no live calibration/CMU flow-control or recovery claim",
)
(path / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(log.getvalue())
print("DURABLE TEST EVIDENCE:", path)
assert stable, "source changed during tests"
raise SystemExit(0 if result.wasSuccessful() else 1)
