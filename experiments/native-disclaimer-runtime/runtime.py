#!/usr/bin/env python3
"""Native-only HOST renderer. No serial/camera/device execution interface."""
import argparse,hashlib,importlib.util,json,math,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from cmu_bench.files import posix_cksum
from cmu_bench.session import wrap_command
TARGET="/jci/mmui/uia/libjciuiasystem.so"
PARENTS=("/jci","/jci/mmui","/jci/mmui/uia")
INITIAL="64785:5484:1433953535:454142:755:1018:3015:1"
O=dict(bytes=454142,md5="b9ff5edc632163f88cda04686c118591",crc=3625493025,sha256="acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302")
ORIGINAL=ROOT/"runs/20261113T100437-0600-t14-mmui-upstream/originals/jci/mmui/uia/libjciuiasystem.so"
KEYS=("registry","pending","phase","goal","initial","directory","original","candidate","cstage","ostage")
STATES={"prepared":("disabled","ENABLE"),"staged":("disabled","ENABLE"),"candidate_verified":("enabled","none"),"planned_restore":("enabled","DISABLE"),"restoring_O":("enabled","DISABLE"),"original_restored":("disabled","none"),"original_present":("disabled","none")}
def sha(b):return hashlib.sha256(b).hexdigest()
def fp(b):return dict(bytes=len(b),md5=hashlib.md5(b).hexdigest(),crc=posix_cksum(b),sha256=sha(b))
def nonce(v):
 if not isinstance(v,str) or not re.fullmatch("[0-9a-f]{32}",v):raise ValueError("32hex nonce")
 return v
def artifact(path,limit=4194304):
 p=Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:raise ValueError("bounded regular artifact")
 return p.read_bytes()
