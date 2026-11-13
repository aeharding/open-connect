import copy,json,tempfile,unittest
from pathlib import Path
import runtime as rt,recover_rw as rw,recover_observe as obs
PROFILE=rw.RUN/"recovery/O-recovery-boot.profile.json"
class OriginalRecoveryObserverChecks(unittest.TestCase):
 def test_real_Bundle_event_keyword_contract(self):
  import ast,inspect
  tree=ast.parse((rt.HERE/"recover_observe.py").read_text())
  signature=inspect.signature(rt.fields().stock.Bundle.event)
  found=0
  for n in ast.walk(tree):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="event":
    signature.bind(None,"actual_event",**{kw.arg:None for kw in n.keywords})
    found+=1
  self.assertGreaterEqual(found,3)
 def test_actual_O_sync_RW_binding_and_C_refusal(self):
  v,p=obs.approved(PROFILE);self.assertEqual(v["kind"],"O");self.assertEqual(v["pre_mount"],"rw")
  for changed in [dict(kind="C"),dict(identity=rw.CID)]:
   with tempfile.TemporaryDirectory() as d:
    q=Path(d)/"bad.json";q.write_text(json.dumps(dict(v,**changed)))
    with self.assertRaises(ValueError):obs.approved(q)
 def test_postboot_cannot_accept_RW_or_old_deleted_mapping(self):
  v,p=obs.approved(PROFILE);b=Path(v["fresh_O_bundle"])
  raw,e=rt.core_output(b,Path(v["fresh_O_command"]).read_text())
  with self.assertRaises(ValueError):rt.observation(0,raw,p,"O",rw.OID)
  # Synthetic postboot fields change only bootstrap facts/mapping, not source bytes.
  fixed=raw.replace(b"relfs rw,noatime",b"relfs ro,noatime")
  old=(b"/jci/mmui/uia/.libjciuiasystem.so.cmu-bench-7c748f8ac79ca2a8ae45170150798589-candidate (deleted)")
  fixed=fixed.replace(old,rt.TARGET.encode()).replace(b"fd:11 5484",b"fd:11 9457")
  f=rt.observation(0,fixed,p,"O",rw.OID);self.assertEqual(f["META"],rw.OID)
  with self.assertRaises(rt.IdentityConflict):rt.observation(0,fixed.replace(b"fd:11 9457",b"fd:11 1606"),p,"O",rw.OID)
if __name__=="__main__":unittest.main()
