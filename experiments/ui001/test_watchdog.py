import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(HERE))
import prepare
import invoke
from cmu_bench.session import Bundle,Session,UnknownOutcome,wrap_command
RUN='0123456789abcdef'*2


def fixture(root,mode,profile='ui001',hook=None,fault=None,slow=False):
    fake=root/'fake-dialog'
    text=(HERE/'fake_dialog.py').read_text().split('\n',1)[1]
    fake.write_text('#!'+sys.executable+'\n'+text); fake.chmod(0o700)
    command,plan=prepare.render(RUN,profile)
    args=shlex.split(command)
    assert args[:2]==['timeout','-t'] and args[3:7]==['-s','15','/bin/sh','-c']
    body=args[7]
    tool='/jci/tools/jci-dialog' if profile=='ui001' else '/bin/sleep'
    body=body.replace('_tool='+tool,'_tool='+shlex.quote(str(fake)))
    body=body.replace('_proc=/proc','_proc='+shlex.quote(str(root/'proc')))
    if hook:
        # Child exec is ready; interruption is deterministic within each exact window.
        body=body.replace('# TEST_POINT_'+hook,'/bin/sleep 0.12\n/bin/kill -TERM "$$"')
    calls=root/'signal-requests.txt'
    delay='0.07' if slow else '0.02'
    sleepfirst='/bin/sleep 0.15; '+('return 1;' if fault=='sleep' else ':;')
    prefix=('_fake_calls=0\nid() { printf "0\\n"; }\n'
            'sleep() { _fake_calls=$((_fake_calls+1)); if [ "$_fake_calls" -eq 1 ]; then '
            +sleepfirst+' else /bin/sleep '+delay+'; fi; }\n'
            'kill() { printf "%s\\n" "$*" >> '+shlex.quote(str(calls))+'; /bin/kill "$@"; }\n')
    if fault=='inspection':
        flag=shlex.quote(str(root/'inspection-failed-once'))
        prefix+=('od() { case "$*" in */cmdline) if [ ! -e '+flag+' ]; then : > '+flag
                 +'; return 1; fi;; esac; /usr/bin/od "$@"; }\n')
    env=dict(os.environ,UI001_FAKE_ROOT=str(root),UI001_FAKE_MODE=mode)
    return prefix+body,env,calls,command,plan


def finish_fake(child,root,calls):
    try:
        out,err=child.communicate(timeout=7)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL)  # Only this test's created session/group.
        child.communicate(timeout=2)
        raise AssertionError('owned local fake did not finish')
    events=[json.loads(s) for s in (root/'fake-events.jsonl').read_text().splitlines()]
    requested=calls.read_text().splitlines() if calls.exists() else []
    assert any(e['kind']=='exited' for e in events),events
    assert not any((root/'proc').iterdir())
    return child.returncode,out,requested,events,err


