"""Separate explicit known-C/RW undo. Original RO code stays unchanged."""
from pathlib import Path
import re
import runtime as rt
RUN=rt.ROOT/"runs/20261113T111353-0600-t14-native-intro"
CID="64785:1606:8839:454142:755:1018:3015:1"
OID="64785:9457:1433953535:454142:755:1018:3015:1"
AUTHORITY=rt.ROOT/"notes/native-apply-recovery-handoff.txt"
def state():
 ret=rt.json_data(RUN/"retained-plan/retained-plan.json")
 p=rt.profile(rt.json_data(RUN/"packet/packet.json")["candidate_profile"])
 return p,ret,rt.json_data(RUN/"code.actual.json")
def self_guard(code):
 f=code["fingerprint"]
 return f'''_self="$_d/recovery.sh"
test -f "$_self" && test ! -L "$_self" || die code_type
canon "$_self"
test "$(_id "$_self")" = '{code["identity"]}' || die code_identity
test "$(md5sum < "$_self")" = '{f["md5"]}  -' || die code_hash
test "$(cksum < "$_self")" = '{f["crc"]} {f["bytes"]}' || die code_crc
'''
def inspector(kind,mode):
 if kind not in ("C","O") or mode not in ("rw","ro"):raise ValueError("fixed state/mount")
 p,ret,code=state();expected=CID if kind=="C" else OID
 control="enabled:none:candidate_verified" if kind=="C" else "disabled:none:original_restored"
 action=self_guard(code)+f'''test "$_kind" = {kind} && test "$_sid" = '{expected}' || die exact_recovery_image
test "$_registry:$_pending:$_phase" = {control} || die known_control
'''+r'''
if test -e "$_os" || test -L "$_os";then
 _verify_o "$_os" 64785
 test "$(_id "$_os")" = "$_osi" || die original_stage_changed
fi
emit "FULL_JOURNAL $_jtext"
emit "RECOVERY_INSPECT kind=$_kind id=$_sid registry=$_registry pending=$_pending phase=$_phase writes=0 root_mode=MODE"
exit 0
'''.replace("MODE",mode)
 text=rt.native(rt.legacy().common(ret["context"],action),p,ret["baseline"])
 anchor="_root_mode ro || die physical_root_mode"
 if text.count(anchor)!=1:raise ValueError("mount anchor")
 return text.replace(anchor,"_root_mode "+mode+" || die physical_root_mode")
def undo_body():
 p,ret,code=state();text=(RUN/"retained-plan/recovery.sh").read_text()
 m=re.search(r"(?m)^_mode=.*\ncase .*?\n",text)
 if not m or "VERIFY|RESTORE_ORIGINAL" not in m[0]:raise ValueError("explicit mode anchor")
 new="_mode=$"+"{1-RW_ENTRY_REQUIRED}\ncase $_mode in RESTORE_FROM_RW) ;;*) exit 2;;esac\n"
 text=text[:m.start()]+new+text[m.end():]
 anchor="_root_mode ro || die physical_root_mode"
 if text.count(anchor)!=1:raise ValueError("initial mount anchor")
 text=text.replace(anchor,"_root_mode rw || die physical_root_mode")
 anchor="\n_classify\n"
 if text.count(anchor)!=1:raise ValueError("initial classify anchor")
 guard=f'''test "$_kind:$_registry:$_pending:$_phase" = C:enabled:none:candidate_verified || die RW_entry_requires_known_C
test "$_sid" = '{CID}' || die RW_entry_C_identity
'''
 return text.replace(anchor,anchor+self_guard(code)+guard)
