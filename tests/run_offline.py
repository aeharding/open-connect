"""Run offline tests in parallel; preserve exact source bytes BEFORE execution under runs/tests/."""

import argparse
import concurrent.futures
import datetime
import hashlib
import io
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import traceback
import unittest
from collections import defaultdict
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]

# Heavy classes whose individual tests are fully isolated (temp dirs only, no fixed ports).
# Note: InstallerService binds fixed localhost ports 15555/15557, so it intentionally stays
# out of HEAVY_CLASSES and executes inside a single unsplit shard.
HEAVY_CLASSES = {
    "tests.test_installer_boot_selection.NativeBootSelection",
    "tests.test_installer_native_maintenance.NativeMaintenance",
    "tests.test_installer_native_install.NativeInstall",
}

LONGEST_FIRST = ()


def _iter_cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_cases(item)
        else:
            yield item


def _parse_shard_spec(spec: str | None) -> tuple[int, int]:
    if not spec:
        return 1, 1
    parts = spec.split("/")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"invalid --shard specification {spec!r}; expected K/N (1-based)")
    index, total = int(parts[0]), int(parts[1])
    if total < 1 or index < 1 or index > total:
        raise ValueError(f"invalid --shard specification {spec!r}; expected 1 <= K <= N")
    return index, total


def _build_shards(
    suite, *, shard_index: int = 1, shard_total: int = 1
) -> tuple[list[unittest.TestCase], list[list[str]]]:
    failed_cases: list[unittest.TestCase] = []
    by_class: dict[str, list[str]] = defaultdict(list)
    for case in _iter_cases(suite):
        if isinstance(case, unittest.loader._FailedTest):
            failed_cases.append(case)
            continue
        test_id = case.id()
        cls_key = test_id.rsplit(".", 1)[0]
        by_class[cls_key].append(test_id)
    lpt_rank = {tid: idx for idx, tid in enumerate(LONGEST_FIRST)}
    all_shards: list[list[str]] = []
    emitted: set[str] = set()
    for tid in LONGEST_FIRST:
        cls_key = tid.rsplit(".", 1)[0]
        if tid in by_class.get(cls_key, ()):
            all_shards.append([tid])
            emitted.add(tid)
    ordered = sorted(
        by_class.items(),
        key=lambda kv: (0 if kv[0] in HEAVY_CLASSES else 1, -len(kv[1]), kv[0]),
    )
    for cls_key, ids in ordered:
        remaining = [tid for tid in ids if tid not in emitted]
        if not remaining:
            continue
        remaining.sort(key=lambda tid: (lpt_rank.get(tid, 999), tid))
        step = 1 if cls_key in HEAVY_CLASSES else len(remaining)
        for i in range(0, len(remaining), step):
            all_shards.append(remaining[i : i + step])
    if shard_total > 1:
        selected = [s for i, s in enumerate(all_shards) if (i % shard_total) == (shard_index - 1)]
        # Run discovery-time _FailedTest cases on shard 1 so CI never hides import/syntax errors.
        return (failed_cases if shard_index == 1 else []), selected
    return failed_cases, all_shards


