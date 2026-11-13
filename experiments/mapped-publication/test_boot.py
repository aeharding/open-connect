import ast,inspect,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import boot
from bench import rt,stock,ROOT
class BootIntegration(unittest.TestCase):
 def test_real_bundle_signatures(self):
  tree=ast.parse(Path(boot.__file__).read_text())
  sig=inspect.signature(stock.Bundle.event)
  for n in ast.walk(tree):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="event":
    sig.bind(None,"event",**{k.arg:None for k in n.keywords})
 def test_complete_observer_frontdoor_with_real_bundle(self):
  plan=dict(original=rt.O,candidate=rt.fp(b"C"*454142),target=rt.TARGET,
            stage="/jci/mmui/uia/.library-stage",hold_o="/jci/mmui/uia/.library-O",
            hold_c="/jci/mmui/uia/.library-C",
            parents={path:"64785:100:755:1018:3015" for path in rt.PARENTS})
  original=("\n".join([
   "SWST|META|64785:9457:1433953535:454142:755:1018:3015:1",
   "SWST|HASH|"+rt.O["md5"]+"  -",
   "SWST|CRC|"+str(rt.O["crc"])+" 454142",
   "SWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0",
   "SWST|UPTIME|2203.28 4051.27",
   "SWST|BOOT_ID|c06478b8-eaab-4f74-875d-071783afd300",
   *["NATIVE_PARENT|"+path+"|"+sid for path,sid in plan["parents"].items()],
   "NATIVE_MODULE|757|213:1582|a43fc1bb895b0e6c13480c8f4b875a58  -",
   "NATIVE_MAP|1000-2000 r-xp 00000000 fd:11 9457 "+rt.TARGET,
   "NATIVE_MANAGER|64785:999:1:1234:755:1018:3015:1|"+"a"*32+"  -|123 1234",
  ])+"\n").encode()
  load_patch=patch.object(boot,"load",return_value=plan)
  load_patch.start();self.addCleanup(load_patch.stop)
  entry_patch=patch.object(boot,"entry",return_value="VERIFY")
  entry_patch.start();self.addCleanup(entry_patch.stop)
  sid="64785:777:9000:454142:755:1018:3015:2"
  before=original.replace(b"64785:9457:1433953535:454142:755:1018:3015:1",sid.encode())
  before=before.replace(plan["original"]["md5"].encode(),plan["candidate"]["md5"].encode())
  before=before.replace(str(plan["original"]["crc"]).encode(),str(plan["candidate"]["crc"]).encode())
  after=before.replace(b"fd:11 9457",b"fd:11 777").replace(b"2203.28 4051.27",b"70.00 60.00").replace(b"c06478b8-eaab-4f74-875d-071783afd300",b"d06478b8-eaab-4f74-875d-071783afd300").replace(b"757|213:1582",b"760|214:1600")
  manager=rt.typed_records(original,b"NATIVE_MANAGER|")[0]
  v=dict(kind="C",identity=sid,manager=manager,previously_loaded=dict(identity="64785:9457:1433953535:454142:755:1018:3015:1",process=rt.typed_records(original,b"NATIVE_MODULE|")[0]))
  boot.check_output(0,before,v,pre=True)
  old_deleted=before.replace(plan["target"].encode(),(plan["stage"]+" (deleted)").encode())
  boot.check_output(0,old_deleted,v,pre=True)
  with self.assertRaises(ValueError):boot.check_output(0,after.replace(plan["target"].encode(),(plan["stage"]+" (deleted)").encode()),v)
  with self.assertRaises(ValueError):boot.check_output(0,after.replace(b"fd:11 777",b"fd:11 778"),v)
  with self.assertRaises(ValueError):boot.check_output(0,after.replace(b"ro,noatime",b"rw,noatime"),v)
  sent=[]
  class Session:
   def __init__(self,*a,**kw):self.checks=0
   def observe_prompt(self,**kw):pass
   def identify(self):pass
   def execute(self,cmd):
    if "SWST|META" in cmd:
     self.checks+=1
     return 0,before if self.checks==1 else after
    return 0,f"OCLINK|VERIFY|C|candidate|{sid}|ro,noatime|writes=0\n".encode()
   def _send(self,data,**kw):sent.append(data)
   def _read(self,*a,**kw):return b"data"
  class Gate:
   def __init__(self):self.events=iter(["login","password","shell"]);self.raw=bytearray()
   def feed(self,chunk):return next(self.events)
  class Video:
   def __init__(self,*a):pass
   def start(self):pass
   def stop(self):pass
  class Lock:
   def __init__(self,**kw):pass
   def __enter__(self):return self
   def __exit__(self,*a):pass
  tick=iter(range(0,10000,3))
  with tempfile.TemporaryDirectory() as d:
   args=SimpleNamespace(bundle=Path(d)/"bundle",credentials=None,camera_index=0,owner="t6",solicit_prompt=True)
   with patch.object(boot,"validate_live_dependencies"),patch.object(stock,"Session",Session),patch.object(stock,"AdapterLock",Lock),patch.object(stock,"Video",Video),patch.object(stock,"BootGate",Gate),patch.object(stock,"open_adapter",return_value=SimpleNamespace(close=lambda:None)),patch.object(stock,"private_credentials",return_value=(b"test-user",b"test-password")),patch.object(boot,"time",SimpleNamespace(monotonic=lambda:next(tick))):
    self.assertEqual(boot.observe(args,v,plan),0)
   self.assertEqual(sent,[stock.REBOOT,b"test-user",b"test-password"])
   m=json.loads((args.bundle/"manifest.json").read_text())
   self.assertEqual(m["outcome"],"native_C_startup_access_mapping_RO_verified")
   self.assertTrue(m["port_closed"])
if __name__=="__main__":unittest.main()
