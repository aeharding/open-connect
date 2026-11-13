#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
run=HERE/'checks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');run.mkdir(parents=True)
pins={}
for p in [HERE/'prepare.py',HERE/'test_persistent.py',HERE/'check.py',ROOT/'experiments/disclaimer-recovery-inspection/inspect.sh.in',ROOT/'experiments/disclaimer-recovery-inspection/restore.review.sh.in',ROOT/'experiments/disclaimer-recovery-inspection/journal.py',ROOT/'experiments/target-copy-transaction/prepare.py']:
 rel=p.relative_to(ROOT);data=p.read_bytes();dest=run/'sources'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);pins[str(rel)]=hashlib.sha256(data).hexdigest()
argv=[sys.executable,'-B','-m','unittest','-v','test_persistent']
p=subprocess.run(argv,cwd=HERE,capture_output=True);(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr)
manifest=dict(scope='host private full-size copies/fakes only; no UART/camera/real target',command=argv,returncode=p.returncode,source_sha256=pins)
(run/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if p.returncode==0:
 import prepare
 prepare.save(run/'ready-copy',prepare.copy_phase1('0123456789abcdef0123456789abcdef'),dict(mode='COPY_ONLY',nonce='0123456789abcdef0123456789abcdef',real_root_authority=False))
print(p.stdout.decode(),end='');print(p.stderr.decode(),end='');print('EVIDENCE',run);print('PASS',p.returncode==0)
raise SystemExit(p.returncode)