def json_data(path):
 def unique(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise ValueError("duplicate JSON key")
   d[k]=v
  return d
 return json.loads(artifact(path,1048576),object_pairs_hook=unique)
def hostpath(v,base):return Path(v) if Path(v).is_absolute() else Path(base)/v
def reconstruct(o,d):
 if len(o)!=454142 or len(d)!=12288:raise ValueError("recipe sizes")
 b=bytearray(o)
 for i,j in enumerate([0,7,72]):b[j*4096:(j+1)*4096]=d[i*4096:(i+1)*4096]
 return bytes(b)
def profile(path):
 p=json_data(path)
 if p.get("schema")!="NATIVE_INTRO_CANDIDATE_V1" or p.get("target")!=TARGET or p.get("original")!=O:raise ValueError("native schema/base")
 if p.get("live_authority") not in (None,False):raise ValueError("host-only candidate")
 c=p["candidate"];d=p["delta"]
 if c.get("bytes")!=454142 or set(c)!=set(O) or c.get("sha256")==O["sha256"]:raise ValueError("same-size exact candidate")
 if d.get("block_size")!=4096 or d.get("block_indices")!=[0,7,72] or d.get("bytes")!=12288:raise ValueError("three-block recipe")
 o=artifact(ORIGINAL);cbytes=artifact(hostpath(p["candidate_path"],Path(path).parent));delta=artifact(hostpath(d["path"],Path(path).parent))
 if fp(o)!=O or fp(cbytes)!=c or fp(delta)!={k:d[k] for k in O}:raise ValueError("candidate/delta hashes")
 if reconstruct(o,delta)!=cbytes:raise ValueError("delta reconstruction differs")
 pins=p.get("source_pins")
 if not isinstance(pins,dict) or not pins:raise ValueError("builder pins required")
 for n,h in pins.items():
  if sha(artifact(hostpath(n,ROOT)))!=h:raise ValueError("builder pin changed")
 return p
def verify_dependencies():
 for n,h in json_data(HERE/"dependencies.json").items():
  if sha(artifact(ROOT/n))!=h:raise ValueError("passed dependency changed: "+n)
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def legacy():
 verify_dependencies();p=ROOT/"experiments/disclaimer-startup-trial/root_review.py";sys.path.insert(0,str(p.parent))
 return module("_native_legacy",p)
def delivery():verify_dependencies();return module("_native_delivery",ROOT/"experiments/staged-delivery/deliver.py")
def fields():verify_dependencies();return module("_native_fields",ROOT/"experiments/disclaimer-startup-trial/boot/observe.py")
def identity(v,dev,size,mt=None):
 if not isinstance(v,str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?::(?:0|[1-9][0-9]*)){7}",v):raise ValueError("numeric full identity")
 f=v.split(":")
 if f[0]!=str(dev) or int(f[1])<1 or f[3:]!=[str(size),"755","1018","3015","1"]:raise ValueError("identity profile")
 if mt is not None and f[2]!=str(mt):raise ValueError("mtime")
 return f
def baseline_valid(b):
 if not isinstance(b,dict) or b.get("initial")!=INITIAL or set(b.get("parents",{}))!=set(PARENTS):raise ValueError("actual baseline/parents required")
 for v in b["parents"].values():
  f=v.split(":")
  if len(f)!=5 or any(not re.fullmatch("[0-9]+",x) for x in f) or f[0]!="64785" or int(f[1])<1 or f[2] not in ("755","775") or f[3:]!=["1018","3015"]:raise ValueError("actual parent profile")
 return b
def native_check():
 return r'''set -f
p=/jci/mmui/uia/libjciuiasystem.so
for d in /jci /jci/mmui /jci/mmui/uia;do
 test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
 printf 'NATIVE_PARENT|%s|' "$d";stat -c '%d:%i:%a:%u:%g' "$d" || exit 71
done
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
printf 'SWST|META|';stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p" || exit 73
printf 'SWST|HASH|';md5sum < "$p" || exit 74
printf 'SWST|CRC|';cksum < "$p" || exit 75
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{print "SWST|ROOT|"$0}' /proc/mounts
m=/jci/lib/libjciuiamgr.so
test -f "$m" && test ! -L "$m" && test "$(readlink -f "$m")" = "$m" || exit 88
mi=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$m") || exit 89
mh=$(md5sum < "$m") && mc=$(cksum < "$m") || exit 90
printf 'NATIVE_MANAGER|%s|%s|%s\n' "$mi" "$mh" "$mc"
printf 'SWST|UPTIME|';cat /proc/uptime || exit 76
printf 'SWST|BOOT_ID|';cat /proc/sys/kernel/random/boot_id || exit 77
pid=$(pgrep -f '(^| )/jci/mmui/svcjcimmui[.]so( |$)') || exit 78
case "$pid" in ''|*[!0-9]*) exit 79;;esac
test "$pid" -gt 1 || exit 80
procid() {
 s=$(cat "/proc/$pid/stat") || return 1
 s=$(printf '%s\n' "$s" | sed 's/.*) //')
 set -- $s
 test "$#" -ge 20 || return 2
 pp=$2;shift 19
 printf '%s:%s' "$pp" "$1"
}
pi=$(procid) || exit 81
cm=$(md5sum < "/proc/$pid/cmdline") || exit 82
test "$cm" = 'a43fc1bb895b0e6c13480c8f4b875a58  -' || exit 83
maps=$(awk -v p="$p" '$6==p&&(NF==6||(NF==7&&$7=="(deleted)")){print}' "/proc/$pid/maps") || exit 84
mc=$(printf '%s\n' "$maps" | awk 'NF{n++}END{print n+0}')
mb=$(printf '%s\n' "$maps" | wc -c)
test "$mc" -gt 0 && test "$mc" -le 32 && test "$mb" -le 8192 || exit 85
printf '%s\n' "$maps" | awk '{print "NATIVE_MAP|"$0}'
pi2=$(procid) && cm2=$(md5sum < "/proc/$pid/cmdline") || exit 86
test "$pi" = "$pi2" && test "$cm" = "$cm2" || exit 87
printf 'NATIVE_MODULE|%s|%s|%s\n' "$pid" "$pi" "$cm"
'''
def typed_records(raw,prefix):
 out=[]
 for l in raw.splitlines(keepends=True):
  n=l.count(prefix)
  if not n:continue
  if n!=1 or not l.endswith(b"\n"):raise ValueError("partial/duplicate native record")
  r=l[l.index(prefix):].removesuffix(b"\n").removesuffix(b"\r")
  if any(c<32 and c!=9 for c in r):raise ValueError("record control")
  out.append(r[len(prefix):].decode("ascii"))
 return out
class IdentityConflict(ValueError):
 def __init__(self,actual):self.actual=actual;super().__init__("native identity conflict/OTHER; no adoption")
def observation(status,raw,p,kind,expected,before=None,mapped_identity=None,deleted=False,process=None,parents=None):
 if status:raise ValueError("native check nonzero")
 f=fields().candidate_fields(raw);w=O if kind=="O" else p["candidate"]
 identity(f["META"],64785,w["bytes"])
 if f["META"]!=expected:raise IdentityConflict(f)
 if f["HASH"].split()!=[w["md5"],"-"] or f["CRC"].split()!=[str(w["crc"]),str(w["bytes"])]:raise ValueError("native bytes")
 row=f["ROOT"].split()
 if len(row)!=6 or row[:3]!=["/dev/ffx01p1","/","relfs"] or set(row[3].split(","))!={"ro","noatime"}:raise ValueError("physical RO")
 u=float(f["UPTIME"].split()[0])
 if not math.isfinite(u) or u<0:raise ValueError("uptime")
 if before and (f["BOOT_ID"]==before["BOOT_ID"] or u>=before["uptime_seconds"]):raise ValueError("fresh boot identity/uptime")
 pars={}
 for l in typed_records(raw,b"NATIVE_PARENT|"):
  k,v=l.split("|")
  if k in pars:raise ValueError("duplicate parent")
  pars[k]=v
 baseline_valid(dict(initial=INITIAL,parents=pars))
 if parents is not None and pars!=parents:raise IdentityConflict(dict(f,parents=pars))
 mod=typed_records(raw,b"NATIVE_MODULE|");maps=typed_records(raw,b"NATIVE_MAP|")
 if len(mod)!=1 or not 0<len(maps)<=32:raise ValueError("single fresh module/maps")
 a=mod[0].split("|")
 if len(a)!=3 or not re.fullmatch("[1-9][0-9]*",a[0]) or not re.fullmatch("[1-9][0-9]*:[0-9]+",a[1]) or a[2]!="a43fc1bb895b0e6c13480c8f4b875a58  -":raise ValueError("module argv")
 if process is not None and mod[0]!=process:raise IdentityConflict(dict(f,module=mod[0]))
 mi=(mapped_identity or expected).split(":")[1]
 for l in maps:
  a=l.split()
  if len(a) not in ((6,7) if deleted is None else ((7,) if deleted else (6,))) or a[3]!="fd:11" or a[4]!=mi or a[5]!=TARGET or (len(a)==7 and a[6]!="(deleted)"):raise IdentityConflict(dict(f,mapping=l))
 mgr=typed_records(raw,b"NATIVE_MANAGER|")
 if len(mgr)!=1:raise ValueError("one ABI dependency record")
 mid,mh,mc=mgr[0].split("|");dep=p["manager_dependency"]
 identity(mid,64785,dep["bytes"])
 if mh.split()!=[dep["md5"],"-"] or mc.split()!=[str(dep["crc"]),str(dep["bytes"])]:raise ValueError("runtime manager ABI dependency changed")
 if before and mgr[0]!=before["manager"]:raise IdentityConflict(dict(f,manager=mgr[0]))
 return dict(f,uptime_seconds=u,kind=kind,parents=pars,module=mod[0],maps=maps,manager=mgr[0],exact_full_identity=True)
def core_output(bundle,command=None):
 b=Path(bundle);m=json_data(b/"manifest.json")
 if m.get("outcome")!="completed" or not m.get("port_closed") or m.get("identity")!={"uid":0,"user":"root","firmware":"55.00.750B","flavor":"cmu150_NA"}:raise ValueError("actual completed root55/closed core evidence")
 ops=[o for o in m.get("operations",[]) if not o.get("identity_probe")]
 if len(ops)!=1 or ops[0].get("exit_status")!=0 or ops[0].get("outcome")!="completed":raise ValueError("one actual END0/PS1")
 o=ops[0]
 def read(suffix):
  n=o["nonce"]+suffix;d=artifact(b/n);i=m["artifacts"].get(n,{})
  if i.get("bytes")!=len(d) or i.get("sha256")!=sha(d):raise ValueError("core artifact integrity")
  return d
 c=read(".command.txt");raw=read(".output.bin")
 if command is not None and c!=command.encode():raise ValueError("pinned command differs")
 return raw,dict(core_bundle=str(b.resolve()),manifest_sha256=sha((b/"manifest.json").read_bytes()),command_sha256=sha(c),output_sha256=sha(raw))
def bind_baseline(bundle,p):
 raw,e=core_output(bundle,native_check());f=observation(0,raw,p,"O",INITIAL)
 return dict(initial=f["META"],parents=f["parents"],mapping=f["maps"],module=f["module"],manager=f["manager"],evidence=e)
def parent_function(b):
 baseline_valid(b);a=["_source_route() {"]
 for path in PARENTS:
  a+=[" test -d "+path+" && test ! -L "+path+" || die source_parent_type"," canon "+path,
   " test \"$(stat -c '%d:%i:%a:%u:%g' "+path+")\" = '"+b["parents"][path]+"' || die source_parent_changed"]
 return "\n".join(a+["}"])+"\n"
def replace_function(text,name,new):
 m=re.search(r"^"+re.escape(name)+r"\(\) \{",text,re.M)
 if not m:raise ValueError("missing helper "+name)
 e=text.index("\n}\n",m.start())+3
 return text[:m.start()]+new+text[e:]
def native(text,p,b):
 text=replace_function(text,"_source_route",parent_function(b))
 pairs={"/jci/gui/apps/system/js/systemApp.js":TARGET,"/jci/gui/apps/system/js":str(Path(TARGET).parent),
 ".systemApp.js":".libjciuiasystem.so","cmu-bench-startup-":"cmu-bench-native-","1433953097":"1433953535",
 "94058":"454142","94055":"454142","584c67f7186ada6bae9aae1be59b5cd0":O["md5"],"376717896":str(O["crc"]),
 "64db9d0df2277e1d95a037929aef30c4":p["candidate"]["md5"],"776631029":str(p["candidate"]["crc"]),
 "WARM1":"NATIVE1","printf 'WARM %s":"printf 'NATIVE %s","printf 'RECOVERY %s":"printf 'NREC %s",
 "CANDIDATE_BOOT_BIND":"NATIVE_CANDIDATE_BOOT_BIND","ROOT_FINAL":"NATIVE_ROOT_FINAL"}
 for a,v in pairs.items():text=text.replace(a,v)
 if any(v in text for v in ["systemApp.js","94058","94055","WARM1","cmu-bench-startup-"]):raise ValueError("stale JS profile")
 return text
def parse_journal(raw,p):
 if not 0<len(raw)<=2048 or raw.count(b"\n")!=1 or not raw.endswith(b"\n") or b"\0" in raw:raise ValueError("one exact journal")
 f=raw[:-1].decode("ascii").split("|")
 if len(f)!=12 or f[0]!="NATIVE1":raise ValueError("native record")
 c=dict(nonce=nonce(f[1]))
 for k,v in zip(KEYS,f[2:]):
  if not v.startswith(k+"="):raise ValueError("ordered data keys")
  c[k]=v[len(k)+1:]
 if c["goal"]!="O" or STATES.get(c["phase"])!=(c["registry"],c["pending"]):raise ValueError("intent/state")
 identity(c["initial"],64785,454142,1433953535);identity(c["original"],45826,454142,1433953535)
 cf=identity(c["candidate"],45826,454142)
 if not re.fullmatch("45826:[1-9][0-9]*",c["directory"]):raise ValueError("retained identity")
 for k,mt in [("cstage",cf[2]),("ostage","1433953535")]:
  if c[k]!="none":identity(c[k],64785,454142,mt)
 if c["phase"] not in ("prepared","original_present") and "none" in (c["cstage"],c["ostage"]):raise ValueError("recorded stages")
 return c
def record(c):return ("NATIVE1|"+nonce(c["nonce"])+"|"+"|".join(k+"="+c[k] for k in KEYS)+"\n").encode()
def stage_descriptor(raw,data,run):
 d=delivery();s=dict(data=data,**d.fingerprint(data));prefix=("DELIVERY "+nonce(run)+" ").encode()
 normalized=b"".join(prefix+x.encode()+b"\n" for x in typed_records(raw,prefix))
 return d.stage_result(normalized,s,run)
def stage_guard(s,variable="q"):
 delivery().descriptor(s);v="$"+variable;directory=s["path"].rsplit("/",1)[0]
 return f'''{variable}={s["path"]}
test -d {directory} && test ! -L {directory} && test "$(readlink -f {directory})" = {directory} || exit 70
test "$(stat -c '%d:%i:%Y:%a:%u:%g:%h' {directory})" = '{s["dir_id"]}' || exit 71
test -f "{v}" && test ! -L "{v}" && test "$(readlink -f "{v}")" = "{v}" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "{v}")" = '{s["file_id"]}' || exit 73
test "$(md5sum < "{v}")" = '{s["md5"]}  -' || exit 74
test "$(cksum < "{v}")" = '{s["cksum"]} {s["bytes"]}' || exit 75
'''
def prepare(p,b,run,delta_stage):
 baseline_valid(b);nonce(run);delivery().descriptor(delta_stage)
 if (delta_stage["bytes"],delta_stage["md5"],delta_stage["cksum"],delta_stage["host_sha256"])!=(p["delta"]["bytes"],p["delta"]["md5"],p["delta"]["crc"],p["delta"]["sha256"]):raise ValueError("staged delta profile")
 old=legacy();t=old.WARM.replace("@RUN@",run);prefix=t[:t.index("emit() {")]
 prefix=re.sub(r"(?m)^_expected_initial=.*$",lambda _: "_expected_initial="+b["initial"],prefix).replace("cmu-bench-warm-","cmu-bench-startup-")
 h="".join(old.function(x) for x in ["emit","die","status"])+old.copy.old.helpers()+old.function("_control")+old.function("_write_state")+old.function("_flush")
 body=t[t.index("# PREPARE RETAINED BACKUP, CANDIDATE AND INTENT"):t.index("\n# RW and RO use these exact")]
 a=body.index('_slice=$(dd');z=body.index('status FROZEN_CANDIDATE_BYTES "$?"',a)+len('status FROZEN_CANDIDATE_BYTES "$?"')
 recipe=stage_guard(delta_stage,"_delta")+r'''
{
 dd if="$_delta" bs=4096 count=1 &&
 dd if="$_d/original" bs=4096 skip=1 count=6 &&
 dd if="$_delta" bs=4096 skip=1 count=1 &&
 dd if="$_d/original" bs=4096 skip=8 count=64 &&
 dd if="$_delta" bs=4096 skip=2 count=1 &&
 dd if="$_d/original" bs=4096 skip=73 count=38
} > "$_d/candidate"
status FROZEN_CANDIDATE_BYTES "$?"
'''
 body=body[:a]+recipe+body[z:]
 tail=r'''
emit "PREPARED registry=disabled pending=ENABLE phase=prepared source_O=1 physical_RO=1 retained=$_d"
emit "JOURNAL $_jexpected"
_jn=$(wc -c < "$_d/journal") || die journal_count
_jh=$(md5sum < "$_d/journal") || die journal_md5
_jc=$(cksum < "$_d/journal") || die journal_crc
emit "JOURNAL_COUNT $_jn"
emit "JOURNAL_MD5 $_jh"
emit "JOURNAL_CRC $_jc"
'''
 return native(prefix+h+"\n"+body+tail,p,b)
def retained_context(bundle,command,p,run):
 raw,e=core_output(bundle,command);rows=typed_records(raw,("NATIVE "+nonce(run)+" ").encode())
 def one(key):
  a=[x[len(key)+1:] for x in rows if x.startswith(key+" ")]
  if len(a)!=1:raise ValueError("missing/duplicate "+key)
  return a[0]
 raw=(one("JOURNAL")+"\n").encode();c=parse_journal(raw,p)
 if c["nonce"]!=run or c["initial"]!=INITIAL or c["phase"]!="prepared" or c["cstage"]!="none" or c["ostage"]!="none":raise ValueError("actual prepared context")
 if (int(one("JOURNAL_COUNT")),one("JOURNAL_MD5").split()[0],int(one("JOURNAL_CRC").split()[0]))!=(len(raw),hashlib.md5(raw).hexdigest(),posix_cksum(raw)):raise ValueError("journal capture checks")
 return dict(context=c,evidence=e),raw
def recovery(p,b,c):parse_journal(record(c),p);return native(legacy().persistent_recovery(c),p,b)
def apply(p,b,c,recovery_body):return native(legacy().apply_candidate(c,recovery_body),p,b)
def checked_body(body):
 data=body.encode()
 if len(data)>16384:raise ValueError("exceeds proven DATA16KiB; no silent limit raise")
 subprocess.run(["/bin/sh","-n"],input=data,check=True,capture_output=True,timeout=5)
 wire=wrap_command(body,"0"*32)
 return dict(fp(data),max_physical_line=max(map(len,wire.splitlines())),wire_bytes=len(wire))
def saved_body(out,name,body):pin=checked_body(body);(out/name).write_text(body);return pin
def packet(path,out,run):
 p=profile(path);out=Path(out);out.mkdir(parents=True,exist_ok=False);nonce(run)
 (out/"baseline.command.sh").write_text(native_check())
 data=artifact(hostpath(p["delta"]["path"],Path(path).parent));d=delivery()
 stage=d.stage_command(dict(data=data,**d.fingerprint(data)),run);(out/"delta.stage.sh").write_text(stage)
 plan=dict(schema="NATIVE_RUNTIME_PACKET_V1",live_authority=False,nonce=run,candidate_profile=str(Path(path).resolve()),candidate_profile_sha256=sha(Path(path).read_bytes()),baseline=None,retained=None,applied=None,recovery_code_identity=None,restored_original=None,request_budget=dict(candidate=1,original_confirmation=1,login_each=1),baseline_command_sha256=sha(native_check().encode()),delta_stage_nonce=run,delta_stage_sha256=sha(stage.encode()),candidate=p["candidate"],original=O,target=TARGET,scope="host-only; actual IDs unset until completed target evidence")
 (out/"packet.json").write_text(json.dumps(plan,indent=2)+"\n");return plan
def main(argv=None):
 a=argparse.ArgumentParser(description=__doc__);s=a.add_subparsers(dest="action",required=True)
 x=s.add_parser("packet");x.add_argument("--candidate-profile",type=Path,required=True);x.add_argument("--out",type=Path,required=True);x.add_argument("--nonce",required=True)
 x=s.add_parser("baseline");x.add_argument("--candidate-profile",type=Path,required=True);x.add_argument("--bundle",type=Path,required=True);x.add_argument("--out",type=Path,required=True)
 args=a.parse_args(argv)
 if args.action=="packet":v=packet(args.candidate_profile,args.out,args.nonce)
 else:
  v=bind_baseline(args.bundle,profile(args.candidate_profile))
  if args.out.exists():raise ValueError("new output required")
  args.out.write_text(json.dumps(v,indent=2)+"\n")
 print(json.dumps(v,indent=2))


# Typed host binding helpers. Inputs are completed core evidence; no target execution.
def stage_plan(data,out,run):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);d=delivery()
 cmd=d.stage_command(dict(data=data,**d.fingerprint(data)),nonce(run))
 (out/"body.bin").write_bytes(data);(out/"data-stage.sh").write_text(cmd)
 v=dict(stage_nonce=run,body=fp(data),stage_command_sha256=sha(cmd.encode()),live_authority=False)
 (out/"stage-plan.json").write_text(json.dumps(v,indent=2)+"\n");return v
