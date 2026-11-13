"""Focused shell/guard checks, pre-test source copies and ONE review-only preparation."""
from datetime import datetime,timezone
import hashlib,json,secrets,shutil,subprocess,sys
from pathlib import Path
import prepare
ROOT=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 out=ROOT/'checks'/stamp;copies=out/'source';copies.mkdir(parents=True)
 pins={}
 for path in sorted(ROOT.glob('*.py')):
  shutil.copyfile(path,copies/path.name);pins[path.name]=digest(path)
 shutil.copyfile(prepare.REFERENCE/'command.sh',copies/'passed-reference.sh')
 shutil.copyfile(prepare.REFERENCE/'plan.json',copies/'passed-reference-plan.json')
 result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT),'-p','test_transaction.py','-v'],capture_output=True,text=True,timeout=55)
 (out/'tests.txt').write_text(result.stdout+result.stderr)
 same=all(digest(ROOT/name)==value for name,value in pins.items())
 passed=result.returncode==0 and same
 ready=None
 if passed:
  ready=out/'ready-stop'
  generated=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),'--phase','stop','--nonce',secrets.token_hex(16),'--out',str(ready)],capture_output=True,text=True,timeout=5)
  (out/'prepare.txt').write_text(generated.stdout+generated.stderr)
  passed=generated.returncode==0
 record=dict(passed=passed,tests=4,exit_code=result.returncode,source_sha256=pins,source_copies='source/',source_unchanged=same,ready_stop=str(ready) if ready else None,tests_sha256=digest(out/'tests.txt'),scope='HOST syntax/owned-file/control-data checks with logical UID/GID/device shim; no BusyBox equivalence or device execution',reference=str(prepare.REFERENCE/'command.sh'),device_actions=False)
 (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 print(result.stdout+result.stderr,end='');print('EVIDENCE '+str(out));print('READY '+str(ready));print('PASS '+str(passed),flush=True)
 return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
