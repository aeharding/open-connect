"""Existing native boot loop with the paired JS image independently checked pre/post."""
import importlib.util,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"mapped-publication"))
import boot as native
spec=importlib.util.spec_from_file_location("intro_js_runtime",HERE/"runtime.py")
js=importlib.util.module_from_spec(spec);spec.loader.exec_module(js)
original_verify=native.verify
def verify(session,kind,sid):
 raw=original_verify(session,kind,sid)
 rows=js.load("apply.json" if kind=="C" else "undo.json")["rows"]
 key="APPLIED|" if kind=="C" else "RESTORED|"
 ids=[r[len(key):] for r in rows if r.startswith(key)]
 if len(ids)!=1 or rows[-1]!="FINAL|operation=0|sync=0|ro_request=0|row=ro,noatime":
  raise ValueError("completed JS transition required")
 phase="candidate" if kind=="C" else "restored"
 rc,out=session.execute(js.entry("VERIFY"))
 if rc or js.rt.typed_records(out,b"OCLINK|")!=[f"VERIFY|{kind}|{phase}|{ids[0]}|ro,noatime|writes=0"]:
  raise ValueError("JS pair changed")
 session.bundle.event("intro_js_verified",source_kind=kind,identity=ids[0])
 return raw
native.verify=verify
if __name__=="__main__":raise SystemExit(native.main())
