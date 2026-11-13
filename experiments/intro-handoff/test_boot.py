import importlib.util,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("intro_boot",Path(__file__).with_name("boot.py"))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class PairCheck(unittest.TestCase):
 def test_pair_verification_uses_actual_session_bundle_and_refuses_wrong_image(self):
  sid="64785:123:4:94717:755:1018:3015:2"
  rows=["APPLIED|"+sid,"FINAL|operation=0|sync=0|ro_request=0|row=ro,noatime"]
  with tempfile.TemporaryDirectory() as d:
   bundle=b.native.stock.Bundle(Path(d)/"bundle","paired check","t6")
   s=SimpleNamespace(bundle=bundle,execute=lambda cmd:(0,("OCLINK|VERIFY|C|candidate|"+sid+"|ro,noatime|writes=0\n").encode()))
   with patch.object(b,"original_verify",return_value=b"native checked"),patch.object(b.js,"load",return_value={"rows":rows}),patch.object(b.js,"entry",return_value="VERIFY"):
    self.assertEqual(b.verify(s,"C","native-id"),b"native checked")
    s.execute=lambda cmd:(0,b"OCLINK|VERIFY|O|restored|wrong|ro,noatime|writes=0\n")
    with self.assertRaises(ValueError):b.verify(s,"C","native-id")
   bundle.finish("offline")
if __name__=="__main__":unittest.main()
