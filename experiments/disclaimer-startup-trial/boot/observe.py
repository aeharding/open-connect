#!/usr/bin/env python3
"""Candidate C startup observer. Review-only without a separately approved profile."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
STOCK_REVIEW = ROOT / "experiments/stock-warm-start/corrected-review.json"
STOCK_PATH = ROOT / "experiments/stock-warm-start/observe.py"
CMD5 = "64db9d0df2277e1d95a037929aef30c4"
CCRC = "776631029 94055"
SUCCESS = "candidate_restart_access_C_RO_verified"
VIDEO_FAILED = "access_C_RO_verified_video_failed"
CONFLICT = "candidate_recovery_identity_conflict"
IDENTITY_POLICY = "exact_full_applied_cstage_or_OTHER_no_adoption"
BIND = b"CANDIDATE_BOOT_BIND|"
HEX32 = re.compile(r"[0-9a-f]{32}")
FIELDS = {"META", "HASH", "CRC", "ROOT", "UPTIME", "BOOT_ID"}


class RecoveryIdentityConflict(ValueError):
    def __init__(self, observation):
        self.observation = observation
        super().__init__("candidate recovery identity conflict: OTHER; preserve/stop; no adoption")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_data(path, limit=524288):
    p = Path(path)
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size > limit:
        raise ValueError("expected bounded regular JSON data")
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    return json.loads(p.read_bytes(), object_pairs_hook=unique)


def load_stock():
    profile = json_data(STOCK_REVIEW)
    for name, expected in profile["source_pins"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("corrected stock dependency pin mismatch")
    spec = importlib.util.spec_from_file_location("_cmu_candidate_stock_helpers", STOCK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stock = load_stock()
# Preserve the corrected parser, camera/credential rules and Session implementation.
BootGate, Video = stock.BootGate, stock.Video


def read_artifact(bundle, manifest, name, limit):
    p = bundle / name
    info = manifest["artifacts"].get(name, {})
    if p.is_symlink() or not p.is_file() or p.stat().st_size > limit:
        raise ValueError("missing/oversize core evidence artifact")
    data = p.read_bytes()
    if info.get("bytes") != len(data) or info.get("sha256") != digest(data):
        raise ValueError("core artifact integrity mismatch")
    return data


def observed_identity(value):
    fields = value.split(":")
    if len(fields) != 8 or any(not x.isdigit() for x in fields) or int(fields[1]) <= 0:
        raise ValueError("candidate metadata is not a positive-inode numeric 8-tuple")
    return fields


def candidate_identity(value):
    fields = observed_identity(value)
    if (fields[0] != "64785" or
            fields[3:] != ["94055", "755", "1018", "3015", "1"]):
        raise ValueError("candidate C root-device/size/attributes mismatch")
    return fields


def apply_binding(path, root=ROOT):
    evidence = json_data(path, 4096)
    if set(evidence) != {"schema", "core_bundle", "trial_nonce"} or evidence["schema"] != 1:
        raise ValueError("apply evidence requires the exact three-field contract")
    nonce = evidence["trial_nonce"]
    if not isinstance(nonce, str) or not HEX32.fullmatch(nonce):
        raise ValueError("invalid apply trial nonce")
    bundle = Path(evidence["core_bundle"]).resolve(strict=True)
    if not bundle.is_relative_to((root / "runs").resolve()) or not bundle.is_dir():
        raise ValueError("apply evidence must reference a private runs core bundle")
    manifest = json_data(bundle / "manifest.json")
    if (manifest.get("mode") != "live" or manifest.get("outcome") != "completed" or
            manifest.get("port_closed") is not True or manifest.get("serial_port_opened") is not True or
            manifest.get("identity") != {"uid": 0, "user": "root", "firmware": "55.00.750B", "flavor": "cmu150_NA"}):
        raise ValueError("actual completed root55 apply evidence is required")
    adapter = manifest.get("adapter", {})
    if (adapter.get("vid"), adapter.get("pid"), adapter.get("serial_number")) != (0x0403, 0x6001, "A9048JM0"):
        raise ValueError("apply evidence is from a different bench")
    operations = [x for x in manifest.get("operations", []) if not x.get("identity_probe")]
    if not operations:
        raise ValueError("no actual apply operation")
    op = operations[-1]
    tag = op.get("nonce", "")
    if (not HEX32.fullmatch(tag) or op.get("outcome") != "completed" or op.get("exit_status") != 0):
        raise ValueError("apply core END must be known zero")
    raw = read_artifact(bundle, manifest, tag + ".output.bin", 262144)
    if op.get("output_sha256") != digest(raw):
        raise ValueError("apply operation output digest mismatch")
    rx = stock.ANSI.sub(b"", read_artifact(bundle, manifest, "rx.bin", 4 * 1048576))
    ends = list(re.finditer(rb"(?:^|[\r\n])CMU1 " + tag.encode() + rb" END 0\r?\n", rx))
    if len(ends) != 1 or not stock.PROMPT.search(rx[ends[0].end():]):
        raise ValueError("actual core END0 followed by normal PS1 is required")
    records = [line for line in raw.splitlines() if line.startswith(BIND)]
    if len(records) != 1:
        raise ValueError("one actual CANDIDATE_BOOT_BIND output line is required")
    fields = records[0].decode("ascii").split("|")
    if (len(fields) != 10 or fields[1:3] != [nonce, "C"] or fields[4:] !=
            ["94055", CMD5, "776631029", "ro", "1", "candidate_verified"]):
        raise ValueError("candidate C apply/rootRO/recovery/control binding refused")
    candidate_identity(fields[3])
    return dict(schema=1, trial_nonce=nonce, source_kind="C", source_identity=fields[3],
                bytes=94055, md5=CMD5, crc=CCRC, physical_root_ro=True,
                recovery_ready_before_publish=True, control_phase="candidate_verified",
                apply_evidence=str(Path(path).resolve()), core_bundle=str(bundle),
                manifest_sha256=digest((bundle / "manifest.json").read_bytes()),
                operation_nonce=tag, output_sha256=digest(raw))


# A logger may have an unfinished line when the command emits its first field.
# Accept that prefix, but require one complete, uniquely typed record per field.
FIELD_SHAPES = {
    "META": rb"[0-9]+(?::[0-9]+){7}",
    "HASH": rb"[0-9a-f]{32}[ \t]+-",
    "CRC": rb"[0-9]+[ \t]+[0-9]+",
    "ROOT": rb"[^ \t|]+(?:[ \t]+[^ \t|]+){5}",
    "UPTIME": rb"[0-9]+(?:\.[0-9]+)?[ \t]+[0-9]+(?:\.[0-9]+)?",
    "BOOT_ID": rb"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
}


def candidate_fields(raw):
    found = {}
    lines = raw.split(b"\n")
    for index, line in enumerate(lines):
        count = line.count(b"SWST|")
        if not count:
            continue
        if index == len(lines) - 1:
            raise ValueError("unterminated candidate persistence record")
        if count != 1:
            raise ValueError("interleaved candidate persistence markers")
        line = line.removesuffix(b"\r")
        record = line[line.index(b"SWST|"):]
        match = re.fullmatch(rb"SWST\|([A-Z_]+)\|([^|\r\n]*)", record)
        if match is None:
            raise ValueError("malformed candidate persistence record")
        key = match[1].decode("ascii")
        if key not in FIELDS or key in found:
            raise ValueError("unexpected/duplicate candidate persistence field")
        value = match[2].strip(b" \t")
        if any((c < 32 and c != 9) or c == 127 for c in value):
            raise ValueError("control byte in candidate persistence value")
        if re.fullmatch(FIELD_SHAPES[key], value) is None:
            raise ValueError("malformed/partial candidate persistence value")
        found[key] = value.decode("ascii")
    if set(found) != FIELDS:
        raise ValueError("missing/unexpected candidate persistence field")
    return found


def checked_candidate_output(status, raw, binding, before=None):
    if status != 0:
        raise ValueError("candidate C persistence check nonzero")
    found = candidate_fields(raw)
    current = observed_identity(found["META"])
    candidate_identity(binding["source_identity"])
    if found["HASH"].split() != [CMD5, "-"] or " ".join(found["CRC"].split()) != CCRC:
        raise ValueError("source bytes are not the applied candidate C")
    row = found["ROOT"].split()
    if (len(row) != 6 or row[:3] != ["/dev/ffx01p1", "/", "relfs"] or
            "ro" not in row[3].split(",") or "rw" in row[3].split(",")):
        raise ValueError("candidate C physical root must be RO")
    uptime = float(found["UPTIME"].split()[0])
    if not math.isfinite(uptime) or uptime < 0:
        raise ValueError("invalid candidate C uptime")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", found["BOOT_ID"]):
        raise ValueError("invalid candidate C boot identity")
    if before is not None and (found["BOOT_ID"] == before["BOOT_ID"] or uptime >= before["uptime_seconds"]):
        raise ValueError("new candidate kernel boot/lower uptime not established")
    found.update(uptime_seconds=uptime, source_bytes_kind="C",
                 applied_source_identity=binding["source_identity"])
    if found["META"] != binding["source_identity"]:
        if before is None:
            raise ValueError("candidate preflight is not the exact applied full C identity")
        found.update(source_kind="OTHER", recovery_classification="OTHER",
                     recovery_identity_conflict=True, restore_ready=False, automatic_adoption=False)
        raise RecoveryIdentityConflict(found)
    # Exact full identity is necessary for the current persistent classifier.
    # Its independent VERIFY is still required; this observer does not claim undo readiness.
    found.update(source_kind="C", recovery_classification="C",
                 recovery_identity_matches=True, persistent_verify_still_required=True)
    return found


def make_profile(binding=None):
    pins = dict(json_data(STOCK_REVIEW)["source_pins"])
    pins[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).read_bytes())
    pins[str(STOCK_REVIEW.relative_to(ROOT))] = digest(STOCK_REVIEW.read_bytes())
    return dict(mode="CANDIDATE_STARTUP_REVIEW_ONLY", live_authority=False, reboot_hex=None,
                normal_reboot_route_verified=False, source_kind="C", request_limit=1,
                credential_attempts=1, deadline_s=180, source_pins=pins, apply_binding=binding,
                recovery_identity_policy=IDENTITY_POLICY, persistent_verify_still_required=True)


def live_profile(path):
    profile = json_data(path)
    if (profile.get("live_authority") is not True or profile.get("reboot_hex") != stock.REBOOT.hex() or
            profile.get("normal_reboot_route_verified") is not True or profile.get("source_kind") != "C" or
            profile.get("request_limit") != 1 or profile.get("credential_attempts") != 1 or
            profile.get("deadline_s") != 180 or profile.get("recovery_identity_policy") != IDENTITY_POLICY):
        raise ValueError("review-only candidate profile; separate combined trial disposition required")
    required = {str(Path(__file__).resolve().relative_to(ROOT)), str(STOCK_PATH.relative_to(ROOT)),
                "src/open_connect/session.py", str(STOCK_REVIEW.relative_to(ROOT))}
    if not required.issubset(profile.get("source_pins", {})):
        raise ValueError("missing candidate/corrected-stock/core source pins")
    for name, expected in profile["source_pins"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("candidate profile source mismatch")
    binding = profile.get("apply_binding")
    if not binding or apply_binding(binding["apply_evidence"]) != binding:
        raise ValueError("candidate profile does not match actual apply evidence")
    return profile, binding


def observe(args, profile, binding):
    username, password = stock.private_credentials(args.credentials)
    bundle = stock.Bundle(args.bundle, "ONE candidate C warm startup", args.owner, mode="live")
    bundle.meta.update(profile=profile, expected_source_kind="C", apply_binding=binding)
    video = Video(bundle, args.camera_index)
    outcome, error, port, requested = "failed_before_request", None, None, False
    with stock.AdapterLock(owner=args.owner, purpose="ONE candidate C startup"):
        try:
            port = stock.open_adapter(bundle)
            session = stock.Session(port, bundle, timeout=20, output_cap=stock.MAX_RX)
            session.observe_prompt(solicit=args.solicit_prompt)
            session.identify()
            before = checked_candidate_output(*session.execute(stock.CHECK), binding)
            bundle.save("before.json", (json.dumps(before, indent=2) + "\n").encode())
            video.start()
            start = time.monotonic()
            deadline = start + 180
            received = bytearray()
            requested = True
            session.state, session.identity = "intentional_restart", None
            bundle.event("restart_request", command_hex=stock.REBOOT.hex(), source_kind="C",
                         no_framed_END_expected=True, deadline_monotonic=deadline)
            session._send(stock.REBOOT, deadline=min(deadline, start + 2), received=received)
            gate = BootGate()
            pending_rx = bytearray(received)
            while time.monotonic() < deadline:
                if pending_rx:
                    chunk = bytes(pending_rx)
                    pending_rx.clear()
                else:
                    chunk = session._read(received, until=deadline)
                if not chunk:
                    continue
                event = gate.feed(chunk)
                if event:
                    bundle.event("restart_transition", transition=event)
                if event in ("login", "password"):
                    credential = username if event == "login" else password
                    session._send(credential, deadline=min(deadline, time.monotonic() + 2),
                                  received=received, on_rx=pending_rx.extend)
                if event == "shell":
                    session.state = "shell"
                    session.timeout = min(20, deadline - time.monotonic())
                    if session.timeout <= 1:
                        raise TimeoutError("no time for bounded fresh candidate identity")
                    session.identify()
                    session.timeout = min(20, deadline - time.monotonic())
                    after = checked_candidate_output(*session.execute(stock.CHECK), binding, before)
                    bundle.save("after.json", (json.dumps(after, indent=2) + "\n").encode())
                    bundle.event("post_restart_verified", elapsed_s=time.monotonic() - start,
                                 root_identity=session.identity, source_C=True, physical_root_RO=True)
                    tail = min(deadline, time.monotonic() + 20)
                    while time.monotonic() < tail:
                        extra = session._read(received, until=tail)
                        if extra:
                            gate.raw.extend(extra)
                            if len(list(stock.KERNEL_BANNER.finditer(stock.ANSI.sub(b"", bytes(gate.raw))))) > 1:
                                raise RuntimeError("second kernel during candidate settling")
                    outcome = SUCCESS
                    break
            else:
                raise TimeoutError("180s candidate readiness deadline; no retry/recovery")
        except RecoveryIdentityConflict as exc:
            bundle.save("after-conflict.json", (json.dumps(exc.observation, indent=2) + "\n").encode())
            bundle.meta.update(recovery_identity_conflict=True, recovery_classification="OTHER",
                               actual_post_source_identity=exc.observation["META"],
                               restore_ready=False, automatic_adoption=False)
            bundle.event("recovery_identity_conflict", actual_identity=exc.observation["META"],
                         applied_identity=binding["source_identity"], classification="OTHER",
                         preserve=True, automatic_adoption=False)
            error = type(exc).__name__ + ": " + str(exc)
            outcome = CONFLICT
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
            outcome = "unknown_after_request" if requested else "failed_before_request"
        finally:
            try:
                video.stop()
            except BaseException as exc:
                error = (error or "") + "; camera cleanup: " + str(exc)
                if outcome == SUCCESS:
                    outcome = VIDEO_FAILED
                elif outcome != CONFLICT:
                    outcome = "unknown_after_request" if requested else "failed_before_request"
            if port is not None:
                port.close()
                bundle.meta["port_closed"] = True
            bundle.finish(outcome, error)
    print(json.dumps(dict(outcome=outcome, error=error, bundle=str(args.bundle),
                          post_source_kind="C" if outcome in (SUCCESS, VIDEO_FAILED) else None)))
    return 0 if outcome == SUCCESS else 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply-evidence", type=Path)
    p.add_argument("--write-profile", type=Path)
    p.add_argument("--live", action="store_true")
    p.add_argument("--profile", type=Path)
    p.add_argument("--bundle", type=Path)
    p.add_argument("--credentials", type=Path)
    p.add_argument("--camera-index", type=int)
    p.add_argument("--owner", default="t14")
    p.add_argument("--solicit-prompt", action="store_true")
    args = p.parse_args(argv)
    if not args.live:
        binding = apply_binding(args.apply_evidence) if args.apply_evidence else None
        profile = make_profile(binding)
        if args.write_profile:
            if binding is None:
                raise ValueError("actual apply evidence required before writing a bound profile")
            args.write_profile.write_text(json.dumps(profile, indent=2) + "\n")
        print(json.dumps(profile, indent=2))
        return 0
    if args.write_profile or args.apply_evidence:
        p.error("live uses an approved bound profile, not an evidence/profile-writing operation")
    if not args.profile:
        p.error("live requires a separately approved candidate profile")
    profile, binding = live_profile(args.profile)  # refuses before credentials/locks/device opens
    if not all((args.bundle, args.credentials)) or args.camera_index is None or args.camera_index < 0:
        p.error("live requires private bundle/credentials and camera-index")
    return observe(args, profile, binding)


if __name__ == "__main__":
    raise SystemExit(main())