def bound_stage(plan_dir,bundle):
 d=Path(plan_dir);v=json_data(d/"stage-plan.json");data=artifact(d/"body.bin")
 if fp(data)!=v["body"]:raise ValueError("staging source changed")
 cmd=(d/"data-stage.sh").read_text()
 if sha(cmd.encode())!=v["stage_command_sha256"]:raise ValueError("staging command changed")
 raw,e=core_output(bundle,cmd);s=stage_descriptor(raw,data,v["stage_nonce"])
 return dict(descriptor=s,evidence=e,body=v["body"])
def execute_entry(stage):
 s=stage["descriptor"];return stage_guard(s)+"\n/bin/sh \"$q\" </dev/null\n"
def remove_delivery(stage):return delivery().cleanup_command(stage["descriptor"])
def prepared_plan(p,b,run,delta_stage,out):
 body=prepare(p,b,run,delta_stage["descriptor"]);out=Path(out);out.mkdir(parents=True,exist_ok=False)
 pin=saved_body(out,"prepare.sh",body)
 v=dict(nonce=run,baseline=b,delta_stage=delta_stage,prepare_pin=pin,live_authority=False)
 (out/"prepared-plan.json").write_text(json.dumps(v,indent=2)+"\n");return v
def retained_plan(p,prepared,execution_bundle,entry,out):
 x=Path(prepared);v=json_data(x/"prepared-plan.json")
 body=(x/"prepare.sh").read_text()
 if fp(body.encode())!={k:v["prepare_pin"][k] for k in O}:raise ValueError("preparation body changed")
 # Execution command must be the typed entry for this exact body, bound separately.
 raw,e=core_output(execution_bundle,entry)
 rows=typed_records(raw,("NATIVE "+nonce(v["nonce"])+" ").encode())
 def one(key):
  a=[z[len(key)+1:] for z in rows if z.startswith(key+" ")]
  if len(a)!=1:raise ValueError("missing/duplicate prepared "+key)
  return a[0]
 journal=(one("JOURNAL")+"\n").encode();ctx=parse_journal(journal,p)
 if ctx["nonce"]!=v["nonce"] or ctx["initial"]!=v["baseline"]["initial"] or ctx["phase"]!="prepared" or ctx["cstage"]!="none" or ctx["ostage"]!="none":raise ValueError("prepared control profile")
 if (len(journal),hashlib.md5(journal).hexdigest(),posix_cksum(journal))!=(int(one("JOURNAL_COUNT")),one("JOURNAL_MD5").split()[0],int(one("JOURNAL_CRC").split()[0])):raise ValueError("journal exact checks")
 out=Path(out);out.mkdir(parents=True,exist_ok=False);rec=recovery(p,v["baseline"],ctx)
 pin=saved_body(out,"recovery.sh",rec);(out/"journal.exact.bin").write_bytes(journal)
 result=dict(nonce=v["nonce"],baseline=v["baseline"],context=ctx,recovery_pin=pin,preparation_evidence=e,code_identity=None,applied_identity=None,restored_identity=None,live_authority=False)
 (out/"retained-plan.json").write_text(json.dumps(result,indent=2)+"\n");return result
