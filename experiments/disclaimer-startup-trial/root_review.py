#!/usr/bin/env python3
"""ROOT startup boundary PREPARATION ONLY. No hardware; examples are not live profiles."""
import argparse,hashlib,json,re,secrets,subprocess
from pathlib import Path
import prepare as copy

HERE=Path(__file__).resolve().parent
ROOT=copy.ROOT
WARM=(ROOT/'experiments/disclaimer-warm-roundtrip/warm.sh.in').read_text()
INSPECT=(ROOT/'experiments/disclaimer-recovery-inspection/inspect.sh.in').read_text()
RESTORE=(ROOT/'experiments/disclaimer-recovery-inspection/restore.review.sh.in').read_text()

def function(name,text=WARM):
 m=re.search(r'^'+re.escape(name)+r'\(\) \{',text,re.M)
 if not m:raise ValueError('missing proven helper '+name)
 line_end=text.index('\n',m.start())
 end=line_end if text[m.start():line_end].rstrip().endswith('}') else text.index('\n}\n',m.start())+2
 return text[m.start():end]+'\n'

COMMIT=function('_commit_record',RESTORE)
# Refuse changed control evidence before journal staging and publication.
_CONTROL_SAME=''' _now_id=$(_id "$_d/journal") || die control_identity
 test "$_now_id" = "$_journal_id_start" || die control_changed_identity
 _now_hash=$(md5sum "$_d/journal") || die control_hash
 set -- $_now_hash;test "$1" = "$_journal_hash_start" || die control_changed_bytes
'''
COMMIT=COMMIT.replace(' _backup_guard\n',' _backup_guard\n'+_CONTROL_SAME,1)
COMMIT=COMMIT.replace(' mv -f "$_d/journal.new" "$_d/journal"\n',_CONTROL_SAME+' mv -f "$_d/journal.new" "$_d/journal"\n',1)
COMMIT=COMMIT.replace(' status COMMIT_RECORD "$?"\n',' status COMMIT_RECORD "$?"\n _read_record\n',1)
MOUNT=function('_mount_request')+function('_flush')
# File handling cannot exit this isolated flush block and bypass the paired RO.
FINISH=r'''
_rw_requested=0
_final_verified=0
_finish_root() {
 _entry_rc=$?
 trap - 0 1 2 15
 _flush_rc=not_needed
 if test "$_final_verified" = 1;then
  ( _flush VERIFIED_FILE_AND_CONTROL )
  _flush_rc=$?
 fi
 _ro_req=not_requested
 if test "$_rw_requested" = 1;then _mount_request ro;_ro_req=$?;fi
 _root_mode ro;_ro_row=$?
 _final_rc=1
 ( _read_record;_backups;_classify;test "$_kind" = "$_finish_kind" )
 _final_rc=$?
 if test "$_entry_rc" = 0 && test "$_flush_rc" = 0 && test "$_ro_row" = 0 &&
 test "$_final_rc" = 0 && { test "$_ro_req" = 0 || test "$_ro_req" = not_requested; };then
  emit "ROOT_FINAL mode=$_root_action rc=0 kind=$_finish_kind physical_ro=1 retained=$_d"
  if test "$_root_action" = APPLY_C;then
   test "$_recovery_ready" = 1 || exit 1
   printf 'CANDIDATE_BOOT_BIND|%s|C|%s|94055|64db9d0df2277e1d95a037929aef30c4|776631029|ro|1|candidate_verified\n' "$_run" "$_csi"
  fi
  exit 0
 fi
 emit "ROOT_FINAL mode=$_root_action rc=1 entry=$_entry_rc flush=$_flush_rc ro_request=$_ro_req ro_row=$_ro_row file=$_final_rc preserve=$_d"
 exit 1
}
_arm_root_finish() {
 trap '_finish_root' 0
 trap 'exit 125' 1 2 15
}
# As in the accepted warm helper, repeated signals during cleanup can interrupt it.
# No ignored-TERM children, forced cleanup or durability guarantee is introduced.
'''


