"""Build the tested developer feature from explicit private firmware inputs.

This command runs on the host. Device operations are separate from building.
The target sources and private checks live in a source checkout selected with --workspace.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from .paths import verify_package

FIRMWARE = "55.00.750B NA/cmu150_NA"
INPUTS = {
    "autostart": "usr/bin/autostart",
    "config": "jci/sm/sm.conf",
    "native": "jci/mmui/uia/libjciuiasystem.so",
    "system_app": "jci/gui/apps/system/js/systemApp.js",
    "base_app": "jci/gui/framework/js/BaseApp.js",
    "plugin": "jci/mmui/svcjcimmui.so",
    "mmui_xml": "jci/mmui/mmui_config.xml",
    "index": "jci/gui/index.html",
}
# Runtime/build implementation dependencies; test-only edits do not invalidate a payload.
SOURCE_FILES = (
    "tooling/open_connect/__init__.py",
    "tooling/open_connect/__main__.py",
    "tooling/open_connect/bench.py",
    "tooling/open_connect/cli.py",
    "tooling/open_connect/device/__init__.py",
    "tooling/open_connect/device/boot.py",
    "tooling/open_connect/device/feature_state.py",
    "tooling/open_connect/device/feature_workflow.py",
    "tooling/open_connect/device/publication.py",
    "tooling/open_connect/device/records.py",
    "tooling/open_connect/device/staging.py",
    "tooling/open_connect/feature.py",
    "tooling/open_connect/files.py",
    "tooling/open_connect/firmware55/__init__.py",
    "tooling/open_connect/firmware55/anchors.py",
    "tooling/open_connect/firmware55/build_flush.py",
    "tooling/open_connect/firmware55/build_pair.py",
    "tooling/open_connect/firmware55/build_receiver.py",
    "tooling/open_connect/firmware55/check_native.py",
    "tooling/open_connect/firmware55/generation.py",
    "tooling/open_connect/firmware55/javascript.py",
    "tooling/open_connect/firmware55/native.py",
    "tooling/open_connect/firmware55/readiness.py",
    "tooling/open_connect/firmware55/selection.py",
    "tooling/open_connect/paths.py",
    "tooling/open_connect/session.py",
    "tooling/open_connect/startup.py",
    "tooling/open_connect/uart.py",
    "tooling/open_connect/usb.py",
    "cmu/features/disclaimer/native.c",
    "cmu/startup/flush.c",
    "cmu/startup/selector.sh.in",
    "cmu/startup/ready-watch.sh.in",
    "cmu/startup/publication.sh.in",
    "cmu/startup/ready-receiver.c",
    "cmu/adapters/fw55/home-ready.js",
    "cmu/adapters/fw55/system-app-path.js",
)

PAYLOAD_SOURCES = tuple(
    name for name in SOURCE_FILES if name.startswith(("tooling/open_connect/firmware55/", "cmu/"))
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workspace(path):
    root = path.resolve()
    verify_package(root)
    for name in (
        "pyproject.toml",
        "tooling/open_connect/firmware55/build_pair.py",
        "tooling/open_connect/firmware55/readiness.py",
        "cmu/startup/ready-receiver.c",
    ):
        if not (root / name).is_file():
            raise ValueError("use --workspace with an Open Connect source checkout")
    return root


def private_output(root, output):
    # Reject symlink traversal, including a dangling final symlink.
    absolute = output.absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise ValueError("output must not traverse a symlink")
    output = absolute.resolve()
    if not output.is_relative_to(root / "runs") or output == root / "runs":
        raise ValueError("generated OEM files must stay under WORKSPACE/runs/")
    if output.exists():
        raise ValueError("output already exists; choose a fresh directory")
    return output


def sources(root):
    return {name: sha(root / name) for name in SOURCE_FILES}


def compatible_sources(root, record):
    """A host-only fix must not require rebuilding unchanged target payloads."""
    return all(record.get(name) == sha(root / name) for name in PAYLOAD_SOURCES)


def execution_snapshot(root, evidence):
    verify_package(root)
    source = {}
    for name, digest in sources(root).items():
        path = evidence / "host-source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes())
        source[name] = digest
    (evidence / "host-source.json").write_text(json.dumps(source, indent=2) + "\n")


def commands(root, inputs, output, generation, recover):
    python = sys.executable
    selection = "open_connect.firmware55."
    pair = [
        python,
        "-m",
        selection + "build_pair",
        "--native-original",
        str(inputs["native"]),
        "--system-app",
        str(inputs["system_app"]),
        "--base-app",
        str(inputs["base_app"]),
        "--output",
        str(output / "pair"),
    ]
    feature = [python, "-m", selection + "generation"]
    for flag, key in (
        ("original", "autostart"),
        ("config", "config"),
        ("plugin", "plugin"),
        ("mmui-xml", "mmui_xml"),
        ("index", "index"),
    ):
        feature += ["--" + flag, str(inputs[key])]
    feature += [
        "--flush",
        str(output / "flush/flush-arm"),
        "--pair",
        str(output / "pair"),
        "--directory",
        generation,
        "--output",
        str(output / "selected"),
        "--home-ready-probe",
    ]
    health = [
        python,
        "-m",
        selection + "readiness",
        "--source",
        str(output / "selected"),
        "--receiver",
        str(output / "receiver/ready-receiver-arm"),
        "--output",
        str(output / "payload"),
    ]
    if recover:
        health.append("--recover-on-timeout")
    return [
        ("pair", pair),
        ("flush", [python, "-m", selection + "build_flush", "--output", str(output / "flush")]),
        (
            "receiver",
            [python, "-m", selection + "build_receiver", "--output", str(output / "receiver")],
        ),
        ("selection", feature),
        ("readiness", health),
    ]


def build(args):
    root = workspace(args.workspace)
    output = private_output(root, args.output)
    firmware = args.firmware.resolve()
    inputs = {key: firmware / relative for key, relative in INPUTS.items()}
    missing = [str(p) for p in inputs.values() if not p.is_file()]
    if missing:
        raise ValueError("missing private originals: " + ", ".join(missing))
    generation = "/tmp/mnt/data_persist/oc-boot-" + secrets.token_hex(16)
    steps = commands(root, inputs, output, generation, args.recover_on_timeout)
    record = dict(
        schema=1,
        feature="disclaimer",
        firmware=FIRMWARE,
        workspace=str(root),
        generation=generation,
        payload=str(output / "payload"),
        device_state="not_observed",
        device_operations=False,
        recover_on_timeout=args.recover_on_timeout,
        inputs={key: dict(path=str(p), sha256=sha(p)) for key, p in inputs.items()},
        source_sha256=sources(root),
        commands=dict(steps),
    )
    if args.dry_run:
        return dict(record, outcome="dry_run_not_built", files_written=False), 0
    output.mkdir(parents=True, mode=0o700)
    record.update(outcome="build_failed", error=None, stages=[])
    rc = 1
    try:
        for name, command in steps:
            print("Building " + name + "…", file=sys.stderr, flush=True)
            run = subprocess.run(
                command,
                cwd=root,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OC_WORKSPACE=str(root)),
                capture_output=True,
                timeout=600,
            )
            (output / (name + ".stdout")).write_bytes(run.stdout)
            (output / (name + ".stderr")).write_bytes(run.stderr)
            record["stages"].append(dict(name=name, returncode=run.returncode))
            if run.returncode:
                raise ValueError(f"{name} failed; see {output / (name + '.stderr')}")
        if sources(root) != record["source_sha256"]:
            raise ValueError("source changed during build")
        if any(sha(p) != record["inputs"][key]["sha256"] for key, p in inputs.items()):
            raise ValueError("firmware input changed during build")
        plan = json.loads((output / "payload/plan.json").read_text())
        if (
            plan["directory"] != generation
            or plan["health"]["recover_on_timeout"] != args.recover_on_timeout
        ):
            raise ValueError("built plan does not match requested generation/recovery")
        record.update(
            outcome="built_not_installed",
            artifacts={
                str(p.relative_to(output)): sha(p)
                for directory in ("pair", "flush", "receiver", "selected", "payload")
                for p in sorted((output / directory).rglob("*"))
                if p.is_file()
            },
        )
        rc = 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        record["error"] = str(exc)
        if isinstance(exc, subprocess.TimeoutExpired):
            (output / "timeout.stdout").write_bytes(exc.stdout or b"")
            (output / "timeout.stderr").write_bytes(exc.stderr or b"")
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    return dict(
        outcome=record["outcome"],
        error=record["error"],
        build=str(output),
        payload=record["payload"],
        generation=generation,
        device_operations=False,
        device_state="not_observed",
    ), rc


def inspect_build(path):
    """Read-only local validation. Never infer installed or loaded device state."""
    path = path.resolve()
    record = json.loads((path / "build.json").read_text())
    if record.get("schema") != 1 or record.get("outcome") != "built_not_installed":
        raise ValueError("a completed feature build is required")
    if record.get("payload") != str(path / "payload"):
        raise ValueError("build was moved; rebuild at its final path")
    if record.get("feature") != "disclaimer" or record.get("firmware") != FIRMWARE:
        raise ValueError("unsupported feature build")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict) or "payload/plan.json" not in artifacts:
        raise ValueError("missing build artifacts")
    for name, expected in artifacts.items():
        p = path / name
        if Path(name).is_absolute() or ".." in Path(name).parts or p.is_symlink():
            raise ValueError("invalid artifact path")
        if not p.resolve().is_relative_to(path) or sha(p) != expected:
            raise ValueError("build artifact changed: " + name)
    return dict(
        outcome="local_build_verified",
        feature=record["feature"],
        firmware=record["firmware"],
        generation=record["generation"],
        recover_on_timeout=record["recover_on_timeout"],
        payload=record["payload"],
        device_state="not_observed",
        device_operations=False,
    )


def run_device(command, root, evidence, action, success):
    # Everything after attempting process launch belongs to an execution
    # outcome. A disk/log/JSON error here must never become "nothing happened".
    snapshot = evidence.with_name(evidence.name + "-host-source")
    snapshot.mkdir(mode=0o700, parents=True, exist_ok=False)
    execution_snapshot(root, snapshot)
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            env=dict(os.environ, OC_WORKSPACE=str(root)),
        )
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if evidence.is_dir():
            (evidence / "host.stdout").write_text(result.stdout)
            (evidence / "host.stderr").write_text(result.stderr)
        observed = None
        for name in ("state.json", "after.json"):
            if (evidence / name).is_file():
                observed = json.loads((evidence / name).read_text())
        return dict(
            outcome=success if result.returncode == 0 else "incomplete_preserved",
            action=action,
            returncode=result.returncode,
            evidence=str(evidence),
            device_operations=True,
            observed=observed,
        ), 0 if result.returncode == 0 else 2
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as exc:
        return dict(
            outcome="incomplete_preserved",
            action=action,
            device_operations=True,
            device_state="unknown",
            error=type(exc).__name__ + ": " + str(exc),
            evidence=str(evidence),
        ), 2


def prepare(args):
    build_path = args.build.resolve()
    inspect_build(build_path)
    record = json.loads((build_path / "build.json").read_text())
    root = workspace(Path(record["workspace"]))
    if not compatible_sources(root, record["source_sha256"]):
        raise ValueError("payload producer changed; rebuild before preparation")
    state = private_output(root, args.state)
    command = [
        sys.executable,
        "-m",
        "open_connect.device.feature_state",
        "--build",
        str(build_path),
        "--state",
        str(state),
        "--owner",
        args.owner,
    ]
    if args.baseline_system_app:
        command += ["--baseline-system-app", str(args.baseline_system_app.resolve())]
    if not args.live:
        return dict(
            outcome="dry_run_not_prepared",
            command=command,
            device_operations=False,
            state_written=False,
            installs_startup_hook=False,
        ), 0
    # The device entry records partial operations itself. A nonzero result is not
    # permission to repeat preparation; the fresh state path will be occupied.
    return run_device(command, root, state, "prepare", "prepared_not_installed")


def device_action(args):
    state = args.state.resolve()
    run = json.loads((state / "run.json").read_text())
    # Restoration/status use the retained recovery binding, not a requirement
    # that feature builders are still present or unchanged.
    root = Path(run["workspace"]).resolve()
    if not (root / "tooling/open_connect/device/feature_workflow.py").is_file():
        raise ValueError("trial source checkout is missing")
    bundle = private_output(root, args.bundle)
    command = [
        sys.executable,
        "-m",
        "open_connect.device.feature_workflow",
        args.action,
        "--state",
        str(state),
        "--owner",
        args.owner,
        "--bundle",
        str(bundle),
    ]
    if args.action != "status":
        if args.live and (args.credentials is None or args.camera_index is None):
            raise ValueError("trial/disable require --credentials and --camera-index")
        if args.credentials:
            command += ["--credentials", str(args.credentials.resolve())]
        if args.camera_index is not None:
            command += ["--camera-index", str(args.camera_index)]
    if not args.live:
        return dict(outcome="dry_run_not_executed", command=command, device_operations=False), 0
    return run_device(command, root, bundle, args.action, "completed")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="oc feature",
        description="Build and prepare the FW55 developer feature. Device operations require --live.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("build", help="compile, check and compose the disclaimer trial")
    p.add_argument("--workspace", type=Path, default=Path.cwd(), help="Open Connect checkout")
    p.add_argument("--firmware", type=Path, required=True, help="private original filesystem tree")
    p.add_argument(
        "--output", type=Path, required=True, help="fresh directory under WORKSPACE/runs/"
    )
    p.add_argument(
        "--recover-on-timeout",
        action="store_true",
        help="build with one failed-Home normal reboot; otherwise observe only",
    )
    p.add_argument("--dry-run", action="store_true", help="show build commands; write nothing")
    p = sub.add_parser("inspect", help="verify local build files; does not query the CMU")
    p.add_argument("--build", type=Path, required=True)
    p = sub.add_parser("prepare", help="stage generation and independent undo; no root publication")
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True, help="fresh private operation directory")
    p.add_argument("--owner", default=os.environ.get("USER", "oc-feature"))
    p.add_argument(
        "--baseline-system-app",
        type=Path,
        help="explicit private as-found JS if bench already differs from original",
    )
    p.add_argument("--live", action="store_true", help="stage verified files on the CMU")
    for action, help_text in (
        ("trial", "publish once, reboot and verify selected feature with video"),
        ("status", "read current hook, loaded code and Home acknowledgement"),
        ("disable", "restore startup hook, boot baseline and verify it"),
    ):
        p = sub.add_parser(action, help=help_text)
        p.add_argument("--state", type=Path, required=True)
        p.add_argument(
            "--bundle", type=Path, required=True, help="fresh private evidence directory"
        )
        p.add_argument("--owner", default=os.environ.get("USER", "oc-feature"))
        p.add_argument("--live", action="store_true")
        if action != "status":
            p.add_argument("--credentials", type=Path, help="private root credentials JSON")
            p.add_argument("--camera-index", type=int)
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            result, code = build(args)
        elif args.action == "prepare":
            result, code = prepare(args)
        elif args.action == "inspect":
            result, code = inspect_build(args.build), 0
        else:
            result, code = device_action(args)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        result, code = dict(outcome="refused", error=str(exc), device_operations=False), 2
    print(json.dumps(result, indent=2))
    return code
