#!/usr/bin/env python3
"""Prepare isolated full-size persistent recovery rehearsal; never opens hardware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'experiments/disclaimer-recovery-inspection'))
import journal as old
from cmu_bench.session import wrap_command

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
copy=module('startup_passed_copy',ROOT/'experiments/target-copy-transaction/prepare.py')
warm=module('startup_frozen_inputs',ROOT/'experiments/disclaimer-warm-roundtrip/prepare.py')

def sha(b):return hashlib.sha256(b).hexdigest()
def nonce(v):
 if not re.fullmatch('[0-9a-f]{32}',v):raise ValueError('fresh32 lowercasehex nonce required')
 return v

def parse_record(raw,target_device=45826):
 if not 0<len(raw)<=2048 or raw.count(b'\n')!=1 or not raw.endswith(b'\n') or b'\0' in raw:raise ValueError('one bounded LF WARM1 record required')
 f=raw[:-1].decode('ascii').split('|')
 if len(f)!=12 or f[0]!='WARM1':raise ValueError('WARM1 header/fields')
 out={'nonce':nonce(f[1])}
 for key,value in zip(old.KEYS,f[2:]):
  if not value.startswith(key+'='):raise ValueError('ordered WARM1 fields required')
  out[key]=value[len(key)+1:]
 if out['goal']!='O' or old.STATES.get(out['phase'])!=(out['registry'],out['pending']):raise ValueError('invalid existing intent/state')
 old.identity(out['initial'],target_device,94058,1433953097)
 old.identity(out['original'],45826,94058,1433953097)
 c=old.identity(out['candidate'],45826,94055)
 if not re.fullmatch('45826:[1-9][0-9]*',out['directory']):raise ValueError('directory profile')
 for key,size,mt in [('cstage',94055,c[2]),('ostage',94058,1433953097)]:
  if out[key]=='none':raise ValueError('recorded stage identity required')
  old.identity(out[key],target_device,size,mt)
 return out


def copy_phase1(run):
 nonce(run);warm.frozen_inputs()
 head,parents,setup=copy.borrowed(run)
 # This NEW readonly-source guard uses the currently reverified O inode. The
 # historical full-copy source/reference remains untouched.
 head=head.replace('64785|1606|94058|1433953097','64785|9457|94058|1433953097')
 body=r'''
cp -p "$_d/original" "$_d/active"
_s INITIAL_ACTIVE_O "$?"
_v "$_d/active" 94058 584c67f7186ada6bae9aae1be59b5cd0 376717896
_initial=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/active") || _die initial_id
cp -p "$_d/candidate" "$_d/stage"
_s STAGE_COPY_C "$?"
_v "$_d/stage" 94055 64db9d0df2277e1d95a037929aef30c4 776631029
_csi=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/stage") || _die staged_C_id
mv -f "$_d/stage" "$_d/active"
_s PUBLISH_COPY_C "$?"
_v "$_d/active" 94055 64db9d0df2277e1d95a037929aef30c4 776631029
cmp "$_d/candidate" "$_d/active"
_s COMPARE_COPY_C "$?"
_oi=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/original") || _die original_id
_ci=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/candidate") || _die candidate_id
_next="WARM1|$_run|registry=enabled|pending=none|phase=candidate_verified|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_initial"
test ! -e "$_d/journal" && test ! -L "$_d/journal" || _die journal_exists
printf '%s\n' "$_next" > "$_d/journal"
_s RECORD_KNOWN_COPY_C "$?"
test "$(stat -c '%F|%a|%u|%g|%h|%d' "$_d/journal")" = 'regular file|600|0|0|1|45826' || _die journal_metadata
_jn=$(wc -c < "$_d/journal") || _die journal_count
_jh=$(md5sum "$_d/journal") || _die journal_md5
_jc=$(cksum "$_d/journal") || _die journal_crc
_text=$(cat "$_d/journal") || _die journal_read
test "$_text" = "$_next" && test "$_jn" -eq "$((${#_next}+1))" || _die journal_bytes
_sv
_emit "JOURNAL $_next"
_emit "JOURNAL_COUNT $_jn"
_emit "JOURNAL_MD5 $_jh"
_emit "JOURNAL_CRC $_jc"
_emit "END phase=COPY_C_PREPARED rc=0 retained=$_d target=isolated_copy real_source=O_unchanged"
'''
 return head+'\n_sv\n'+parents+setup+body


def context_from_bundle(bundle,prepared):
 bundle=Path(bundle);prepared=Path(prepared)
 plan=json.loads((prepared/'plan.json').read_text());run=nonce(plan['nonce'])
 m=json.loads((bundle/'manifest.json').read_text())
 if m['outcome']!='completed':raise ValueError('phase1 must complete with real END/prompt')
 ops=[x for x in m['operations'] if not x.get('identity_probe')]
 if len(ops)!=1 or ops[0].get('exit_status')!=0 or ops[0].get('outcome')!='completed':raise ValueError('exact successful phase1 task required')
 command=(bundle/(ops[0]['nonce']+'.command.txt')).read_bytes()
 if sha(command)!=plan['command_sha256']:raise ValueError('phase1 source pin mismatch')
 data=(bundle/(ops[0]['nonce']+'.output.bin')).read_text().replace('\r','')
 def field(name):
  found=[x[len('COPYTX '+run+' '+name+' '):] for x in data.splitlines() if x.startswith('COPYTX '+run+' '+name+' ')]
  if len(found)!=1:raise ValueError('missing/duplicate '+name)
  return found[0]
 raw=(field('JOURNAL')+'\n').encode();ctx=parse_record(raw)
 if ctx['nonce']!=run:raise ValueError('nonce mismatch')
 if int(field('JOURNAL_COUNT'))!=len(raw) or field('JOURNAL_MD5').split()[0]!=hashlib.md5(raw).hexdigest():raise ValueError('journal exact count/MD5 mismatch')
 crc=subprocess.check_output(['/usr/bin/cksum'],input=raw).decode().split()
 if field('JOURNAL_CRC').split()[:2]!=crc[:2]:raise ValueError('journal CRC mismatch')
 return ctx,raw


def recovery(context):
 """Persist this COPY-only body. Default VERIFY is readonly; explicit restore only."""
 c=context;run=nonce(c['nonce']);d='/tmp/mnt/data_persist/cmu-bench-probe-'+run
 text=(ROOT/'experiments/disclaimer-recovery-inspection/inspect.sh.in').read_text()
 helpers=old.helpers()
 a=helpers.index('_source_route() {');z=helpers.index('\n}\n',a)+2
 helpers=helpers[:a]+'_source_route() { _backup_guard; }'+helpers[z:]
 replacements={'@WARM@':run,'@INSPECT@':run,'@DIRECTORY@':c['directory'],'@ORIGINAL_ID@':c['original'],
 '@CANDIDATE_ID@':c['candidate'],'@INITIAL_ID@':c['initial'],'@CSTAGE_ID@':c['cstage'],
 '@HELPERS@':helpers,'@ROOT_MODE@':'ro','@ACTION@':action()}
 for a,b in replacements.items():text=text.replace(a,b)
 text=text.replace('_src=/jci/gui/apps/system/js/systemApp.js','_src='+d+'/active')
 text=text.replace('_parent=/jci/gui/apps/system/js','_parent='+d)
 text=text.replace('_d="$_persist/cmu-bench-warm-$_run"','_d='+d)
 text=text.replace('_cs="$_parent/.systemApp.js.cmu-bench-$_run-candidate"','_cs="$_d/stage"')
 text=text.replace('_os="$_parent/.systemApp.js.cmu-bench-$_inspect-recovery-original"','_os="$_d/restore"')
 text=text.replace("$(printf 'candidate\\njournal\\noriginal')","$(printf 'active\\ncandidate\\njournal\\noriginal\\nrecovery.sh')")
 text=text.replace('64785','45826')
 # Standalone runtime mode never reads code/control with source/eval.
 text=text.replace('set -f\n','set -f\numask 077\n_mode=${1-VERIFY}\ncase $_mode in VERIFY|RESTORE_ORIGINAL) ;;*) exit 2;;esac\n',1)
 if re.search(r'@[A-Z_]+@',text):raise ValueError('unexpanded template')
 if re.search(r'^\s*(?:mount|sync|eval|source)\s',text,re.M) or '"$_bb"' in text:raise ValueError('COPY tool must not mount/sync/execute data')
 return text


def action():
 old_action=(ROOT/'experiments/disclaimer-recovery-inspection/restore.review.sh.in').read_text()
 commit=re.search(r'^_commit_record\(\) \{.*?^\}',old_action,re.M|re.S).group()
 old_action=old_action.replace(commit,'')
 # Existing C restoration is unchanged. Allow explicit O completion/no-op around
 # it, preserving the host model's distinct COMPLETE-disable intent.
 return commit+r'''
_self="$_d/recovery.sh"
test -f "$_self" && test ! -L "$_self" || die persistent_code_type
canon "$_self"
test "$(stat -c '%F|%a|%u|%g|%h|%d' "$_self")" = 'regular file|600|0|0|1|45826' || die persistent_code_metadata
if test "$_mode" = VERIFY;then
 case "$_kind:$_registry:$_pending:$_phase" in
 C:enabled:none:candidate_verified|O:disabled:none:original_restored|O:disabled:none:original_present) ;;
 *) die VERIFY_inconsistent;;esac
 emit "END mode=VERIFY rc=0 kind=$_kind registry=$_registry pending=$_pending writes=0 persistent_code=1"
 exit 0
fi
if test "$_kind" = O;then
 cmp "$_d/original" "$_src"
 status EXACT_PRESENT_O "$?"
 case "$_registry:$_pending:$_phase" in
 disabled:none:original_restored|disabled:none:original_present)
 emit "END mode=RESTORE_ORIGINAL rc=0 kind=O registry=disabled pending=none noop=1 no_rewrite=1"
 exit 0;;
 enabled:DISABLE:planned_restore|enabled:DISABLE:restoring_O) ;;
 *) die O_restore_intent;;esac
 _next="WARM1|$_run|registry=disabled|pending=none|phase=original_present|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_sid"
 _commit_record "$_next"
 _read_record;_backups;_classify
 test "$_kind:$_registry:$_pending" = O:disabled:none || die O_incomplete
 emit "END mode=RESTORE_ORIGINAL rc=0 kind=O registry=disabled pending=none no_rewrite=1"
 exit 0
fi
'''+old_action


def save(out,command,record,name='command.sh'):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 wire=wrap_command(command,'0'*32)
 subprocess.run(['/bin/sh','-n'],input=command.encode(),check=True,timeout=5)
 crc=subprocess.check_output(['/usr/bin/cksum'],input=command.encode()).decode().split()
 record.update(command_sha256=sha(command.encode()),command_md5=hashlib.md5(command.encode()).hexdigest(),command_crc=int(crc[0]),command_bytes=len(command.encode()),sample_wire_bytes=len(wire),max_physical_line=max(map(len,wire.splitlines())),deadline=45,output_cap=65536)
 (out/name).write_text(command);(out/'plan.json').write_text(json.dumps(record,indent=2)+'\n')
 return record


def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 a=sub.add_parser('copy-prepare');a.add_argument('--nonce');a.add_argument('--out',type=Path,required=True)
 a=sub.add_parser('copy-recovery');a.add_argument('--from-phase1',type=Path,required=True);a.add_argument('--prepared',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
 a=p.parse_args()
 if a.action=='copy-prepare':
  run=nonce(a.nonce or secrets.token_hex(16));v=save(a.out,copy_phase1(run),dict(mode='COPY_ONLY',nonce=run,target='fresh owned data_persist active COPY ONLY',opens_uart=False,real_root_authority=False))
 else:
  ctx,raw=context_from_bundle(a.from_phase1,a.prepared);body=recovery(ctx)
  v=save(a.out,body,dict(mode='COPY_ONLY_PERSISTENT_RECOVERY',nonce=ctx['nonce'],context=ctx,opens_uart=False,real_root_authority=False,default='VERIFY',explicit_mutation='RESTORE_ORIGINAL on isolated COPY only',delivery='verified DATA staging to owned persistent recovery.sh0600 before separate-process use; remove/ignore tmpfs stage then invoke persistentpath'),name='recovery.sh')
  (a.out/'journal.exact.bin').write_bytes(raw)
 print(json.dumps(v,indent=2))

if __name__=='__main__':main()