def common(ctx,action):
 """Same WARM1 record and passed guards; actual stage IDs follow controlled journal."""
 run=copy.nonce(ctx['nonce']);text=INSPECT
 replacements={'@WARM@':run,'@INSPECT@':run,'@DIRECTORY@':ctx['directory'],
 '@ORIGINAL_ID@':ctx['original'],'@CANDIDATE_ID@':ctx['candidate'],
 '@INITIAL_ID@':ctx['initial'],'@CSTAGE_ID@':ctx['cstage'],
 '@HELPERS@':copy.old.helpers(),'@ROOT_MODE@':'ro','@ACTION@':action}
 for a,b in replacements.items():text=text.replace(a,b)
 text=text.replace('_d="$_persist/cmu-bench-warm-$_run"','_d="$_persist/cmu-bench-startup-$_run"')
 text=text.replace('_os="$_parent/.systemApp.js.cmu-bench-$_inspect-recovery-original"','_os="$_parent/.systemApp.js.cmu-bench-$_run-original"')
 text=text.replace("$(printf 'candidate\\njournal\\noriginal')","$(printf 'candidate\\njournal\\noriginal\\nrecovery.sh')")
 # Before APPLY, cstage=none. The sole writer later records its exact new stage
 # inode. The strict record parser, retained identities and active-vs-record ID
 # equality remain mandatory; unknown C bytes/metadata/identity are never adopted.
 old='test "$_initial" = "$_expected_initial" && test "$_csi" = "$_expected_csi" || die transaction_profile_changed'
 new='test "$_initial" = "$_expected_initial" || die transaction_initial_changed'
 if text.count(old)!=1:raise ValueError('record guard anchor changed')
 text=text.replace(old,new)
 text=text.replace('set -f\n','set -f\numask 077\n_bb=/bin/busybox\n_sync=/bin/sync\n',1)
 if re.search(r'@[A-Z_]+@',text):raise ValueError('unexpanded field')
 return text


def persistent_recovery(ctx):
 action=COMMIT+MOUNT+FINISH+r'''
_self="$_d/recovery.sh"
test -f "$_self" && test ! -L "$_self" || die persistent_code_type
canon "$_self"
test "$(stat -c '%F|%a|%u|%g|%h|%d' "$_self")" = 'regular file|600|0|0|1|45826' || die persistent_code_metadata
# Readiness cannot hide an unknown retained root rollback stage.
if test -e "$_os" || test -L "$_os";then
 _verify_o "$_os" 64785
 test "$(_id "$_os")" = "$_osi" || die readiness_original_stage_changed
fi
if test "$_mode" = VERIFY;then
 case "$_kind:$_registry:$_pending:$_phase" in
 O:disabled:ENABLE:prepared|O:disabled:none:original_restored|O:disabled:none:original_present|C:enabled:none:candidate_verified) ;;
 *) die VERIFY_inconsistent_no_mutation;;esac
 emit "END mode=VERIFY rc=0 kind=$_kind registry=$_registry pending=$_pending phase=$_phase writes=0 recovery_ready=1 current_id=$_sid"
 exit 0
fi
case "$_kind:$_registry:$_pending:$_phase" in
 C:enabled:none:candidate_verified|C:enabled:DISABLE:planned_restore|C:enabled:DISABLE:restoring_O|C:disabled:ENABLE:staged|O:enabled:DISABLE:planned_restore|O:enabled:DISABLE:restoring_O|O:disabled:ENABLE:prepared|O:disabled:ENABLE:staged|O:disabled:none:original_restored|O:disabled:none:original_present) ;;
 *) die RESTORE_inconsistent_or_OTHER;;esac
_root_action=RESTORE_ORIGINAL
_finish_kind=O
_arm_root_finish
if test "$_kind" = O;then
 cmp "$_d/original" "$_src"
 status PRESENT_ORIGINAL_EXACT "$?"
 case "$_registry:$_pending" in
 disabled:none) _final_verified=1;emit "ORIGINAL_PRESENT no_rewrite=1 already_disabled=1 current_id=$_sid";exit 0;;
 esac
 _next="WARM1|$_run|registry=disabled|pending=none|phase=original_present|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_sid"
 _commit_record "$_next"
 _final_verified=1
 emit "ORIGINAL_PRESENT no_rewrite=1 current_id=$_sid"
 exit 0
fi
# Validate any retained root stage BEFORE requesting RW. Missing stage is safely
# recreated from the independently retained original after the RW row is proved.
if test -e "$_os" || test -L "$_os";then
 _verify_o "$_os" 64785
 test "$(_id "$_os")" = "$_osi" || die existing_original_stage_changed
fi
_flush RETAINED_EVIDENCE_BEFORE_RW
_rw_requested=1
_mount_request rw || die restore_rw_or_physical_row
_root_mode rw || die restore_not_verified_rw
if test ! -e "$_os" && test ! -L "$_os";then
 cp -p "$_d/original" "$_os"
 status STAGE_STORED_ORIGINAL "$?"
fi
_verify_o "$_os" 64785
_new_osi=$(_id "$_os") || die original_stage_identity
_next="WARM1|$_run|registry=enabled|pending=DISABLE|phase=restoring_O|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_new_osi"
_commit_record "$_next"
_read_record;_backups;_classify
test "$_kind" = C || die candidate_changed_before_undo
_verify_o "$_os" 64785
test "$(_id "$_os")" = "$_new_osi" || die original_stage_changed
mv -f "$_os" "$_src"
status RESTORE_REAL_ORIGINAL "$?"
_verify_o "$_src" 64785
cmp "$_d/original" "$_src"
status COMPARE_RESTORED_ORIGINAL "$?"
_final=$(_id "$_src") || die original_final_identity
test "$_final" = "$_new_osi" || die original_replacement_identity
_next="WARM1|$_run|registry=disabled|pending=none|phase=original_restored|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_final"
_commit_record "$_next"
_final_verified=1
emit "ORIGINAL_RESTORED current_id=$_final inode=replaced attributes=bytes-mode-uid-gid-mtime"
exit 0
'''
 text=common(ctx,action)
 return text.replace('set -f\n','set -f\n_mode=${1-VERIFY}\ncase $_mode in VERIFY|RESTORE_ORIGINAL) ;;*) exit 2;;esac\n',1)


