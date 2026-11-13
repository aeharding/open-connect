"""Small JS companion using the already bench-tested linked transaction."""
import json,os,secrets,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"mapped-publication"))
from bench import ROOT,rt,command,stage
import linked,trial
import patch
R=ROOT/os.environ.get("OC_JS_RUN","runs/open-connect-smooth/js")
TARGET="/jci/gui/apps/system/js/systemApp.js"
def save(name,value):(R/name).write_text(json.dumps(value,indent=2)+"\n")
def load(name):return json.loads((R/name).read_text())
def one(raw,prefix):
 rows=rt.typed_records(raw,prefix)
 if len(rows)!=1:raise ValueError("unique "+str(prefix))
 return rows[0]
def entry(mode):
 return trial.bound_entry(load("plan/plan.json"),load("code.json"),mode)
def prepare():
 R.mkdir(parents=True,exist_ok=False)
 f=patch.build(R/"feature",patch.BASE);o=f["original"];c=f["candidate"]
 raw=command(f'''p={TARGET}
for d in /jci /jci/gui /jci/gui/apps /jci/gui/apps/system /jci/gui/apps/system/js;do
 test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
 v=$(stat -c '%d:%i:%a:%u:%g' "$d") || exit 71
 printf 'OCJS_PARENT|%s|%s\\n' "$d" "$v"
done
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p") || exit 73;printf 'OCJS_ID|%s\\n' "$v"
test "$(stat -c '%Y:%s:%a:%u:%g:%h' "$p")" = 1433953097:94058:755:1018:3015:1 || exit 74
test "$(md5sum < "$p")" = '{o["md5"]}  -' || exit 75
test "$(cksum < "$p")" = '{o["crc"]} {o["bytes"]}' || exit 76
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{{n++;m=$4}}END{{exit !(n==1&&m=="ro,noatime")}}' /proc/mounts || exit 77
''',R/"baseline")
 oid=one(raw,b"OCJS_ID|");parents=dict(x.split("|") for x in rt.typed_records(raw,b"OCJS_PARENT|"))
 if len(parents)!=5:raise ValueError("parent records")
 nonce=secrets.token_hex(16);d="/tmp/mnt/data_persist/oc-intro-hook-"+nonce
 prefix="/jci/gui/apps/system/js/.systemApp.js.oc-"+nonce
 p=dict(target=TARGET,directory=d,oid=oid.rsplit(":",1)[0],parents=parents,
        hold_o=prefix+"-O",hold_c=prefix+"-C",stage=prefix+"-stage",original=o,candidate=c)
 body=linked.render(TARGET,d,p["hold_o"],p["hold_c"],p["stage"],p["oid"],parents,o,c)
 # No process maps a JS source file. Preserve the common candidate-mapping refusal;
 # omit only the native-MMUI original-library-specific positive mapping assertion.
 start=body.index("  pid=$(pgrep")
 end=body.index("  begin_write",start)
 body=body[:start]+body[end:]
 p["body"]=rt.fp(body.encode())
 (R/"plan").mkdir();save("plan/plan.json",p);(R/"plan/recovery.sh").write_text(body)
 ins=stage((R/"feature/insert.bin").read_bytes(),R/"insert-stage")
 desc=stage(body.encode(),R/"body-stage")
 prep=rt.stage_guard(ins,"insert")+rt.stage_guard(desc,"code")+f'''
d={d};p={TARGET}
for q in /tmp /tmp/mnt /tmp/mnt/data_persist;do
 test -d "$q" && test ! -L "$q" && test "$(readlink -f "$q")" = "$q" || exit 70
done
test "$(stat -c '%a:%u:%g:%d' /tmp/mnt/data_persist)" = 755:0:0:45826 || exit 71
test ! -e "$d" && test ! -L "$d" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{oid}' || exit 73
test "$(md5sum < "$p")" = '{o["md5"]}  -' || exit 74
umask 077
mkdir -m 700 "$d" || exit 75
cp -p "$p" "$d/original" || exit 76
{{
 dd if="$d/original" bs=1 count={f["offset"]} &&
 cat "$insert" &&
 dd if="$d/original" bs=1 skip={f["offset"]}
}} > "$d/candidate" || exit 77
chmod 755 "$d/candidate" && chown 1018:3015 "$d/candidate" || exit 78
test "$(md5sum < "$d/candidate")" = '{c["md5"]}  -' || exit 79
test "$(cksum < "$d/candidate")" = '{c["crc"]} {c["bytes"]}' || exit 80
printf 'prepared|none\\n' > "$d/state" || exit 81
cp -p "$code" "$d/recovery.sh" || exit 82
test "$(md5sum < "$d/recovery.sh")" = '{p["body"]["md5"]}  -' || exit 83
test "$(cksum < "$d/recovery.sh")" = '{p["body"]["crc"]} {p["body"]["bytes"]}' || exit 84
v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$d/recovery.sh");printf 'OCJS_CODE|%s\\n' "$v"
v=$(stat -c '%d:%i:%a:%u:%g' "$d");printf 'OCJS_DIR|%s\\n' "$v"
'''
 (R/"plan/prepare.sh").write_text(prep)
 prepdesc=stage(prep.encode(),R/"prepare-stage")
 out=command(rt.stage_guard(prepdesc)+"\n/bin/sh \"$q\" </dev/null",R/"prepare")
 codeid=one(out,b"OCJS_CODE|");rt.code_identity(codeid,body.encode())
 save("code.json",dict(identity=codeid,directory=one(out,b"OCJS_DIR|")))
 command(entry("VERIFY"),R/"ready-verify")
 for name,descriptor in [("insert",ins),("body",desc),("prepare",prepdesc)]:
  command(rt.delivery().cleanup_command(descriptor),R/(name+"-delivery-clean"))
 print("JS completion hook and independent undo ready; installed source unchanged")
def action(mode):
 out=command(entry(mode),R/mode.lower())
 rows=rt.typed_records(out,b"OCLINK|");save(mode.lower()+".json",dict(mode=mode,rows=rows))
 print("\n".join(rows))
if __name__=="__main__":
 mode=sys.argv[1]
 if mode=="prepare":prepare()
 elif mode in ("APPLY","UNDO","VERIFY","CLEAN"):action(mode)
 else:raise ValueError("explicit mode")
