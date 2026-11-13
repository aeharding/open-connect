"""Focused overlay checks only; exact pre-test source copies, no hardware."""
import datetime,hashlib,io,json
from pathlib import Path
import sys,unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT))
folder=HERE/'checks'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
folder.mkdir(parents=True)
paths=list(HERE.glob('*.py'))+[ROOT/p for p in ['experiments/ui001/watchdog.sh.in','experiments/ui001/prepare.py','experiments/ui001/invoke.py','experiments/ui001/test_watchdog.py','experiments/ui001/fake_dialog.py','src/open_connect/session.py','src/open_connect/uart.py']]
pins={}
for p in paths:
 data=p.read_bytes();name=str(p.relative_to(ROOT));out=folder/'source'/name
 out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data);pins[name]=hashlib.sha256(data).hexdigest()
log=io.StringIO();suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_overlay.py')
r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(folder/'tests.txt').write_text(log.getvalue())
record=dict(tests=r.testsRun,passed=r.wasSuccessful(),failures=len(r.failures),errors=len(r.errors),source_sha256=pins,hardware_opened=False,scope='overlay bounds/quoting/owned-cleanup only; local existing shell/fake model',command='hc run --bg --name status-overlay-checks --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/status-overlay/run_checks.py')
(folder/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(log.getvalue());print('EVIDENCE',folder)
raise SystemExit(0 if r.wasSuccessful() else 1)
