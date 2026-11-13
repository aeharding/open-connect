import importlib.util,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout,nullcontext
import observe as o

OLD='11111111-1111-1111-1111-111111111111'
NEW='22222222-2222-2222-2222-222222222222'

def snapshot(identity=o.EXPECTED_O,boot=OLD,uptime=100,md5=o.OMD5,crc=o.OCRC):
 return (f'SWST|META|{identity}\nSWST|HASH|{md5}  -\nSWST|CRC|{crc}\n'
         'SWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0\n'
         f'SWST|UPTIME|{uptime} 10.0\nSWST|BOOT_ID|{boot}\n').encode()

class ObserverTests(unittest.TestCase):
 def test_exact_O9456_prefix_and_strict_postidentity_boot_RO(self):
  before=o.checked_original_output(0,snapshot())
  raw=b'logger object(0x47ea'+snapshot(boot=NEW,uptime=10)
  after=o.checked_original_output(0,raw,before)
  self.assertEqual(after['source_kind'],'O');self.assertEqual(after['META'],o.EXPECTED_O)
  changes={0:'64786',1:'9457',2:'1433953098',3:'94055',4:'644',5:'0',6:'0',7:'2'}
  for index,value in changes.items():
   parts=o.EXPECTED_O.split(':');parts[index]=value
   with self.subTest(index=index),self.assertRaises(o.OriginalIdentityConflict):
    o.checked_original_output(0,snapshot(':'.join(parts),NEW,10),before)
  for bad in [snapshot(boot=OLD,uptime=10),snapshot(boot=NEW,uptime=100),raw.replace(b'ro,noatime',b'rw,noatime'),raw+b'SWST|META|'+o.EXPECTED_O.encode()+b'\n',raw[:-1],snapshot(boot=NEW,uptime=10,md5='64db9d0df2277e1d95a037929aef30c4',crc='776631029 94055')]:
   with self.assertRaises(ValueError):o.checked_original_output(0,bad,before)
 def test_retained_VERIFY_is_readonly_and_exact_disabled_O(self):
  o.retained_verified(0,b'ROOT_ROW: ro\nnoise-prefix'+o.VERIFY_END+b'\r\n')
  for raw in [o.VERIFY_END,o.VERIFY_END+b'\n'+o.VERIFY_END+b'\n',o.VERIFY_END.replace(b'kind=O',b'kind=C')+b'\n',o.VERIFY_END.replace(b'writes=0',b'writes=1')+b'\n',o.VERIFY_END.replace(b'pending=none',b'pending=DISABLE')+b'\n']:
   with self.assertRaises(ValueError):o.retained_verified(0,raw)
  with self.assertRaises(ValueError):o.retained_verified(1,o.VERIFY_END+b'\n')
  self.assertNotIn('RESTORE_ORIGINAL',o.VERIFY_COMMAND)
  for verb in ['mount ','sync','cp ','mv ','rm ','chmod','chown','eval','source ']:self.assertNotIn(verb,o.VERIFY_COMMAND)
  self.assertTrue(o.VERIFY_COMMAND.endswith('/bin/sh "$p" VERIFY </dev/null\n'))
 def fake(self,fail_verify=False,changed_post=False):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
  p=root/'profile.json';p.write_text(json.dumps(o.profile(live=True)))
  sent=[];checked=[];closed=[];started=[]
  class Port:
   def close(self):closed.append(True)
  class Session:
   def __init__(self,port,bundle,**kw):self.bundle=bundle;self.timeout=20;self.identity=None;self.count=0;self.chunks=iter([b'Linux version 3.0.35 synthetic\ncmu login: ',b'\r\nPassword: ',b'\r\n/tmp/root # '])
   def observe_prompt(self,**kw):pass
   def identify(self):
    self.identity={'uid':0,'user':'root','firmware':'55.00.750B','flavor':'cmu150_NA'};self.bundle.meta['identity']=self.identity
   def execute(self,command,**kw):
    checked.append(command)
    if command==o.stock.CHECK:
     self.count+=1
     identity=o.EXPECTED_O if not(changed_post and self.count==2) else o.EXPECTED_O.replace(':9456:',':9457:')
     return 0,snapshot(identity,OLD if self.count==1 else NEW,100 if self.count==1 else 10)
    if command==o.VERIFY_COMMAND:return (1,b'failed') if fail_verify else (0,o.VERIFY_END+b'\n')
    raise AssertionError('unexpected target command')
   def _send(self,data,**kw):sent.append(data)
   def _read(self,*args,**kw):return next(self.chunks,b'')
  class Video:
   def __init__(self,*args):pass
   def start(self):started.append(True)
   def stop(self):pass
  ticks=iter(range(0,10000,2))
  with patch.object(o.stock,'Session',Session),patch.object(o.stock,'AdapterLock',lambda **kw:nullcontext()),patch.object(o.stock,'open_adapter',lambda b:Port()),patch.object(o.stock,'Video',Video),patch.object(o.stock,'private_credentials',lambda p:(b'root\r',b'synthetic-only\r')),patch.object(o.stock.time,'monotonic',lambda:next(ticks)),redirect_stdout(io.StringIO()) as output:
   rc=o.main(['--live','--profile',str(p),'--bundle',str(root/'bundle'),'--credentials',str(root/'synthetic-private'),'--camera-index','0','--solicit-prompt'])
  m=json.loads((root/'bundle/manifest.json').read_text());events=[json.loads(x) for x in (root/'bundle/events.jsonl').read_text().splitlines()]
  return rc,m,sent,checked,closed,started,output.getvalue(),events
 def test_fake_full_O_flow_verifies_retention_pre_post_and_truthful_labels(self):
  rc,m,sent,commands,closed,started,output,events=self.fake()
  self.assertEqual(rc,0);self.assertEqual(m['outcome'],'stock_restart_access_O_RO_verified')
  self.assertEqual(m['expected_source_kind'],'O');self.assertEqual(m['accepted_original_identity'],o.EXPECTED_O)
  self.assertEqual(sent,[o.stock.REBOOT,b'root\r',b'synthetic-only\r'])
  self.assertEqual(commands,[o.stock.CHECK,o.VERIFY_COMMAND,o.stock.CHECK,o.VERIFY_COMMAND])
  self.assertTrue(closed);self.assertEqual(len(started),1)
  retained=[e for e in events if e['kind']=='persistent_original_verified'];self.assertEqual([e['phase'] for e in retained],['preflight','postboot'])
  verified=next(e for e in events if e['kind']=='post_restart_verified');self.assertTrue(verified['source_O']);self.assertNotIn('source_C',verified)
 def test_fresh_retention_failure_stops_before_video_or_reboot(self):
  rc,m,sent,commands,closed,started,_,events=self.fake(fail_verify=True)
  self.assertEqual((rc,m['outcome'],sent,started),(2,'failed_before_request',[],[]));self.assertTrue(closed)
 def test_changed_post_O_identity_stops_without_adoption(self):
  rc,m,sent,commands,closed,started,_,events=self.fake(changed_post=True)
  self.assertEqual((rc,m['outcome']),(2,'unknown_after_request'))
  self.assertEqual(sent.count(o.stock.REBOOT),1);self.assertTrue(closed)
  self.assertEqual(len([x for x in commands if x==o.VERIFY_COMMAND]),1)
  conflict=next(e for e in events if e['kind']=='original_identity_conflict');self.assertFalse(conflict['automatic_adoption'])
 def test_review_profile_refuses_before_credentials_or_hardware(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'profile.json';p.write_text(json.dumps(o.profile()))
   with patch.object(o.stock,'open_adapter') as port,patch.object(o.stock,'private_credentials') as credentials,patch.object(o.stock,'Video') as video:
    with self.assertRaises(ValueError):o.main(['--live','--profile',str(p)])
   port.assert_not_called();credentials.assert_not_called();video.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
