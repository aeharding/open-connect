#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
run=HERE/'checks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');run.mkdir(parents=True)
pins={}
for p in [HERE/'observe.py',HERE/'test_observe.py',HERE/'check.py']:
 rel=p.relative_to(ROOT);data=p.read_bytes();dest=run/'sources'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);pins[str(rel)]=hashlib.sha256(data).hexdigest()
argv=[sys.executable,'-B','-m','unittest','-v','test_observe'];p=subprocess.run(argv,cwd=HERE,capture_output=True)
(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr)
manifest=dict(scope='OFFLINE new O wrapper focused synthetic Session/Video only; no hardware/target',command=argv,returncode=p.returncode,source_sha256=pins)
(run/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if p.returncode==0:
 import observe
 v=observe.profile(live=True);v.update(test_manifest=str((run/'manifest.json').relative_to(ROOT)),test_manifest_sha256=hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest())
 (HERE/'ready.json').write_text(json.dumps(v,indent=2)+'\n')
print(p.stdout.decode(),end='');print(p.stderr.decode(),end='');print('EVIDENCE',run);print('PASS',p.returncode==0)
raise SystemExit(p.returncode)
