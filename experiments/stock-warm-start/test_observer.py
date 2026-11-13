import importlib.util
import json
import signal
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stock_observer', HERE/'observe.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def check_output(boot='11111111-1111-1111-1111-111111111111', uptime=8000):
    return ('\nSWST|META|'+m.ORIGINAL+'\nSWST|HASH|'+m.MD5+'  -\nSWST|CRC|'+m.CRC+
            '\nSWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0\nSWST|UPTIME|'+str(uptime)+
            ' 9000.1\nSWST|BOOT_ID|'+boot+'\n').encode()


class Tests(unittest.TestCase):
    def test_fragmented_boot_noise_and_exact_one_prompt_sequence(self):
        g=m.BootGate();events=[]
        data=b'old / # \r\ncmu login: old noise\r\nU-Boot 2009\r\nLinux version 3.0.35 vendor\r\nnoise\r\ncmu login: '
        for b in data:
            e=g.feed(bytes([b]))
            if e: events.append(e)
        self.assertEqual(events,['login'])
        self.assertEqual(g.feed(b'root\r\nPass'),None)
        self.assertEqual(g.feed(b'word: '),'password')
        self.assertEqual(g.feed(b'\r\n/jci # '),'shell')
        self.assertEqual(g.events,['new_kernel_banner','login','password','shell'])

    def test_fragmented_numeric_and_logger_interleaved_kernel_prefixes(self):
        logger=(HERE/'fixtures/logger-boot.txt').read_bytes()
        forms=[b'[    0.000000] Linux version 3.0.35 synthetic\ncmu login: ',logger]
        for data in forms:
            for size in (1,3,17):
                g=m.BootGate();events=[]
                for start in range(0,len(data),size):
                    event=g.feed(data[start:start+size])
                    if event:events.append(event)
                self.assertTrue(g.kernel_seen)
                self.assertEqual(events,['login'])
                self.assertEqual(g.events.count('new_kernel_banner'),1)
                with self.assertRaisesRegex(RuntimeError,'repeated boot'):
                    g.feed(b'\n'+data)
        # The login prefix interleaved BEFORE the kernel is never reused as a
        # fresh post-kernel prompt. Detection alone is not login/readiness.
        g=m.BootGate();self.assertIsNone(g.feed(logger.splitlines()[0]+b'\n'))
        self.assertTrue(g.kernel_seen);self.assertEqual(g.stage,'boot')
        for fake in (b'echo Linux version 3.0.35\n',b'logger says Linux version 3.0.35\n'):
            g=m.BootGate();self.assertIsNone(g.feed(fake));self.assertFalse(g.kernel_seen)

    def test_no_bootloader_TX_no_stale_login_and_loop_stop(self):
        g=m.BootGate()
        self.assertIsNone(g.feed(b'\r\ncmu login: \r\nU-Boot 2009\r\nHit any key: '))
        self.assertEqual(g.stage,'boot')
        with self.assertRaisesRegex(RuntimeError,'repeated boot'):
            g.feed(b'\r\nU-Boot 2009\r\n')
        g=m.BootGate();g.feed(b'Linux version 3.0.35\r\n')
        with self.assertRaisesRegex(RuntimeError,'bootloader returned'):
            g.feed(b'U-Boot 2009\r\n')

    def test_auth_failure_duplicate_login_password_or_continuation_never_retry(self):
        for suffix in (b'cmu login: ',b'Login incorrect\r\n',b'> '):
            g=m.BootGate();self.assertEqual(g.feed(b'Linux version 3.0.35\r\ncmu login: '),'login')
            with self.assertRaises(RuntimeError):g.feed(b'\r\n'+suffix)
        g=m.BootGate();g.feed(b'Linux version 3.0.35\r\ncmu login: ');g.feed(b'\r\nPassword: ')
        with self.assertRaises(RuntimeError):g.feed(b'\r\nPassword: ')

    def test_original_RO_new_boot_and_uptime_checks(self):
        before=m.checked_output(0,check_output())
        after=m.checked_output(0,check_output('22222222-2222-2222-2222-222222222222',30),before)
        self.assertEqual(after['uptime_seconds'],30)
        changed=check_output('33333333-3333-3333-3333-333333333333',31).replace(b':9457:',b':9876:')
        self.assertIn(':9876:',m.checked_output(0,changed,before)['META'])
        with self.assertRaises(RuntimeError):m.checked_output(0,changed)
        for raw in (check_output(),check_output().replace(b'ro,noatime',b'rw,noatime'),
                    check_output().replace(b':755:',b':644:'),check_output()+b'SWST|META|x\n'):
            with self.assertRaises(RuntimeError):m.checked_output(0,raw,before)
        with self.assertRaises(RuntimeError):m.checked_output(1,check_output())

    def test_front_door_ONE_unframed_request_then_gated_credentials_and_postchecks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cred=root/'credentials.json'
            cred.write_text(json.dumps(dict(username='root',password='synthetic')));cred.chmod(0o600)
            profile=root/'profile.json';profile.write_text(json.dumps(dict(
                normal_reboot_route_verified=True,reboot_hex=m.REBOOT.hex(),source_pins={
                    'experiments/stock-warm-start/observe.py':m.sha(HERE/'observe.py'),
                    'src/open_connect/session.py':m.sha(m.ROOT/'src/open_connect/session.py')})))
            sent=[];closed=[]
            class Lock:
                def __init__(self,**kw):pass
                def __enter__(self):pass
                def __exit__(self,*a):pass
            class Port:
                def close(self):closed.append(True)
            class Video:
                def __init__(self,*a):pass
                def start(self):sent.append('video_started')
                def stop(self):
                    sent.append('video_stopped')
                    if camera_fail:raise RuntimeError('synthetic final ffprobe failure')
            class Session:
                def __init__(self,*a,**kw):
                    self.checks=0;self.identity=None
                    self.chunks=iter([b'U-Boot 2009\r\n',b'Linux version 3.0.35\r\n',b'cmu login: ',b'\r\nPassword: ',b'\r\n/jci # '])
                def observe_prompt(self,**kw):pass
                def identify(self):self.identity={'uid':0,'installed':'55.00.750B'}
                def execute(self,command):
                    self.checks+=1
                    return 0,check_output() if self.checks==1 else check_output('22222222-2222-2222-2222-222222222222',30)
                def _send(self,data,**kw):sent.append(data)
                def _read(self,*a,**kw):return next(self.chunks,b'')
            for camera_fail in (False,True):
                sent.clear();closed.clear()
                ticks=iter(range(0,10000,2));bundle=root/('camera_failed' if camera_fail else 'bundle')
                with patch.object(m,'AdapterLock',Lock),patch.object(m,'open_adapter',lambda b:Port()),patch.object(m,'Video',Video),patch.object(m,'Session',Session),patch.object(m.time,'monotonic',lambda:next(ticks)):
                    rc=m.main(['--live','--bundle',str(bundle),'--credentials',str(cred),'--profile',str(profile),'--camera-index','0'])
                self.assertEqual(rc,2 if camera_fail else 0)
                self.assertEqual(sent,['video_started',b'/sbin/reboot\r',b'root\r',b'synthetic\r','video_stopped'])
                manifest=json.loads((bundle/'manifest.json').read_text())
                self.assertEqual(manifest['outcome'],'access_O_RO_verified_video_failed' if camera_fail else 'stock_restart_access_O_RO_verified')
                self.assertTrue(closed)
                self.assertNotIn(b'BEGIN',m.REBOOT)

    def test_streamable_video_stops_decodes_with_inherited_INT_ignored_NO_camera(self):
        actual_popen=subprocess.Popen
        def synthetic_input(argv,**kw):
            # Replace ONLY camera input with ffmpeg's generated test pattern.
            # Keep production exec wrapper, container, codec and stop/validation.
            argv=list(argv)
            if argv[0] != sys.executable:return actual_popen(argv,**kw)
            first=argv.index('-f');end=argv.index('-an')
            argv[first:end]=['-f','lavfi','-re','-i','testsrc=size=128x96:rate=5']
            return actual_popen(argv,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            b=m.Bundle(Path(tmp)/'bundle','synthetic local video, no hardware','unittest')
            v=m.Video(b,0);previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
            try:
                with patch.object(m.subprocess,'Popen',side_effect=synthetic_input):
                    v.start();time.sleep(.7);v.stop()
                result=json.loads((b.path/'camera-result.json').read_text())
                self.assertTrue(result['video_verified'])
                self.assertEqual(result['ffprobe_rc'],0)
                self.assertGreaterEqual(result['decoded_frames'],2)
                self.assertGreater(result['actual_interval_fps'],0)
                signals=[x['signal'] for x in result['stop_requests']]
                self.assertEqual(signals[0],'SIGINT')
                self.assertTrue(set(signals).issubset({'SIGINT','SIGTERM'}))
            finally:
                signal.signal(signal.SIGINT,previous)
                if v.proc and v.proc.poll() is None:v.proc.terminate();v.proc.wait(timeout=3)
                b.finish('synthetic_test_finished')

    def test_actual_core_Session_constructor_accepts_observer_RX_bound(self):
        session=m.Session(object(),None,timeout=20,output_cap=m.MAX_RX)
        self.assertEqual(session.output_cap,4*1024*1024)

    def test_default_review_opens_nothing_and_private_credential_guard(self):
        p=subprocess.run([sys.executable,'-B',str(HERE/'observe.py')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['mode'],'review_only')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'credentials.json';p.write_text('{"username":"root","password":"synthetic"}');p.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'private'):m.private_credentials(p)

if __name__=='__main__':unittest.main(verbosity=2)
