import importlib.util,json,os,re,shlex,shutil,subprocess,sys,unittest
from pathlib import Path
import prepare,root_review

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('old_warm_fixture',prepare.ROOT/'experiments/disclaimer-warm-roundtrip/test_warm.py')
warm_fixture=importlib.util.module_from_spec(spec)
previous=sys.modules.get('prepare');sys.modules.pop('prepare',None)
sys.path.insert(0,str(prepare.ROOT/'experiments/disclaimer-warm-roundtrip'));spec.loader.exec_module(warm_fixture);sys.path.pop(0)
if previous is not None:sys.modules['prepare']=previous
NONCE='1234567890abcdef1234567890abcdef'

class RootBoundaryTests(unittest.TestCase):
 def fixture(self,**faults):
  h=warm_fixture.WarmTests();self.addCleanup(h.doCleanups)
  lab,src,O,_,env=h.fixture(**faults);persist=lab/'tmp/mnt/data_persist';d=persist/('cmu-bench-startup-'+NONCE);d.mkdir(mode=0o700)
  f=prepare.warm.frozen_inputs();C=(prepare.ROOT/f['private_candidate']).read_bytes()
  owners=json.loads((lab/'owners.json').read_text())
  for name,data,mt in [('original',O,1433953097),('candidate',C,13392)]:
   p=d/name;p.write_bytes(data);p.chmod(0o755);os.utime(p,(mt,mt));owners[str(p.stat().st_ino)]=[1018,3015]
  (lab/'owners.json').write_text(json.dumps(owners))
  # A contract-fake fault only: alter the retained root O stage after its
  # staged-intent commit, before the new publication prerequisite checks.
  for tool in (lab/'bin').iterdir():
   code=tool.read_text()
   anchor=" if name=='mv' and b==src and a.name.endswith('-candidate'):"
   inject=""" if name=='mv' and b.name=='journal' and os.environ.get('O_STAGE_FAULT') and 'phase=staged' in b.read_text():
  stage=next(src.parent.glob('.systemApp.js.cmu-bench-*-original'))
  if os.environ['O_STAGE_FAULT']=='missing':stage.unlink()
  else:stage.write_bytes(b'unknown later rollback stage')
  log('injected_O_stage',fault=os.environ['O_STAGE_FAULT'])
"""
   assert code.count(anchor)==1;tool.write_text(code.replace(anchor,inject+anchor))

  def ident(p,dev):
   s=p.stat();return f'{dev}:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015:1'
  ctx=dict(nonce=NONCE,registry='disabled',pending='ENABLE',phase='prepared',goal='O',initial=ident(src,64785),directory='45826:'+str(d.stat().st_ino),original=ident(d/'original',45826),candidate=ident(d/'candidate',45826),cstage='none',ostage='none')
  (d/'journal').write_text('WARM1|'+NONCE+'|'+'|'.join(k+'='+ctx[k] for k in prepare.old.KEYS)+'\n');(d/'journal').chmod(0o600)
  def translate(text):
   mapping={'/tmp/mnt/data_persist':str(persist),'/tmp/mnt':str(lab/'tmp/mnt'),'/tmp':str(lab/'tmp'),'/jci':str(lab/'jci'),'/proc/mounts':str(lab/'mounts')}
   text=re.sub('|'.join(re.escape(x) for x in sorted(mapping,key=len,reverse=True)),lambda m:mapping[m[0]],text)
   return text.replace('_bb=/bin/busybox','_bb='+shlex.quote(str(lab/'bin/busybox'))).replace('_sync=/bin/sync','_sync='+shlex.quote(str(lab/'bin/sync')))
  recovery=translate(root_review.persistent_recovery(ctx));code=d/'recovery.sh';code.write_text(recovery);code.chmod(0o600)
  apply=translate(root_review.apply_candidate(ctx,recovery))
  return h,lab,src,O,C,d,ctx,code,apply,env
 def execute(self,text,env):return subprocess.run(['/bin/sh'],input=text,text=True,capture_output=True,env=env,timeout=45)
 def tool(self,code,env,mode='VERIFY'):return subprocess.run(['/bin/sh',str(code),mode],env=env,text=True,capture_output=True,timeout=45)
 def snapshot(self,lab):
  return {str(p.relative_to(lab)):(p.read_bytes(),p.stat().st_ino,p.stat().st_mode&0o777,int(p.stat().st_mtime)) for p in lab.rglob('*') if p.is_file() and p.name!='events.jsonl'}
 def test_apply_requires_persistent_recovery_then_independent_undo_O_RO(self):
  h,lab,src,O,C,d,ctx,code,apply,env=self.fixture();start=src.stat().st_ino
  r=self.execute(apply,env);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertEqual(src.read_bytes(),C);self.assertIn('/dev/ffx01p1 / relfs ro,noatime',(lab/'mounts').read_text())
  self.assertIn('RECOVERY_READY before_publication=1 independent=1',r.stdout)
  self.assertEqual(r.stdout.count('CANDIDATE_BOOT_BIND|'+NONCE+'|C|'),1)
  events=h.events(lab);moves=[e for e in events if e['kind']=='mv' and e['target']==str(src)];self.assertEqual(len(moves),1)
  self.assertLess(r.stdout.index('RECOVERY_READY'),r.stdout.index('PUBLISH_REAL_C'))
  before=self.snapshot(lab);v=self.tool(code,env);self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertEqual(self.snapshot(lab),before)
  old=src.stat().st_ino;r=self.tool(code,env,'RESTORE_ORIGINAL')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);h.assert_O_RO(lab,src,O)
  self.assertNotEqual(src.stat().st_ino,old);self.assertIn('ROOT_FINAL mode=RESTORE_ORIGINAL rc=0',r.stdout)
  before=self.snapshot(lab);v=self.tool(code,env);self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertEqual(self.snapshot(lab),before)
  self.assertIn('registry=disabled|pending=none',(d/'journal').read_text())
  print('ROOT_FAKE_APPLY_UNDO_PASS persistent_before_C=True undo_separate_process=True O_RO=True')
 def test_missing_recovery_or_bad_journal_refuses_before_RW(self):
  for case in ('code','journal'):
   with self.subTest(case=case):
    h,lab,src,O,C,d,ctx,code,apply,env=self.fixture()
    if case=='code':code.write_bytes(b'changed code')
    else:(d/'journal').write_bytes(b'$(touch /tmp/PWN)\n')
    before=self.snapshot(lab);r=self.execute(apply,env)
    self.assertNotEqual(r.returncode,0);self.assertEqual(self.snapshot(lab),before)
    self.assertFalse([e for e in h.events(lab) if e['kind']=='mount']);self.assertEqual(src.read_bytes(),O)
 def test_OTHER_after_publication_is_preserved_and_RO_still_attempted(self):
  h,lab,src,O,C,d,ctx,code,apply,env=self.fixture(AFTER_C='source')
  r=self.execute(apply,env);self.assertNotEqual(r.returncode,0)
  self.assertNotEqual(src.read_bytes(),O);self.assertNotEqual(src.read_bytes(),C)
  self.assertIn('/dev/ffx01p1 / relfs ro,noatime',(lab/'mounts').read_text())
  self.assertNotIn('CANDIDATE_BOOT_BIND|',r.stdout)
  self.assertEqual([e['argv'][5] for e in h.events(lab) if e['kind']=='mount'][-1],'remount,ro,noatime')
 def test_changed_or_missing_Ostage_refuses_publication_and_RO(self):
  for fault in ('changed','missing'):
   with self.subTest(fault=fault):
    h,lab,src,O,C,d,ctx,code,apply,env=self.fixture(O_STAGE_FAULT=fault)
    r=self.execute(apply,env);self.assertNotEqual(r.returncode,0)
    self.assertEqual(src.read_bytes(),O)
    self.assertFalse([e for e in h.events(lab) if e['kind']=='mv' and e['target']==str(src)])
    self.assertNotIn('CANDIDATE_BOOT_BIND|',r.stdout)
    self.assertIn('/dev/ffx01p1 / relfs ro,noatime',(lab/'mounts').read_text())
    self.assertEqual([e['argv'][5] for e in h.events(lab) if e['kind']=='mount'][-1],'remount,ro,noatime')
    if fault=='changed':
     stage=next(src.parent.glob('.systemApp.js.cmu-bench-*-original'))
     self.assertEqual(stage.read_bytes(),b'unknown later rollback stage')
 def test_undo_postflush_failure_cannot_skip_paired_RO(self):
  h,lab,src,O,C,d,ctx,code,apply,env=self.fixture()
  a=self.execute(apply,env);self.assertEqual(a.returncode,0,a.stdout+a.stderr)
  env['SYNC_FAIL_AT']='4'
  r=self.tool(code,env,'RESTORE_ORIGINAL');self.assertNotEqual(r.returncode,0)
  h.assert_O_RO(lab,src,O);self.assertIn('ROOT_FINAL mode=RESTORE_ORIGINAL rc=1',r.stdout)
  self.assertEqual([e['argv'][5] for e in h.events(lab) if e['kind']=='mount'][-1],'remount,ro,noatime')

if __name__=='__main__':unittest.main(verbosity=2)
