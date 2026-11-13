"""Freeze inputs, build private candidate, run focused host tests, retain evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import patch

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    evidence = REPO / 'runs' / (stamp + '-t12-disclaimer-host')
    evidence.mkdir(mode=0o700)
    snapshots = evidence / 'source'
    snapshots.mkdir()
    sources = {}
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.js', '.txt', '.json') and path.name != 'freeze.json':
            shutil.copyfile(path, snapshots / path.name)
            sources[str(path.relative_to(REPO))] = digest(path)
    original = patch.DEFAULT_ORIGINAL
    source_meta_path = original.parents[6] / 'systemapp-exact-result.json'
    # Keep exact operator capture metadata alongside copied test inputs.
    shutil.copyfile(source_meta_path, evidence / 'source-acquisition.json')
    candidate_plan = patch.build(original, evidence / 'candidate')
    completed = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                                '-s', str(ROOT), '-p', 'test_patch.py', '-v'],
                               cwd=REPO, capture_output=True, text=True, timeout=45)
    transcript = completed.stdout + completed.stderr
    (evidence / 'tests.txt').write_text(transcript)
    same = all(digest(REPO / name) == value for name, value in sources.items())
    passed = completed.returncode == 0 and same and digest(original) == patch.BASE_SHA256
    result = {
        'question': 'OEM-derived first-display fast timeout; no target install',
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'passed': passed, 'exit_code': completed.returncode, 'source_sha256': sources,
        'pretest_source_copies': 'source/', 'source_unchanged_after_checks': same,
        'original': {'path': str(original.relative_to(REPO)), 'sha256': digest(original),
                     'bytes': original.stat().st_size, 'capture_metadata': 'source-acquisition.json'},
        'plan': candidate_plan, 'tests': 'tests.txt', 'tests_sha256': digest(evidence / 'tests.txt'),
        'python': sys.version, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
        'third_party_implementation_read': False, 'target_modified': False,
        'limits': 'Host semantic/byte tests only; startup/render/nativeMMUI/installation/recovery unvalidated'
    }
    (evidence / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(transcript, end='')
    print('EVIDENCE ' + str(evidence), flush=True)
    print('MANIFEST_SHA256 ' + digest(evidence / 'manifest.json'), flush=True)
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
