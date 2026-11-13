#!/usr/bin/env python3
"""Small offline transition checks with exact pre-test source copies."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
run=HERE/'checks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
run.mkdir(parents=True,mode=0o700)
files=[HERE/'observe.py',HERE/'test_observer.py',HERE/'check.py',ROOT/'src/open_connect/session.py']
files += [p for p in [HERE/'replay.py',HERE/'fixtures/logger-boot.txt'] if p.exists()]
pins={}
for p in files:
    rel=p.relative_to(ROOT);b=p.read_bytes();target=run/'sources'/rel
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
    pins[str(rel)]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
if len(sys.argv)>1:
    argv=[sys.executable,'-B','-m','unittest','-v',*sys.argv[1:]]
    cwd=HERE
else:
    argv=[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_observer.py','-v']
    cwd=ROOT
p=subprocess.run(argv,cwd=cwd,capture_output=True)
(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr)
manifest=dict(scope='offline synthetic transitions only; no camera/UART/reboot',returncode=p.returncode,sources=pins)
(run/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(p.stdout.decode(),end='');print(p.stderr.decode(),end='')
print('EVIDENCE',run);print('PASS',p.returncode==0)
raise SystemExit(p.returncode)
