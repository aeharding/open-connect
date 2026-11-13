from pathlib import Path
import json,os,re,shlex,subprocess,sys,tempfile,unittest
import prepare

HERE=Path(__file__).resolve().parent
NONCE='1234567890abcdef1234567890abcdef'
# Contract fakes only. No native mount/sync/chown; every actual file operation is LAB-confined.
SHIM=r'''
import hashlib,json,os,re,stat,subprocess,sys
from pathlib import Path
lab=Path(os.environ['WARM_LAB']).resolve();name=Path(sys.argv[0]).name
src=lab/'jci/gui/apps/system/js/systemApp.js';persist=lab/'tmp/mnt/data_persist'
owners=lab/'owners.json';mounts=lab/'mounts';events=lab/'events.jsonl'
def log(kind,**data):
 with events.open('a') as f:f.write(json.dumps(dict(kind=kind,**data))+'\n')
def safe(value):
 p=Path(value).absolute()
 if not p.is_relative_to(lab):raise SystemExit('HOST GUARD outside LAB: '+str(p))
 return p
def own(p):
 return json.loads(owners.read_text()).get(str(p.lstat().st_ino),[0,0])
def setown(p,pair):
 values=json.loads(owners.read_text());values[str(p.lstat().st_ino)]=pair;owners.write_text(json.dumps(values))
def rows(mode):
 mounts.write_text('rootfs / rootfs rw 0 0\n/dev/ffx01p1 / relfs '+mode+',noatime 0 0\n/dev/mmcblk0p2 '+str(persist)+' relfs rw,noatime 0 0\n')
if name=='stat':
 p=safe(sys.argv[3]);s=p.lstat();image=p.is_file();source=p.is_relative_to(lab/'jci')
 pair=own(p) if image else ([1018,3015] if source else [0,0])
 v={'F':'directory' if stat.S_ISDIR(s.st_mode) else 'regular file','a':format(stat.S_IMODE(s.st_mode),'o'),
 'u':str(pair[0]),'g':str(pair[1]),'h':str(s.st_nlink),'d':'64785' if source else '45826',
 'i':str(s.st_ino),'s':str(s.st_size),'Y':str(int(s.st_mtime))}
 print(re.sub(r'%([FaughdisY])',lambda m:v[m[1]],sys.argv[2]))
elif name=='readlink':print(safe(sys.argv[-1]).resolve(strict=True))
elif name=='md5sum':
 data=safe(sys.argv[1]).read_bytes() if len(sys.argv)>1 else sys.stdin.buffer.read()
 print(hashlib.md5(data).hexdigest()+'  '+(sys.argv[1] if len(sys.argv)>1 else '-'))
elif name=='id':print('0')
elif name=='df':
 p=sys.argv[1];device='/dev/ffx01p1' if p=='/' else '/dev/mmcblk0p2'
 print('Filesystem 1K-blocks Used Available Use% Mounted on')
 print(device+' 100000 1000 99000 1% '+p)
elif name=='busybox':
 if sys.argv[1]=='timeout':
  args=sys.argv[6:]
  command=safe(args[0]);os.execv(str(command),args)
 elif sys.argv[1]=='mount':
  args=sys.argv[2:];log('mount',argv=args)
  if args[:5]!=['-i','-n','-t','relfs','-o'] or args[-2:]!=['/dev/ffx01p1','/']:raise SystemExit(9)
  mode=args[5].split(',')[1]
  if os.environ.get('UNSUPPORTED_FLAGS')=='1':raise SystemExit(1)
  if mode=='ro' and os.environ.get('RO_FAIL')=='1':raise SystemExit(1)
  if not(mode=='rw' and os.environ.get('FALLBACK_RO')=='1'):rows(mode)
 else:raise SystemExit(9)
elif name=='sync':
 count=sum(json.loads(line)['kind']=='sync' for line in events.read_text().splitlines()) if events.exists() else 0
 log('sync',argv=sys.argv[1:],number=count+1)
 if sys.argv[1:]:raise SystemExit(9)
 if os.environ.get('SYNC_FAIL_AT')==str(count+1):raise SystemExit(1)
elif name=='chown':
 p=safe(sys.argv[2]);setown(p,list(map(int,sys.argv[1].split(':'))));log('chown',path=str(p))
elif name in ('cp','mv'):
 a=safe(sys.argv[-2]);b=safe(sys.argv[-1]);pair=own(a)
 result=subprocess.run(['/bin/'+name]+sys.argv[1:]);
 if result.returncode:raise SystemExit(result.returncode)
 setown(b,pair);log(name,source=str(a),target=str(b))
 if name=='mv' and b==src and a.name.endswith('-candidate'):
  fault=os.environ.get('AFTER_C','')
  if fault=='source':src.write_bytes(src.read_bytes().replace(b'Copyright',b'CopyRight',1));log('injected_OTHER')
  elif fault=='journal':
   journal=next(persist.glob('cmu-bench-warm-*/journal'));journal.write_bytes(b'bad control data\n');log('injected_bad_journal')
  elif fault=='original':
   original=next(persist.glob('cmu-bench-warm-*/original'));tmp=src.parent/'.host-original'
   subprocess.check_call(['/bin/cp','-p',str(original),str(tmp)]);setown(tmp,own(original));os.replace(tmp,src)
   log('injected_O',inode=src.stat().st_ino)
 if name=='mv' and b==src and a.name.endswith('-original') and os.environ.get('AFTER_O')=='stage_conflict':
  unknown=a.with_name(a.name[:-len('-original')]+'-candidate');unknown.write_bytes(b'unknown later stage bytes\n');unknown.chmod(0o600)
  log('injected_stage_conflict',path=str(unknown))
elif name=='rm':
 for value in sys.argv[1:]:safe(value).unlink();log('rm',path=value)
else:raise SystemExit('Unexpected fake '+name)
'''

