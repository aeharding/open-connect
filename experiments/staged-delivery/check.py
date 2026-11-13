"""One offline check run, preserving the exact pre-test authored sources and dependency pins."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    out=HERE/'checks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    (out/'sources').mkdir(parents=True)
    pins={}
    for p in [HERE/'deliver.py',HERE/'test_deliver.py',HERE/'check.py']:
        data=p.read_bytes();(out/'sources'/p.name).write_bytes(data);pins[str(p.relative_to(ROOT))]=sha(data)
    deps={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in
          [ROOT/'src/open_connect/session.py',ROOT/'src/open_connect/files.py',ROOT/'src/open_connect/uart.py']}
    result=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_deliver'],cwd=HERE,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=180)
    (out/'stdout.txt').write_bytes(result.stdout);(out/'stderr.txt').write_bytes(result.stderr)
    manifest=dict(schema=1,scope='offline staged DATA delivery/cleanup contract; no hardware',
                  hardware_opened=False,payload_executed=False,returncode=result.returncode,
                  source_sha256=pins,dependency_sha256=deps,
                  evidence={k:sha((out/k).read_bytes()) for k in ['stdout.txt','stderr.txt']})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sys.stdout.buffer.write(result.stdout);sys.stdout.buffer.write(result.stderr)
    print('EVIDENCE',out,flush=True)
    if result.returncode==0:
        review=dict(schema=1,live_authority=False,hardware_validated=False,default='dry_run',
                    entry='experiments/staged-delivery/deliver.py',
                    checks=str((out/'manifest.json').relative_to(ROOT)),
                    source_sha256=pins,dependency_sha256=deps,
                    target='/tmp/cmu-bench-payload-<fresh32hex>/p',max_bytes=16384,
                    payload_execution=False,cleanup='explicit; exact observed identity/hash; preserve conflicts')
        (HERE/'review.json').write_text(json.dumps(review,indent=2)+'\n')
    return result.returncode
if __name__=='__main__':raise SystemExit(main())
