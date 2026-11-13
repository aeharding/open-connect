"""UI001 offline tests with exact pre-test source copies and hash provenance."""
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT))
frozen=[ROOT/p for p in ('scripts/cmu-session.py','cmu_bench/session.py','cmu_bench/files.py','cmu_bench/__init__.py')]
frozen+=list((ROOT/'tests').glob('*.py'))
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
folder=HERE/'test-evidence'/stamp
folder.mkdir(mode=0o700,parents=True)
# Preserve bytes BEFORE execution, including this runner and frozen dependencies.
sources=sorted(set(frozen+[p for p in HERE.iterdir() if p.is_file()]))
source_copies={}
for path in sources:
    data=path.read_bytes();name=str(path.relative_to(ROOT))
    target=folder/'source'/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    target.write_bytes(data)
    source_copies[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),snapshot=str(target.relative_to(folder)))
log=io.StringIO()
suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_watchdog.py')
result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(folder/'tests.txt').write_text(log.getvalue())
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
source_stable=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==entry['sha256'] for name,entry in source_copies.items())
record=dict(scope='UI001 local shell/synthetic proc/fake child ONLY; host-timeout model uses local timeout shim',
            question='Own-identity cleanup including startup/errors/host timeout and honest readiness?',
            firmware_scope='55.00.750B cmu150_NA applicability; no live action',real_uart_opened=False,real_camera_opened=False,
            command='hc run --bg --name ui001-final-tests --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/run_tests.py',
            source_copies=source_copies,source_bytes_stable_during_tests=source_stable,
            frozen_harness_before=before,frozen_harness_after=after,harness_unchanged=(before==after),
            tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),
            started_at=stamp,ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            test_log_sha256=hashlib.sha256((folder/'tests.txt').read_bytes()).hexdigest(),
            cleanup='Owned fake children finite2.5s, reaped/observed exit; temp fixtures removed; only local owned group cleanup on unexpected test timeout',
            limitation='Modeled proc/clock/timeout do not prove vendor runtime. No actual host serial close -> target HUP assumption.',
            original_draft_provenance_gap='Initial failed source .in/.py not copied before overwrite; original rendered prepared payload and6/8-test hashes/logs retained; no reconstructed originals claimed')
(folder/'manifest.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(log.getvalue());print('DURABLE UI001 TEST EVIDENCE:',folder)
assert before==after and source_stable,'Source changed during test run'
raise SystemExit(0 if result.wasSuccessful() else 1)