def retained_guard(ctx):
 nonce(ctx["nonce"])
 if not re.fullmatch("45826:[1-9][0-9]*",ctx["directory"]):raise ValueError("retained directory identity")
 d="/tmp/mnt/data_persist/cmu-bench-native-"+ctx["nonce"]
 return f'''d={d}
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 80
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = '{ctx["directory"]}:700:0:0' || exit 81
'''
def persist_entry(stage,ctx):
 s=stage["descriptor"]
 return stage_guard(s)+retained_guard(ctx)+f'''p="$d/recovery.sh"
test ! -e "$p" && test ! -L "$p" || exit 82
cp -p "$q" "$p" || exit 83
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 84
test "$(stat -c '%a:%u:%g:%h:%d:%s' "$p")" = '600:0:0:1:45826:{s["bytes"]}' || exit 85
test "$(md5sum < "$p")" = '{s["md5"]}  -' || exit 86
test "$(cksum < "$p")" = '{s["cksum"]} {s["bytes"]}' || exit 87
printf 'NATIVE_CODE|';stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p" || exit 88
'''
def code_identity(value,body):
 f=value.split(":")
 if len(f)!=8 or any(not re.fullmatch("[0-9]+",x) for x in f) or f[0]!="45826" or int(f[1])<1 or f[3:]!=[str(len(body)),"600","0","0","1"]:raise ValueError("actual code identity")
 return value
