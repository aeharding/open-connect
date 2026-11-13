"""Prepare one retained-journal inspector. Default VERIFY is read-only; no UART."""
import argparse,hashlib,json,re,secrets,subprocess,sys
from pathlib import Path
import journal as retained
HERE=Path(__file__).resolve().parent
ROOT=retained.ROOT
sys.path.insert(0,str(ROOT))
from cmu_bench.session import wrap_command

VERIFY=r'''
case "$_kind:$_registry:$_pending:$_phase" in
 O:disabled:none:original_restored|O:disabled:none:original_present) ;;
 *) die VERIFY_inconsistent_or_C_OTHER_no_mutation;;
esac
_journal_id=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/journal") || die journal_identity
test "$_journal_id" = "$_journal_id_start" || die journal_changed_during_verify
_current_hash=$(md5sum "$_d/journal") || die journal_final_hash
set -- $_current_hash;test "$1" = "$_journal_hash_start" || die journal_changed_during_verify
emit "END mode=VERIFY rc=0 kind=O registry=disabled pending=none noop=1 writes=0 current_id=$_sid journal_id=$_journal_id"
'''


def render(context,nonce,mode='VERIFY'):
 if not re.fullmatch('[0-9a-f]{32}',nonce):raise ValueError('fresh32 lowercase hex inspection nonce required')
 if mode not in ('VERIFY','RESTORE_ORIGINAL'):raise ValueError('explicit known mode required')
 text=(HERE/'inspect.sh.in').read_text()
 replacements={'@WARM@':context['nonce'],'@INSPECT@':nonce,'@DIRECTORY@':context['directory'],
 '@ORIGINAL_ID@':context['original'],'@CANDIDATE_ID@':context['candidate'],
 '@INITIAL_ID@':context['initial'],'@CSTAGE_ID@':context['cstage'],'@HELPERS@':retained.helpers(),
 '@ROOT_MODE@':'ro' if mode=='VERIFY' else 'rw',
 '@ACTION@':VERIFY if mode=='VERIFY' else (HERE/'restore.review.sh.in').read_text()}
 for old,new in replacements.items():text=text.replace(old,new)
 if re.search(r'@[A-Z_]+@',text):raise ValueError('unexpanded template field')
 if mode=='VERIFY' and re.search(r'^\s*(?:cp|mv|rm|mkdir|chmod|chown|mount|sync|eval|source)\s',text,re.M):
  raise ValueError('VERIFY must contain read commands only')
 return text


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--mode',choices=('VERIFY','RESTORE_ORIGINAL'),default='VERIFY')
 p.add_argument('--nonce');p.add_argument('--out',type=Path)
 a=p.parse_args();context=retained.retained_profile();nonce=a.nonce or secrets.token_hex(16)
 command=render(context,nonce,a.mode);wire=wrap_command(command,'0'*32)
 crc=subprocess.check_output(['/usr/bin/cksum'],input=command.encode()).decode().strip().split()
 result=dict(mode=a.mode,preparation_only=True,opens_uart=False,
 live_scope='ONE VERIFY on current O only' if a.mode=='VERIFY' else 'NO LIVE RESTORE AUTHORITY; future review only',
 warm_nonce=context['nonce'],inspect_nonce=nonce,retained_context=context,
 journal_fixture=str(retained.FIXTURE),guard_authority=str(retained.AUTHORITY),
 command_bytes=len(command.encode()),command_sha256=retained.sha(command.encode()),
 command_md5=hashlib.md5(command.encode()).hexdigest(),command_crc=int(crc[0]),
 sample_wire_bytes=len(wire),max_physical_line=max(map(len,wire.splitlines())),
 deadline=30,output_cap=65536,delivery='verified base64 DATA-only staging plus short guarded entry; no executable long paste',
 profile='AS-FOUND55 exact O/C metadata and existing WARM1 state machine; not product recovery policy',
 limits='single-writer/runtime verification; no power-loss, startup, mount or rootwriter authority from VERIFY')
 if a.out:
  a.out.mkdir(parents=True,exist_ok=False)
  (a.out/'command.sh').write_text(command)
  (a.out/'plan.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
