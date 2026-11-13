"""Focused explicit COMPLETE recovery, adapter and default-ABORT regressions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import disclaimer_adapter as adapter

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_pins():
    if digest(adapter.FREEZE) != adapter.FREEZE_SHA:
        raise RuntimeError('frozen independent record changed')
    record = json.loads(adapter.FREEZE.read_text())
    pins = record['code_and_design_sha256']
    if not all(digest(adapter.REPO / path) == value for path, value in pins.items()):
        raise RuntimeError('frozen independent files changed')
    return pins


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    evidence = ROOT / 'adapter-checks' / stamp
    copies = evidence / 'source'; copies.mkdir(parents=True)
    sources = {}
    for path in sorted(ROOT.glob('*.py')):
        shutil.copyfile(path, copies / path.name)
        sources[path.name] = digest(path)
    pins = frozen_pins()
    # Authored pure patch only: no OEM originals or candidate bytes copied into tracked paths.
    shutil.copyfile(adapter.REPO / 'experiments/disclaimer/patch.py', copies / 'frozen-disclaimer-patch.py')
    completed = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                                '-s', str(ROOT), '-p', 'test_*.py', '-v'],
                               capture_output=True, text=True, timeout=45)
    transcript = completed.stdout + completed.stderr
    (evidence / 'tests.txt').write_text(transcript)
    report = None
    if completed.returncode == 0:
        try:
            report = adapter.demo()
            (evidence / 'demo.json').write_text(json.dumps(report, indent=2) + '\n')
        except Exception:
            (evidence / 'demo-error.txt').write_text(traceback.format_exc())
    same = all(digest(ROOT / name) == value for name, value in sources.items())
    unchanged = frozen_pins() == pins
    status = ('FAIL' if completed.returncode != 0 or not same or not unchanged or report is None
              else report['result'])
    result = {'status': status, 'passed': status == 'PASS',
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'tests': {'existing_engine': 6, 'existing_adapter': 4, 'explicit_completion': 6,
                        'exit_code': completed.returncode},
              'source_sha256': sources, 'source_copies': 'source/', 'source_unchanged': same,
              'frozen_disclaimer_sha256': adapter.FREEZE_SHA, 'frozen_disclaimer_pins': pins,
              'frozen_disclaimer_unchanged': unchanged,
              'tests_sha256': digest(evidence / 'tests.txt'),
              'demo_sha256': digest(evidence / 'demo.json') if report is not None else None,
              'scope': 'temporary private host COPIES only; OEM bytes never stored in feature/evidence source copies',
              'recovery_api': 'complete_uninstall() opt-in; recover() retains ABORT',
              'device_actions': False, 'python': sys.version,
              'limitations': 'As-found55 exact-byte support; host process exit and bytes+mode, not device/startup/power-loss proof'}
    (evidence / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(transcript, end='')
    print('PRIVATE COPY DEMO ' + status, flush=True)
    print('EVIDENCE ' + str(evidence), flush=True)
    print('MANIFEST_SHA256 ' + digest(evidence / 'manifest.json'), flush=True)
    return 0 if status in ('PASS', 'SKIP') else 1


if __name__ == '__main__':
    raise SystemExit(main())
