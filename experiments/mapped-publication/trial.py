"""One direct native trial. Preparation and apply are separate explicit CLI actions."""
import json,sys,os
from pathlib import Path
from bench import command,stage,rt,ROOT
import linked
R=ROOT/os.environ.get("OC_RUN","runs/open-connect-native-linked")
def save(name,x): (R/name).write_text(json.dumps(x,indent=2)+"\n")
def load(name):return json.loads((R/name).read_text())
def entry(mode):
 return bound_entry(load("plan/plan.json"),load("code.json"),mode)
def bound_entry(p,code,mode):
 return f'''d={p["directory"]}
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = '{code["directory"]}' || exit 71
p="$d/recovery.sh"
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{code["identity"]}' || exit 73
test "$(md5sum < "$p")" = '{p["body"]["md5"]}  -' || exit 74
test "$(cksum < "$p")" = '{p["body"]["crc"]} {p["body"]["bytes"]}' || exit 75
/bin/sh "$p" {mode} </dev/null
'''
def prepare():
 R.mkdir(exist_ok=True)
 delta=None
 if os.environ.get("OC_NATIVE_PROFILE"):
  delta=stage(linked.relocated(linked.P["delta"]["path"]).read_bytes(),R/"delta-stage")
 p=linked.plan(R/"plan",delta)
 import boot
 raw=command(boot.mapping_command(),R/"baseline")
 fields=rt.fields().candidate_fields(raw)
 assert fields["META"]==p["oid"]+":1"
 assert fields["HASH"].split()==[p["original"]["md5"],"-"]
 assert fields["ROOT"]=="/dev/ffx01p1 / relfs ro,noatime 0 0"
 baseline=dict(fields,module=rt.typed_records(raw,b"NATIVE_MODULE|")[0],
               manager=rt.typed_records(raw,b"NATIVE_MANAGER|")[0])
 save("baseline.json",baseline)
 body=(R/"plan/recovery.sh").read_bytes()
 desc=stage(body,R/"body-stage")
 command((R/"plan/prepare.sh").read_text(),R/"prepare")
 d=p["directory"];s=dict(descriptor=desc)
 cmd=rt.stage_guard(desc)+f'''d={d}
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 80
test "$(stat -c '%a:%u:%g:%d' "$d")" = 700:0:0:45826 || exit 81
test ! -e "$d/recovery.sh" && test ! -L "$d/recovery.sh" || exit 82
cp -p "$q" "$d/recovery.sh" || exit 83
test "$(md5sum < "$d/recovery.sh")" = '{p["body"]["md5"]}  -' || exit 84
test "$(cksum < "$d/recovery.sh")" = '{p["body"]["crc"]} {p["body"]["bytes"]}' || exit 85
printf 'OCCODE|';stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$d/recovery.sh"
printf 'OCDIR|';stat -c '%d:%i:%a:%u:%g' "$d"
'''
 out=command(cmd,R/"persist")
 def one(prefix):
  rows=rt.typed_records(out,prefix)
  if len(rows)!=1:raise ValueError("one actual "+str(prefix))
  return rows[0]
 identity=one(b"OCCODE|");directory=one(b"OCDIR|")
 rt.code_identity(identity,body)
 save("code.json",dict(identity=identity,directory=directory))
 command(rt.delivery().cleanup_command(desc),R/"stage-cleanup")
 if delta:command(rt.delivery().cleanup_command(delta),R/"delta-cleanup")
 command(entry("VERIFY"),R/"ready-verify")
 print("Persistent linked recovery ready; no root publication yet.")
def action(mode):
 out=command(entry(mode),R/mode.lower())
 print("\n".join(rt.typed_records(out,b"OCLINK|")))
 save(mode.lower()+".json",dict(mode=mode,rows=rt.typed_records(out,b"OCLINK|")))
if __name__=="__main__":
 a=sys.argv[1]
 if a=="prepare":prepare()
 elif a in ("APPLY","UNDO","VERIFY","CLEAN"):action(a)
 else:raise ValueError("explicit action")
