import importlib.util,json,os,re,shutil,subprocess,sys,unittest
from pathlib import Path
import prepare

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('borrowed_fixture',prepare.ROOT/'experiments/disclaimer-recovery-inspection/test_inspection.py')
fixture=importlib.util.module_from_spec(spec)
# The old fixture imports its own prepare module; bind explicitly only while loading.
previous=sys.modules.get('prepare');sys.modules.pop('prepare',None)
sys.path.insert(0,str(prepare.ROOT/'experiments/disclaimer-recovery-inspection'))
spec.loader.exec_module(fixture)
sys.path.pop(0)
if previous is not None:sys.modules['prepare']=previous
NONCE='1234567890abcdef1234567890abcdef'

class PersistentTests(unittest.TestCase):
 def setup_copy(self):
  helper=fixture.InspectionTests();self.addCleanup(helper.doCleanups)
  lab,d,unused,original,candidate,ctx,_,mount_rows,env=helper.fixture('C',('enabled','none','candidate_verified'))
  renamed=d.parent/('cmu-bench-probe-'+NONCE);d.rename(renamed);d=renamed
  ctx['nonce']=NONCE
  active=d/'active';active.write_bytes(original);active.chmod(0o755);os.utime(active,(1433953097,1433953097))
  def ident(p):
   s=p.stat();return f'45826:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015:1'
  ctx['initial']=ident(active);ctx['ostage']=ctx['initial']
  stage=d/'stage';shutil.copy2(d/'candidate',stage);stage.replace(active)
  ctx['cstage']=ident(active);ctx['directory']='45826:'+str(d.stat().st_ino)
  raw=('WARM1|'+NONCE+'|'+'|'.join(k+'='+ctx[k] for k in prepare.old.KEYS)+'\n').encode()
  prepare.parse_record(raw);(d/'journal').write_bytes(raw)
  # Reuse host command contracts, adding only this copy's image names.
  for p in (lab/'bin').iterdir():
   text=p.read_text().replace("p.name in ('original','candidate')","p.name in ('original','candidate','active','restore','stage')")
   p.write_text(text)
  body=prepare.recovery(ctx)
  mapping={'/tmp/mnt/data_persist':str(lab/'tmp/mnt/data_persist'),'/tmp/mnt':str(lab/'tmp/mnt'),'/tmp':str(lab/'tmp'),'/proc/mounts':str(lab/'mounts')}
  body=re.sub('|'.join(re.escape(x) for x in sorted(mapping,key=len,reverse=True)),lambda m:mapping[m[0]],body)
  code=d/'recovery.sh';code.write_text(body);code.chmod(0o600)
  return helper,lab,d,active,code,env,original,candidate,ctx
 def run_tool(self,code,env,mode=None):
  argv=['/bin/sh',str(code)]+([] if mode is None else [mode])
  return subprocess.run(argv,capture_output=True,text=True,env=env,timeout=35)
 def test_fresh_process_C_restore_after_delivery_removed_then_O_noop(self):
  h,lab,d,active,code,env,O,C,ctx=self.setup_copy()
  delivery=lab/'tmp/delivery';delivery.mkdir();(delivery/'p').write_bytes(code.read_bytes());shutil.rmtree(delivery)
  before=h.snapshot(lab);v=self.run_tool(code,env)
  self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertEqual(h.snapshot(lab),before)
  self.assertIn('kind=C registry=enabled pending=none writes=0',v.stdout)
  old=active.stat().st_ino;r=self.run_tool(code,env,'RESTORE_ORIGINAL')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(active.read_bytes(),O)
  self.assertNotEqual(active.stat().st_ino,old);self.assertEqual(int(active.stat().st_mtime),1433953097)
  record=prepare.parse_record((d/'journal').read_bytes());self.assertEqual((record['registry'],record['pending']),('disabled','none'))
  before=h.snapshot(lab)
  for mode in (None,'RESTORE_ORIGINAL'):
   r=self.run_tool(code,env,mode);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertEqual(h.snapshot(lab),before)
  print('PERSISTENT_COPY_RESTORE_PASS separate_process=True delivery_absent=True O_exact=True disabled=True no_op=True')
 def test_bad_journal_OTHER_metadata_or_backup_preserved(self):
  for case in ('journal','OTHER','mode','backup'):
   with self.subTest(case=case):
    h,lab,d,active,code,env,O,C,ctx=self.setup_copy()
    if case=='journal':(d/'journal').write_text('$(touch '+str(lab/'PWN')+')\n')
    elif case=='OTHER':active.write_bytes(C+b'later edit')
    elif case=='mode':active.chmod(0o644)
    else:(d/'original').write_bytes(b'badbackup')
    before=h.snapshot(lab);r=self.run_tool(code,env,'RESTORE_ORIGINAL')
    self.assertNotEqual(r.returncode,0);self.assertEqual(h.snapshot(lab),before);self.assertFalse((lab/'PWN').exists())
 def test_explicit_complete_already_original_does_not_rewrite(self):
  h,lab,d,active,code,env,O,C,ctx=self.setup_copy()
  stage=d/'restore';shutil.copy2(d/'original',stage);stage.replace(active)
  s=active.stat();ctx.update(registry='enabled',pending='DISABLE',phase='restoring_O',ostage=f'45826:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015:1')
  (d/'journal').write_text('WARM1|'+NONCE+'|'+'|'.join(k+'='+ctx[k] for k in prepare.old.KEYS)+'\n')
  identity=(s.st_ino,s.st_mtime,s.st_mode);r=self.run_tool(code,env,'RESTORE_ORIGINAL')
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);s=active.stat();self.assertEqual((s.st_ino,s.st_mtime,s.st_mode),identity)
  self.assertIn('no_rewrite=1',r.stdout)
 def test_syntax_bounds_default_verify_and_frozen_patch(self):
  prepare.warm.frozen_inputs()
  h,lab,d,active,code,env,O,C,ctx=self.setup_copy()
  for text in (prepare.copy_phase1(NONCE),prepare.recovery(ctx)):
   p=subprocess.run(['/bin/sh','-n'],input=text,text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
   wire=prepare.wrap_command(text,'0'*32);self.assertLessEqual(len(wire),32768);self.assertLessEqual(max(map(len,wire.splitlines())),600)
  body=prepare.recovery(ctx);self.assertIn('_mode=${1-VERIFY}',body)
  self.assertNotRegex(body,r'^\s*(mount|sync|eval|source)\s')
  with self.assertRaises(ValueError):prepare.nonce('../../etc')

if __name__=='__main__':unittest.main(verbosity=2)
