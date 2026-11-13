"""Offline shell contract model only; never opens UART/camera or executes payload bytes."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import deliver as d

RUN = '1234567890abcdef1234567890abcdef'
HERE = Path(__file__).resolve().parent
SHIM = r'''#!/usr/bin/env python3
import base64,hashlib,os,stat,sys
from pathlib import Path
name=Path(sys.argv[0]).name;a=sys.argv[1:]
if name=='id':print(0)
elif name=='awk':pass # Explicit contract fake: one canonical tmpfs row, not a mount proof.
elif name=='readlink':print(os.path.realpath(a[-1]))
elif name=='stat':
 s=os.stat(a[-1]);v={'d':s.st_dev,'i':s.st_ino,'Y':int(s.st_mtime),'s':s.st_size,
 'a':format(stat.S_IMODE(s.st_mode),'o'),'u':0,'g':0,'h':s.st_nlink}
 f=a[1]
 for k,x in v.items():f=f.replace('%'+k,str(x))
 print(f)
elif name=='md5sum':print(hashlib.md5(sys.stdin.buffer.read()).hexdigest()+'  -')
elif name=='cksum':
 import subprocess
 sys.stdout.buffer.write(subprocess.check_output(['/usr/bin/cksum'],input=sys.stdin.buffer.read()))
elif name=='base64':
 sys.stdout.buffer.write(base64.b64decode(sys.stdin.buffer.read(),validate=False))
else:raise RuntimeError(name)
'''


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.root = Path(self.temp.name).resolve()
        self.tmp = self.root/'tmp';self.tmp.mkdir(mode=0o700)
        self.bin = self.root/'bin';self.bin.mkdir()
        shim = self.bin/'shim';shim.write_text(SHIM);shim.chmod(0o700)
        for name in ('id','awk','readlink','stat','md5sum','cksum','base64'):
            (self.bin/name).symlink_to(shim)
        self.env = {**os.environ,'PATH':str(self.bin)+os.pathsep+os.environ['PATH']}
        self.payload = self.root/'source';self.payload.write_bytes(b'hello\x00\xff\r\n$(touch NEVER)\n')
        self.snapshot = d.source(self.payload)
        self.stagepath = self.tmp/('cmu-bench-payload-'+RUN)

    def tearDown(self):
        self.temp.cleanup()

    def shell(self, command):
        # Production renderer has no path/transport override. Only this offline test translates /tmp.
        return subprocess.run(['/bin/sh'],input=command.replace('/tmp',str(self.tmp)),
                              text=True,capture_output=True,env=self.env,timeout=15)

    def staged(self):
        result=self.shell(d.stage_command(self.snapshot,RUN))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return d.stage_result(result.stdout.encode(),self.snapshot,RUN)

    def test_default_and_frontdoor_failure_open_nothing_write_nothing(self):
        with patch.object(d,'open_adapter',side_effect=AssertionError('hardware')), \
             patch.object(d,'Bundle',side_effect=AssertionError('bundle')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(d.main(['stage','--source',str(self.payload)]),0)
            plan=json.loads(out.getvalue())
            self.assertFalse(plan['target_observed']);self.assertFalse(plan['opens_port'])
            self.assertFalse(plan['execution'])
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                d.main(['stage','--source',str(self.root/'missing'),'--live','--bundle',str(self.root/'nope')])
        self.assertFalse((self.root/'nope').exists())

    def test_binary_data_exact_maximum_wire_bounds_and_guarded_cleanup(self):
        data=bytes(range(256))*64
        self.payload.write_bytes(data);self.snapshot=d.source(self.payload)
        command=d.stage_command(self.snapshot,RUN)
        wire=d.wrap_command(command,'a'*32)
        self.assertLessEqual(len(wire),32768)
        self.assertLess(max(map(len,wire.splitlines())),600)
        self.assertNotIn('DELIVERY '+RUN+' END',command)
        self.assertEqual(subprocess.run(['/bin/sh','-n'],input=command,text=True).returncode,0)
        stage=self.staged()
        self.assertEqual((self.stagepath/'p').read_bytes(),data)
        self.assertEqual(stage['bytes'],16384);self.assertFalse(stage['execution'])
        self.assertEqual(subprocess.run(['/bin/sh','-n'],input=d.cleanup_command(stage),text=True).returncode,0)
        result=self.shell(d.cleanup_command(stage))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(d.records(result.stdout.encode(),RUN),['END|CLEANUP|0|absent=1'])
        self.assertFalse(self.stagepath.exists())

    def test_source_conflict_nonregular_symlink_and_limit_refused(self):
        self.payload.write_bytes(b'changed')
        with self.assertRaises(ValueError):d.unchanged(self.snapshot)
        self.payload.write_bytes(b'x'*(d.LIMIT+1))
        with self.assertRaises(ValueError):d.source(self.payload)
        link=self.root/'link';link.symlink_to(self.payload)
        with self.assertRaises(OSError):d.source(link)
        with self.assertRaises(ValueError):d.source(self.tmp)
        os.mkfifo(self.root/'fifo')
        with self.assertRaises(ValueError):d.source(self.root/'fifo')

    def test_existing_target_and_conflicting_cleanup_preserved(self):
        stage=self.staged();before=(self.stagepath/'p').read_bytes()
        second=self.shell(d.stage_command(self.snapshot,RUN))
        self.assertEqual(second.returncode,73);self.assertIn('already_exists',second.stdout)
        self.assertEqual((self.stagepath/'p').read_bytes(),before)
        (self.stagepath/'p').write_bytes(b'later change')
        refused=self.shell(d.cleanup_command(stage))
        self.assertEqual(refused.returncode,73);self.assertEqual((self.stagepath/'p').read_bytes(),b'later change')
        (self.stagepath/'p').write_bytes(before)
        (self.stagepath/'unrelated').write_text('keep')
        refused=self.shell(d.cleanup_command(stage))
        self.assertEqual(refused.returncode,73)
        self.assertTrue((self.stagepath/'p').exists());self.assertEqual((self.stagepath/'unrelated').read_text(),'keep')

    def test_strict_records_and_descriptor_reject_echo_duplicate_partial_or_forged_data(self):
        stage=self.staged()
        good=('DELIVERY '+RUN+' FILE|'+stage['file_id']+'\nDELIVERY '+RUN+' DIR|'+stage['dir_id']+
              '\nDELIVERY '+RUN+f" DATA|{stage['bytes']}|{stage['md5']}|{stage['cksum']}\n"+
              'DELIVERY '+RUN+' END|STAGE|0|execution=0\n').encode()
        self.assertEqual(d.stage_result(b'noise\n'+good,self.snapshot,RUN),stage)
        for bad in (good+good,good[:-1],good[:-12],b'echo "'+good,
                    good.replace(b'DATA|',b'DATA|999|'),good.replace(b'FILE|',b'FILE|bad:')):
            with self.subTest(bad=bad[:50]),self.assertRaises(ValueError):
                d.stage_result(bad,self.snapshot,RUN)
        for change in ({'path':'/jci/p'},{'observed':False},{'nonce':RUN+';id'},
                       {'file_id':stage['file_id'].replace(':600:',':755:')},{'extra':'x'}):
            with self.assertRaises(ValueError):d.cleanup_command({**stage,**change})

    def test_live_frontdoor_mocks_failed_open_and_uncertain_TX_preserve_evidence(self):
        # Front door exercised with mocks; production FTDI identity selection remains unchanged.
        for name,error,expected in [('open',RuntimeError('synthetic open failed'),'failed'),
                                    ('tx',SystemExit(7),'unknown_preserved')]:
            bundle=self.root/name
            session=MagicMock();session.state='shell';session.execute.side_effect=error
            lock=MagicMock()
            with patch.object(d,'AdapterLock',return_value=lock), \
                 patch.object(d,'open_adapter',side_effect=error if name=='open' else None,
                              return_value=MagicMock()) as opened, \
                 patch.object(d,'Session',return_value=session),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(d.main(['stage','--source',str(self.payload),'--live','--bundle',str(bundle)]),
                                 1 if name=='open' else 2)
            m=json.loads((bundle/'manifest.json').read_text())
            self.assertEqual(m['outcome'],expected)
            self.assertFalse(m['adapter_observed']);self.assertFalse(m['serial_port_opened'])
            self.assertFalse((bundle/'stage.json').exists())
            self.assertTrue((bundle/'delivery-command.sh').exists())
            if name=='tx':opened.return_value.close.assert_called_once()
        session=MagicMock();session.state='shell'
        session.identify.side_effect=lambda:self.payload.write_bytes(b'changed before TX')
        with patch.object(d,'AdapterLock'),patch.object(d,'open_adapter'), \
             patch.object(d,'Session',return_value=session),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(d.main(['stage','--source',str(self.payload),'--live','--bundle',str(self.root/'source-race')]),1)
            session.execute.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
