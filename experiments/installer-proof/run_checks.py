"""Run only this tiny experiment; preserve exact pre-test code, results and demo."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import demo

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    evidence = ROOT / 'checks' / stamp
    copies = evidence / 'source'; copies.mkdir(parents=True)
    sources = {}
    for source in sorted(ROOT.glob('*.py')):
        shutil.copyfile(source, copies / source.name)
        sources[source.name] = digest(source)
    completed = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                                '-s', str(ROOT), '-p', 'test_engine.py', '-v'],
                               capture_output=True, text=True, timeout=35)
    transcript = completed.stdout + completed.stderr
    (evidence / 'tests.txt').write_text(transcript)
    report = None
    if completed.returncode == 0:
        try:
            report = demo.run()
            (evidence / 'demo.json').write_text(json.dumps(report, indent=2) + '\n')
        except Exception:
            (evidence / 'demo-error.txt').write_text(traceback.format_exc())
    same = all(digest(ROOT / name) == value for name, value in sources.items())
    passed = completed.returncode == 0 and same and report is not None and report['result'] == 'PASS'
    result = {
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'passed': passed,
        'tests': 6, 'test_exit': completed.returncode, 'demo_passed': report is not None,
        'source_sha256': sources, 'source_copies': 'source/', 'source_unchanged_after_checks': same,
        'tests_sha256': digest(evidence / 'tests.txt'),
        'demo_sha256': digest(evidence / 'demo.json') if report is not None else None,
        'python': sys.version, 'scope': 'synthetic host temporary fixtures only; no device operations',
        'limitation': 'Process exit on host filesystem, not power loss/CMU/USB architecture or recovery proof'
    }
    (evidence / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(transcript, end='')
    if report is not None:
        print('DEMO ' + report['result'] + ': plan/apply/verify/reapply/reconfigure/uninstall/recover; conflicts preserved')
    print('EVIDENCE ' + str(evidence), flush=True)
    print('MANIFEST_SHA256 ' + digest(evidence / 'manifest.json'), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
