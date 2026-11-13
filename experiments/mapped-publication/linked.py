"""Render one linked publication experiment; frozen native feature bytes unchanged."""
import json,re,secrets,shlex,subprocess,os
from pathlib import Path
from bench import rt,ROOT
HERE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get("OC_NATIVE_PROFILE",str(ROOT/"runs/t12-native-host-20261113T170401.731894Z/candidate/profile.json")))
P=rt.json_data(SOURCE)
def relocated(s):
    return Path(s.replace("/Users/aeharding/mazda-cmu-bench",str(ROOT),1))
def feature():
    for key,path in [("original",rt.ORIGINAL),("candidate",relocated(P["candidate_path"]))]:
        if rt.fp(path.read_bytes())!=P[key]:raise ValueError(key+" changed")
    for path,h in P["source_pins"].items():
        if rt.sha((ROOT/path).read_bytes())!=h:raise ValueError("native code changed")
    return P
def render(target,d,hold_o,hold_c,stage,oid,parents,original=None,candidate=None):
    o=original or P["original"];c=candidate or P["candidate"]
    vals={"TARGET":target,"DIRECTORY":d,"HOLD_O":hold_o,"HOLD_C":hold_c,"STAGE":stage,
          "ORIGINAL_ID":oid,"ORIGINAL_HASH":o["md5"],"CANDIDATE_HASH":c["md5"],
          "ORIGINAL_CRC":str(o["crc"]),"CANDIDATE_CRC":str(c["crc"])}
    guards=[]
    for path,sid in parents.items():
        guards.extend([f'test -d {path} && test ! -L {path} && test "$(readlink -f {path})" = {path} || die parent',
                       f'test "$(stat -c "%d:%i:%a:%u:%g" {path})" = "{sid}" || die parent_identity'])
    vals["PARENT_GUARDS"]="\n".join(guards)
    s=(HERE/"linked.sh.in").read_text()
    s=re.sub(r"@([A-Z_]+)@",lambda m: vals[m[1]] if m[1]=="PARENT_GUARDS" else shlex.quote(vals[m[1]]),s)
    subprocess.run(["/bin/sh","-n"],input=s.encode(),check=True)
    if len(s.encode())>16384:raise ValueError("staging bound")
    return s
def plan(out,delta=None):
    feature();out=Path(out);out.mkdir(exist_ok=False)
    baseline=rt.json_data(ROOT/"runs/20261113T111353-0600-t14-native-intro/recovery/original-boot-v2/after.json")
    n=secrets.token_hex(16);d="/tmp/mnt/data_persist/oc-native-"+n
    prefix="/jci/mmui/uia/.libjciuiasystem.so.oc-"+n
    v=dict(nonce=n,target=rt.TARGET,directory=d,hold_o=prefix+"-O",hold_c=prefix+"-C",
           stage=prefix+"-stage",oid=baseline["META"].rsplit(":",1)[0],parents=baseline["parents"],
           original=P["original"],candidate=P["candidate"],candidate_profile_sha256=rt.sha(SOURCE.read_bytes()))
    body=render(v["target"],d,v["hold_o"],v["hold_c"],v["stage"],v["oid"],v["parents"])
    (out/"recovery.sh").write_text(body)
    old="/tmp/mnt/data_persist/cmu-bench-native-7c748f8ac79ca2a8ae45170150798589"
    # Only uses old immutable image backups; never rewrites old control or code.
    prep=f'''set -fu
umask 077
d={d}
old={old}
for p in /tmp /tmp/mnt /tmp/mnt/data_persist "$old";do
 test -d "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 70
done
test "$(stat -c '%d:%i:%a:%u:%g' "$old")" = 45826:64:700:0:0 || exit 71
test ! -e "$d" && test ! -L "$d" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' {rt.TARGET})" = '{baseline["META"]}' || exit 73
mkdir -m 700 "$d" || exit 74
'''
    for name,k in [("original","original"),("candidate","candidate")]:
        f=P[k]
        if name=="candidate" and delta:
            prep+=rt.stage_guard(delta,"delta")
            prep+='''{
 dd if="$delta" bs=4096 count=1 &&
 dd if="$d/original" bs=4096 skip=1 count=6 &&
 dd if="$delta" bs=4096 skip=1 count=1 &&
 dd if="$d/original" bs=4096 skip=8 count=64 &&
 dd if="$delta" bs=4096 skip=2 count=1 &&
 dd if="$d/original" bs=4096 skip=73 count=38
} > "$d/candidate" || exit 78
chmod 755 "$d/candidate" && chown 1018:3015 "$d/candidate" || exit 78
'''
        else:
            prep+=f'''test -f "$old/{name}" && test ! -L "$old/{name}" || exit 75
test "$(md5sum < "$old/{name}")" = '{f["md5"]}  -' || exit 76
test "$(cksum < "$old/{name}")" = '{f["crc"]} 454142' || exit 77
cp -p "$old/{name}" "$d/{name}" || exit 78
'''
        prep+=f'''test "$(md5sum < "$d/{name}")" = '{f["md5"]}  -' || exit 79
test "$(cksum < "$d/{name}")" = '{f["crc"]} 454142' || exit 80
'''
    prep+='printf "prepared|none\\n" > "$d/state" || exit 81\nprintf "OCLINK|PREPARED|%s\\n" "$d"\n'
    (out/"prepare.sh").write_text(prep)
    v["body"]=rt.fp(body.encode());(out/"plan.json").write_text(json.dumps(v,indent=2)+"\n")
    return v
if __name__=="__main__":
    import sys
    print(json.dumps(plan(sys.argv[1]),indent=2))
