"""Few confined host checks; produces only a VERIFY live-handoff candidate."""
from datetime import datetime,timezone
import hashlib,json,secrets,shutil,subprocess,sys
from pathlib import Path
import prepare
HERE=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 out=HERE/'checks'/stamp;copies=out/'source';copies.mkdir(parents=True);pins={}
 for path in sorted(HERE.iterdir()):
  if path.is_file() and path.suffix in ('.py','.in'):
   shutil.copyfile(path,copies/path.name);pins[path.name]=digest(path)
 result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_inspection.py','-v'],capture_output=True,text=True,timeout=210)
 (out/'tests.txt').write_text(result.stdout+result.stderr)
 same=all(digest(HERE/name)==value for name,value in pins.items());passed=result.returncode==0 and same
 ready=None
 if passed:
  ready=out/'ready-VERIFY'
  generated=subprocess.run([sys.executable,'-B',str(HERE/'prepare.py'),'--mode','VERIFY','--nonce',secrets.token_hex(16),'--out',str(ready)],capture_output=True,text=True,timeout=10)
  (out/'prepare.txt').write_text(generated.stdout+generated.stderr);passed=generated.returncode==0
 record=dict(passed=passed,tests=6,exit_code=result.returncode,source_sha256=pins,source_copies='source/',source_unchanged=same,ready_VERIFY=str(ready) if ready else None,tests_sha256=digest(out/'tests.txt'),fixture=str(prepare.retained.FIXTURE),scope='HOST byte/mode/inode checks with logical UID/GID/device fakes; no UART/native mount/sync; restore remains review-only',live_scope='ONE VERIFY on current original only')
 (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 print(result.stdout+result.stderr,end='');print('EVIDENCE '+str(out));print('READY_VERIFY '+str(ready));print('PASS '+str(passed),flush=True)
 return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
