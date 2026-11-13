"""Focused profile checks: real shell/DBus formatting and real CLI Bundle boundary."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oc_profile", HERE / "profile.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
from cmu_bench.session import verify_identity, wrap_command

INSTANCE = dict(boot="11111111-1111-1111-1111-111111111111", bus="a" * 32, owner=":1.26")
FAKE_DBUS = r'''
import json, os, sys
from pathlib import Path
path=Path(os.environ["FAKE_DBUS_STATE"])
d=json.loads(path.read_text()); a=sys.argv[1:]
if d.get("unavailable"):sys.exit(1)
method=next(x for x in a if x.startswith("org.freedesktop.DBus.") or x.endswith(".Request"))
sender="org.freedesktop.DBus"
if method.endswith("GetId"):value=d["bus"]
elif method.endswith("GetNameOwner"):value=d["owner"]
else:
 dest=next(x.split("=",1)[1] for x in a if x.startswith("--dest="))
 if dest!=d["owner"]:sys.exit(1)
 sender=d["owner"]; args=[x[7:] for x in a if x.startswith("string:")]
 if args[0]=="enableStatus":
  if "pending" in d:
   d["remaining"]-=1
   if d["remaining"]<=0:d["enabled"]=d.pop("pending")
  value=json.dumps({"enable":1 if d.get("malformed") else d["enabled"]},separators=(",",":"))
  if d.get("change_owner_on_read"):d["owner"]=":1.99"
 elif args[0]=="enable":
  wanted=json.loads(args[1])["enable"];d["mutations"].append(wanted)
  if d.get("delay"):d["pending"]=wanted;d["remaining"]=d["delay"]
  else:d["enabled"]=wanted
  value="bad" if d.get("bad_ack") else "{}"
 else:sys.exit(2)
path.write_text(json.dumps(d))
print("method return sender="+sender+" -> dest=:1.900 reply_serial=2")
print('   string "'+value+'"')
'''


class ShellSession:
    """Execute the actual rendered shell; only hardware paths/DBus are fixtures."""
    state = "shell"
    def __init__(self, root, bundle=None):
        self.root, self.bundle = root, bundle
        self.timeout = 40
    def execute(self, command):
        wrap_command(command, "a"*32)  # actual serial wire limits
        command = command.replace(p.RO, "test 1 = 1 || exit 70")
        command = command.replace(p.BOOT, shlex.quote(str(self.root/"boot")))
        env = dict(os.environ, PATH=str(self.root)+os.pathsep+os.environ["PATH"],
                   FAKE_DBUS_STATE=str(self.root/"dbus.json"))
        result = subprocess.run(["/bin/sh","-c",command],env=env,capture_output=True,timeout=10)
        if result.stderr:
            raise AssertionError(result.stderr.decode())
        return result.returncode, result.stdout
    def observe_prompt(self, solicit=False):
        if not solicit:raise AssertionError("test expected explicit idle-shell assertion")
    def identify(self):
        return verify_identity(b'uid=0(root) gid=0(root)\nJCI_SW_VER="MAZ_CMU-150_55.00.750"\nJCI_SW_VER_PATCH="B"\nJCI_SW_FLAVOR="cmu150_NA"\n')


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.data=self.root/"dbus.json"
        self.data.write_text(json.dumps(dict(INSTANCE,enabled=False,mutations=[])))
        (self.root/"boot").write_text(INSTANCE["boot"])
        exe=self.root/"dbus-send"
        exe.write_text("#!"+sys.executable+"\n"+FAKE_DBUS);exe.chmod(0o755)
        self.session=ShellSession(self.root)
        self.audio=p.Audio(self.session,time.monotonic()+60)
        self.store=p.Store(self.root/"private"/"profile.json")
    def tearDown(self):
        self.tmp.cleanup()
    def modify(self,**kwargs):
        data=json.loads(self.data.read_text());data.update(kwargs);self.data.write_text(json.dumps(data))
    def values(self):return json.loads(self.data.read_text())
    def runmode(self,mode):return p.transition(mode,self.audio,self.store,self.root/"run")

    def test_setup_repeat_status_teardown_real_shell(self):
        self.assertTrue(self.runmode("setup")["active"])
        self.assertTrue(self.runmode("setup")["owned"])
        self.assertTrue(self.runmode("status")["active"])
        self.assertFalse(self.runmode("teardown")["audio_enabled"])
        self.assertEqual(self.values()["mutations"],[True,False])
        self.assertEqual(self.runmode("teardown")["phase"],"off")
        self.assertEqual(self.values()["mutations"],[True,False])

    def test_already_enabled_not_owned_and_not_disabled(self):
        self.modify(enabled=True)
        self.assertFalse(self.runmode("setup")["owned"])
        self.assertTrue(self.runmode("teardown")["audio_enabled"])
        self.assertEqual(self.values()["mutations"],[])

    def test_delay_and_known_bad_ack_readback_no_resend(self):
        self.modify(delay=2,bad_ack=True)
        self.assertTrue(self.runmode("setup")["active"])
        self.assertEqual(self.values()["mutations"],[True])
        self.assertFalse(self.runmode("teardown")["audio_enabled"])
        self.assertEqual(self.values()["mutations"],[True,False])

    def test_stale_owner_teardown_does_not_disable_new_owner(self):
        self.runmode("setup")
        self.modify(owner=":1.99")
        result=self.runmode("teardown")
        self.assertTrue(result["expired_previous_instance"])
        self.assertTrue(result["audio_enabled"])
        self.assertFalse(result["owned"])
        self.assertEqual(self.values()["mutations"],[True])

    def test_mutation_guard_rejects_changed_owner(self):
        observed=self.audio.observe()
        self.modify(owner=":1.99")
        with self.assertRaises(p.Conflict):self.audio.set(observed["binding"],True)
        self.assertEqual(self.values()["mutations"],[])

    def test_invalid_status_and_changing_owner_are_readonly(self):
        for fault in ("malformed","unavailable","change_owner_on_read"):
            with self.subTest(fault=fault):
                flags=dict(malformed=False,unavailable=False,change_owner_on_read=False,owner=":1.26")
                flags[fault]=True
                self.modify(**flags)
                with self.assertRaises(p.Conflict):self.runmode("setup")
                self.assertEqual(self.values()["mutations"],[])

    def test_uncertain_tx_preserves_pending_then_teardown_can_reconcile(self):
        real=self.audio.set
        def ambiguous(instance,enabled):
            real(instance,enabled)
            raise p.UnknownOutcome("lost UART completion")
        with patch.object(self.audio,"set",side_effect=ambiguous):
            with self.assertRaises(p.UnknownOutcome):self.runmode("setup")
        self.assertEqual(self.store.load()["phase"],"setup_pending")
        with self.assertRaises(p.Conflict):self.runmode("setup")
        self.assertEqual(self.values()["mutations"],[True])
        self.assertFalse(self.runmode("teardown")["audio_enabled"])

    def test_damaged_receipt_and_symlink_refuse(self):
        self.runmode("setup")
        self.store.path.write_text('{"schema":1}')
        with self.assertRaises(p.Conflict):self.runmode("teardown")
        self.store.path.unlink();self.store.path.symlink_to(self.data)
        with self.assertRaises(p.Conflict):self.runmode("teardown")
        self.assertEqual(self.values()["mutations"],[True])

    def test_marker_integrity_and_deadline(self):
        token="b"*32
        row=b"BP1 "+token.encode()+b" field "+base64.b64encode(b"payload")+b"\r\n"
        self.assertEqual(p.records(b"logger-prefix:"+row,token,{"field"})["field"],b"payload")
        for raw in (row+row,row.replace(b"field",b"unknown"),row[:-4]):
            with self.assertRaises(p.Conflict):p.records(raw,token,{"field"})
        self.audio.deadline=time.monotonic()-1
        with self.assertRaises(p.Conflict):self.runmode("setup")
        self.assertEqual(self.values()["mutations"],[])

    def test_actual_cli_frontdoor_bundle_and_failed_open(self):
        class Port:
            closed=False
            def close(self):self.closed=True
        port=Port()
        fake_session=ShellSession(self.root)
        with patch.object(p,"open_adapter",return_value=port),patch.object(p,"Session",return_value=fake_session),patch.object(p,"AdapterLock",return_value=contextlib.nullcontext()),contextlib.redirect_stdout(io.StringIO()):
            code=p.main(["setup","--live","--bundle",str(self.root/"bundle"),"--state",str(self.store.path),"--solicit-prompt"])
        self.assertEqual(code,0)
        manifest=json.loads((self.root/"bundle/manifest.json").read_text())
        self.assertTrue(manifest["port_closed"]);self.assertTrue(port.closed)
        self.assertTrue(manifest["bench_profile"]["active"])
        with patch.object(p,"open_adapter",side_effect=OSError("offline")),patch.object(p,"AdapterLock",return_value=contextlib.nullcontext()),contextlib.redirect_stdout(io.StringIO()):
            code=p.main(["status","--live","--bundle",str(self.root/"failed"),"--state",str(self.store.path),"--owner","test"])
        self.assertEqual(code,1)
        self.assertEqual(json.loads((self.root/"failed/manifest.json").read_text())["outcome"],"failed")
        self.assertEqual(self.values()["mutations"],[True])

    def test_public_cli_dry_run_no_state_or_bundle(self):
        result=subprocess.run([sys.executable,str(HERE.parent/"scripts/oc"),"bench","setup","--state",str(self.store.path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        output=json.loads(result.stdout)
        self.assertEqual(output["outcome"],"dry_run_not_executed")
        self.assertFalse(output["executed"])
        self.assertFalse(output["state_written"])
        self.assertNotIn("state",output)
        self.assertFalse(output["opens_port"])
        self.assertFalse(self.store.path.exists())


if __name__=="__main__":unittest.main()