class WarmTests(unittest.TestCase):
 def fixture(self,**faults):
  tmp=tempfile.TemporaryDirectory(prefix='t12-warm-review-',dir=prepare.ROOT/'runs');self.addCleanup(tmp.cleanup)
  lab=Path(tmp.name).resolve();persist=lab/'tmp/mnt/data_persist';persist.mkdir(parents=True)
  (lab/'tmp').chmod(0o755);(lab/'tmp/mnt').chmod(0o755);persist.chmod(0o755)
  parent=lab/'jci/gui/apps/system/js';parent.mkdir(parents=True)
  for part,mode in [('jci',0o775),('jci/gui',0o755),('jci/gui/apps',0o775),('jci/gui/apps/system',0o755),('jci/gui/apps/system/js',0o755)]:
   (lab/part).chmod(mode)
  freeze=prepare.frozen_inputs();data=(prepare.ROOT/freeze['original']['path']).read_bytes()
  src=parent/'systemApp.js';src.write_bytes(data);src.chmod(0o755);os.utime(src,(1433953097,1433953097))
  (lab/'owners.json').write_text(json.dumps({str(src.stat().st_ino):[1018,3015]}))
  (lab/'mounts').write_text('rootfs / rootfs rw 0 0\n/dev/ffx01p1 / relfs ro,noatime 0 0\n/dev/mmcblk0p2 '+str(persist)+' relfs rw,noatime 0 0\n')
  tools=lab/'bin';tools.mkdir()
  for name in ('stat','readlink','md5sum','id','df','busybox','sync','chown','cp','mv','rm'):
   p=tools/name;p.write_text('#!'+sys.executable+'\n'+SHIM);p.chmod(0o755)
  script=prepare.render(NONCE)
  mapping={'/tmp/mnt/data_persist':str(persist),'/tmp/mnt':str(lab/'tmp/mnt'),'/tmp':str(lab/'tmp'),'/jci':str(lab/'jci'),'/proc/mounts':str(lab/'mounts')}
  script=re.sub('|'.join(re.escape(p) for p in sorted(mapping,key=len,reverse=True)),lambda m:mapping[m[0]],script)
  script=script.replace('_bb=/bin/busybox','_bb='+shlex.quote(str(tools/'busybox')))
  script=script.replace('_sync=/bin/sync','_sync='+shlex.quote(str(tools/'sync')))
  initial=f'64785:{src.stat().st_ino}:1433953097:94058:755:1018:3015:1'
  script=re.sub(r'^_expected_initial=.*$', '_expected_initial='+initial,script,flags=re.M)
  self.assertNotIn('_bb=/bin/busybox',script);self.assertNotIn('_sync=/bin/sync',script)
  env=dict(os.environ,PATH=str(tools)+':/usr/bin:/bin',WARM_LAB=str(lab),**{k:str(v) for k,v in faults.items()})
  return lab,src,data,script,env
 def execute(self,script,env):
  return subprocess.run(['/bin/sh'],input=script,text=True,capture_output=True,env=env,timeout=50)
 def events(self,lab):
  p=lab/'events.jsonl';return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []
 def assert_O_RO(self,lab,src,original):
  self.assertEqual(src.read_bytes(),original);self.assertEqual(src.stat().st_mode&0o777,0o755)
  self.assertEqual(int(src.stat().st_mtime),1433953097)
  self.assertIn('/dev/ffx01p1 / relfs ro,noatime 0 0',(lab/'mounts').read_text())
  self.assertEqual(json.loads((lab/'owners.json').read_text())[str(src.stat().st_ino)],[1018,3015])
 def test_review_only_syntax_wire_and_exact_argv(self):
  script=prepare.render(NONCE)
  parsed=subprocess.run(['/bin/sh','-n'],input=script,text=True,capture_output=True,timeout=5)
  self.assertEqual(parsed.returncode,0,parsed.stderr)
  record=prepare.plan(NONCE,script)
  self.assertFalse(record['opens_uart']);self.assertFalse(record['operator_handoff_authorized'])
  self.assertEqual(record['rw_argv'],['/bin/busybox','mount','-i','-n','-t','relfs','-o','remount,rw,noatime','/dev/ffx01p1','/'])
  self.assertEqual(record['sync_argv'],['/bin/sync']);self.assertLessEqual(record['sample_wire_bytes'],32768)
  self.assertLessEqual(record['max_physical_line'],600)
  with self.assertRaises(ValueError):prepare.render('../not-a-nonce')
 def test_normal_roundtrip_restores_stated_metadata_records_new_inode_and_retains_evidence(self):
  lab,src,original,script,env=self.fixture();initial=src.stat().st_ino
  result=self.execute(script,env);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assert_O_RO(lab,src,original);self.assertNotEqual(src.stat().st_ino,initial)
  retained=next((lab/'tmp/mnt/data_persist').glob('cmu-bench-warm-*'))
  self.assertEqual((retained/'original').read_bytes(),original)
  self.assertIn('registry=disabled|pending=none',(retained/'journal').read_text())
  self.assertFalse(list(src.parent.glob('.systemApp.js.cmu-bench-*')))
  events=self.events(lab);mounts=[e for e in events if e['kind']=='mount'];syncs=[e for e in events if e['kind']=='sync']
  self.assertEqual([e['argv'][5] for e in mounts],['remount,rw,noatime','remount,ro,noatime'])
  self.assertEqual(len(syncs),2);self.assertTrue(all(e['argv']==[] for e in syncs))
  self.assertLess(events.index(syncs[0]),events.index(mounts[0]));self.assertLess(events.index(syncs[1]),events.index(mounts[1]))
  self.assertIn('inode=replaced',result.stdout);self.assertIn('END outcome=warm_roundtrip_pass',result.stdout)
 def test_rw_fallback_and_unsupported_switches_refuse_before_root_staging(self):
  for fault in ('FALLBACK_RO','UNSUPPORTED_FLAGS'):
   with self.subTest(fault=fault):
    lab,src,original,script,env=self.fixture(**{fault:1});initial=src.stat().st_ino
    result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
    self.assert_O_RO(lab,src,original);self.assertEqual(src.stat().st_ino,initial)
    events=self.events(lab);mounts=[e for e in events if e['kind']=='mount']
    self.assertEqual(len(mounts),2);self.assertTrue(all(e['argv'][:2]==['-i','-n'] for e in mounts))
    self.assertFalse([e for e in events if e['kind']=='cp' and e['target'].startswith(str(src.parent))])
 def test_known_candidate_failure_restores_O_and_O_already_present_is_not_rewritten(self):
  for fault in ('known_C','already_O'):
   with self.subTest(fault=fault):
    lab,src,original,script,env=self.fixture(**({'AFTER_C':'original'} if fault=='already_O' else {}))
    if fault=='known_C':script=script.replace('# CANDIDATE_VERIFIED_CHECKPOINT','die injected_after_known_C')
    result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
    self.assert_O_RO(lab,src,original)
    events=self.events(lab)
    if fault=='already_O':
     injected=next(e for e in events if e['kind']=='injected_O');self.assertEqual(src.stat().st_ino,injected['inode'])
     self.assertIn('COMPLETE no_rewrite=1',result.stdout)
    else:self.assertIn('COMPLETE no_rewrite=0',result.stdout)
    self.assertEqual([e['argv'][5] for e in events if e['kind']=='mount'][-1],'remount,ro,noatime')
 def test_OTHER_or_bad_journal_refusal_cannot_skip_RO(self):
  for fault in ('source','journal'):
   with self.subTest(fault=fault):
    lab,src,original,script,env=self.fixture(AFTER_C=fault)
    result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
    self.assertNotEqual(src.read_bytes(),original)
    self.assertIn('/dev/ffx01p1 / relfs ro,noatime 0 0',(lab/'mounts').read_text())
    events=self.events(lab);moves=[e for e in events if e['kind']=='mv' and e['target']==str(src)]
    self.assertEqual(len(moves),1)
    self.assertEqual([e['argv'][5] for e in events if e['kind']=='mount'][-1],'remount,ro,noatime')
    retained=next((lab/'tmp/mnt/data_persist').glob('cmu-bench-warm-*'));self.assertTrue((retained/'original').exists())
 def test_sync_failure_refuses_before_mutation_or_still_attempts_RO_after_restore(self):
  for number in (1,2):
   with self.subTest(number=number):
    lab,src,original,script,env=self.fixture(SYNC_FAIL_AT=number);initial=src.stat().st_ino
    result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
    self.assert_O_RO(lab,src,original)
    mounts=[e for e in self.events(lab) if e['kind']=='mount']
    if number==1:self.assertEqual(mounts,[]);self.assertEqual(src.stat().st_ino,initial)
    else:self.assertEqual(mounts[-1]['argv'][5],'remount,ro,noatime')
 def test_stage_cleanup_refusal_still_flushes_verified_original_then_attempts_RO(self):
  lab,src,original,script,env=self.fixture(AFTER_O='stage_conflict')
  result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
  self.assert_O_RO(lab,src,original)
  events=self.events(lab);syncs=[e for e in events if e['kind']=='sync'];mounts=[e for e in events if e['kind']=='mount']
  self.assertEqual(len(syncs),2);self.assertEqual(mounts[-1]['argv'][5],'remount,ro,noatime')
  self.assertLess(events.index(syncs[1]),events.index(mounts[-1]))
  conflict=next(e for e in events if e['kind']=='injected_stage_conflict')
  self.assertEqual(Path(conflict['path']).read_bytes(),b'unknown later stage bytes\n')
 def test_failed_RO_is_explicit_unresolved_even_when_original_restored(self):
  lab,src,original,script,env=self.fixture(RO_FAIL=1)
  result=self.execute(script,env);self.assertNotEqual(result.returncode,0)
  self.assertEqual(src.read_bytes(),original)
  self.assertIn('/dev/ffx01p1 / relfs rw,noatime 0 0',(lab/'mounts').read_text())
  self.assertIn('RO_FINAL request_rc=1 physical_row_rc=1',result.stdout)
  self.assertIn('outcome=failed_or_unresolved',result.stdout)

if __name__=='__main__':unittest.main(verbosity=2)
