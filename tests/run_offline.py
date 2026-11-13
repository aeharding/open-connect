"""Run synthetic/PTY tests and retain immutable evidence under examples/ only."""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import serial

stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
path = ROOT / "examples" / "tooling-runs" / stamp
path.mkdir(parents=True, mode=0o700)
log = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
(path / "tests.txt").write_text(log.getvalue())
source = {}
for pattern in ("cmu_bench/*.py", "scripts/cmu-session.py", "tests/*.py"):
    for p in ROOT.glob(pattern):
        source[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
manifest = dict(question="Does the offline vertical slice preserve evidence and fail closed?",
                firmware_scope="55.00.750B cmu150_NA; no real device used", mode="offline_only",
                hardware_opened=False, camera_opened=False, synthetic_pty_only=True,
                command="hc run --bg --name cmu-tooling-tests --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B tests/run_offline.py",
                started_at=stamp, ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                passed=result.wasSuccessful(), python=sys.version, pyserial=serial.VERSION,
                platform=platform.platform(), source_sha256=source,
                test_log_sha256=hashlib.sha256((path / "tests.txt").read_bytes()).hexdigest(),
                cleanup="PTY child owned by each test terminated/reaped; temp bundles/locks removed; real UART/camera never opened",
                interpretation="Host/PTY evidence only; no live CMU or recovery claim")
(path / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(log.getvalue())
print("DURABLE TEST EVIDENCE:", path)
raise SystemExit(0 if result.wasSuccessful() else 1)
