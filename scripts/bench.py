#!/usr/bin/env python3
"""Mac-side CMU bench inventory, receive-only serial logging, and still capture."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now().astimezone().isoformat()


def stamp():
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S.%f%z")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    print(path)


def run(command, timeout=20):
    result = {"observed_at": now(), "command": command}
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        result.update(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired as exc:
        result.update(error=f"timed out after {timeout} seconds")
        for key in ("stdout", "stderr"):
            value = getattr(exc, key) or b""
            result[key] = value.decode(errors="replace") if isinstance(value, bytes) else value
    except OSError as exc:
        result.update(error=str(exc))
    return result


def ports():
    fields = ("device", "description", "hwid", "serial_number", "manufacturer", "product", "location")
    result = []
    for port in sorted(list_ports.comports()):
        entry = {field: getattr(port, field) for field in fields}
        entry.update(vid=f"{port.vid:04x}" if port.vid is not None else None,
                     pid=f"{port.pid:04x}" if port.pid is not None else None)
        result.append(entry)
    return result


def inventory(_args):
    types = run(["system_profiler", "-listDataTypes"])
    available = types.get("stdout", "").split()
    usb_type = next((x for x in ("SPUSBHostDataType", "SPUSBDataType") if x in available), None)
    selected = [x for x in (usb_type, "SPCameraDataType") if x in available]
    report = {
        "observed_at": now(), "serial_ports_opened": False,
        "macos": run(["sw_vers"]), "architecture": run(["uname", "-m"]),
        "profiler_types": types,
        "devices": run(["system_profiler", *selected, "-json"]) if selected else None,
        "serial_ports": ports(),
        "serial_ioreg": run(["ioreg", "-r", "-c", "IOSerialBSDClient", "-l"]),
        "python": {"executable": sys.executable, "version": sys.version},
        "pyserial_version": serial.__version__,
        "tools": {name: shutil.which(name) for name in
                  ("python3", "ffmpeg", "ffprobe", "imagesnap", "screen", "cu", "swift")},
        "ffmpeg_version": run(["ffmpeg", "-hide_banner", "-version"]),
    }
    save(ROOT / "inventory" / f"{stamp()}-inventory.json", report)
    print(json.dumps({"serial_ports": report["serial_ports"], "tools": report["tools"]}, indent=2))
    return 0


def serial_log(args):
    connection = serial.Serial(port=None, baudrate=115200, bytesize=serial.EIGHTBITS,
                               parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                               timeout=0.5, write_timeout=1, xonxoff=False,
                               rtscts=False, dsrdtr=False, exclusive=True)
    connection.dtr = False
    connection.rts = False
    metadata = {"prepared_at": now(), "port": args.port, "settings": connection.get_settings(),
                "dtr": False, "rts": False, "receive_only": True,
                "planned_seconds": args.seconds, "serial_port_opened": False,
                "bytes_received": 0}
    if not args.open:
        metadata["status"] = "configuration only; no device opened"
        save(ROOT / "inventory" / f"{stamp()}-serial-plan.json", metadata)
        print(json.dumps(metadata, indent=2))
        return 0
    if not args.port:
        raise ValueError("--open requires --port from a fresh inventory")
    selected = [port for port in ports() if port["device"] == args.port]
    if len(selected) != 1 or selected[0]["vid"] is None:
        raise ValueError("Select a currently enumerated USB serial port; run inventory first")
    metadata["adapter"] = selected[0]
    prefix = ROOT / "logs" / f"{stamp()}-uart"
    raw_path, chunks_path, meta_path = (Path(str(prefix) + ext) for ext in (".bin", ".jsonl", ".json"))
    metadata.update(raw_log=str(raw_path), timestamped_hex_log=str(chunks_path), status="opening")
    result = 0
    try:
        with raw_path.open("xb") as raw, chunks_path.open("x") as chunks:
            connection.port = args.port
            connection.open()
            metadata.update(serial_port_opened=True, opened_at=now(), status="capturing")
            save(meta_path, metadata)
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                data = connection.read(min(max(connection.in_waiting, 1), 4096))
                if not data:
                    continue
                raw.write(data)
                raw.flush()
                chunks.write(json.dumps({"received_at": now(), "hex": data.hex(), "length": len(data)}) + "\n")
                chunks.flush()
                metadata["bytes_received"] += len(data)
                print(repr(data), flush=True)
            metadata["status"] = "capture finished"
    except KeyboardInterrupt:
        metadata["status"] = "capture stopped by operator"
    except (OSError, serial.SerialException) as exc:
        metadata.update(status="capture failed", error=str(exc))
        result = 1
    finally:
        connection.close()
        metadata["ended_at"] = now()
        save(meta_path, metadata)
    print(f"Received {metadata['bytes_received']} bytes; this alone does not establish an interactive console.")
    return result


def camera(args):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("ffmpeg is not installed")
    report = run([ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""])
    devices = []
    in_video = False
    for line in report.get("stderr", "").splitlines():
        if "AVFoundation video devices:" in line:
            in_video = True
        elif "AVFoundation audio devices:" in line:
            in_video = False
        elif in_video:
            match = re.search(r"\]\s+\[(\d+)\]\s+(.+)$", line)
            if match:
                devices.append({"index": int(match[1]), "name": match[2]})
    report["video_devices"] = devices
    report["note"] = "Enumeration normally returns an input error; it does not prove capture works."
    save(ROOT / "inventory" / f"{stamp()}-camera-devices.json", report)
    print(json.dumps(devices, indent=2, ensure_ascii=False))
    if not args.device:
        return 0 if devices else 1
    selected = [device for device in devices if device["name"] == args.device]
    if len(selected) != 1:
        raise ValueError("--device must exactly match one currently listed camera name")
    token = stamp()
    image = ROOT / "captures" / f"{token}-webcam.jpg"
    command = [ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "avfoundation",
               "-framerate", args.framerate, "-video_size", args.size,
               "-pixel_format", "uyvy422",
               "-i", f"{selected[0]['index']}:none", "-ss", "2", "-frames:v", "1",
               "-q:v", "2", "-update", "1", str(image)]
    capture = run(command, timeout=25)
    capture.update(device=selected[0], audio="none", image_path=str(image),
                   image_bytes=image.stat().st_size if image.is_file() else 0)
    capture["capture_ok"] = capture.get("returncode") == 0 and capture["image_bytes"] > 0
    save(ROOT / "logs" / f"{token}-camera-capture.json", capture)
    print(json.dumps(capture, indent=2, ensure_ascii=False))
    return 0 if capture["capture_ok"] else 1


def positive_seconds(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("seconds must be finite and positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", help="Record Mac, USB, and serial devices without opening ports").set_defaults(func=inventory)
    uart = commands.add_parser("serial", help="Prepare settings; only --open starts receive-only capture")
    uart.add_argument("--port")
    uart.add_argument("--open", action="store_true", help="Use only after physical UART wiring is verified")
    uart.add_argument("--seconds", type=positive_seconds, default=60)
    uart.set_defaults(func=serial_log)
    cam = commands.add_parser("camera", help="List cameras; --device captures one still with no audio")
    cam.add_argument("--device", help="Exact name from the current camera list")
    cam.add_argument("--size", default="1280x720")
    cam.add_argument("--framerate", default="5", help="5 fps suits still capture and the observed webcam's 720p UYVY mode")
    cam.set_defaults(func=camera)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, OSError, serial.SerialException) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
