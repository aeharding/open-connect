"""Supervisor decisions with real shell, sockets, child exit and file flush."""
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import time
import unittest

import readiness
import test_receiver
import test_selector

BOOT = "01234567-89ab-cdef-0123-456789abcdef"
GEN = "a"*32
D = "/tmp/mnt/data_persist/oc-boot-"+GEN


class SupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_receiver.ReceiverTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        test_receiver.ReceiverTests.tearDownClass()

    def setUp(self):
        self.f = test_selector.SelectorTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.w = self.f.r / "work"
        self.boot = self.f.r / "boot"
        self.boot.write_text(BOOT+"\n")
        self.reboots = self.f.r / "reboots"
        self.reboot = self.f.r / "reboot"
        self.reboot.write_text("#!/bin/sh\nprintf 'requested\\n' >> "+shlex.quote(str(self.reboots))+"\n")
        self.reboot.chmod(0o700)
        self.binary = test_receiver.ReceiverTests.exe.read_bytes()
        p=self.f.d/"ready-receiver";p.write_bytes(self.binary);p.chmod(0o600)
        (self.f.bin/"timeout").symlink_to(self.f.bin/"boundary")
        with socket.socket() as s:
            s.bind(("127.0.0.1",0));self.port=s.getsockname()[1]
        self.install()

    def adapt(self, text):
        return (text.replace(D, str(self.f.d))
            .replace("W=/tmp/oc-health-$GEN", "W="+shlex.quote(str(self.w)))
            .replace("/tmp/oc-health-"+GEN, str(self.w))
            .replace("PATH=/bin:/sbin:/usr/bin:/usr/sbin", "PATH="+self.f.env["PATH"])
            .replace("cat /proc/sys/kernel/random/boot_id", "cat "+shlex.quote(str(self.boot)))
            .replace("/sbin/reboot", shlex.quote(str(self.reboot)))
            .replace("/bin/busybox", str(self.f.bin/"busybox")))

    def install(self, recover=True):
        text = self.adapt(readiness.watch(D,self.binary,port=self.port,deadline=5,recover=recover).decode())
        self.script=self.f.d/"ready-watch.sh";self.script.write_text(text);self.script.chmod(0o600)

    def call(self, mode, expected=0):
        if mode == "authorize":
            command = ["/bin/sh", "-c", "SMCFG_NORMALMODE=/jci/sm/sm.conf\n"+
                       self.adapt(readiness.commit(D))+"\noc_commit_selection"]
        else:
            command = ["/bin/sh",str(self.script),mode]
        p=subprocess.run(command,env=self.f.env,capture_output=True,text=True,timeout=8)
        self.assertEqual(p.returncode,expected,p.stdout+p.stderr)
        return p

    def finished(self):
        limit=time.monotonic()+8
        while time.monotonic()<limit:
            if (self.w/"watch-finished").exists():
                return
            time.sleep(0.03)
        self.fail("supervisor did not finish within its deadline")

    def test_real_parent_selects_only_after_prepare_and_authorize(self):
        boundary = self.f.bin / "boundary"
        boundary.write_text(boundary.read_text().replace(
            'assert a[:2]==["-t","5"]', 'assert a[0]=="-t" and a[1] in ("2","5")'))
        self.f.parent.write_text(
            "SMCFG_NORMALMODE=/jci/sm/sm.conf\n" +
            self.adapt(readiness.hook(D, self.f.s.read_bytes())) +
            'printf "CHOSEN|%s\\n" "$SMCFG_NORMALMODE"\n')
        output = self.f.run_parent()
        self.assertIn("OCBOOT|trial|consumed-before-services", output)
        self.assertIn("CHOSEN|"+str(self.f.d/"generation.conf"), output)
        self.assertTrue((self.f.d/"spent").is_file())
        self.assertEqual((self.w/"selected").read_text().strip(), GEN+"."+BOOT)
        self.call("cancel"); self.finished()
        self.f.baseline()
        self.assertFalse(self.reboots.exists())

    def test_real_parent_port_conflict_returns_baseline_with_spent_attempt(self):
        self.f.parent.write_text(
            "SMCFG_NORMALMODE=/jci/sm/sm.conf\n" +
            self.adapt(readiness.hook(D, self.f.s.read_bytes())) +
            'printf "CHOSEN|%s\\n" "$SMCFG_NORMALMODE"\n')
        with socket.socket() as s:
            s.bind(("127.0.0.1",self.port)); s.listen()
            self.f.baseline()
        self.finished()
        self.assertTrue((self.f.d/"spent").is_file())
        self.assertFalse((self.w/"selected").exists())
        self.assertFalse(self.reboots.exists())

    def test_success_requires_authorization_and_does_not_reboot(self):
        self.call("prepare");self.call("authorize")
        self.assertIn(GEN+"."+BOOT,(self.w/"session.js").read_text())
        with socket.create_connection(("127.0.0.1",self.port),timeout=2) as s:
            s.sendall(test_receiver.ReceiverTests.request(GEN+"."+BOOT));s.recv(256)
        self.finished()
        self.assertEqual((self.f.d/"health.result").read_text(),
                         f"OC_HEALTH_1|{GEN}|{BOOT}|ready|0\n")
        self.assertFalse(self.reboots.exists())

    def test_timeout_authorized_requests_once(self):
        self.call("prepare");self.call("authorize");self.finished()
        self.assertEqual(self.reboots.read_text(),"requested\n")
        self.assertIn("|failed|75\n",(self.f.d/"health.result").read_text())
        self.call("cancel",83)
        self.assertEqual(self.reboots.read_text(),"requested\n")

    def test_no_authorization_and_explicit_cancel_never_reboot(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                self.call("prepare")
                if cancel:
                    self.call("authorize");self.call("cancel")
                self.finished()
                self.assertFalse(self.reboots.exists())
                self.assertFalse((self.f.d/"health.result").exists())
                shutil.rmtree(self.w)

    def test_observation_timeout_and_stale_boot_never_reboot(self):
        self.install(recover=False)
        self.call("prepare");self.call("authorize");self.finished()
        self.assertIn("|failed|75\n",(self.f.d/"health.result").read_text())
        self.assertFalse(self.reboots.exists())
        shutil.rmtree(self.w);(self.f.d/"health.result").unlink()
        self.install(recover=True)
        self.call("prepare");self.call("authorize")
        self.boot.write_text("11111111-1111-1111-1111-111111111111\n")
        self.finished()
        self.assertFalse(self.reboots.exists())
        self.assertFalse((self.f.d/"health.result").exists())

    def test_receiver_exit_is_observed_by_separate_supervisor(self):
        self.call("prepare");self.call("authorize")
        worker=(self.w/"worker").read_text().strip()
        children=subprocess.check_output(["pgrep","-P",worker],text=True).split()
        self.assertEqual(len(children),1)
        child=int(children[0])
        command=subprocess.check_output(["ps","-p",str(child),"-o","command="],text=True)
        self.assertIn(str(self.w/"receiver"),command)
        os.kill(child,signal.SIGKILL)
        self.finished()
        self.assertEqual(self.reboots.read_text(),"requested\n")
        self.assertIn("|failed|",(self.f.d/"health.result").read_text())

    def test_evidence_failure_does_not_block_recovery_or_overwrite_conflict(self):
        for fail in ("f", "d", "existing"):
            with self.subTest(fail=fail):
                self.f.env["OC_FAIL_FLUSH"] = fail
                receipt = self.f.d/"health.result"
                if fail == "existing": receipt.write_text("preserve this")
                self.call("prepare"); self.call("authorize"); self.finished()
                self.assertEqual(self.reboots.read_text(), "requested\n")
                self.assertIn("evidence-failed", (self.w/"watch.log").read_text())
                if fail == "existing": self.assertEqual(receipt.read_text(),"preserve this")
                self.call("watch", 87)  # A repeated watcher cannot request a second reboot.
                self.assertEqual(self.reboots.read_text(), "requested\n")
                shutil.rmtree(self.w); receipt.unlink(); self.reboots.unlink()

    def test_parent_commit_refusal_never_leaves_late_authorization(self):
        self.call("prepare")
        (self.w/"decision.lock").mkdir()
        self.call("authorize", 1)
        self.assertFalse((self.w/"selected").exists())
        (self.w/"decision.lock").rmdir()
        self.finished()
        self.assertFalse(self.reboots.exists())
        self.assertFalse((self.w/"selected").exists())

    def test_port_conflict_cannot_authorize_startup(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1",self.port));s.listen()
            self.call("prepare",80)
            self.finished()
            self.call("authorize",1)
        self.assertFalse(self.reboots.exists())
        self.assertFalse((self.f.d/"health.result").exists())


if __name__=="__main__":
    unittest.main()