def _run_shard(args):
    shard_idx, test_ids, root_str = args
    os.chdir(root_str)
    for entry in (root_str, str(Path(root_str) / "tests")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromNames(test_ids)
    buf = io.StringIO()
    result = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    return (
        shard_idx,
        result.testsRun,
        len(result.failures),
        len(result.errors),
        len(result.skipped),
        result.wasSuccessful(),
        buf.getvalue(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline tests with durable evidence.")
    parser.add_argument(
        "--shard",
        default=os.environ.get("OC_TEST_SHARD"),
        help="Optional 1-based shard selector K/N (e.g. 1/3) for CI matrix parallelization.",
    )
    args = parser.parse_args(argv)
    shard_index, shard_total = _parse_shard_spec(args.shard)

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ["OC_WORKSPACE"] = str(ROOT)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = ROOT / "runs/tests" / stamp
    path.mkdir(parents=True, mode=0o700)
    source = {}
    copies = {}
    for pattern in ("tooling/open_connect/**/*.py", "tests/*.py"):
        for p in sorted(ROOT.glob(pattern)):
            data = p.read_bytes()
            name = str(p.relative_to(ROOT))
            h = hashlib.sha256(data).hexdigest()
            target = path / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            source[name] = h
            copies[name] = dict(bytes=len(data), sha256=h, snapshot=str(target.relative_to(path)))

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    workers = int(os.environ.get("OC_TEST_WORKERS") or min(os.cpu_count() or 4, 12))
    workers = max(1, workers)

    bin_cache = Path(tempfile.mkdtemp(prefix="oc-offline-bins-")).resolve()
    os.environ["OC_HOST_BIN_CACHE"] = str(bin_cache)
    t0 = time.monotonic()

    tests_run = 0
    failures = 0
    errors = 0
    skipped = 0
    passed = True
    log_parts: list[str] = []
    try:
        # Pre-warm shared host binaries once before fanning out across workers.
        if shutil.which("clang"):
            from tests.host_bins import (
                host_api,
                host_boot_select,
                host_flush,
                host_ignition,
                host_install,
            )

            host_flush()
            host_boot_select()
            host_api()
            host_install()
            host_ignition()

        failed_cases, shards = _build_shards(
            suite, shard_index=shard_index, shard_total=shard_total
        )
        # Run any discovery-time _FailedTest cases directly in the parent so real
        # ImportError/SyntaxError tracebacks are preserved verbatim.
        if failed_cases:
            fail_buf = io.StringIO()
            fail_res = unittest.TextTestRunner(stream=fail_buf, verbosity=2).run(
                unittest.TestSuite(failed_cases)
            )
            tests_run += fail_res.testsRun
            failures += len(fail_res.failures)
            errors += len(fail_res.errors)
            skipped += len(fail_res.skipped)
            passed = passed and fail_res.wasSuccessful()
            log_parts.append(fail_buf.getvalue())

        if workers == 1:
            seq_ids = [tid for shard in shards for tid in shard]
            if seq_ids:
                seq_suite = unittest.defaultTestLoader.loadTestsFromNames(seq_ids)
                log_buf = io.StringIO()
                result = unittest.TextTestRunner(stream=log_buf, verbosity=2).run(seq_suite)
                tests_run += result.testsRun
                failures += len(result.failures)
                errors += len(result.errors)
                skipped += len(result.skipped)
                passed = passed and result.wasSuccessful()
                log_parts.append(log_buf.getvalue())
        elif shards:
            results: list[tuple[int, int, int, int, int, bool, str]] = []
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
                future_map = {
                    pool.submit(_run_shard, (idx, ids, str(ROOT))): (idx, ids)
                    for idx, ids in enumerate(shards)
                }
                for fut in concurrent.futures.as_completed(future_map):
                    idx, ids = future_map[fut]
                    try:
                        results.append(fut.result())
                    except Exception:
                        tb = traceback.format_exc()
                        results.append(
                            (
                                idx,
                                0,
                                0,
                                1,
                                0,
                                False,
                                f"\nERROR: worker crashed running shard {idx} ({ids}):\n{tb}\n",
                            )
                        )
            results.sort(key=lambda r: r[0])
            tests_run += sum(r[1] for r in results)
            failures += sum(r[2] for r in results)
            errors += sum(r[3] for r in results)
            skipped += sum(r[4] for r in results)
            passed = passed and all(r[5] for r in results)
            log_parts.extend(r[6] for r in results)
    except Exception:
        errors += 1
        passed = False
        log_parts.append(f"\nERROR: offline runner aborted:\n{traceback.format_exc()}\n")
    finally:
        shutil.rmtree(bin_cache, ignore_errors=True)

    elapsed = time.monotonic() - t0
    shard_label = f" (shard {shard_index}/{shard_total})" if shard_total > 1 else ""
    summary = (
        f"\n{'=' * 70}\n"
        f"Ran {tests_run} tests across {workers} workers{shard_label} in {elapsed:.3f}s\n\n"
        f"{'OK' if passed else 'FAILED'} "
        f"(failures={failures}, errors={errors}, skipped={skipped})\n"
    )
    full_log = "".join(log_parts) + summary
    (path / "tests.txt").write_text(full_log)
    stable = all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in source.items()
    )
    manifest = dict(
        question="Do the host CLI, bench profile and UART/file operations pass offline?",
        firmware_scope="74.00.324A cmu150_NA; no real device used",
        mode="offline_only",
        hardware_opened=False,
        camera_opened=False,
        synthetic_pty_only=True,
        command="python tests/run_offline.py"
        + (f" --shard {shard_index}/{shard_total}" if shard_total > 1 else ""),
        shard=f"{shard_index}/{shard_total}",
        workers=workers,
        started_at=stamp,
        ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        tests=tests_run,
        failures=failures,
        errors=errors,
        passed=passed,
        python=sys.version,
        pyserial=serial.VERSION,
        platform=platform.platform(),
        source_sha256=source,
        source_copies=copies,
        source_bytes_stable_during_tests=stable,
        test_log_sha256=hashlib.sha256((path / "tests.txt").read_bytes()).hexdigest(),
        cleanup="Owned PTY children terminated/reaped and temp bundles/locks removed; no real UART/camera",
        interpretation="Host/PTY evidence only; no live calibration/CMU flow-control or recovery claim",
    )
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(full_log)
    print("DURABLE TEST EVIDENCE:", path)
    assert stable, "source changed during tests"
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