class WatchdogTests(unittest.TestCase):
    def run_fake(self,mode='normal',profile='ui001',hook=None,fault=None,interrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            body,env,calls,_,_=fixture(root,mode,profile,hook,fault)
            child=subprocess.Popen(['/bin/sh','-c',body],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            timer=None
            if interrupt:
                timer=threading.Timer(0.10,lambda: child.send_signal(signal.SIGTERM) if child.poll() is None else None)
                timer.start()
            try:
                rc,out,requests,events,err=finish_fake(child,root,calls)
            finally:
                if timer: timer.cancel(); timer.join()
            results=[line for line in out.splitlines() if line.startswith(('UI001 '+RUN+' RESULT ').encode())]
            self.assertEqual(len(results),1,(out,err))
            return rc,out,requests,events

    def assert_owned_term(self,result,rc):
        actual,out,calls,events=result
        pid=next(e['pid'] for e in events if e['kind']=='ready')
        self.assertEqual(actual,rc,out)
        self.assertEqual(calls,['-TERM '+str(pid)])
        self.assertIn(b'cleanup=term_exit_verified',out)
        self.assertIn(b'dialog_rc=143',out)
        self.assertTrue(any(e['kind']=='term_received' for e in events))

    def test_normal_owned_cleanup_and_actual_status(self):
        result=self.run_fake()
        self.assert_owned_term(result,0)
        self.assertIn(b'reason=watchdog_expired',result[1])
        self.assertIn(b'ready=1',result[1])

    def test_pre_pid_assignment_signal_is_deferred_and_cleaned(self):
        self.assert_owned_term(self.run_fake(hook='AFTER_SPAWN'),143)

    def test_post_pid_pre_identity_signal_is_deferred_and_cleaned(self):
        self.assert_owned_term(self.run_fake(hook='AFTER_PID'),143)

    def test_reported_early_sleep_interrupt_regression(self):
        self.assert_owned_term(self.run_fake(interrupt=True),143)

    def test_initial_sleep_failure_cleanup_adopts_and_terminates_owned_child(self):
        result=self.run_fake(fault='sleep')
        self.assert_owned_term(result,78)
        self.assertIn(b'reason=initial_sleep_failed',result[1])
        self.assertIn(b'ready=0',result[1])

    def test_initial_inspection_failure_cleanup_adopts_and_terminates_owned_child(self):
        result=self.run_fake(fault='inspection')
        self.assert_owned_term(result,76)
        self.assertIn(b'reason=initial_identity_unreadable',result[1])

    def test_probe_reuses_safe_cleanup_for_early_failure(self):
        result=self.run_fake(profile='sleep4',fault='sleep')
        self.assert_owned_term(result,78)
        self.assertIn(b'profile=sleep4',result[1])

    def test_already_exited_zero_is_cleaned_but_ui_not_ready(self):
        rc,out,calls,_=self.run_fake('early_exit')
        self.assertEqual(rc,79,out)
        self.assertEqual(calls,[])
        self.assertIn(b'cleanup=already_exited',out)
        self.assertIn(b'dialog_rc=0',out)
        self.assertIn(b'ready=0',out)
        self.assertNotIn(b' READY ',out)

    def test_early_failed_child_preserves_real_nonzero_and_no_ready(self):
        rc,out,calls,_=self.run_fake('early_failure')
        self.assertEqual(rc,7,out)
        self.assertEqual(calls,[])
        self.assertIn(b'dialog_rc=7',out)
        self.assertIn(b'wrapper_rc=7',out)
        self.assertNotIn(b' READY ',out)

    def test_identity_mismatch_never_signals(self):
        for mode in ('wrong_cmdline','wrong_parent','changed_start'):
            with self.subTest(mode=mode):
                rc,out,calls,events=self.run_fake(mode)
                self.assertEqual(rc,77,out)
                self.assertEqual(calls,[])
                self.assertFalse(any(e['kind']=='term_received' for e in events))
                self.assertIn(b'identity_mismatch_no_signal',out)

    def test_ignored_term_is_bounded_failure_without_kill(self):
        rc,out,calls,events=self.run_fake('ignore_term')
        pid=next(e['pid'] for e in events if e['kind']=='ready')
        self.assertEqual(rc,75,out)
        self.assertEqual(calls,['-TERM '+str(pid)])
        self.assertIn(b'cleanup=still_alive_after_term_no_escalation',out)
        self.assertIn(b'dialog_rc=unknown',out)

    def test_nested_wire_syntax_and_independent_term_deadlines(self):
        for profile,seconds,deadline in [('ui001',47,60),('sleep4',6,15)]:
            command,plan=prepare.render(RUN,profile)
            self.assertLessEqual(plan['max_physical_line_bytes'],600)
            self.assertLess(plan['tx_bytes'],32768)
            self.assertEqual(shlex.split(command)[:7],['timeout','-t',str(seconds),'-s','15','/bin/sh','-c'])
            self.assertEqual(plan['host_deadline'],deadline)
            self.assertEqual(subprocess.run(['/bin/sh','-n'],input=command.encode(),capture_output=True,timeout=2).returncode,0)
            self.assertFalse(plan['kill_escalation'])
            self.assertEqual(plan['target_writes'],[])
        command,_=prepare.render(prepare.CAP_RUN,'sleep4')
        self.assertEqual((HERE/'capability-probe.sh').read_text(),command)

    def test_host_timeout_does_not_signal_target_independent_timer_cleans_later(self):
        # Exact frozen Session times out first. Closing this modeled host handle sends
        # no TERM/HUP/CTRL-C. A local independent timeout shim later signals its OWN
        # shell, which attests/TERMs/reaps the fake child. No actual UART/CMU used.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            body,env,calls,production,plan=fixture(root,'normal',slow=True)
            shim=root/'timeout-shim'
            shim.write_text('#!'+sys.executable+'\n'+
                'import json,os,signal,subprocess,sys,time\n'
                'from pathlib import Path\n'
                'p=subprocess.Popen(sys.argv[5:])\n'
                'try: rc=p.wait(timeout=int(sys.argv[2])*0.03)\n'
                'except subprocess.TimeoutExpired:\n'
                ' Path(os.environ["UI001_FAKE_ROOT"],"remote-timer.json").write_text(json.dumps({"at":time.monotonic(),"signal":15}))\n'
                ' p.send_signal(signal.SIGTERM)\n'
                ' rc=p.wait(timeout=3)\n'
                'sys.exit(rc if rc>=0 else 128-rc)\n')
            shim.chmod(0o700)
            local=shlex.quote(str(shim))+' -t 47 -s 15 /bin/sh -c '+shlex.quote(body)
            class Transport:
                def __init__(self): self.child=None; self.sent=bytearray(); self.closed=False; self.seen=bytearray()
                def write(self,data):
                    self.sent.extend(data)
                    if not self.sent.endswith(b'\r'):
                        return len(data)
                    wire=self.sent.decode().removesuffix('\r')
                    wire=wire.replace(shlex.quote(production),shlex.quote(local),1)
                    self.child=subprocess.Popen(['/bin/sh','-c',wire],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
                    return len(data)
                def read(self,n):
                    if self.closed:return b''
                    if self.child is None:
                        time.sleep(0.001)
                        return b''
                    if select.select([self.child.stdout],[],[],0.01)[0]:
                        data=os.read(self.child.stdout.fileno(),n); self.seen.extend(data); return data
                    return b''
                def close(self):self.closed=True
            transport=Transport(); bundle=Bundle(root/'host-bundle','UI001 host-timeout local model','test')
            session=Session(transport,bundle,timeout=3.0); session.state='shell';session.identity={'uid':0}
            try:
                with self.assertRaises(UnknownOutcome):session.execute(production)
                transport.close(); host_closed=time.monotonic()
                self.assertEqual(session.state,'uncertain')
                self.assertTrue(transport.sent.endswith(b'\r'))
                tail=transport.child.communicate(timeout=5)[0]
                output=bytes(transport.seen)+tail
                timer=json.loads((root/'remote-timer.json').read_text())
                self.assertGreater(timer['at'],host_closed)
                self.assertEqual(timer['signal'],15)
                self.assertIn(b'cleanup=term_exit_verified',output)
                self.assertIn(b'reason=terminate',output)
                requested=calls.read_text().splitlines()
                self.assertEqual(len(requested),1)
                self.assertTrue(requested[0].startswith('-TERM '))
                self.assertEqual(bytes(transport.sent), (bundle.path/'tx.bin').read_bytes())
            finally:
                bundle.finish('unknown','intentional host deadline; later local target cleanup observed separately')
                if transport.child and transport.child.poll() is None:
                    os.killpg(transport.child.pid,signal.SIGKILL);transport.child.communicate(timeout=2)

    def synthetic_bundle(self,folder,output,command):
        token='c'*32; name=token+'.output.bin'
        (folder/name).write_bytes(output)
        m=dict(mode='live',outcome='completed',port_closed=True,
               identity=dict(uid=0,user='root',firmware='55.00.750B',flavor='cmu150_NA'),
               operations=[dict(nonce=token,command=command,outcome='completed',exit_status=0)],
               artifacts={name:dict(bytes=len(output),sha256=hashlib.sha256(output).hexdigest())})
        (folder/'manifest.json').write_text(json.dumps(m))

    def test_capability_gate_requires_exact_sleep4_profile_and_verified_reap(self):
        command,_=prepare.render(prepare.CAP_RUN,'sleep4')
        expected=(b'/bin/sleep'+bytes([0])+b'4'+bytes([0])).hex()
        prefix='UI001 '+prepare.CAP_RUN+' '
        lines=['PREP profile=sleep4 parent=100 tool=/bin/sleep sleep_seconds=4',
               'IDENTITY pid=101 ppid=100 start=123 cmdline_hex='+expected+' expected_hex='+expected,
               'READY pid=101 watchdog_seconds=1',
               'TERM_ID pid=101 ppid=100 start=123 cmdline_hex='+expected,
               'TERM pid=101 rc=0','WAIT pid=101 rc=143',
               'RESULT profile=sleep4 cleanup=term_exit_verified cleanup_rc=0 dialog_rc=143 wrapper_rc=0 pid=101 ready=1']
        good=('\n'.join(prefix+line for line in lines)+'\n').encode()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.synthetic_bundle(folder,good,command)
            self.assertEqual(invoke.verify_capability_bundle(folder)['sleep_seconds'],4)
            for bad in (good.replace(b'ppid=100',b'ppid=999'),good.replace(b'sleep_seconds=4',b'sleep_seconds=3'),good.replace(b'WAIT pid=101 rc=143',b'WAIT pid=101 rc=0')):
                self.synthetic_bundle(folder,bad,command)
                with self.assertRaises(ValueError):invoke.verify_capability_bundle(folder)
            self.synthetic_bundle(folder,good,command)
            (folder/('c'*32+'.output.bin')).write_bytes(good+b'corrupt')
            with self.assertRaises(ValueError):invoke.verify_capability_bundle(folder)

    def test_driver_needs_ready_result_and_never_claims_visible_pass(self):
        command,_=prepare.render(RUN)
        prefix='UI001 '+RUN+' '
        lines=['READY pid=101 watchdog_seconds=40','WAIT pid=101 rc=143',
               'RESULT profile=ui001 cleanup=term_exit_verified cleanup_rc=0 dialog_rc=143 wrapper_rc=0 ready=1 pid=101']
        good=('\n'.join(prefix+line for line in lines)+'\n').encode()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.synthetic_bundle(folder,good,command)
            proof=invoke.verify_ui_lifecycle(folder,RUN)
            self.assertTrue(proof['lifecycle_ready_and_cleaned']);self.assertFalse(proof['visible_pass'])
            missing=('\n'.join(prefix+line for line in lines[1:])+'\n').encode()
            self.synthetic_bundle(folder,missing,command)
            with self.assertRaises(ValueError):invoke.verify_ui_lifecycle(folder,RUN)

    def test_live_capability_accepts_current_reviewed_paced_profile(self):
        from unittest.mock import Mock
        runner = Mock(return_value=1)  # Delegate boundary only: no UART/bundle opened.
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(invoke.runpy,"run_path",return_value={"main":runner}):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc=invoke.main(["--phase","capability","--live","--bundle",str(Path(temp)/"run")])
        self.assertEqual(rc,1)
        runner.assert_called_once()
        self.assertEqual(runner.call_args.args[0][runner.call_args.args[0].index("--deadline")+1],"15")

    def test_review_default_does_not_load_live_runner(self):
        with patch.object(invoke.runpy,'run_path',side_effect=AssertionError('live runner loaded')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(invoke.main(['--phase','capability']),0)
            self.assertFalse(json.loads(out.getvalue())['opens_port'])


if __name__=='__main__':unittest.main()
