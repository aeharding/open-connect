#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
run=HERE/'root-checks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');run.mkdir(parents=True)
pins={}
for p in [HERE/'root_review.py',HERE/'test_root.py',HERE/'check_root.py',HERE/'prepare.py',ROOT/'experiments/disclaimer-recovery-inspection/inspect.sh.in',ROOT/'experiments/disclaimer-recovery-inspection/restore.review.sh.in',ROOT/'experiments/disclaimer-warm-roundtrip/warm.sh.in']:
 rel=p.relative_to(ROOT);data=p.read_bytes();dest=run/'sources'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);pins[str(rel)]=hashlib.sha256(data).hexdigest()
argv=[sys.executable,'-B','-m','unittest','-v',*(sys.argv[1:] or ['test_root'])];p=subprocess.run(argv,cwd=HERE,capture_output=True)
(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr)
(run/'manifest.json').write_text(json.dumps(dict(scope='host private images + existing mount/sync contract fakes; NO DEVICE/REBOOT',command=argv,source_sha256=pins,returncode=p.returncode),indent=2)+'\n')
print(p.stdout.decode(),end='');print(p.stderr.decode(),end='');print('EVIDENCE',run);print('PASS',p.returncode==0)
raise SystemExit(p.returncode)
