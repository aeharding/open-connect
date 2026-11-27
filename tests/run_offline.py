"""Run offline tests in parallel; preserve exact source bytes BEFORE execution under runs/tests/."""

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
import unittest
from collections import defaultdict
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]


def _iter_cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_cases(item)
        else:
            yield item


HEAVY_CLASSES = {
    "tests.test_installer_boot_native.NativeBootPlan",
    "tests.test_installer_transaction.InstallerTransaction",
    "tests.test_installer_boot.InstallerBoot",
    "tests.test_installer_boot_selection.NativeBootSelection",
    "tests.test_installer_dvd_upgrade.DVDUpgrade",
    "tests.test_installer_initial.InitialInstall",
}

# Longest individual tests scheduled first (LPT) so workers never hit a late single-test tail.
LONGEST_FIRST = (
    "tests.test_installer_boot_native.NativeBootPlan.test_retained_touch_changed_pin_recovers_and_usb_uninstalls_across_cuts",
    "tests.test_installer_boot_native.NativeBootPlan.test_touch_recovery_retires_real_publisher_stages_across_policy_cuts",
    "tests.test_installer_boot_native.NativeBootPlan.test_interrupted_touch_disable_changed_pin_recovers_then_uninstalls",
    "tests.test_installer_dvd_upgrade.DVDUpgrade.test_dev19_dev20_install_downgrade_and_uninstall_preserve_originals",
    "tests.test_installer_boot_native.NativeBootPlan.test_retained_touch_changed_pin_recovery_refuses_every_third_target",
    "tests.test_installer_boot_native.NativeBootPlan.test_touch_stage_retirement_flush_failure_keeps_old_oc1_across_retries",
    "tests.test_installer_boot_native.NativeBootPlan.test_touch_recovery_checks_restore_stage_inode_identity",
    "tests.test_installer_initial.InitialInstall.test_initial_cuts_retry_with_replacement_media",
    "tests.test_installer_transaction.InstallerTransaction.test_failed_legacy_record_rename_restores_only_definite_unchanged_authority",
    "tests.test_installer_transaction.InstallerTransaction.test_all_six_touch_transitions_for_each_baseline_nvram",
)


def _build_shards(suite) -> list[list[str]]:
    by_class: dict[str, list[str]] = defaultdict(list)
    for case in _iter_cases(suite):
        test_id = case.id()
        cls_key = test_id.rsplit(".", 1)[0]
        by_class[cls_key].append(test_id)
    lpt_rank = {tid: idx for idx, tid in enumerate(LONGEST_FIRST)}
    shards: list[list[str]] = []
    # Emit the longest individual tests at the very front of the queue (LPT scheduling).
    emitted: set[str] = set()
    for tid in LONGEST_FIRST:
        cls_key = tid.rsplit(".", 1)[0]
        if tid in by_class.get(cls_key, ()):
            shards.append([tid])
            emitted.add(tid)
    # Schedule remaining heavy classes at 1-test granularity, then lighter classes whole.
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
            shards.append(remaining[i : i + step])
    return shards


def _run_shard(args):
    shard_idx, test_ids, root_str = args
    os.chdir(root_str)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
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


def main() -> int:
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

    bin_cache = Path(tempfile.mkdtemp(prefix="oc-offline-bins-"))
    os.environ["OC_HOST_BIN_CACHE"] = str(bin_cache)
    t0 = time.monotonic()
    try:
        # Pre-warm shared host binaries once before fanning out across workers.
        if shutil.which("clang"):
            from tests.host_bins import host_api, host_boot_select, host_flush

            host_flush()
            host_boot_select()
            host_api()

        if workers == 1:
            log_buf = io.StringIO()
            result = unittest.TextTestRunner(stream=log_buf, verbosity=2).run(suite)
            tests_run = result.testsRun
            failures = len(result.failures)
            errors = len(result.errors)
            passed = result.wasSuccessful()
            full_log = log_buf.getvalue()
        else:
            shards = _build_shards(suite)
            results = []
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
                tasks = [(idx, ids, str(ROOT)) for idx, ids in enumerate(shards)]
                for item in pool.map(_run_shard, tasks):
                    results.append(item)
            results.sort(key=lambda r: r[0])
            tests_run = sum(r[1] for r in results)
            failures = sum(r[2] for r in results)
            errors = sum(r[3] for r in results)
            skipped = sum(r[4] for r in results)
            passed = all(r[5] for r in results)
            elapsed = time.monotonic() - t0
            summary = (
                f"\n{'=' * 70}\n"
                f"Ran {tests_run} tests across {workers} workers in {elapsed:.3f}s\n\n"
                f"{'OK' if passed else 'FAILED'} "
                f"(failures={failures}, errors={errors}, skipped={skipped})\n"
            )
            full_log = "".join(r[6] for r in results) + summary
    finally:
        shutil.rmtree(bin_cache, ignore_errors=True)

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
        command="python tests/run_offline.py",
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
