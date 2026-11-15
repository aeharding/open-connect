import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from open_connect.firmware55 import javascript as patch


class HookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("CMU_SYSTEM_APP") or not os.environ.get("CMU_BASE_APP"):
            raise unittest.SkipTest(
                "private inputs not supplied; run intro-handoff/check.py --help"
            )
        cls.original = Path(os.environ["CMU_SYSTEM_APP"])
        cls.base_app = Path(os.environ["CMU_BASE_APP"])
        cls.node = os.environ.get("CMU_NODE", "node")

    def test_exact_insertion_and_refuse_unknown(self):
        o = self.original.read_bytes()
        c, at, insert = patch.patch(o)
        self.assertEqual(c[:at] + c[at + len(insert) :], o)
        for b in (c, o + b" ", b""):
            with self.assertRaises(ValueError):
                patch.patch(b)

    def test_real_private_base_dispatcher(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "candidate.js"
            p.write_bytes(patch.patch(self.original.read_bytes())[0])
            subprocess.run([self.node, "--check", str(p)], check=True)
            subprocess.run(
                [
                    self.node,
                    str(Path(__file__).parent / "fixtures/disclaimer-behavior.js"),
                    str(p),
                    str(self.base_app),
                ],
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