def apply_candidate(ctx,recovery_body):
 data=recovery_body.encode();md5=hashlib.md5(data).hexdigest();crc=subprocess.check_output(['/usr/bin/cksum'],input=data).decode().split()[0]
 action=COMMIT+MOUNT+FINISH+r'''
test "$_kind:$_registry:$_pending:$_phase" = O:disabled:ENABLE:prepared || die apply_requires_prepared_O
# Persistent independent recovery is verified BEFORE root RW and publication.
_code="$_d/recovery.sh"
_recovery_code_guard() {
test -f "$_code" && test ! -L "$_code" || die recovery_code_type
canon "$_code"
test "$(stat -c '%F|%a|%u|%g|%h|%d|%s' "$_code")" = 'regular file|600|0|0|1|45826|@CODE_BYTES@' || die recovery_code_metadata
test "$(md5sum < "$_code")" = '@CODE_MD5@  -' || die recovery_code_hash
test "$(cksum < "$_code")" = '@CODE_CRC@ @CODE_BYTES@' || die recovery_code_crc
}
_recovery_code_guard
/bin/sh "$_code" VERIFY
status PERSISTENT_RECOVERY_BEFORE_PUBLICATION "$?"
emit "RECOVERY_READY before_publication=1 independent=1 code_bytes=@CODE_BYTES@ code_md5=@CODE_MD5@ code_crc=@CODE_CRC@"
_recovery_ready=1
_root_action=APPLY_C
_finish_kind=C
_arm_root_finish
_flush BACKUP_CODE_AND_PENDING_INTENT
_rw_requested=1
_mount_request rw || die apply_rw_or_physical_row
_root_mode rw || die apply_not_verified_rw
_source_route
_verify_o "$_src" 64785
test "$(_id "$_src")" = "$_initial" || die original_changed_before_staging
test ! -e "$_cs" && test ! -L "$_cs" || die candidate_stage_exists
test ! -e "$_os" && test ! -L "$_os" || die original_stage_exists
cp -p "$_d/candidate" "$_cs"
status STAGE_REAL_C "$?"
_verify_c "$_cs" 64785
_csi=$(_id "$_cs") || die candidate_stage_id
cp -p "$_d/original" "$_os"
status STAGE_REAL_O "$?"
_verify_o "$_os" 64785
_osi=$(_id "$_os") || die original_stage_id
_next="WARM1|$_run|registry=disabled|pending=ENABLE|phase=staged|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_osi"
_commit_record "$_next"
_backups
_verify_o "$_src" 64785
test "$(_id "$_src")" = "$_initial" || die original_changed_before_publication
_verify_c "$_cs" 64785
test "$(_id "$_cs")" = "$_csi" || die candidate_stage_changed
# Recheck every prerequisite adjacent to the irreversible publication boundary.
_verify_o "$_os" 64785
test "$(_id "$_os")" = "$_osi" || die original_stage_changed_before_publication
_recovery_code_guard
_now_id=$(_id "$_d/journal") || die control_identity
 test "$_now_id" = "$_journal_id_start" || die control_changed_identity
 _now_hash=$(md5sum "$_d/journal") || die control_hash
 set -- $_now_hash;test "$1" = "$_journal_hash_start" || die control_changed_bytes
mv -f "$_cs" "$_src"
status PUBLISH_REAL_C "$?"
_verify_c "$_src" 64785
test "$(_id "$_src")" = "$_csi" || die candidate_publish_id
cmp "$_d/candidate" "$_src"
status COMPARE_PUBLISHED_C "$?"
_next="WARM1|$_run|registry=enabled|pending=none|phase=candidate_verified|goal=O|initial=$_initial|directory=$_di|original=$_oi|candidate=$_ci|cstage=$_csi|ostage=$_osi"
_commit_record "$_next"
_final_verified=1
emit "CANDIDATE_APPLIED source_identity=$_csi bytes=94055 md5=64db9d0df2277e1d95a037929aef30c4 crc=776631029 recovery_ready_before_publish=1"
exit 0
'''
 for k,v in {'@CODE_BYTES@':str(len(data)),'@CODE_MD5@':md5,'@CODE_CRC@':crc}.items():action=action.replace(k,v)
 return common(ctx,action)