def bind_code(bundle,command,body):
 raw,e=core_output(bundle,command);r=typed_records(raw,b"NATIVE_CODE|")
 if len(r)!=1:raise ValueError("one actual persistent code record")
 return dict(identity=code_identity(r[0],body),fingerprint=fp(body),evidence=e)
def code_entry(ctx,code,mode="VERIFY"):
 if mode not in ("VERIFY","RESTORE_ORIGINAL"):raise ValueError("fixed recovery operation")
 f=code["fingerprint"];code_identity(code["identity"],b"x"*f["bytes"])
 return retained_guard(ctx)+f'''p="$d/recovery.sh"
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 82
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{code["identity"]}' || exit 83
test "$(md5sum < "$p")" = '{f["md5"]}  -' || exit 84
test "$(cksum < "$p")" = '{f["crc"]} {f["bytes"]}' || exit 85
/bin/sh "$p" {mode} </dev/null
'''
def verified_output(status,raw,ctx,kind,expected=None):
 if status:raise ValueError("persistent VERIFY nonzero")
 prefix=("NREC "+nonce(ctx["nonce"])+" ").encode()
 rows=[x for x in typed_records(raw,prefix) if x.startswith("END mode=VERIFY ")]
 if len(rows)!=1:raise ValueError("one persistent VERIFY completion")
 pat=r"END mode=VERIFY rc=0 kind="+kind+r" registry=(enabled|disabled) pending=(none|ENABLE) phase=(prepared|candidate_verified|original_restored|original_present) writes=0 recovery_ready=1 current_id=([0-9:]+)"
 m=re.fullmatch(pat,rows[0])
 if not m:raise ValueError("consistent read-only VERIFY completion")
 reg,pending,phase,sid=m.groups()
 if kind=="C":
  if (reg,pending,phase)!=("enabled","none","candidate_verified"):raise ValueError("C control")
  identity(sid,64785,454142)
 else:
  if (reg,pending,phase) not in [("disabled","ENABLE","prepared"),("disabled","none","original_restored"),("disabled","none","original_present")]:raise ValueError("O control")
  identity(sid,64785,454142,1433953535)
 if expected is not None and sid!=expected:raise IdentityConflict(dict(META=sid))
 return sid
