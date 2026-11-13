#!/usr/bin/env python3
"""One restored-stock O9456 confirmation; default offline, no mutation interface."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
FIELD_PROFILE=ROOT/'experiments/disclaimer-startup-trial/boot/field-marker-review.json'
FIELD_SOURCE=ROOT/'experiments/disclaimer-startup-trial/boot/observe.py'
AUTHORITY=ROOT/'notes/restored-stock-startup-handoff.txt'
EXPECTED_O='64785:9456:1433953097:94058:755:1018:3015:1'
OMD5='584c67f7186ada6bae9aae1be59b5cd0'
OCRC='376717896 94058'
RETAINED_NONCE='388ae4f695d2b19f0945f2d8428fca7e'
PROOFS=['runs/20261113T073945-0600-t14-modified-startup/independent-undo/manifest.json',
        'runs/20261113T073945-0600-t14-modified-startup/final-independent-verify/manifest.json']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_helpers():
 profile=json.loads(FIELD_PROFILE.read_text())
 for name,pin in profile['source_pins'].items():
  if sha(ROOT/name)!=pin:raise ValueError('checked field/parser dependency changed')
 spec=importlib.util.spec_from_file_location('_restored_stock_field_helpers',FIELD_SOURCE)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module


fields=load_helpers()
stock=fields.stock
# These are the checked corrected implementations, not forks.
BootGate,Video,Session=stock.BootGate,stock.Video,stock.Session


def checked_original_output(status,raw,before=None):
 if status!=0:raise ValueError('original check nonzero')
 found=fields.candidate_fields(raw)
 fields.observed_identity(found['META'])
 if found['HASH'].split()!=[OMD5,'-'] or ' '.join(found['CRC'].split())!=OCRC:
  raise ValueError('source is not exact AS-FOUND O bytes')
 row=found['ROOT'].split()
 if (len(row)!=6 or row[:3]!=['/dev/ffx01p1','/','relfs'] or
     'ro' not in row[3].split(',') or 'rw' in row[3].split(',')):
  raise ValueError('original physical root is not RO')
 uptime=float(found['UPTIME'].split()[0])
 if not math.isfinite(uptime) or uptime<0:raise ValueError('invalid O uptime')
 if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',found['BOOT_ID']):
  raise ValueError('invalid O boot identity')
 found.update(uptime_seconds=uptime,source_kind='O',expected_original_identity=EXPECTED_O)
 if found['META']!=EXPECTED_O:
  found.update(source_kind='OTHER',identity_conflict=True,automatic_adoption=False)
  raise OriginalIdentityConflict(found)
 if before and (found['BOOT_ID']==before['BOOT_ID'] or uptime>=before['uptime_seconds']):
  raise ValueError('fresh O boot/lower uptime not established')
 return found


class OriginalIdentityConflict(ValueError):
 def __init__(self,observation):
  self.observation=observation
  super().__init__('O full identity conflict/OTHER; preserve/stop; no adoption')


# Fixed current retained code, verified by the accepted completed undo/VERIFY.
# No profile-supplied target command is executed. Explicit VERIFY is read-only.
VERIFY_COMMAND=r'''d=/tmp/mnt/data_persist/cmu-bench-startup-388ae4f695d2b19f0945f2d8428fca7e
p="$d/recovery.sh"
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = 45826:57:700:0:0 || exit 71
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = 45826:63:4521:14428:600:0:0:1 || exit 73
test "$(wc -c < "$p")" = 14428 || exit 74
test "$(md5sum < "$p")" = '080b60d3754f960038804715ee2450fc  -' || exit 75
test "$(cksum < "$p")" = '15793661 14428' || exit 76
/bin/sh "$p" VERIFY </dev/null
'''
VERIFY_END=('RECOVERY '+RETAINED_NONCE+' END mode=VERIFY rc=0 kind=O registry=disabled '
            'pending=none phase=original_restored writes=0 recovery_ready=1 current_id='+EXPECTED_O).encode()


def retained_verified(status,raw):
 if status!=0:raise ValueError('persistent readonly VERIFY failed')
 records=[]
 for line in raw.split(b'\n')[:-1]:
  if b'END mode=VERIFY' in line:
   if line.count(b'RECOVERY ')!=1:raise ValueError('ambiguous persistent VERIFY record')
   records.append(line[line.index(b'RECOVERY '):].removesuffix(b'\r'))
 if records!=[VERIFY_END]:raise ValueError('persistent O/disablednone/writes0 record missing or duplicate')


def profile(live=False):
 pins=dict(json.loads(FIELD_PROFILE.read_text())['source_pins'])
 pins[str(FIELD_PROFILE.relative_to(ROOT))]=sha(FIELD_PROFILE)
 pins[str(Path(__file__).resolve().relative_to(ROOT))]=sha(__file__)
 return dict(mode='ONE_RESTORED_STOCK_O_CONFIRMATION',live_authority=live,
  normal_reboot_route_verified=live,reboot_hex=stock.REBOOT.hex() if live else None,
  source_kind='O',source_identity=EXPECTED_O,md5=OMD5,crc=OCRC,
  request_limit=1,credential_attempts=1,deadline_s=180,
  identity_policy='exact_full_O9456_or_conflict_no_adoption',
  accepted_completed_evidence=PROOFS,authority=str(AUTHORITY.relative_to(ROOT)),
  authority_sha256=sha(AUTHORITY),source_pins=pins,
  persistent_verify_command_sha256=hashlib.sha256(VERIFY_COMMAND.encode()).hexdigest(),
  scope='one NEW stock confirmation only; no source writes/mount/sync/cache/restore mode')


def approved(path):
 p=fields.json_data(path)
 expected=profile(live=True)
 for key in ('live_authority','normal_reboot_route_verified','reboot_hex','source_kind',
             'source_identity','md5','crc','request_limit','credential_attempts','deadline_s',
             'identity_policy','authority','authority_sha256','persistent_verify_command_sha256'):
  if p.get(key)!=expected[key]:raise ValueError('not an approved exact restored-stock profile')
 if p.get('source_pins')!=expected['source_pins']:raise ValueError('restored-stock source pins changed')
 return p


def run(argv):
 base_session=stock.Session;base_bundle=stock.Bundle;base_checker=stock.checked_output
 class OriginalBundle(base_bundle):
  def __init__(self,path,intent,owner,**kw):
   super().__init__(path,'ONE restored-stock O9456 startup confirmation',owner,**kw)
   self.meta.update(expected_source_kind='O',accepted_original_identity=EXPECTED_O)
 class VerifiedSession(base_session):
  def __init__(self,*a,**kw):super().__init__(*a,**kw);self.original_before=None
  def execute(self,command,**kw):
   result=super().execute(command,**kw)
   if command==stock.CHECK:
    try:observation=checked_original_output(*result,before=self.original_before)
    except OriginalIdentityConflict as exc:
     self.bundle.save('original-conflict.json',(json.dumps(exc.observation,indent=2)+'\n').encode())
     self.bundle.event('original_identity_conflict',actual_identity=exc.observation['META'],preserve=True,automatic_adoption=False)
     raise
    phase='postboot' if self.original_before else 'preflight'
    retained_verified(*super().execute(VERIFY_COMMAND))
    self.bundle.event('persistent_original_verified',phase=phase,source_kind='O',writes=0,registry='disabled',pending='none')
    if self.original_before is None:self.original_before=observation
   return result
 try:
  stock.Session=VerifiedSession;stock.Bundle=OriginalBundle;stock.checked_output=checked_original_output
  return stock.main(argv)
 finally:
  stock.Session=base_session;stock.Bundle=base_bundle;stock.checked_output=base_checker


def main(argv=None):
 argv=sys.argv[1:] if argv is None else argv
 p=argparse.ArgumentParser(description=__doc__,add_help=False)
 p.add_argument('--live',action='store_true');p.add_argument('--profile',type=Path)
 args,_=p.parse_known_args(argv)
 if not args.live:
  print(json.dumps(profile(),indent=2));return 0
 if args.profile is None:raise ValueError('checked restored-stock profile required')
 approved(args.profile)  # before credentials, lock, port or camera
 return run(argv)

if __name__=='__main__':raise SystemExit(main())
