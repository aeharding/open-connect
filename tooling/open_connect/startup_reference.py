"""Playground: one pinned ACC restart, UART/video and locally started boot metrics."""

import argparse
import hashlib
import json
import re
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
    parser.add_argument("--condition", choices=["stock", "open-connect"], default="stock")
    parser.add_argument("--package", help="required candidate files.sha256 digest")
    parser.add_argument(
        "--wireless", type=int, choices=[0, 1], help="assert saved/applied wireless policy"
    )
    parser.add_argument(
        "--pandora",
        type=int,
        choices=[0, 1],
        help="assert the applied service choice; does not change it",
    )
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument(
        "--base",
        type=int,
        choices=[0, 1],
        help="assert the installed preset and loaded native policy",
    )
    logging.add_argument(
        "--log-level",
        choices=["Info", "Warn"],
        help="assert the bench RAM choice and loaded native MMUI logging level",
    )
    parser.add_argument(
        "--label",
        default="Stock reference; record phone/peripherals/camera settings with the batch",
    )
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host):
        parser.error("use an existing trusted SSH alias")
    if (
        args.condition == "open-connect" and not re.fullmatch(r"[a-f0-9]{64}", args.package or "")
    ) or (args.condition == "stock" and args.package is not None):
        parser.error("open-connect requires its exact --package; stock has no package")
    if args.base is not None and args.condition != "open-connect":
        parser.error("--base requires open-connect")
    if args.pandora is not None and args.condition != "open-connect":
        parser.error("--pandora requires open-connect")
    if args.wireless is not None and args.condition != "open-connect":
        parser.error("--wireless requires open-connect")
    if not args.live:
        print(
            json.dumps(
                {
                    "outcome": "dry_run",
                    "acc_off_seconds": 30,
                    "post_on_video_seconds": 210,
                    "resources_seconds": 180,
                    "resource_launch": "local stage_1 hook; SSH retrieval after 225 seconds",
                    "device_opened": False,
                    "condition": args.condition,
                    "package": args.package,
                    "pandora": args.pandora,
                    "wireless": args.wireless,
                    **({"base": args.base} if args.base is not None else {}),
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
        "pinned startup measurement; interpret only with its declared batch",
        "primary",
        mode="live",
    )
    bundle.save("startup_reference.py", Path(__file__).read_bytes())
    preflight = (ROOT / "cmu/bench/startup-preflight.sh").read_bytes()
    fetch = (ROOT / "cmu/bench/startup-fetch.sh").read_bytes()
    bundle.save("preflight.sh", preflight)
    bundle.save("fetch.sh", fetch)
    sources = {}
    for name in ("metrics.sh", "startup-launch.sh", "startup-hook.sh"):
        source = (ROOT / "cmu/bench" / name).read_bytes()
        bundle.save(name, source)
        sources[name] = hashlib.sha256(source).hexdigest()
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
    port = relay = uart_worker = None
    outcome, error = "incomplete_preserved", None
    record = {
        "revision": revision,
        "label": args.label,
        "supply_commands_sent": False,
        "events": [],
        "ui_inputs_sent": False,
        "resource_sources": sources,
        "condition": args.condition,
        "package": args.package,
        "pandora": args.pandora,
        "wireless": args.wireless,
    }
    if args.log_level is not None:
        record["log_level"] = args.log_level
    if args.base is not None:
        record["base"] = args.base

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

    try:
        preflight_command = "timeout -t 35 sh -s -- " + shlex.join(
            [
                args.condition,
                args.package or "-",
                str(args.pandora) if args.pandora is not None else "-",
                args.log_level or "-",
                str(args.base) if args.base is not None else "-",
                str(args.wireless) if args.wireless is not None else "-",
            ]
        )
        result = subprocess.run(
            ssh + [preflight_command], input=preflight, capture_output=True, timeout=40
        )
        bundle.save("preflight.out", result.stdout)
        bundle.save("preflight.err", result.stderr)
        if result.returncode:
            raise RuntimeError("condition preflight refused before any device opened")
        old_boot = validate_condition(
            result.stdout, args.condition, args.pandora, args.log_level, args.base, args.wireless
        )
        cameras = subprocess.check_output(
            ["system_profiler", "SPCameraDataType", "-json"], timeout=12
        )
        bundle.save("camera-identity.json", cameras)
        devices = json.loads(cameras)["SPCameraDataType"]
        enumeration = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            timeout=10,
        )
        bundle.save("camera-enumeration.txt", enumeration.stderr)
        video.index = camera_index(devices, enumeration.stderr, args.camera_uid)
        record["camera_index"] = video.index
        with AdapterLock(owner="primary", purpose="pinned ACC trial; UART receive only"):
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
                    ("ACC_ON", "a00101a2", 210),
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
                        on = at
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
                try:
                    video.stop()
                except BaseException as exc:
                    record["camera_error"] = repr(exc)
        # No SSH polling or collection commands run during startup. The local
        # observer is finite and the first SSH here only fetches completed data.
        # Product bootstrap precedes this hook. Allow the candidate's complete
        # local 180-second trace before opening SSH, including slow startup.
        wait_until(on + 225)
        try:
            result = subprocess.run(
                ssh + ["timeout -t 20 sh -s -- " + shlex.join([old_boot, *sources.values()])],
                input=fetch,
                capture_output=True,
                timeout=25,
            )
        except subprocess.TimeoutExpired as exc:
            bundle.save("fetch.out", exc.stdout or b"")
            bundle.save("fetch.err", exc.stderr or b"")
            raise
        bundle.save("fetch.out", result.stdout)
        bundle.save("fetch.err", result.stderr)
        if result.returncode:
            raise RuntimeError("boot trace fetch refused; inspect retained RAM evidence")
        trace = parse_boot_trace(result.stdout, old_boot)
        bundle.save("trace.json", (json.dumps(trace, indent=2) + "\n").encode())
        bundle.save("memory.csv", metrics.memory_csv(trace).encode())
        result = subprocess.run(
            ssh + [preflight_command], input=preflight, capture_output=True, timeout=40
        )
        bundle.save("postflight.out", result.stdout)
        bundle.save("postflight.err", result.stderr)
        if (
            result.returncode
            or validate_condition(
                result.stdout,
                args.condition,
                args.pandora,
                args.log_level,
                args.base,
                args.wireless,
            )
            != trace["boot_id"]
        ):
            raise RuntimeError("condition changed or failed postflight")
        event(
            "trace_retrieved",
            boot_id=trace["boot_id"],
            samples=len(trace["samples"]),
            first_sample_uptime_s=trace["samples"][0]["uptime_start_s"],
            last_sample_uptime_s=trace["samples"][-1]["uptime_end_s"],
        )
    except BaseException as exc:
        error = repr(exc)
    finally:
        if record.get("camera_error"):
            error = error or record["camera_error"]
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


def validate_condition(raw, condition, pandora=None, log_level=None, base=None, wireless=None):
    boots = re.findall(rb"^REFERENCE_BOOT\|(" + metrics.UUID.encode() + rb")$", raw, re.M)
    if len(boots) != 1:
        raise ValueError("missing exact condition boot record")
    if wireless is not None and (
        type(wireless) is not int or wireless not in (0, 1) or condition != "open-connect"
    ):
        raise ValueError("invalid wireless condition")
    if base is not None and (
        type(base) is not int
        or base not in (0, 1)
        or condition != "open-connect"
        or log_level is not None
    ):
        raise ValueError("invalid installed base condition")
    native_level = log_level if base is None else ("Warn" if base else "Info")
    if native_level is not None:
        if native_level not in ("Info", "Warn"):
            raise ValueError("invalid expected logging level")
        expected_root = "8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0"
        expected_sha = hashlib.sha256(f"COMMON_LOG_LEVEL={native_level}\n".encode()).hexdigest()
        if base is None:
            choices = re.findall(
                rb"^NATIVE_LOG_CHOICE\|(Info|Warn)\|([a-f0-9]{64})\|([a-f0-9]{64})$", raw, re.M
            )
            expected_choice = (native_level.encode(), expected_sha.encode(), expected_root.encode())
        else:
            choices = re.findall(
                rb"^BASE_POLICY\|([01])\|(-|[a-f0-9]{64})\|([a-f0-9]{64})$", raw, re.M
            )
            expected_choice = (
                str(base).encode(),
                expected_sha.encode() if base else b"-",
                expected_root.encode(),
            )
        if choices != [expected_choice]:
            raise ValueError("logging choice, RAM bytes or original configuration changed")
        mmui = re.findall(
            rb"^NATIVE_LOG_MMUI\|([1-9][0-9]*)\|([1-9][0-9]*)\|([01])\|([0-7])\|([0-7])\|([0-7])$",
            raw,
            re.M,
        )
        level = b"5" if native_level == "Info" else b"3"
        if len(mmui) != 1 or mmui[0][2:] != (b"1", level, level, b"5"):
            raise ValueError("native MMUI logging level is missing or not applied")
    if condition == "open-connect":
        rows = re.findall(rb"^CANDIDATE_STATUS\|(.*)$", raw, re.M)
        if len(rows) != 1:
            raise ValueError("missing candidate state")
        state = json.loads(rows[0])
        expected = dict(
            ok=True,
            installed=True,
            conflict=False,
            restart=False,
            pending=False,
            touch=1,
            warning=1,
            uart=0,
            ssh=0,
            uartCurrent=0,
            sshCurrent=0,
            notice="-",
        )
        # A settings write retains its restart notice after the selected snapshot
        # is applied. The actual restart/pending flags above must still be false.
        if (pandora is not None or base is not None or wireless is not None) and state.get(
            "notice"
        ) == "restart":
            expected["notice"] = "restart"
        if any(state.get(key) != value for key, value in expected.items()):
            raise ValueError("candidate preferences or applied state do not match")
        if base is not None and (type(state.get("base")) is not int or state["base"] != base):
            raise ValueError("installed base preference is missing or changed")
        if wireless is not None:
            if any(
                type(state.get(k)) is not int or state[k] != wireless
                for k in ("wireless", "wirelessCurrent")
            ):
                raise ValueError("saved/applied wireless policy is missing or changed")
            snapshots = re.findall(rb"^WIRELESS_SNAPSHOT\|(8|OC2)\|([01])$", raw, re.M)
            links = re.findall(rb"^WIRELESS_LINK\|([01])\|([0-9]+)$", raw, re.M)
            if (
                len(snapshots) != 1
                or snapshots[0][1] != str(wireless).encode()
                or len(links) != 1
                or links[0][0] != b"0"
            ):
                raise ValueError("wireless snapshot or phone USB condition changed")
            if snapshots[0][0] == b"OC2":
                rows = state.get("services")
                wanted = {"android-auto": 1, "pandora": state.get("pandora")}
                if (
                    not isinstance(rows, list)
                    or len(rows) != 2
                    or any(
                        not isinstance(row, dict)
                        or row.get("id") != key
                        or any(
                            type(row.get(field)) is not int or row[field] != wanted[key]
                            for field in ("saved", "current")
                        )
                        for row, key in zip(rows, sorted(wanted), strict=True)
                    )
                ):
                    raise ValueError("individual Services choices are missing, pending or changed")
            # Station count is an outcome, not a gate that discards reconnect misses.
        if pandora is not None:
            info = re.findall(rb"^PANDORA_INFO_BEGIN\n(.*?)^PANDORA_INFO_END$", raw, re.M | re.S)
            starts = re.findall(rb"^PANDORA_STARTS\|([0-9]+)$", raw, re.M)
            if len(info) != 1 or len(starts) != 1 or state.get("pandora") != pandora:
                raise ValueError("missing or mismatched service condition")
            autorun = re.findall(rb'^    autorun="([a-z]+)"$', info[0], re.M)
            current = re.findall(rb'^    state="([A-Z_]+)"$', info[0], re.M)
            pid = re.findall(rb'^    pid="([0-9]+)"$', info[0], re.M)
            if autorun != [b"yes" if pandora else b"no"] or len(current) != 1:
                raise ValueError("service policy or state missing")
            if pandora and (
                current != [b"RUNNING"] or len(pid) != 1 or int(pid[0]) <= 0 or starts != [b"1"]
            ):
                raise ValueError("Pandora did not start normally")
            if not pandora and (
                starts != [b"0"] or pid or current[0] in (b"RUNNING", b"STARTING", b"STOPPING")
            ):
                raise ValueError("disabled Pandora was launched or remains active")
    return boots[0].decode()


def camera_index(devices, enumeration, uid):
    selected = [d for d in devices if d.get("spcamera_unique-id") == uid]
    if len(selected) != 1:
        raise ValueError("camera UID absent or ambiguous")
    section = enumeration.split(b"AVFoundation video devices:\n", 1)
    if len(section) != 2 or b"AVFoundation audio devices:" not in section[1]:
        raise ValueError("incomplete camera enumeration")
    video_devices = section[1].split(b"AVFoundation audio devices:", 1)[0]
    indices = re.findall(
        rb"\[([0-9]+)\] " + re.escape(selected[0]["_name"].encode()) + rb"$",
        video_devices,
        re.M,
    )
    if len(indices) != 1:
        raise ValueError("camera name absent or ambiguous in FFmpeg enumeration")
    return int(indices[0])


def parse_boot_trace(raw, old_boot):
    boots = re.findall(rb"^BOOT_TRACE\|(" + metrics.UUID.encode() + rb")$", raw, re.M)
    if len(boots) != 1 or boots[0].decode() == old_boot:
        raise ValueError("missing or stale local boot trace")
    boot = boots[0].decode()
    token = boot.replace("-", "")
    trace_start = raw.index(b"\nOCM1 " + token.encode() + b" boot ")
    trace_raw = raw[trace_start:]
    digests = re.findall(rb"^BOOT_TRACE_SHA\|\(stdin\)= ([a-f0-9]{64})$", raw, re.M)
    if len(digests) != 1 or hashlib.sha256(trace_raw).hexdigest().encode() != digests[0]:
        raise ValueError("retrieved trace digest mismatch")
    trace = metrics.parse(trace_raw, token, [])
    if trace["boot_id"] != boot:
        raise ValueError("trace boot identity mismatch")
    return trace


if __name__ == "__main__":
    main()
