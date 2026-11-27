"""Unit tests for tests/host_bins.py and tests/run_offline.py sharding/error safety."""

import concurrent.futures
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import host_bins, run_offline


class OfflineRunnerTests(unittest.TestCase):
    def test_shards_partition_all_discovered_cases_disjointly(self):
        tests_dir = str(run_offline.ROOT / "tests")
        with (
            mock.patch.dict(os.environ, {"OC_WORKSPACE": str(run_offline.ROOT)}),
            mock.patch.object(
                run_offline.sys, "path", [tests_dir, str(run_offline.ROOT), *run_offline.sys.path]
            ),
        ):
            suite = unittest.defaultTestLoader.discover(
                tests_dir, top_level_dir=str(run_offline.ROOT)
            )
        expected = sorted(case.id() for case in run_offline._iter_cases(suite))
        failed_all, shards_all = run_offline._build_shards(suite)
        self.assertEqual(failed_all, [])
        got_all = sorted(tid for shard in shards_all for tid in shard)
        self.assertEqual(got_all, expected)

        # 3-way sharding produces an exact disjoint partition of all tests.
        seen: list[str] = []
        for idx in (1, 2, 3):
            failed, shards = run_offline._build_shards(suite, shard_index=idx, shard_total=3)
            self.assertEqual(failed, [])
            seen.extend(tid for shard in shards for tid in shard)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(sorted(seen), expected)

    def test_failed_test_cases_preserved_directly_without_reload(self):
        failed = unittest.loader._FailedTest(
            "broken_mod", ImportError("synthetic missing dependency")
        )
        suite = unittest.TestSuite([failed])
        failed_out, shards = run_offline._build_shards(suite, shard_index=1, shard_total=3)
        self.assertEqual(failed_out, [failed])
        self.assertEqual(shards, [])
        failed_2, _ = run_offline._build_shards(suite, shard_index=2, shard_total=3)
        self.assertEqual(failed_2, [])

    def test_parse_shard_spec_validation(self):
        self.assertEqual(run_offline._parse_shard_spec(None), (1, 1))
        self.assertEqual(run_offline._parse_shard_spec("2/3"), (2, 3))
        for bad in ("0/3", "4/3", "1/0", "abc", "1/2/3"):
            with self.assertRaises(ValueError):
                run_offline._parse_shard_spec(bad)

    @unittest.skipUnless(shutil.which("clang"), "Clang required")
    def test_host_bins_thread_safe_cold_cache_header_invalidation_and_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            src = Path(tmp) / "hello.c"
            hdr = Path(tmp) / "hello.h"
            hdr.write_text("#define VAL 1\n")
            src.write_text('#include "hello.h"\nint main(void) { return VAL; }\n')
            with mock.patch.dict(os.environ, {"OC_HOST_BIN_CACHE": str(cache)}):
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                    paths = list(
                        pool.map(
                            lambda _: host_bins._build_cached(
                                "hello", [src], ["-I", tmp], extra_deps=[hdr]
                            ),
                            range(6),
                        )
                    )
                self.assertEqual(len(set(paths)), 1)
                p1 = paths[0]
                self.assertTrue(p1.is_file())
                # Changing a tracked header must invalidate the cache key.
                hdr.write_text("#define VAL 2\n")
                p2 = host_bins._build_cached("hello", [src], ["-I", tmp], extra_deps=[hdr])
                self.assertNotEqual(p1, p2)
                # Compile error must surface clang diagnostics (not swallow stderr).
                bad = Path(tmp) / "bad.c"
                bad.write_text("int main(void) { return undeclared_sym; }\n")
                with self.assertRaises(RuntimeError) as caught:
                    host_bins._build_cached("bad", [bad], [])
                self.assertIn("undeclared_sym", str(caught.exception))
