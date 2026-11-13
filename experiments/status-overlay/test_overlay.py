import importlib.util
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'experiments/ui001'))
import overlay
import test_watchdog as existing
RUN='1234567890abcdef'*2


class OverlayTests(unittest.TestCase):
    def test_bounds_and_short_readable_default(self):
        for seconds in [0,9,16,40,True,12.5]:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):overlay.render(RUN,seconds)
        for title,text in [('bad\ntitle','ok'),('x'*25,'ok'),('ok','x'*161),('ok','a\nb\nc\nd'),('ok','bad\x00')]:
            with self.assertRaises(ValueError):overlay.render(RUN,title=title,text=text)
        command,plan=overlay.render(RUN)
        self.assertEqual(plan['seconds'],12);self.assertEqual(plan['remote_term_timeout'],19)
        self.assertEqual(plan['title'],'BENCH STATUS 12345678')
        self.assertNotIn(chr(10),plan['text'])
        self.assertLessEqual(len(plan['text']),32)
        self.assertIn('55.00.750B',plan['text'])
        self.assertIn('UART root',plan['text'])
        self.assertIn('2 files',plan['text'])
        self.assertLessEqual(plan['max_line_bytes'],600)
        self.assertEqual(plan['target_files'],[]);self.assertEqual(plan['browser_actions'],[])
        self.assertEqual(shlex.split(command)[:7],['timeout','-t','19','-s','15','/bin/sh','-c'])

    def test_quoting_preserves_literal_text_and_owned_cleanup(self):
        text="FW '55' $(printf BAD)\nUART: root\nFiles: 2"
        def rendered(run_id,profile='ui001'):return overlay.render(run_id,10,title="BENCH'S STATUS",text=text)
        with patch.object(existing.prepare,'render',side_effect=rendered):
            result=existing.WatchdogTests().run_fake()
        case=existing.WatchdogTests();case.assert_owned_term(result,0)
        event=next(e for e in result[3] if e['kind']=='ready')
        self.assertIn('--text='+text,event['args'])
        self.assertIn("--title=BENCH'S STATUS "+existing.RUN[:8],event['args'])
        self.assertIn(b'watchdog_seconds=10',result[1])

    def test_identity_mismatch_retains_no_signal_guard(self):
        with patch.object(existing.prepare,'render',side_effect=lambda run_id,profile='ui001':overlay.render(run_id,10)):
            rc,out,calls,events=existing.WatchdogTests().run_fake('wrong_cmdline')
        self.assertEqual(rc,77);self.assertEqual(calls,[])
        self.assertFalse(any(e['kind']=='term_received' for e in events))

    def test_early_failure_is_not_success(self):
        with patch.object(existing.prepare,'render',side_effect=lambda run_id,profile='ui001':overlay.render(run_id,10)):
            rc,out,calls,_=existing.WatchdogTests().run_fake('early_failure')
        self.assertEqual(rc,7);self.assertEqual(calls,[]);self.assertNotIn(b' READY ',out)


if __name__=='__main__':unittest.main()