def root_preparation(run):
 copy.nonce(run);copy.warm.frozen_inputs()
 text=copy.warm.render(run)
 prefix=text[:text.index('emit() {')].replace('64785:1606:','64785:9457:').replace('cmu-bench-warm-','cmu-bench-startup-')
 helpers=''.join(function(x) for x in ['emit','die','status'])+copy.old.helpers()+function('_control')+function('_write_state')+function('_flush')
 start=text.index('# PREPARE RETAINED BACKUP, CANDIDATE AND INTENT')
 end=text.index('\n# RW and RO use these exact',start)
 body=text[start:end]
 return prefix+helpers+'\n'+body+r'''
emit "PREPARED registry=disabled pending=ENABLE phase=prepared source_O=1 physical_RO=1 retained=$_d"
emit "JOURNAL $_jexpected"
_jn=$(wc -c < "$_d/journal") || die journal_count
_jh=$(md5sum "$_d/journal") || die journal_md5
_jc=$(cksum "$_d/journal") || die journal_crc
emit "JOURNAL_COUNT $_jn"
emit "JOURNAL_MD5 $_jh"
emit "JOURNAL_CRC $_jc"
'''


def save_review(out,ctx):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 bodies={'prepare-retained.review.sh':root_preparation(ctx['nonce'])}
 bodies['recovery.review.sh']=persistent_recovery(ctx)
 bodies['apply-C.review.sh']=apply_candidate(ctx,bodies['recovery.review.sh'])
 pins={}
 for name,body in bodies.items():
  subprocess.run(['/bin/sh','-n'],input=body.encode(),check=True,timeout=5)
  wire=copy.wrap_command(body,'0'*32);data=body.encode()
  (out/name).write_bytes(data)
  pins[name]=dict(bytes=len(data),sha256=copy.sha(data),md5=hashlib.md5(data).hexdigest(),crc=int(subprocess.check_output(['/usr/bin/cksum'],input=data).decode().split()[0]),sample_wire_bytes=len(wire),max_physical_line=max(map(len,wire.splitlines())))
 record=dict(mode='REVIEW_ONLY_ROOT_BOUNDARY',operator_handoff_authorized=False,live_authority=False,example_context_only=True,context=ctx,payloads=pins,delivery='retained recovery DATA readback verified before publication; apply long program DATA staged with short guardedentry; no live action here',binding='After separately authorized retained-prepare, parse exact WARM1 evidence and regenerate same pinned renderer with actual IDs. Example IDs are NOT target metadata.')
 (out/'review-plan.json').write_text(json.dumps(record,indent=2)+'\n')
 return record

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 run=secrets.token_hex(16)
 ctx=dict(nonce=run,registry='disabled',pending='ENABLE',phase='prepared',goal='O',initial='64785:9457:1433953097:94058:755:1018:3015:1',directory='45826:1',original='45826:2:1433953097:94058:755:1018:3015:1',candidate='45826:3:1:94055:755:1018:3015:1',cstage='none',ostage='none')
 print(json.dumps(save_review(a.out,ctx),indent=2))
