from pathlib import Path
import json,os,re,shlex,subprocess,sys,tempfile,unittest
import journal,prepare

HERE=Path(__file__).resolve().parent
NONCE='1234567890abcdef1234567890abcdef'
SHIM=r'''
import hashlib,json,os,re,stat,subprocess,sys
from pathlib import Path
lab=Path(os.environ['RECOVERY_LAB']).resolve();name=Path(sys.argv[0]).name
trace=lab/'writes.jsonl'
def safe(v):
 p=Path(v).absolute()
 if not p.is_relative_to(lab):raise SystemExit('outside LAB')
 return p
def log(kind,args):
 with trace.open('a') as f:f.write(json.dumps([kind,args])+'\n')
if name=='stat':
 p=safe(sys.argv[3]);s=p.lstat();tree=p.is_relative_to(lab/'jci');image=tree or p.name in ('original','candidate')
 uid=1018 if image else 0;gid=3015 if image else 0
 if os.environ.get('BAD_UID')==p.name:uid=999
 v={'F':'directory' if stat.S_ISDIR(s.st_mode) else 'regular file','a':format(stat.S_IMODE(s.st_mode),'o'),
 'u':str(uid),'g':str(gid),'h':str(s.st_nlink),'d':'64785' if tree else '45826',
 'i':str(s.st_ino),'s':str(s.st_size),'Y':str(int(s.st_mtime))}
 print(re.sub(r'%([FaughdisY])',lambda m:v[m[1]],sys.argv[2]))
elif name=='readlink':print(safe(sys.argv[-1]).resolve(strict=True))
elif name=='md5sum':
 data=safe(sys.argv[1]).read_bytes() if len(sys.argv)>1 else sys.stdin.buffer.read()
 print(hashlib.md5(data).hexdigest()+'  '+(sys.argv[1] if len(sys.argv)>1 else '-'))
elif name=='id':print(0)
elif name in ('cp','mv'):
 for p in sys.argv[-2:]:safe(p)
 log(name,sys.argv[1:]);raise SystemExit(subprocess.call(['/bin/'+name]+sys.argv[1:]))
else:raise SystemExit('unexpected command '+name)
'''

