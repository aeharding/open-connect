import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
import prepare

ROOT = Path(__file__).resolve().parent
NONCE = '1234567890abcdef1234567890abcdef'
FREEZE = json.loads((prepare.ROOT/'experiments/disclaimer/freeze.json').read_text())

# Host contract shim only: real bytes/modes/links/inodes, modeled CMU UID/GID/device.
SHIM = r'''
import hashlib,json,os,re,stat,sys
from pathlib import Path
name=Path(sys.argv[0]).name
if name=='stat':
 p=Path(sys.argv[3]);s=p.lstat();image=p.name in ('original','candidate','active','stage','restore')
 v={'F':'directory' if stat.S_ISDIR(s.st_mode) else 'regular file','a':format(stat.S_IMODE(s.st_mode),'o'),
 'u':'1018' if image else '0','g':'3015' if image else '0','h':str(s.st_nlink),
 'd':'45826','i':str(s.st_ino),'s':str(s.st_size),'Y':str(int(s.st_mtime))}
 print(re.sub(r'%([FaughdisY])',lambda m:v[m[1]],sys.argv[2]))
elif name=='readlink': print(Path(sys.argv[-1]).resolve(strict=True))
elif name=='md5sum':
 data=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else sys.stdin.buffer.read()
 print(hashlib.md5(data).hexdigest()+'  '+(sys.argv[1] if len(sys.argv)>1 else '-'))
elif name=='mv':
 with open(os.environ['TX_TRACE'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\n')
 os.execv('/bin/mv',['mv']+sys.argv[1:])
else: raise SystemExit(4)
'''


class TransactionTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='t12-tx-host-',dir=prepare.ROOT/'runs')
        self.addCleanup(temp.cleanup)
        base = Path(temp.name); owned = base/'owned'; owned.mkdir(mode=0o700)
        images = {'original': prepare.ROOT/FREEZE['original']['path'],
                  'candidate': prepare.ROOT/FREEZE['private_candidate']}
        for name,path in images.items():
            data=path.read_bytes()
            expected=FREEZE['original']['sha256'] if name=='original' else FREEZE['candidate']['sha256']
            self.assertEqual(prepare.sha(data),expected)
            (owned/name).write_bytes(data);(owned/name).chmod(0o755)
        (owned/'active').write_bytes((owned/'original').read_bytes());(owned/'active').chmod(0o755)
        os.utime(owned/'active',(1433953097,1433953097))
        s=(owned/'active').stat();di='45826:'+str(owned.stat().st_ino)
        ai=f'45826:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015:1'
        tail=f'|dir={di}|o=94058:584c67f7186ada6bae9aae1be59b5cd0:376717896|c=94055:64db9d0df2277e1d95a037929aef30c4:776631029|meta=755:1018:3015:1'
        pending=f'COPYTX1|{NONCE}|registry=enabled|pending=DISABLE{tail}'
        (owned/'journal').write_text(pending+'\n');(owned/'journal').chmod(0o600)
        script=prepare.complete_script(NONCE,di,ai)
        script=re.sub(r'^_d=.*$', '_d='+shlex.quote(str(owned)),script,count=1,flags=re.M)
        # Parent/mount contract is already live-proven; substitute only that outer
        # contract in host tests. All owned path/file/journal/commit guards execute.
        script=re.sub(r'# PARENT_CONTRACT_BEGIN\n.*?# PARENT_CONTRACT_END\n', '_pd=45826\n',script,flags=re.S)
        tools=base/'bin';tools.mkdir()
        for name in ('stat','readlink','md5sum','mv'):
            path=tools/name;path.write_text('#!'+sys.executable+'\n'+SHIM);path.chmod(0o755)
        trace=base/'trace.jsonl'
        env=dict(os.environ,PATH=str(tools)+':/usr/bin:/bin',TX_TRACE=str(trace))
        return owned,script,env,trace,ai

    def run_script(self,script,env):
        return subprocess.run(['/bin/sh'],input=script,text=True,capture_output=True,env=env,timeout=15)

    def test_shell_syntax_wire_bounds_and_nonce_identity_validation(self):
        for script in (prepare.stop_script(NONCE),prepare.complete_script(NONCE,'45826:49','45826:123:1433953097:94058:755:1018:3015:1')):
            parsed=subprocess.run(['/bin/sh','-n'],input=script,text=True,capture_output=True,timeout=5)
            self.assertEqual(parsed.returncode,0,parsed.stderr)
            wire=prepare.wrap_command(script,'0'*32)
            self.assertLessEqual(len(wire),32768)
            self.assertLessEqual(max(map(len,wire.splitlines())),600)
            self.assertNotIn(('COPYTX '+NONCE+' STOP intent=').encode(),wire)
        for nonce in ('../bad','a'*31,'F'*32,'a'*32+';id'):
            with self.assertRaises(ValueError):prepare.stop_script(nonce)
        with self.assertRaises(ValueError):prepare.complete_script(NONCE,'45826:49;id','1:2')

    def test_normal_complete_no_active_rewrite_and_exact_cleanup(self):
        owned,script,env,trace,ai=self.fixture()
        before=(owned/'active').stat()
        result=self.run_script(script,env)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('BEFORE_COMPLETE active_id='+ai,result.stdout)
        self.assertIn('COMMIT registry=disabled pending=none active_id='+ai+' no_rewrite=1',result.stdout)
        self.assertIn('END rc=0 registry=disabled pending=none cleanup=absent',result.stdout)
        self.assertFalse(owned.exists())
        moves=[json.loads(line) for line in trace.read_text().splitlines()]
        self.assertEqual(moves,[['-f',str(owned/'journal.new'),str(owned/'journal')]])
        print('HOST_COMPLETE_CHECK no_active_replace=True inode='+str(before.st_ino))

    def test_bad_journal_is_data_not_code_and_refuses_before_write(self):
        for case in ('text','mode','missing'):
            with self.subTest(case=case):
                owned,script,env,trace,ai=self.fixture()
                journal=owned/'journal';sentinel=owned.parent/'MUST_NOT_EXIST'
                if case=='text':journal.write_text('$(touch '+str(sentinel)+')\n')
                elif case=='mode':journal.chmod(0o644)
                else:journal.unlink()
                before={p.name:p.read_bytes() for p in owned.iterdir()}
                result=self.run_script(script,env)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual({p.name:p.read_bytes() for p in owned.iterdir()},before)
                self.assertFalse(sentinel.exists());self.assertFalse(trace.exists())

    def test_conflicting_images_metadata_identity_or_unknown_entry_preserved(self):
        for case in ('bytes','mode','identity','backup','extra'):
            with self.subTest(case=case):
                owned,script,env,trace,ai=self.fixture()
                if case=='bytes':
                    (owned/'active').write_bytes((owned/'active').read_bytes().replace(b'Copyright',b'CopyRight',1))
                elif case=='mode':(owned/'active').chmod(0o644)
                elif case=='identity':
                    (owned/'replacement').write_bytes((owned/'active').read_bytes());(owned/'replacement').chmod(0o755)
                    os.replace(owned/'replacement',owned/'active')
                elif case=='backup':(owned/'original').write_bytes(b'corrupt original')
                else:(owned/'unexpected').write_bytes(b'leave this alone')
                before={p.name:p.read_bytes() for p in owned.iterdir()}
                result=self.run_script(script,env)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual({p.name:p.read_bytes() for p in owned.iterdir()},before)
                self.assertFalse(trace.exists())


if __name__=='__main__':unittest.main(verbosity=2)
