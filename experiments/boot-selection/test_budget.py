"""Real shell/file ledger tests; only uid/stat/mount/boot inputs are host shims."""
import subprocess
import unittest

import budget
import prototype
import test_selector


class BudgetTests(unittest.TestCase):
    GEN = "0123456789abcdef0123456789abcdef"
    A = "11111111-1111-1111-1111-111111111111"
    B = "22222222-2222-2222-2222-222222222222"
    C = "33333333-3333-3333-3333-333333333333"

    def setUp(self):
        self.fixture = test_selector.SelectorTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.d, self.env = self.fixture.d, self.fixture.env
        self.env.pop("COMMON_LOG_LEVEL", None)
        self.boot = self.fixture.r / "boot-id"
        self.boot.write_text(self.A + "\n")
        self.count = self.fixture.r / "flush-count"
        flush = f"""#!/bin/sh
n=0
if test -f {self.count}; then n=$(cat {self.count}); fi
n=$((n + 1));echo "$n" > {self.count}
test "$n" != "DOLLAR{{OC_FAIL_AT-0}}" || exit 8
exec {self.fixture.real} "$@"
""".replace("DOLLAR", "$").encode()
        self.artifacts = {"flush": flush, "generation.conf": b"configuration\n",
                          "mmui.so": b"plugin", "bootstrap.so": b"native module",
                          "index.html": b"index", "probe.js": b"JS module"}
        for name, content in self.artifacts.items():
            p = self.d / name
            p.write_bytes(content)
            p.chmod(0o700 if name == "flush" else 0o600)
        (self.d / "policy").write_bytes(budget.initial_record(self.GEN))
        (self.d / "policy").chmod(0o600)
        directory = "/tmp/mnt/data_persist/oc-boot-" + self.GEN
        code = budget.render(directory, self.artifacts, 2).decode()
        code = code.replace(directory, str(self.d))
        code = code.replace(prototype.MOUNT_GUARD, ": # actual-mount boundary shim")
        code = code.replace('for p in /tmp /tmp/mnt /tmp/mnt/data_persist "$D"; do',
                            'for p in "$D"; do')
        code = code.replace("BOOT_FILE=/proc/sys/kernel/random/boot_id", "BOOT_FILE=" + str(self.boot))
        code = code.replace("PATH=/bin:/sbin:/usr/bin:/usr/sbin", "PATH=" + self.env["PATH"])
        self.script = self.d / "select.sh"
        self.script.write_text(code)
        self.script.chmod(0o600)
        self.parent = self.fixture.parent
        self.parent.write_text("SMCFG_NORMALMODE=/jci/sm/sm.conf\n" +
            budget.hook(str(self.d), self.script.read_bytes(), "Warn").replace(
                "/bin/busybox", str(self.fixture.bin / "busybox")) +
            'printf "CHOSEN|%s\\n" "$SMCFG_NORMALMODE"\n' +
            'printf "LEVEL|%s\\n" "DOLLAR{COMMON_LOG_LEVEL-unset}"\n'.replace("DOLLAR", "$"))

    def run_script(self, *args, ok=True, **env):
        r = subprocess.run(["/bin/sh", str(self.script), *args],
                           env=dict(self.env, **env), capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode == 0, ok, r.stdout + r.stderr)
        return r.stdout

    def select(self, boot, selected=True, **env):
        self.boot.write_text(boot + "\n")
        r = subprocess.run(["/bin/sh", str(self.parent)], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        path = str(self.d / "generation.conf") if selected else "/jci/sm/sm.conf"
        self.assertIn("CHOSEN|" + path + "\n", r.stdout)
        self.assertIn("LEVEL|" + ("Warn" if selected else "unset") + "\n", r.stdout)
        return r.stdout

    def record(self):
        return (self.d / "policy").read_bytes()

    def confirm(self, boot=None, epoch="0", ok=True):
        return self.run_script("CONFIRM", self.GEN, epoch, boot or self.A, ok=ok)

    def test_unconfirmed_generation_only_gets_one_start(self):
        initial = self.record()
        self.run_script()
        self.assertEqual(self.record(), initial)
        self.select(self.A)
        charged = self.record()
        self.select(self.B, selected=False)
        self.assertEqual(self.record(), charged)
        self.run_script("RENEW", self.GEN, "0", self.B, ok=False)
        self.assertEqual(self.record(), charged)

    def test_ready_confirmation_never_refunds_and_late_reset_exhausts(self):
        self.select(self.A)
        self.confirm()
        first = self.record()
        self.assertIn(b"|0|confirmed|1|" + self.A.encode(), first)
        self.confirm()
        self.assertEqual(self.record(), first)
        self.select(self.A, selected=False)
        self.select(self.B)
        self.confirm(self.B)
        second = self.record()
        self.assertIn(b"|0|confirmed|2|" + self.B.encode(), second)
        # A late failure, warm reboot or unknown reset all reach the same selector.
        for boot in (self.C, self.A):
            self.select(boot, selected=False)
            self.run_script("STATUS")
            self.assertEqual(self.record(), second)

    def test_explicit_epoch_renewal_is_bound_and_cannot_replay(self):
        self.select(self.A)
        self.confirm()
        self.select(self.B)
        self.boot.write_text(self.C + "\n")
        before = self.record()
        for args in [("RENEW", "f" * 32, "0", self.C),
                     ("RENEW", self.GEN, "1", self.C),
                     ("RENEW", self.GEN, "0", self.B),
                     ("CONFIRM", self.GEN, "0", self.B)]:
            self.run_script(*args, ok=False)
            self.assertEqual(self.record(), before)
        self.run_script("RENEW", self.GEN, "0", self.C)
        renewed = self.record()
        self.assertIn(b"|1|confirmed|0|" + self.C.encode(), renewed)
        self.run_script("RENEW", self.GEN, "0", self.C, ok=False)
        self.assertEqual(self.record(), renewed)
        self.select(self.C, selected=False)
        self.select(self.A)
        self.confirm(self.A, epoch="1")
        self.assertIn(b"|1|confirmed|1|" + self.A.encode(), self.record())

    def test_concurrent_selections_admit_at_most_one(self):
        processes = [subprocess.Popen(["/bin/sh", str(self.script), "SELECT"],
                       env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        outputs = [p.communicate(timeout=10) for p in processes]
        self.assertEqual(sum(p.returncode == 0 for p in processes), 1, outputs)
        self.assertIn(b"|trial|1|" + self.A.encode(), self.record())
        self.select(self.A, selected=False)

    def test_concurrent_renewals_never_replay_or_reselect_same_boot(self):
        self.select(self.A)
        self.confirm()
        processes = [subprocess.Popen(["/bin/sh", str(self.script), "RENEW", self.GEN, "0", self.A],
                       env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        outputs = [p.communicate(timeout=10) for p in processes]
        self.assertEqual(sum(p.returncode == 0 for p in processes), 1, outputs)
        self.assertIn(b"|1|confirmed|0|" + self.A.encode(), self.record())
        self.select(self.A, selected=False)

    def test_flush_failures_do_not_admit_effects(self):
        for fail in (1, 2, 3):
            with self.subTest(flush_call=fail):
                self.count.unlink(missing_ok=True)
                (self.d / "policy").write_bytes(budget.initial_record(self.GEN))
                self.select(self.A, selected=False, OC_FAIL_AT=str(fail))
                self.assertEqual((self.d / "policy.lock").exists(), fail < 3)
                if fail == 1:
                    self.assertEqual(self.record(), budget.initial_record(self.GEN))
                    self.assertTrue((self.d / "policy.next").is_file())
                else:
                    self.assertIn(b"|trial|1|" + self.A.encode(), self.record())
                # Before the commit: persistent lock/pending file refuses.
                # After the commit: charged trial and/or lock refuses.
                self.select(self.B, selected=False)
                for name in ("policy.next",):
                    (self.d / name).unlink(missing_ok=True)
                if (self.d / "policy.lock").exists():
                    (self.d / "policy.lock").rmdir()

    def test_corruption_pending_lock_and_symlink_preserve_state(self):
        p = self.d / "policy"
        original = p.read_bytes()
        for content in (original.replace(b"|0|trial|0|", b"|0|trial|2|"),
                        original + b"x", original[:-1], original.replace(self.GEN.encode(), b"f" * 32)):
            p.write_bytes(content)
            self.select(self.A, selected=False)
            self.assertEqual(p.read_bytes(), content)
        p.write_bytes(original)
        saved = self.d / "saved-policy"
        p.rename(saved)
        p.symlink_to(saved)
        self.select(self.A, selected=False)
        self.assertEqual(saved.read_bytes(), original)
        p.unlink()
        saved.rename(p)
        (self.d / "policy.lock").mkdir()
        self.select(self.A, selected=False)
        self.assertEqual(p.read_bytes(), original)

    def test_changed_dependency_cannot_charge_or_select(self):
        p = self.d / "bootstrap.so"
        p.write_bytes(b"changed")
        before = self.record()
        self.select(self.A, selected=False)
        self.assertEqual(self.record(), before)
        self.assertTrue((self.d / "policy.lock").is_dir())


if __name__ == "__main__":
    unittest.main()
