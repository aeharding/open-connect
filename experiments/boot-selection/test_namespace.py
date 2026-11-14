"""Check ordering and failure behavior without host namespace privileges."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name("namespace.c")


class NamespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        directory = Path(cls.tmp.name)
        harness = directory / "harness.c"
        harness.write_text(r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define OC_TEST
#include "namespace.c"
static int calls;
static char **expected_env;
long oc_syscall(long n, long a, long b, long c, long d, long e) {
    if(n == 4) return c;
    calls++;
    if(n == 337) {
        assert(calls == 1 && a == 0x20000 && !b && !c && !d && !e);
        puts("unshare");
        return getenv("FAIL_UNSHARE") ? -38 : 0;
    }
    if(n == 21) {
        assert(calls == 2 && !a && !strcmp((char *)b, "/") && !c);
        assert(d == 0x44000 && !e);
        puts("private");
        return getenv("FAIL_PRIVATE") ? -1 : 0;
    }
    assert(n == 11 && calls == 3 && !d && !e);
    assert(!strcmp((char *)a, "/bin/sh"));
    char **args = (char **)b;
    assert(!strcmp(args[0], "/bin/sh") && !strcmp(args[1], "script.sh") && !args[2]);
    assert((char **)c == expected_env);
    assert(!strcmp(expected_env[0], "KEPT=the value") && !expected_env[1]);
    puts("exec");
    return -2;
}
int main(int argc, char **argv) {
    char *env[] = {"KEPT=the value", NULL};
    expected_env = env;
    return run(argc, argv, env);
}
""")
        cls.binary = directory / "namespace-test"
        subprocess.run(
            [shutil.which("cc") or "cc", "-Wall", "-Wextra", "-Werror",
             "-I", str(SOURCE.parent.resolve()), str(harness), "-o", str(cls.binary)],
            check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def invoke(self, args, env=None):
        return subprocess.run([str(self.binary), *args], env=env, capture_output=True, text=True)

    def test_usage_has_no_namespace_or_mount_effect(self):
        for args in ([], ["relative"]):
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result.returncode, 64)
                self.assertEqual(result.stdout, "")

    def test_unshare_failure_cannot_mount_or_execute(self):
        result = self.invoke(["/bin/sh", "script.sh"], {"FAIL_UNSHARE": "1"})
        self.assertEqual(result.returncode, 38)
        self.assertEqual(result.stdout, "unshare\n")

    def test_private_failure_cannot_execute(self):
        result = self.invoke(["/bin/sh", "script.sh"], {"FAIL_PRIVATE": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "unshare\nprivate\n")

    def test_exec_gets_original_arguments_and_environment_after_isolation(self):
        result = self.invoke(["/bin/sh", "script.sh"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "unshare\nprivate\nexec\n")


if __name__ == "__main__":
    unittest.main()