class InspectionTests(unittest.TestCase):
 def fixture(self,current='O',state=None,mode='VERIFY'):
  temp=tempfile.TemporaryDirectory(prefix='t12-recovery-host-',dir=journal.ROOT/'runs');self.addCleanup(temp.cleanup)
  lab=Path(temp.name).resolve();persist=lab/'tmp/mnt/data_persist';persist.mkdir(parents=True)
  for p in (lab/'tmp',lab/'tmp/mnt',persist):p.chmod(0o755)
  parent=lab/'jci/gui/apps/system/js';parent.mkdir(parents=True)
  for part,m in [('jci',0o775),('jci/gui',0o755),('jci/gui/apps',0o775),('jci/gui/apps/system',0o755),('jci/gui/apps/system/js',0o755)]:
   (lab/part).chmod(m)
  frozen=json.loads((journal.ROOT/'experiments/disclaimer/freeze.json').read_text())
  original=(journal.ROOT/frozen['original']['path']).read_bytes()
  candidate=(journal.ROOT/frozen['private_candidate']).read_bytes()
  self.assertEqual(journal.sha(original),frozen['original']['sha256']);self.assertEqual(journal.sha(candidate),frozen['candidate']['sha256'])
  ctx=journal.retained_profile();d=persist/('cmu-bench-warm-'+ctx['nonce']);d.mkdir(mode=0o700)
  for name,data,mt in [('original',original,1433953097),('candidate',candidate,13392)]:
   p=d/name;p.write_bytes(data);p.chmod(0o755);os.utime(p,(mt,mt))
  src=parent/'systemApp.js';src.write_bytes(original if current=='O' else candidate);src.chmod(0o755)
  mt=1433953097 if current=='O' else 13392;os.utime(src,(mt,mt))
  def ident(p,dev):
   s=p.stat();return f'{dev}:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015:1'
  ctx['directory']='45826:'+str(d.stat().st_ino)
  ctx['original']=ident(d/'original',45826);ctx['candidate']=ident(d/'candidate',45826)
  ctx['initial']='64785:1606:1433953097:94058:755:1018:3015:1'
  if current=='O':ctx['ostage']=ident(src,64785)
  else:ctx['cstage']=ident(src,64785)
  if state:
   ctx['registry'],ctx['pending'],ctx['phase']=state
  raw=('WARM1|'+ctx['nonce']+'|'+'|'.join(k+'='+ctx[k] for k in journal.KEYS)+'\n').encode()
  journal.parse(raw);(d/'journal').write_bytes(raw);(d/'journal').chmod(0o600)
  tools=lab/'bin';tools.mkdir()
  for name in ('stat','readlink','md5sum','id','cp','mv'):
   p=tools/name;p.write_text('#!'+sys.executable+'\n'+SHIM);p.chmod(0o755)
  def script(which):
   body=prepare.render(ctx,NONCE,which)
   mapping={'/tmp/mnt/data_persist':str(persist),'/tmp/mnt':str(lab/'tmp/mnt'),'/tmp':str(lab/'tmp'),'/jci':str(lab/'jci'),'/proc/mounts':str(lab/'mounts')}
   return re.sub('|'.join(re.escape(p) for p in sorted(mapping,key=len,reverse=True)),lambda m:mapping[m[0]],body)
  def mount_rows(want):
   (lab/'mounts').write_text('rootfs / rootfs rw 0 0\n/dev/ffx01p1 / relfs '+want+',noatime 0 0\n/dev/mmcblk0p2 '+str(persist)+' relfs rw,noatime 0 0\n')
  mount_rows('ro' if mode=='VERIFY' else 'rw')
  env=dict(os.environ,PATH=str(tools)+':/usr/bin:/bin',RECOVERY_LAB=str(lab))
  return lab,d,src,original,candidate,ctx,script,mount_rows,env
 def execute(self,body,env):return subprocess.run(['/bin/sh'],input=body,text=True,capture_output=True,env=env,timeout=40)
 def snapshot(self,lab):
  return {str(p.relative_to(lab)):(p.read_bytes(),p.stat().st_ino,p.stat().st_mode&0o777,int(p.stat().st_mtime)) for p in lab.rglob('*') if p.is_file()}
 def test_exact_fixture_parser_syntax_and_no_verify_write_commands(self):
  ctx=journal.retained_profile();self.assertEqual(ctx['phase'],'original_restored');self.assertIn(':9457:',ctx['ostage']);self.assertIn(':1606:',ctx['initial'])
  for mode in ('VERIFY','RESTORE_ORIGINAL'):
   body=prepare.render(ctx,NONCE,mode)
   parsed=subprocess.run(['/bin/sh','-n'],input=body,text=True,capture_output=True,timeout=5)
   self.assertEqual(parsed.returncode,0,parsed.stderr)
   wire=prepare.wrap_command(body,'0'*32);self.assertLessEqual(len(wire),32768);self.assertLessEqual(max(map(len,wire.splitlines())),600)
  body=prepare.render(ctx,NONCE)
  self.assertNotIn('_commit_record()',body)
  self.assertFalse(re.search(r'^\s*(?:cp|mv|rm|mkdir|chmod|chown|mount|sync|eval|source)\s',body,re.M))
  raw=journal.FIXTURE.read_bytes()
  for bad in (raw+b'\n',raw[:-1],raw.replace(b'pending=none',b'pending=DISABLE'),raw.replace(b'original=',b'bad='),raw.replace(b'ostage=',b'ostage=$(touch /tmp/PWN)'),raw+b'|extra=x\n'):
   with self.assertRaises(ValueError):journal.parse(bad)
 def test_VERIFY_fresh_process_new_original_inode_noop_and_no_mutation(self):
  lab,d,src,original,candidate,ctx,script,mount_rows,env=self.fixture()
  before=self.snapshot(lab);result=self.execute(script('VERIFY'),env)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertEqual(self.snapshot(lab),before)
  self.assertIn('END mode=VERIFY rc=0 kind=O registry=disabled pending=none noop=1 writes=0',result.stdout)
  self.assertIn('historical_initial=64785:1606:',result.stdout);self.assertIn('CURRENT kind=O id=64785:'+str(src.stat().st_ino),result.stdout)
 def test_VERIFY_refuses_C_OTHER_wrong_mode_or_owner_without_writes(self):
  for case in ('C','OTHER','mode','owner'):
   with self.subTest(case=case):
    current='C' if case=='C' else 'O';state=('enabled','DISABLE','planned_restore') if current=='C' else None
    lab,d,src,original,candidate,ctx,script,mount_rows,env=self.fixture(current,state)
    if case=='OTHER':src.write_bytes(original.replace(b'Copyright',b'CopyRight',1))
    elif case=='mode':src.chmod(0o644)
    elif case=='owner':env['BAD_UID']='systemApp.js'
    before=self.snapshot(lab);result=self.execute(script('VERIFY'),env)
    self.assertNotEqual(result.returncode,0);self.assertEqual(self.snapshot(lab),before)
 def test_bad_journal_backup_links_and_pending_O_refuse_without_evaluation_or_mutation(self):
  for case in ('journal','backup','link','pending'):
   with self.subTest(case=case):
    state=('enabled','DISABLE','planned_restore') if case=='pending' else None
    lab,d,src,original,candidate,ctx,script,mount_rows,env=self.fixture(state=state)
    if case=='journal':(d/'journal').write_text('$(touch '+str(lab/'PWN')+')\n')
    elif case=='backup':(d/'original').write_bytes(b'bad backup')
    elif case=='link':
     (d/'candidate').unlink();(d/'candidate').symlink_to(d/'original')
    before=self.snapshot(lab);result=self.execute(script('VERIFY'),env)
    self.assertNotEqual(result.returncode,0);self.assertEqual(self.snapshot(lab),before);self.assertFalse((lab/'PWN').exists())
 def test_restore_review_capability_known_C_then_fresh_VERIFY_of_updated_record(self):
  lab,d,src,original,candidate,ctx,script,mount_rows,env=self.fixture('C',('enabled','DISABLE','planned_restore'),'RESTORE_ORIGINAL')
  old=src.stat().st_ino;result=self.execute(script('RESTORE_ORIGINAL'),env)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertEqual(src.read_bytes(),original);self.assertEqual(int(src.stat().st_mtime),1433953097);self.assertNotEqual(src.stat().st_ino,old)
  record=journal.parse((d/'journal').read_bytes());self.assertEqual((record['registry'],record['pending']),('disabled','none'))
  # Host-only caller models its separately owned RO return; restore script does not remount.
  mount_rows('ro');before=self.snapshot(lab);verify=self.execute(script('VERIFY'),env)
  self.assertEqual(verify.returncode,0,verify.stdout+verify.stderr);self.assertEqual(self.snapshot(lab),before)
 def test_restore_review_capability_refuses_OTHER_bad_backup_or_inconsistent_intent(self):
  for case in ('OTHER','backup','intent'):
   with self.subTest(case=case):
    state=('disabled','none','original_restored') if case=='intent' else ('enabled','DISABLE','planned_restore')
    lab,d,src,original,candidate,ctx,script,mount_rows,env=self.fixture('C',state,'RESTORE_ORIGINAL')
    if case=='OTHER':src.write_bytes(candidate.replace(b'Copyright',b'CopyRight',1))
    elif case=='backup':(d/'original').write_bytes(b'bad')
    before=self.snapshot(lab);result=self.execute(script('RESTORE_ORIGINAL'),env)
    self.assertNotEqual(result.returncode,0);self.assertEqual(self.snapshot(lab),before)

if __name__=='__main__':unittest.main(verbosity=2)
