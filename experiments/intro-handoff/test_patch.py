import subprocess,tempfile,unittest,sys
from pathlib import Path
import patch
class HookTests(unittest.TestCase):
 def test_exact_insertion_and_refuse_unknown(self):
  o=patch.BASE.read_bytes();c,at,insert=patch.patch(o)
  self.assertEqual(c[:at]+c[at+len(insert):],o)
  for b in (c,o+b" ",b""):
   with self.assertRaises(ValueError):patch.patch(b)
 def test_real_private_base_dispatcher(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"candidate.js";p.write_bytes(patch.patch(patch.BASE.read_bytes())[0])
   subprocess.run(["node","--check",str(p)],check=True)
   subprocess.run(["node",str(Path(__file__).with_name("test_behavior.js")),str(p),
    str(patch.ROOT/"runs/20261113T081530-0600-t14-rev2-lifecycle/originals/jci/gui/framework/js/BaseApp.js")],check=True)
if __name__=="__main__":unittest.main()
