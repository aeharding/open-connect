#!/usr/bin/env python3
"""Focused offline candidate checks, source snapshots, compact review profile."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys

BOOT = Path(__file__).resolve().parent
ROOT = BOOT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    dependencies = json.loads((ROOT / "experiments/stock-warm-start/corrected-review.json").read_text())
    names = ["experiments/disclaimer-startup-trial/boot/" + x
             for x in ("observe.py", "test_candidate.py", "check.py", "README.md")]
    names += list(dependencies["source_pins"])
    names += ["experiments/stock-warm-start/corrected-review.json"]
    pins = {name: sha(ROOT / name) for name in names}
    run = BOOT / "checks" / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run.mkdir(parents=True)
    for name in names:
        target = run / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    argv = [sys.executable, "-B", "-m", "unittest", "-v", "test_candidate"]
    result = subprocess.run(argv, cwd=BOOT, capture_output=True)
    (run / "stdout.txt").write_bytes(result.stdout)
    (run / "stderr.txt").write_bytes(result.stderr)
    unchanged = all(sha(ROOT / name) == pin for name, pin in pins.items())
    code = result.returncode or (0 if unchanged else 1)
    manifest = dict(scope="OFFLINE synthetic evidence/fake port/camera only; no device opens or reboot",
                    command=argv, returncode=code, unchanged_sources=unchanged, source_sha256=pins)
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if code == 0:
        sys.path.insert(0, str(BOOT))
        import observe
        profile = observe.make_profile()
        profile.update(test_manifest=str((run / "manifest.json").relative_to(ROOT)),
                       test_manifest_sha256=sha(run / "manifest.json"),
                       apply_evidence_contract="README.md; exact three-field pointer and one actual target BIND line",
                       candidate_expected=dict(bytes=94055, md5=observe.CMD5, crc=observe.CCRC))
        (BOOT / "review.json").write_text(json.dumps(profile, indent=2) + "\n")
    print(json.dumps(dict(manifest=str(run / "manifest.json"), returncode=code,
                          review_profile=str(BOOT / "review.json") if code == 0 else None)))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
