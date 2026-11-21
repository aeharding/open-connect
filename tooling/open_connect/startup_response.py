# SPDX-License-Identifier: AGPL-3.0-or-later
"""One settled CarPlay input sequence, camera and system-counter trace."""


def main():
    import hashlib
    import json
    import re
    import signal
    import subprocess
    import sys
    import time
    from pathlib import Path

    from open_connect import startup_reference as reference
    from open_connect.device.boot import Video
    from open_connect.paths import ROOT
    from open_connect.session import Bundle

    if sys.argv[1:2] != ["--live"]:
        raise SystemExit("Live input recording requires --live and all six arguments")
    condition, boot, package, bundle_root, host, ssh_config = sys.argv[2:]
    assert condition in ("stock", "open-connect")
    assert re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", boot)
    assert package == "-" if condition == "stock" else re.fullmatch(r"[a-f0-9]{64}", package)
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", host)
    base = Path(bundle_root).resolve()
    bundle = Bundle(
        base / ("response-" + condition),
        "Five injected Right/Left pairs on settled wired CarPlay; not physical-input qualification",
        "primary",
        mode="live",
    )
    bundle.save("response.py", Path(__file__).read_bytes())
    bundle.save("response.sh", (ROOT / "cmu/bench/startup-response.sh").read_bytes())
    ssh = ["ssh", "-T", "-F", ssh_config, "-oBatchMode=yes", "-oConnectTimeout=8", host]
    preflight = (ROOT / "cmu/bench/startup-preflight.sh").read_bytes()
    r = subprocess.run(
        ssh + ["timeout -t 35 sh -s -- " + condition + " " + package],
        input=preflight,
        capture_output=True,
        timeout=40,
    )
    bundle.save("preflight.out", r.stdout)
    bundle.save("preflight.err", r.stderr)
    assert r.returncode == 0 and reference.validate_condition(r.stdout, condition) == boot
    cameras = json.loads(
        subprocess.check_output(["system_profiler", "SPCameraDataType", "-json"], timeout=12)
    )["SPCameraDataType"]
    enumeration = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        timeout=10,
    )
    video = Video(bundle, reference.camera_index(cameras, enumeration.stderr, "0x8400000046d0825"))
    bundle.save("camera-enumeration.txt", enumeration.stderr)
    sampler = None
    error = None
    try:
        video.start()
        with (bundle.path / "sampler.log").open("xb") as output:
            sampler = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "open_connect.metrics",
                    "--live",
                    "--host",
                    host,
                    "--ssh-config",
                    ssh_config,
                    "--seconds",
                    "60",
                    "--interval",
                    "1",
                    "--bundle",
                    str(bundle.path / "resources"),
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            time.sleep(3)
            sha = hashlib.sha256((ROOT / "cmu/bench/startup-response.sh").read_bytes()).hexdigest()
            command = (
                'set -eu; d=$(openssl dgst -sha256 < /tmp/oc-dev-response-comparison.sh); test "${d##* }" = '
                + sha
                + "; timeout -t 35 sh /tmp/oc-dev-response-comparison.sh "
                + boot
            )
            try:
                r = subprocess.run(ssh + [command], capture_output=True, timeout=40)
            except subprocess.TimeoutExpired as exc:
                bundle.save("action.out", exc.stdout or b"")
                bundle.save("action.err", exc.stderr or b"")
                raise
            bundle.save("action.out", r.stdout)
            bundle.save("action.err", r.stderr)
            if r.returncode:
                raise RuntimeError("input probe failed; no resend")
            if sampler.wait(timeout=110):
                raise RuntimeError("resource sampler failed")
    except BaseException as exc:
        error = repr(exc)
    finally:
        if sampler is not None and sampler.poll() is None:
            sampler.send_signal(signal.SIGINT)
            try:
                sampler.wait(timeout=10)
            except subprocess.TimeoutExpired:
                sampler.kill()
                sampler.wait(timeout=3)
        try:
            video.stop()
        except BaseException as exc:
            error = error or repr(exc)
        bundle.finish("recorded" if error is None else "incomplete_preserved", error)
    if error:
        raise SystemExit(error)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "open_connect.clock_reference",
            "--live",
            "--host",
            host,
            "--ssh-config",
            ssh_config,
            "--expect-boot",
            boot,
            "--bundle",
            str(base / ("response-clock-" + condition)),
        ],
        check=True,
        timeout=30,
    )
    print("INPUT_RESPONSE_CAPTURE_COMPLETE", condition)


if __name__ == "__main__":
    main()
