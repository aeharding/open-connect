"""Playground: one stock ACC restart, receive-only UART/video and post-SSH metrics."""

import argparse
import json
import re
import secrets
import shlex
import subprocess
import threading
import time
from pathlib import Path

import serial
from serial.tools import list_ports

from open_connect import metrics
from open_connect.device.boot import Video
from open_connect.paths import ROOT, verify_package
from open_connect.session import AdapterLock, Bundle, Session, open_adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="my-cmu")
    parser.add_argument("--ssh-config", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--relay-location", default="2-1")
    parser.add_argument("--camera-uid", default="0x8400000046d0825")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host):
        parser.error("use an existing trusted SSH alias")
    if not args.live:
        print(
            json.dumps(
                {
                    "outcome": "dry_run",
                    "acc_off_seconds": 30,
                    "post_on_video_seconds": 120,
                    "resources_seconds": 120,
                    "device_opened": False,
                }
            )
        )
        return
    if args.bundle is None:
        parser.error("--live requires a fresh --bundle")
    verify_package(ROOT)
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", "tooling/open_connect", "cmu/bench"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "tooling/open_connect/startup_reference.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    bundle = Bundle(
        args.bundle,
        "stock startup coverage trial, not a performance comparison",
        "primary",
        mode="live",
    )
    bundle.save("startup_reference.py", Path(__file__).read_bytes())
    preflight = (ROOT / "cmu/bench/startup-preflight.sh").read_bytes()
    ready = (ROOT / "cmu/bench/startup-ready.sh").read_bytes()
    bundle.save("preflight.sh", preflight)
    bundle.save("ready.sh", ready)
    ssh = [
        "ssh",
        "-T",
        "-oBatchMode=yes",
        "-oStrictHostKeyChecking=yes",
        "-oConnectTimeout=2",
        "-oConnectionAttempts=1",
        "-oControlMaster=no",
        "-oControlPath=none",
    ]
    if args.ssh_config:
        ssh += ["-F", str(args.ssh_config)]
    ssh += [args.host]
    video = Video(bundle, 0)
    stop = threading.Event()
    errors = []
    port = relay = uart_worker = sample_worker = None
    outcome, error = "incomplete_preserved", None
    record = {
        "revision": revision,
        "supply_commands_sent": False,
        "events": [],
        "ui_inputs_sent": False,
    }

    def event(kind, **values):
        row = {"kind": kind, "monotonic_s": time.monotonic(), **values}
        record["events"].append(row)
        (bundle.path / "trial.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(row), flush=True)
        return row["monotonic_s"]

    def resolve_relay():
        matches = [
            p
            for p in list_ports.comports()
            if (p.vid, p.pid, p.location) == (0x1A86, 0x7523, args.relay_location)
        ]
        if len(matches) != 1:
            raise RuntimeError("relay identity not unique")
        return matches[0].device

    def receive():
        try:
            session = Session(port, bundle)
            while not stop.is_set():
                session.receive(0.3)
        except BaseException as exc:
            errors.append("UART: " + repr(exc))

    def wait_until(deadline):
        while time.monotonic() < deadline:
            if errors:
                raise RuntimeError(errors[0])
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def sample_after_ready(old_boot, on):
        try:
            token = secrets.token_hex(16)
            deadline, attempt = on + 100, 0
            while time.monotonic() < deadline and not stop.is_set():
                before = time.monotonic()
                try:
                    result = subprocess.run(
                        ssh + ["timeout -t 3 sh -s -- " + shlex.join([old_boot, token])],
                        input=ready,
                        capture_output=True,
                        timeout=5,
                    )
                    raw, err, rc = result.stdout, result.stderr, result.returncode
                except subprocess.TimeoutExpired as exc:
                    raw, err, rc = exc.stdout or b"", exc.stderr or b"", None
                after = time.monotonic()
                bundle.save(f"probe-{attempt}.out", raw)
                bundle.save(f"probe-{attempt}.err", err)
                match = re.findall(
                    rb"^STARTUP_READY\|"
                    + token.encode()
                    + rb"\|([a-f0-9-]{36})\|([0-9.]+) ([0-9.]+)$",
                    raw,
                    re.M,
                )
                event("ssh_probe", attempt=attempt, before_s=before, after_s=after, returncode=rc)
                if rc == 0 and len(match) == 1:
                    new_boot, uptime, _ = match[0]
                    record["ready"] = {
                        "boot": new_boot.decode(),
                        "uptime_s": float(uptime),
                        "host_before_s": before,
                        "host_after_s": after,
                    }
                    options = [
                        "--live",
                        "--host",
                        args.host,
                        "--seconds",
                        "120",
                        "--interval",
                        "1",
                        "--workspace",
                        str(ROOT),
                        "--bundle",
                        str(bundle.path / "resources"),
                    ]
                    if args.ssh_config:
                        options += ["--ssh-config", str(args.ssh_config)]
                    record["sampler_returncode"] = metrics.main(options)
                    event("sampling_complete", returncode=record["sampler_returncode"])
                    return
                attempt += 1
                stop.wait(0.5)
            raise RuntimeError("new-boot owner SSH not ready within 100 seconds")
        except BaseException as exc:
            record["sampling_error"] = repr(exc)
            event("sampling_error", error=repr(exc))

    try:
        result = subprocess.run(
            ssh + ["timeout -t 15 sh -s"], input=preflight, capture_output=True, timeout=20
        )
        bundle.save("preflight.out", result.stdout)
        bundle.save("preflight.err", result.stderr)
        if result.returncode:
            raise RuntimeError("stock preflight refused before any device opened")
        boots = re.findall(rb"^STOCK_BOOT\|([a-f0-9-]{36})$", result.stdout, re.M)
        if len(boots) != 1:
            raise RuntimeError("missing exact stock boot record")
        old_boot = boots[0].decode()
        cameras = subprocess.check_output(
            ["system_profiler", "SPCameraDataType", "-json"], timeout=12
        )
        bundle.save("camera-identity.json", cameras)
        devices = json.loads(cameras)["SPCameraDataType"]
        if len(devices) != 1 or devices[0]["spcamera_unique-id"] != args.camera_uid:
            raise RuntimeError("reference trial requires its one identified camera at index 0")
        with AdapterLock(owner="primary", purpose="stock ACC trial; UART receive only"):
            try:
                port = open_adapter(bundle)
                uart_worker = threading.Thread(target=receive)
                uart_worker.start()
                video.start()
                device = resolve_relay()
                relay = serial.Serial(
                    port=None, baudrate=9600, timeout=0.15, write_timeout=1, exclusive=True
                )
                relay.dtr = relay.rts = False
                relay.port = device
                if resolve_relay() != device:
                    raise RuntimeError("relay changed before open")
                relay.open()
                if resolve_relay() != device:
                    raise RuntimeError("relay changed after open")
                for name, frame, delay in (
                    ("ACC_OFF", "a00100a1", 30),
                    ("ACC_ON", "a00101a2", 120),
                ):
                    if resolve_relay() != device:
                        raise RuntimeError("relay changed; no transmission")
                    count = relay.write(bytes.fromhex(frame))
                    relay.flush()
                    at = event(name, bytes_acknowledged=count, frame=frame)
                    if count != 4:
                        raise RuntimeError("partial relay transmission; no resend")
                    if name == "ACC_ON":
                        relay.close()
                        sample_worker = threading.Thread(
                            target=sample_after_ready, args=(old_boot, at)
                        )
                        sample_worker.start()
                    wait_until(at + delay)
                outcome = "observed"
            finally:
                if relay:
                    relay.close()
                if uart_worker:
                    stop.set()
                    uart_worker.join(2)
                if port:
                    port.close()
                video.stop()
                if sample_worker:
                    sample_worker.join(160)
                    if sample_worker.is_alive():
                        raise RuntimeError("resource worker exceeded its finite deadline")
    except BaseException as exc:
        error = repr(exc)
    finally:
        if record.get("sampling_error") or record.get("sampler_returncode") != 0:
            error = error or record.get("sampling_error") or "sampling did not complete"
        record.update(
            outcome=outcome if error is None else "incomplete_preserved",
            error=error,
            uart_closed=port is None or not port.is_open,
            relay_closed=relay is None or not relay.is_open,
        )
        (bundle.path / "trial.json").write_text(json.dumps(record, indent=2) + "\n")
        bundle.meta["port_closed"] = record["uart_closed"]
        bundle.finish(record["outcome"], error)
    if error:
        raise SystemExit(error)


if __name__ == "__main__":
    main()
