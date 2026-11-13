import unittest,subprocess,json,tempfile
from pathlib import Path
import runtime as rt
import recover_rw as rw
class RecoveryDeltaChecks(unittest.TestCase):
 def test_explicit_rw_entry_preserves_writer(self):
  body=rw.undo_body();rt.checked_body(body)
  self.assertIn('case $_mode in RESTORE_FROM_RW)',body)
  self.assertIn('_root_mode rw || die physical_root_mode',body)
  self.assertIn('RW_entry_requires_known_C',body);self.assertIn(rw.CID,body)
  self.assertIn('_mount_request ro',body);self.assertIn('( _flush VERIFIED_FILE_AND_CONTROL )',body)
  original=(rw.RUN/'retained-plan/recovery.sh').read_text()
  self.assertIn('case $_mode in VERIFY|RESTORE_ORIGINAL)',original)
  self.assertIn('_root_mode ro || die physical_root_mode',original)
 def test_readonly_inspection(self):
  for kind in ["C","O"]:
   body=rw.inspector(kind,"rw");rt.checked_body(body)
   for x in ["_mount_request","_flush()","mv -f","cp -p"]:self.assertNotIn(x,body)
   self.assertIn("writes=0 root_mode=rw",body)
 def test_default_refuses_before_io(self):
  body=rw.undo_body();header=body[:body.index("_run=")]
  p=subprocess.run(["/bin/sh"],input=header.encode(),capture_output=True);self.assertEqual(p.returncode,2)
 def test_actual_relfs_deleted_mapping_format(self):
  p,ret,code=rw.state()
  raw=(rw.RUN/"recovery/fresh-state-refined-output.bin").read_bytes()
  f=rw.rw_observation(0,raw,p,"C",rw.CID,ret["baseline"])
  self.assertEqual(f["kind"],"C");self.assertIn("5484",f["maps"][0])
  with self.assertRaises(rt.IdentityConflict):
   rw.rw_observation(0,raw.replace(b"fd:11 5484",b"fd:11 1606"),p,"C",rw.CID,ret["baseline"])
  with self.assertRaises(ValueError):
   rw.rw_observation(0,raw.replace(b"relfs rw,noatime",b"relfs ro,noatime"),p,"C",rw.CID,ret["baseline"])
 def test_unknown_or_missing_sync_never_boot_binding(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/"manifest.json").write_text(json.dumps(dict(outcome="unknown",port_closed=True,operations=[])))
   with self.assertRaises(ValueError):rw.known_undo_failure(p,"")
if __name__=="__main__":unittest.main()
