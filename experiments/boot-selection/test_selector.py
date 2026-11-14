"""Exercise the real selector/parent shell with local files and OS-boundary shims."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import prototype


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="oc-selector-")
        self.addCleanup(self.tmp.cleanup)
        self.r = Path(self.tmp.name).resolve()
        self.d = self.r / "persist"
        self.d.mkdir(mode=0o700)
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.real = self.r / "real-flush"
        subprocess.run([shutil.which("clang") or "cc", "-DOC_HOST", str(prototype.HERE / "flush.c"),
                        "-o", str(self.real)], check=True)
        flush = f"""#!/bin/sh
test "$1" != "$OC_FAIL_FLUSH" || exit 1
if test "$OC_HANG_FLUSH" = 1; then sleep 8; fi
exec {self.real} "$@"
""".encode()
        for name, data, mode in [("flush", flush, 0o700), ("generation.conf", b"stock\n", 0o600),
                                 ("armed", b"OC_TRIAL_1|test\n", 0o600)]:
            p = self.d / name
            p.write_bytes(data)
            p.chmod(mode)
        stub = self.bin / "boundary"
        stub.write_text("#!" + sys.executable + "\n" + r'''
import hashlib,os,signal,subprocess,sys
from pathlib import Path
name=Path(sys.argv[0]).name
a=sys.argv[1:]
if name=="busybox":name=a.pop(0)
if name=="id":print(0)
elif name=="readlink":print(Path(a[-1]).resolve())
elif name=="md5sum":print(hashlib.md5(sys.stdin.buffer.read()).hexdigest()+"  -")
elif name=="stat":
 s=Path(a[-1]).stat();f=a[1]
 for k,v in {"a":oct(s.st_mode&0o777)[2:],"u":0,"g":0,"h":s.st_nlink,"s":s.st_size}.items():
  f=f.replace("%"+k,str(v))
 print(f)
elif name=="timeout":
 assert a[:2]==["-t","5"]
 p=subprocess.Popen(a[2:],start_new_session=True)
 # Full selectors launch many Python boundary shims. Keep the actual five-second
 # budget; only the isolated descendant test opts into an accelerated timeout.
 try:rc=p.wait(timeout=float(os.environ.get("OC_TEST_TIMEOUT", "5")))
 except subprocess.TimeoutExpired:
  p.terminate();p.wait();rc=143
 sys.exit(rc)
else:raise ValueError(name)
''')
        stub.chmod(0o755)
        for name in ["id", "readlink", "md5sum", "stat", "busybox"]:
            (self.bin / name).symlink_to(stub)
        self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                        OC_FAIL_FLUSH="", OC_HANG_FLUSH="0")
        self.install_selector()

    def install_selector(self, dependencies=None, log_level=None):
        text = prototype.selector(str(self.d), b"stock\n", (self.d / "flush").read_bytes(),
                                  b"OC_TRIAL_1|test\n", dependencies)
        text = text.replace(prototype.MOUNT_GUARD, ": # mounted-volume boundary stub")
        text = text.replace('for p in /tmp /tmp/mnt /tmp/mnt/data_persist "$D"; do',
                            'for p in "$D"; do')
        text = text.replace("PATH=/bin:/sbin:/usr/bin:/usr/sbin", "PATH=" + self.env["PATH"])
        self.s = self.d / "select.sh"
        self.s.write_text(text)
        self.s.chmod(0o600)
        self.parent = self.r / "parent.sh"
        self.parent.write_text(
            "SMCFG_NORMALMODE=/jci/sm/sm.conf\n" +
            prototype.hook(str(self.d), self.s.read_bytes(), log_level).replace("/bin/busybox", str(self.bin / "busybox")) +
            'printf "CHOSEN|%s\\n" "$SMCFG_NORMALMODE"\n' +
            'printf "LEVEL|%s\\n" "${COMMON_LOG_LEVEL-unset}"\n')

    def run_parent(self, **env):
        r = subprocess.run(["/bin/sh", str(self.parent)], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def baseline(self, **env):
        out = self.run_parent(**env)
        self.assertIn("CHOSEN|/jci/sm/sm.conf\n", out)
        self.assertNotIn("OCBOOT|trial|", out)

    def test_select_once_then_next_process_baseline(self):
        first = self.run_parent()
        self.assertIn("OCBOOT|trial|consumed-before-services", first)
        self.assertIn("CHOSEN|" + str(self.d / "generation.conf"), first)
        self.assertFalse((self.d / "armed").exists())
        self.assertEqual((self.d / "spent").read_bytes(), b"OC_TRIAL_1|test\n")
        self.baseline()

    def test_consumed_before_failed_flush_and_timeout(self):
        for env in (dict(OC_FAIL_FLUSH="f"), dict(OC_FAIL_FLUSH="d"), dict(OC_HANG_FLUSH="1")):
            with self.subTest(env=env):
                self.baseline(**env)
                self.assertTrue((self.d / "spent").is_file())
                self.assertFalse((self.d / "armed").exists())
                self.baseline()
                (self.d / "spent").rename(self.d / "armed")
                if (self.d / "select.lock").exists():
                    (self.d / "select.lock").rmdir()

    def test_unknown_missing_symlink_and_lock_preserve_armed(self):
        armed = (self.d / "armed").read_bytes()
        for name in ("generation.conf", "flush", "select.sh", "armed"):
            p = self.d / name
            original = p.read_bytes()
            p.write_bytes(original + b"x")
            self.baseline()
            p.write_bytes(original)
        self.assertEqual((self.d / "armed").read_bytes(), armed)
        p = self.d / "generation.conf"
        p.rename(self.d / "save")
        p.symlink_to(self.d / "save")
        self.baseline()
        p.unlink()
        self.baseline()
        (self.d / "save").rename(p)
        (self.d / "select.lock").mkdir()
        self.baseline()
        self.assertEqual((self.d / "armed").read_bytes(), armed)

    def test_success_exit_required_and_descendant_cannot_hold_parent_pipe(self):
        for body in ("exit 9\n", "sleep 2 &\nwait\n"):
            self.s.write_text(body)
            self.parent.write_text(
                "SMCFG_NORMALMODE=/jci/sm/sm.conf\n" +
                prototype.hook(str(self.d), body.encode()).replace("/bin/busybox", str(self.bin / "busybox")) +
                'printf "CHOSEN|%s\\n" "$SMCFG_NORMALMODE"\n')
            started = __import__("time").monotonic()
            self.baseline(OC_TEST_TIMEOUT="0.8")
            self.assertLess(__import__("time").monotonic() - started, 1.8)


    def test_complete_generation_selects_environment_once(self):
        dependencies = {"mmui.so": b"plugin", "bootstrap.so": b"code",
                        "index.html": b"index", "probe.js": b"script"}
        for name, data in dependencies.items():
            p = self.d / name
            p.write_bytes(data)
            p.chmod(0o600)
        self.env.pop("COMMON_LOG_LEVEL", None)
        self.install_selector(dependencies, "Warn")
        first = self.run_parent()
        self.assertIn("OCBOOT|trial|", first)
        self.assertIn("LEVEL|Warn\n", first)
        second = self.run_parent()
        self.assertIn("CHOSEN|/jci/sm/sm.conf\n", second)
        self.assertIn("LEVEL|unset\n", second)
        self.assertNotIn("OCBOOT|trial|", second)

    def test_changed_generation_dependency_cannot_select_or_consume(self):
        dependencies = {"mmui.so": b"plugin", "bootstrap.so": b"code",
                        "index.html": b"index", "probe.js": b"script"}
        for name, data in dependencies.items():
            p = self.d / name
            p.write_bytes(data)
            p.chmod(0o600)
        self.env.pop("COMMON_LOG_LEVEL", None)
        self.install_selector(dependencies, "Warn")
        for name, original in dependencies.items():
            with self.subTest(dependency=name):
                p = self.d / name
                p.write_bytes(original + b"changed")
                out = self.run_parent()
                self.assertIn("CHOSEN|/jci/sm/sm.conf\n", out)
                self.assertIn("LEVEL|unset\n", out)
                self.assertFalse((self.d / "spent").exists())
                self.assertEqual((self.d / "armed").read_bytes(), b"OC_TRIAL_1|test\n")
                p.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
