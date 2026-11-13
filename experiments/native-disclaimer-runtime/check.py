#!/usr/bin/env python3
from pathlib import Path
import datetime,hashlib,json,subprocess,sys
root=Path(__file__).resolve().parents[2];here=Path(__file__).resolve().parent
out=here/"checks"/datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ");out.mkdir(parents=True)
pins={}
for name in ["runtime.py","observe.py","test_runtime.py","check.py","dependencies.json"]:
 p=here/name;data=p.read_bytes();(out/name).write_bytes(data);pins[str(p.relative_to(root))]=hashlib.sha256(data).hexdigest()
argv=[sys.executable,"-B","-m","unittest","-v","test_runtime"]
p=subprocess.run(argv,cwd=here,capture_output=True,text=True,timeout=60)
(out/"stdout.txt").write_text(p.stdout);(out/"stderr.txt").write_text(p.stderr)
record=dict(returncode=p.returncode,argv=argv,source_pins=pins,host_only=True,device_opens=0,source_snapshots=str(out),candidate_profile="runs/t12-native-host-20261113T170401.731894Z/candidate/profile.json")
(out/"manifest.json").write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(dict(manifest=str(out/"manifest.json"),returncode=p.returncode)));print(p.stderr)
raise SystemExit(p.returncode)
