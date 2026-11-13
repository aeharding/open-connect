"""Focused offline review checks. Never executes the production remount payload."""
from datetime import datetime,timezone
import hashlib,json,secrets,shutil,subprocess,sys
from pathlib import Path
import prepare
HERE=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 out=HERE/'checks'/stamp;copies=out/'source';copies.mkdir(parents=True)
 pins={}
 for path in sorted(HERE.iterdir()):
  if path.is_file() and path.suffix in ('.py','.in'):
   shutil.copyfile(path,copies/path.name);pins[path.name]=digest(path)
 frozen_before=digest(prepare.FREEZE)
 result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_warm.py','-v'],capture_output=True,text=True,timeout=240)
 (out/'tests.txt').write_text(result.stdout+result.stderr)
 same=all(digest(HERE/name)==value for name,value in pins.items())
 passed=result.returncode==0 and same and digest(prepare.FREEZE)==frozen_before
 ready=None
 if passed:
  ready=out/'review-ready'
  rendered=subprocess.run([sys.executable,'-B',str(HERE/'prepare.py'),'--nonce',secrets.token_hex(16),'--out',str(ready)],capture_output=True,text=True,timeout=10)
  (out/'prepare.txt').write_text(rendered.stdout+rendered.stderr);passed=rendered.returncode==0
 record=dict(passed=passed,tests=8,exit_code=result.returncode,source_sha256=pins,source_copies='source/',source_unchanged=same,frozen_disclaimer_unchanged=digest(prepare.FREEZE)==frozen_before,review_ready=str(ready) if ready else None,tests_sha256=digest(out/'tests.txt'),scope='HOST contract fakes only; no native mount/sync/chown, no UART/CMU work, not BusyBox/RelFS equivalence',operator_handoff_authorized=False)
 (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 print(result.stdout+result.stderr,end='');print('EVIDENCE '+str(out));print('REVIEW_READY '+str(ready));print('PASS '+str(passed),flush=True)
 return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
