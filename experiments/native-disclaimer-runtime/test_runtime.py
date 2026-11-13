import copy,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
import runtime as r
import observe
PROFILE=r.ROOT/"runs/t12-native-host-20261113T170401.731894Z/candidate/profile.json"
class RuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=r.profile(PROFILE);cls.tmp=tempfile.TemporaryDirectory(prefix="native-runtime-host-",dir=r.ROOT/"runs")
  cls.root=Path(cls.tmp.name)
  cls.b=dict(initial=r.INITIAL,parents={"/jci":"64785:10:775:1018:3015","/jci/mmui":"64785:11:755:1018:3015","/jci/mmui/uia":"64785:12:755:1018:3015"},module="754|210:1576|a43fc1bb895b0e6c13480c8f4b875a58  -",manager="64785:5276:1433953355:196469:755:1018:3015:1|8ce49f8bc9833c48a3a89e5c4c683ddc  -|552157721 196469")
  cls.ctx=dict(nonce="1"*32,registry="disabled",pending="ENABLE",phase="prepared",goal="O",initial=r.INITIAL,directory="45826:1",original="45826:2:1433953535:454142:755:1018:3015:1",candidate="45826:3:100:454142:755:1018:3015:1",cstage="none",ostage="none")
  d=cls.p["delta"]
  cls.ds=dict(schema=1,kind="cmu_bench_data_stage",nonce="2"*32,path="/tmp/cmu-bench-payload-"+("2"*32)+"/p",bytes=d["bytes"],md5=d["md5"],cksum=d["crc"],host_sha256=d["sha256"],file_id="1:2:9:12288:600:0:0:1",dir_id="1:1:9:700:0:0:2",observed=True,execution=False)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_candidate_delta_and_actual_dd_recipe(self):
  body=r.prepare(self.p,self.b,"1"*32,self.ds);r.checked_body(body)
  start=body.index('{\n dd if="$_delta"');end=body.index('status FROZEN_CANDIDATE_BYTES',start)
  d=self.root/"recipe";d.mkdir();(d/"original").write_bytes(r.ORIGINAL.read_bytes())
  script='_d='+str(d)+'\n_delta='+self.p["delta"]["path"]+'\n'+body[start:end]
  result=subprocess.run(["/bin/sh"],input=script.encode(),capture_output=True,timeout=5)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual((d/"candidate").read_bytes(),Path(self.p["candidate_path"]).read_bytes())
 def test_native_recovery_apply_and_source_guards(self):
  rec=r.recovery(self.p,self.b,self.ctx);ap=r.apply_bound(self.p,self.b,self.ctx,rec,dict(identity="45826:4:100:"+str(len(rec.encode()))+":600:0:0:1"))
  for body in [rec,ap]:
   self.assertLessEqual(r.checked_body(body)["bytes"],16384)
   self.assertNotIn("systemApp.js",body);self.assertNotIn("WARM1",body)
   self.assertIn(r.TARGET,body);self.assertIn("NATIVE1",body)
  self.assertIn('case $_mode in VERIFY|RESTORE_ORIGINAL)',rec)
  self.assertLess(ap.index('/bin/sh "$_code" VERIFY'),ap.index('_mount_request rw || die apply_rw'))
  self.assertLess(ap.index('die original_stage_changed_before_publication'),ap.index('mv -f "$_cs" "$_src"'))
  self.assertIn('NATIVE_CANDIDATE_BOOT_BIND',ap)
 def test_paired_ro_after_flush_failure(self):
  base=r.legacy();finish=base.FINISH
  script='''emit() { printf '%s\\n' "$*"; }
_flush() { return 1; }
_mount_request() { printf 'REQUEST_%s\\n' "$1";return 0; }
_root_mode() { return 0; }
_read_record() { return 0; }
_backups() { return 0; }
_classify() { _kind=C; }
'''+finish+'''
_rw_requested=1
_final_verified=1
_root_action=APPLY_C
_finish_kind=C
_arm_root_finish
exit 0
'''
  p=subprocess.run(["/bin/sh"],input=script.encode(),capture_output=True)
  self.assertEqual(p.returncode,1);self.assertIn(b"REQUEST_ro",p.stdout);self.assertNotIn(b"CANDIDATE_BOOT_BIND",p.stdout)
 def test_strict_native_journal_and_shell_parser(self):
  raw=r.record(self.ctx);self.assertEqual(r.parse_journal(raw,self.p),self.ctx)
  for bad in [raw+b"x",raw.replace(b"NATIVE1",b"WARM1"),raw.replace(b"goal=O",b"goal=$(id)"),raw.replace(b"registry=disabled",b"registry=enabled")]:
   with self.assertRaises(ValueError):r.parse_journal(bad,self.p)
  rec=r.recovery(self.p,self.b,self.ctx);a=rec.index("awk -F'|' -v warm=\"$_run\" '")+len("awk -F'|' -v warm=\"$_run\" '");z=rec.index("' \"$_d/journal\"",a)
  for data,rc in [(raw,0),(raw.replace(b"goal=O",b"goal=$(id)"),1)]:
   p=subprocess.run(["/usr/bin/awk","-F|","-v","warm="+("1"*32),rec[a:z]],input=data,capture_output=True);self.assertEqual(p.returncode,rc,p.stderr)
 def sample(self,sid,kind,mi=None,deleted=False,prefix=False):
  w=r.O if kind=="O" else self.p["candidate"];mi=mi or sid
  rows=[b"noise SWST|META|"+sid.encode(),b"SWST|HASH|"+(w["md5"]+"  -").encode(),b"SWST|CRC|"+str(w["crc"]).encode()+b" 454142",b"SWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0",b"SWST|UPTIME|30.5 10.0",b"SWST|BOOT_ID|2856eca4-ba2a-405b-a253-1fb9a5f6eecf"]
  rows+=[("NATIVE_PARENT|"+k+"|"+v).encode() for k,v in self.b["parents"].items()]
  rows+=[b"NATIVE_MODULE|754|210:1576|a43fc1bb895b0e6c13480c8f4b875a58  -",("NATIVE_MAP|1000-2000 r-xp 00000000 fd:11 "+mi.split(":")[1]+" "+r.TARGET+(" (deleted)" if deleted else "")).encode(),("NATIVE_MANAGER|"+self.b["manager"]).encode()]
  return b"\r\n".join(rows)+b"\r\n"
 def test_disk_loaded_phase_and_identity_conflicts(self):
  cid="64785:99:100:454142:755:1018:3015:1"
  pre=self.sample(cid,"C",r.INITIAL,True)
  v=r.observation(0,pre,self.p,"C",cid,mapped_identity=r.INITIAL,deleted=None,process=self.b["module"],parents=self.b["parents"]);self.assertEqual(v["kind"],"C")
  with self.assertRaises(r.IdentityConflict):r.observation(0,pre,self.p,"C",cid)
  post=self.sample(cid,"C");self.assertEqual(r.observation(0,post,self.p,"C",cid)["META"],cid)
  with self.assertRaises(r.IdentityConflict):r.observation(0,post.replace(b"64785:99:",b"64785:100:"),self.p,"C",cid)
  with self.assertRaises(ValueError):r.observation(0,post+b"SWST|META|partial\n",self.p,"C",cid)
 def test_actual_data_descriptor_and_typed_entry(self):
  data=b"safe fixture\n";f=r.delivery().fingerprint(data);run="3"*32
  raw=("logger DELIVERY "+run+" FILE|1:2:9:"+str(len(data))+":600:0:0:1\nDELIVERY "+run+" DIR|1:1:9:700:0:0:2\nDELIVERY "+run+" DATA|"+str(len(data))+"|"+f["md5"]+"|"+str(f["cksum"])+"\nDELIVERY "+run+" END|STAGE|0|execution=0\n").encode()
  desc=r.stage_descriptor(raw,data,run);entry=r.execute_entry(dict(descriptor=desc))
  subprocess.run(["/bin/sh","-n"],input=entry.encode(),check=True)
  self.assertIn('/bin/sh "$q" </dev/null',entry);self.assertNotIn("grep",entry)
  with self.assertRaises(ValueError):r.stage_descriptor(raw+raw,data,run)
 def test_packet_unbound_and_live_refused(self):
  out=self.root/"packet";v=r.packet(PROFILE,out,"4"*32)
  for k in ["baseline","retained","applied","recovery_code_identity","restored_original"]:self.assertIsNone(v[k])
  self.assertFalse(v["live_authority"])
  with self.assertRaises(ValueError):observe.approved(out/"packet.json")
  with self.assertRaises(ValueError):r.prepare(self.p,None,"1"*32,self.ds)
 def test_unknown_core_cannot_bind(self):
  b=self.root/"unknown";b.mkdir();(b/"manifest.json").write_text(json.dumps(dict(outcome="unknown",port_closed=True)))
  with self.assertRaises(ValueError):r.core_output(b)
 def test_pending_and_exact_verify_records(self):
  sid="64785:99:100:454142:755:1018:3015:1"
  raw=("log NREC "+self.ctx["nonce"]+" END mode=VERIFY rc=0 kind=C registry=enabled pending=none phase=candidate_verified writes=0 recovery_ready=1 current_id="+sid+"\n").encode()
  self.assertEqual(r.verified_output(0,raw,self.ctx,"C",sid),sid)
  with self.assertRaises(r.IdentityConflict):r.verified_output(0,raw,self.ctx,"C",sid.replace(":99:",":98:"))
  with self.assertRaises(ValueError):r.verified_output(0,raw.replace(b"pending=none",b"pending=ENABLE"),self.ctx,"C",sid)
if __name__=="__main__":unittest.main()