def rw_observation(status,raw,p,kind,expected,baseline):
 if status:raise ValueError("RW check nonzero")
 f=rt.fields().candidate_fields(raw);which=rt.O if kind=="O" else p["candidate"]
 if f["META"]!=expected:raise rt.IdentityConflict(f)
 rt.identity(f["META"],64785,454142,1433953535 if kind=="O" else None)
 if f["HASH"].split()!=[which["md5"],"-"] or f["CRC"].split()!=[str(which["crc"]),"454142"]:raise ValueError("recovery bytes")
 row=f["ROOT"].split()
 if len(row)!=6 or row[:3]!=["/dev/ffx01p1","/","relfs"] or set(row[3].split(","))!={"rw","noatime"}:raise ValueError("actual physical RW required")
 parents=dict(x.split("|") for x in rt.typed_records(raw,b"NATIVE_PARENT|"))
 module=rt.typed_records(raw,b"NATIVE_MODULE|");maps=rt.typed_records(raw,b"NATIVE_MAP|")
 manager=rt.typed_records(raw,b"NATIVE_MANAGER|")
 if parents!=baseline["parents"] or module!=[baseline["module"]] or manager!=[baseline["manager"]] or not 0<len(maps)<=32:raise ValueError("loadedO process/ABI/parents changed")
 for m in maps:
  v=m.split()
  if len(v) not in (6,7) or v[3]!="fd:11" or v[4]!="5484" or v[5] not in (rt.TARGET, "/jci/mmui/uia/.libjciuiasystem.so.cmu-bench-7c748f8ac79ca2a8ae45170150798589-candidate") or (len(v)==7 and v[6]!="(deleted)"):raise rt.IdentityConflict(dict(f,mapping=m))
 return dict(f,kind=kind,root_mode="rw",parents=parents,module=module[0],maps=maps,manager=manager[0],uptime_seconds=float(f["UPTIME"].split()[0]),physical_RO=False)
def inspection_output(status,raw,kind,mode):
 p,ret,code=state();expected=CID if kind=="C" else OID
 rows=rt.typed_records(raw,("NREC "+ret["nonce"]+" ").encode())
 records=[s[len("FULL_JOURNAL "):] for s in rows if s.startswith("FULL_JOURNAL ")]
 end=[s for s in rows if s.startswith("RECOVERY_INSPECT ")]
 if len(records)!=1 or len(end)!=1:raise ValueError("complete read-only result")
 ctx=rt.parse_journal((records[0]+"\n").encode(),p)
 want=("enabled","none","candidate_verified") if kind=="C" else ("disabled","none","original_restored")
 if tuple(ctx[k] for k in ("registry","pending","phase"))!=want or ctx["cstage"]!=CID or ctx["ostage"]!=OID:raise ValueError("strict transaction state")
 expected_end=f"RECOVERY_INSPECT kind={kind} id={expected} registry={want[0]} pending={want[1]} phase={want[2]} writes=0 root_mode={mode}"
 if status or end!=[expected_end]:raise ValueError("exact read-only state")
 return ctx
def known_undo_failure(bundle,entry):
 b=Path(bundle);m=rt.json_data(b/"manifest.json");ops=[x for x in m["operations"] if not x.get("identity_probe")]
 if m.get("outcome")!="remote_nonzero" or not m.get("port_closed") or len(ops)!=1 or ops[0].get("exit_status")!=1:raise ValueError("known final-RO failure only")
 op=ops[0]
 for suffix in [".command.txt",".output.bin"]:
  name=op["nonce"]+suffix;data=rt.artifact(b/name);pin=m["artifacts"][name]
  if pin["bytes"]!=len(data) or pin["sha256"]!=rt.sha(data):raise ValueError("undo artifact integrity")
  if suffix==".command.txt" and data!=entry.encode():raise ValueError("undo entry source")
 raw=rt.artifact(b/(op["nonce"]+".output.bin"));p,ret,code=state()
 rows=rt.typed_records(raw,("NREC "+ret["nonce"]+" ").encode())
 exact=f"NATIVE_ROOT_FINAL mode=RESTORE_ORIGINAL rc=1 entry=0 flush=0 ro_request=1 ro_row=1 file=0 preserve=/tmp/mnt/data_persist/cmu-bench-native-{ret['nonce']}"
 if rows.count(exact)!=1 or b"mount: mounting /dev/ffx01p1 on / failed: Device or resource busy" not in raw:raise ValueError("not solely paired RO EBUSY")
 if not any(x.startswith("ORIGINAL_RESTORED current_id="+OID+" ") for x in rows):raise ValueError("exact original restoration missing")
 return dict(kind="O",identity=OID,paired_ro_failed="EBUSY",sync_verified=True,evidence=dict(core_bundle=str(b.resolve()),manifest_sha256=rt.sha((b/"manifest.json").read_bytes()),command_sha256=rt.sha(entry.encode()),output_sha256=rt.sha(raw)))