def apply_bound(p,b,ctx,recovery_body,code):
 text=apply(p,b,ctx,recovery_body)
 anchor='_recovery_code_guard() {\n'
 if text.count(anchor)!=1:raise ValueError("apply guard anchor")
 return text.replace(anchor,anchor+'test "$(_id "$_code")" = \''+code["identity"]+'\' || die recovery_code_identity\n')
def bind_apply(bundle,entry,p,ctx):
 raw,e=core_output(bundle,entry);rows=typed_records(raw,b"NATIVE_CANDIDATE_BOOT_BIND|")
 if len(rows)!=1:raise ValueError("one actual apply/RO/recovery binding")
 v=rows[0].split("|");c=p["candidate"]
 if len(v)!=9 or v[:2]!=[ctx["nonce"],"C"] or v[3:]!=[str(c["bytes"]),c["md5"],str(c["crc"]),"ro","1","candidate_verified"]:raise ValueError("native applied profile")
 identity(v[2],64785,c["bytes"])
 return dict(kind="C",identity=v[2],evidence=e,physical_ro=True,recovery_ready_before_publish=True)
def bind_original(bundle,entry,p,ctx):
 raw,e=core_output(bundle,entry);sid=verified_output(0,raw,ctx,"O")
 if sid==INITIAL:raise ValueError("first native experiment requires actual undo/restored identity, not historical initial")
 return dict(kind="O",identity=sid,evidence=e,physical_ro=True)

if __name__=="__main__":main()
