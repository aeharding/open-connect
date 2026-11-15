"""Build and check the paired native/JS feature from explicit private OEM inputs."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from open_connect.paths import ROOT, source_name

from . import javascript as patch
from . import native

HERE = Path(__file__).resolve().parent
BASE_APP_SHA = "54c1e498bd430a59dccd3e204661d48864d093e6aa51999a5c35bccaa0801690"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-original", type=Path, required=True)
    parser.add_argument("--system-app", type=Path, required=True)
    parser.add_argument("--base-app", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="new private directory under runs/"
    )
    parser.add_argument("--clang")
    parser.add_argument("--objdump")
    parser.add_argument("--host-cc")
    parser.add_argument("--node")
    args = parser.parse_args()
    try:
        out = native.private_output(args.output)
        if not out.is_relative_to(patch.ROOT / "runs"):
            raise ValueError("paired output must be under runs/")
        native.guard(args.native_original.read_bytes())
        patch.patch(args.system_app.read_bytes())
        if hashlib.sha256(args.base_app.read_bytes()).hexdigest() != BASE_APP_SHA:
            raise ValueError("unsupported exact OEM55 BaseApp.js")
        clang = native.tool("clang", args.clang)
        objdump = native.tool("llvm-objdump", args.objdump)
        host_cc = native.tool("clang", args.host_cc)
        node = native.tool("node", args.node)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"checks not run: {exc}\n")

    out.mkdir(mode=0o700, parents=True)
    sources = [
        Path(patch.__file__),
        Path(__file__),
        ROOT / "tests/test_javascript.py",
        ROOT / "tests/fixtures/disclaimer-behavior.js",
    ]
    (out / "sources").mkdir()
    pins = {}
    for path in sources:
        data = path.read_bytes()
        (out / "sources" / path.name).write_bytes(data)
        pins[source_name(path)] = hashlib.sha256(data).hexdigest()
    result = dict(status="FAIL", live_authority=False, source_sha256=pins)
    try:
        cmd = [
            sys.executable,
            "-m",
            "open_connect.firmware55.check_native",
            "--original",
            str(args.native_original.resolve()),
            "--output",
            str(out / "native"),
            "--clang",
            clang,
            "--objdump",
            objdump,
            "--host-cc",
            host_cc,
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        (out / "native-check.stdout").write_text(run.stdout)
        (out / "native-check.stderr").write_text(run.stderr)
        if run.returncode:
            raise ValueError("native checks failed; see native-check.stdout/stderr")
        result["js_profile"] = patch.build(out / "js", args.system_app)
        env = dict(
            os.environ,
            CMU_SYSTEM_APP=str(args.system_app.resolve()),
            CMU_BASE_APP=str(args.base_app.resolve()),
            CMU_NODE=node,
            PYTHONDONTWRITEBYTECODE="1",
        )
        cmd = [sys.executable, "-B", "-m", "unittest", "-v", "test_javascript"]
        run = subprocess.run(
            cmd, cwd=ROOT / "tests", env=env, capture_output=True, text=True, timeout=30
        )
        (out / "js-check.stdout").write_text(run.stdout)
        (out / "js-check.stderr").write_text(run.stderr)
        if run.returncode:
            raise ValueError("JS checks failed; see js-check.stdout/stderr")
        result.update(
            status="PASS",
            node=dict(
                path=node, version=subprocess.check_output([node, "--version"], text=True).strip()
            ),
            base_app_sha256=BASE_APP_SHA,
            native_manifest="native/manifest.json",
            native_profile="native/candidate/profile.json",
        )
    except Exception as exc:
        result["error"] = str(exc)
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], output=str(out), error=result.get("error"))))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
