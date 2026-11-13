#!/usr/bin/env python3
"""One bench setup/status/teardown. Dry-run by default; current profile: silent UI."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cmu_bench.session import AdapterLock, BenchError, Bundle, Session, UnknownOutcome, open_adapter, digest

PROFILE = "silent-ui-v1"
STATE = ROOT / ".bench-state" / "profile.json"
BUS = "unix:path=/tmp/dbus_hmi_socket"
SERVICE = "com.xsembedded.service.AudioManagement"
OBJECT = "/com/xse/service/AudioManagement/HmiMode"
METHOD = "com.xsembedded.ServiceProvider.Request"
RO = """awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{n++;m=$4}END{exit !(n==1&&m=="ro,noatime")}' /proc/mounts || exit 70"""
BOOT = "/proc/sys/kernel/random/boot_id"
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
OWNER = r":[0-9]+\.[0-9]+"
IDENTIFIERS = {"boot": UUID, "bus": r"[0-9a-f]{32}", "owner": OWNER}


class Conflict(BenchError):
    pass


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Conflict("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs)
    except (ValueError, TypeError) as exc:
        raise Conflict("invalid JSON data") from exc


def binding(value):
    if not isinstance(value, dict) or set(value) != set(IDENTIFIERS):
        raise Conflict("invalid service binding")
    if any(not isinstance(value[k], str) or not re.fullmatch(p, value[k])
           for k, p in IDENTIFIERS.items()):
        raise Conflict("invalid service identity")
    return value


def dbus_string(raw, sender=None):
    """Parse dbus-send's one-string return, including unescaped inner JSON quotes."""
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise Conflict("non-ASCII DBus response") from exc
    if len(lines) != 2 or not re.fullmatch(
            r"method return sender=(?:org\.freedesktop\.DBus|:[0-9]+\.[0-9]+) -> dest=:[0-9]+\.[0-9]+ reply_serial=[0-9]+",
            lines[0]):
        raise Conflict("malformed DBus return")
    actual_sender = lines[0].split("sender=", 1)[1].split(" ", 1)[0]
    if sender is not None and actual_sender != sender:
        raise Conflict("reply from unexpected service owner")
    if not lines[1].startswith('   string "') or not lines[1].endswith('"'):
        raise Conflict("expected exactly one DBus string")
    return lines[1][11:-1]


def request(dest, obj, method, *args):
    return " ".join(shlex.quote(v) for v in [
        "dbus-send", "--address=" + BUS, "--dest=" + dest, "--type=method_call",
        "--print-reply", "--reply-timeout=2000", obj, method, *args])


def bus_call(method, *args):
    return request("org.freedesktop.DBus", "/org/freedesktop/DBus",
                   "org.freedesktop.DBus." + method, *args)


def audio_call(owner, method, arguments):
    binding({"boot": "00000000-0000-0000-0000-000000000000", "bus": "0" * 32, "owner": owner})
    return request(owner, OBJECT, METHOD, "string:" + method, "string:" + arguments)


def records(raw, token, expected):
    """Nonce-tagged fields; tolerate a logger prefix, never partial/duplicate records."""
    result = {}
    pattern = re.compile(rb"BP1 " + token.encode() + rb" ([a-z_]+) ([A-Za-z0-9+/=]+)$")
    for line in raw.replace(b"\r\n", b"\n").splitlines():
        if b"BP1 " + token.encode() not in line:
            continue
        match = pattern.search(line)
        if not match or line.count(b"BP1 ") != 1:
            raise Conflict("malformed profile record")
        key = match[1].decode()
        if key not in expected or key in result:
            raise Conflict("unknown/duplicate profile field")
        try:
            result[key] = base64.b64decode(match[2], validate=True)
        except ValueError as exc:
            raise Conflict("bad profile encoding") from exc
    if set(result) != set(expected):
        raise Conflict("missing profile field")
    return result


def envelope(token):
    return """set -fu
""" + RO + """
emit() {
 v=$(printf '%s' "$2" | base64 | tr -d '\n') || exit 71
 printf '\nBP1 %s %s %s\n' """ + shlex.quote(token) + """ "$1" "$v"
}
scalar() { sed -n 's/^   string "\\(.*\\)"$/\\1/p'; }
"""


def observe_command(token):
    return envelope(token) + """
boot=$(cat """ + BOOT + """) || exit 72
bus=$(""" + bus_call("GetId") + """) || exit 73
owner=$(""" + bus_call("GetNameOwner", "string:" + SERVICE) + """) || exit 74
o=$(printf '%s\n' "$owner" | scalar)
case "$o" in :[0-9]*.[0-9]*) ;; *) exit 75;; esac
status=$(dbus-send --address=""" + BUS + """ --dest="$o" --type=method_call --print-reply --reply-timeout=2000 """ + OBJECT + " " + METHOD + """ string:enableStatus 'string:{}') || exit 76
bus_after=$(""" + bus_call("GetId") + """) || exit 77
owner_after=$(""" + bus_call("GetNameOwner", "string:" + SERVICE) + """) || exit 78
test "$(cat """ + BOOT + """)" = "$boot" || exit 79
emit boot "$boot"
emit bus "$bus"
emit owner "$owner"
emit status "$status"
emit bus_after "$bus_after"
emit owner_after "$owner_after"
"""


def set_command(token, instance, enabled):
    binding(instance)
    return envelope(token) + """
test "$(cat """ + BOOT + """)" = """ + shlex.quote(instance["boot"]) + """ || exit 80
bus=$(""" + bus_call("GetId") + """) || exit 81
owner=$(""" + bus_call("GetNameOwner", "string:" + SERVICE) + """) || exit 82
test "$(printf '%s\n' "$bus" | scalar)" = """ + shlex.quote(instance["bus"]) + """ || exit 83
test "$(printf '%s\n' "$owner" | scalar)" = """ + shlex.quote(instance["owner"]) + """ || exit 84
reply=$(""" + audio_call(instance["owner"], "enable", json.dumps({"enable": enabled}, separators=(",", ":"))) + """)
rc=$?
test "$rc" -eq 0 || exit "$rc"
emit reply "$reply"
"""


class Audio:
    def __init__(self, session, deadline):
        self.session, self.deadline = session, deadline

    def execute(self, command):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Conflict("bench operation deadline exceeded")
        self.session.timeout = min(60, remaining)
        rc, raw = self.session.execute(command)
        if rc:
            raise Conflict("remote operation returned " + str(rc))
        return raw

    def observe(self):
        token = secrets.token_hex(16)
        fields = records(self.execute(observe_command(token)), token,
                         {"boot", "bus", "owner", "status", "bus_after", "owner_after"})
        instance = binding(dict(boot=fields["boot"].decode("ascii"),
                                bus=dbus_string(fields["bus"]),
                                owner=dbus_string(fields["owner"])))
        if (dbus_string(fields["bus_after"]) != instance["bus"] or
                dbus_string(fields["owner_after"]) != instance["owner"]):
            raise Conflict("service changed during observation")
        value = strict_json(dbus_string(fields["status"], instance["owner"]))
        if not isinstance(value, dict) or set(value) != {"enable"} or type(value["enable"]) is not bool:
            raise Conflict("expected strict enable boolean")
        return dict(binding=instance, enabled=value["enable"])

    def set(self, instance, enabled):
        token = secrets.token_hex(16)
        fields = records(self.execute(set_command(token, instance, enabled)), token, {"reply"})
        if strict_json(dbus_string(fields["reply"], instance["owner"])) != {}:
            raise Conflict("unexpected enable acknowledgement")

    def verify(self, instance, enabled):
        # Reply precedes state change; read back. Never resend a mutation.
        for attempt in range(5):
            actual = self.observe()
            if actual["binding"] != instance:
                raise Conflict("service owner/bus/boot changed; no further mutation")
            if actual["enabled"] is enabled:
                return actual
            if attempt < 4:
                time.sleep(min(0.2, max(0, self.deadline - time.monotonic())))
        raise Conflict("audio state did not converge before bounded readback")


class Store:
    """Small private host receipt. Serialized by the same FTDI AdapterLock."""
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists() and not self.path.is_symlink():
            return None
        info = self.path.lstat()
        parent = self.path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077
                or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 8192):
            raise Conflict("unsafe bench receipt")
        record = strict_json(self.path.read_text())
        keys = {"schema", "profile", "desired", "phase", "binding", "before", "owned", "bundle"}
        if (not isinstance(record, dict) or set(record) != keys or record["schema"] != 1
                or record["profile"] != PROFILE or record["desired"] not in ("on", "off")
                or record["phase"] not in ("setup_pending", "on", "teardown_pending", "off")
                or type(record["before"]) is not bool or type(record["owned"]) is not bool
                or not isinstance(record["bundle"], str)):
            raise Conflict("invalid bench receipt")
        binding(record["binding"])
        if record["owned"] and record["before"]:
            raise Conflict("cannot own a pre-enabled helper")
        if ((record["phase"] in ("setup_pending", "on")) != (record["desired"] == "on")
                or (record["phase"] == "off" and record["owned"])):
            raise Conflict("inconsistent bench receipt")
        return record

    def save(self, record):
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        parent = self.path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise Conflict("unsafe receipt directory")
        self.load()  # refuse an unsafe existing path before replacing it
        fd, name = tempfile.mkstemp(prefix=".profile-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(record, f, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def summary(record, observed, action):
    same = record is not None and record["binding"] == observed["binding"]
    return dict(profile=PROFILE, action=action,
                desired=record["desired"] if record else "off",
                active=bool(same and record["phase"] == "on" and observed["enabled"]),
                phase=record["phase"] if record else "off",
                audio_enabled=observed["enabled"], same_instance=same,
                owned=bool(same and record["owned"]), binding=observed["binding"],
                startup_hook_installed=False)


def transition(action, audio, store, bundle):
    previous = store.load()
    observed = audio.observe()
    if action == "status":
        return summary(previous, observed, action)
    same = previous is not None and previous["binding"] == observed["binding"]
    if action == "setup":
        if same and previous["phase"].endswith("_pending"):
            raise Conflict("pending operation: inspect status or use teardown; no repeated setup mutation")
        if same and previous["phase"] == "on":
            if not observed["enabled"]:
                raise Conflict("active bench override was lost; teardown before a new setup")
            return summary(previous, observed, action)
        record = dict(schema=1, profile=PROFILE, desired="on", phase="setup_pending",
                      binding=observed["binding"], before=observed["enabled"],
                      owned=not observed["enabled"], bundle=str(bundle))
        store.save(record)  # receipt before mutation, including ambiguous outcomes
        if record["owned"]:
            try:
                audio.set(record["binding"], True)
            except UnknownOutcome:
                raise  # no commands after uncertain UART completion
            except Conflict:
                # A known-completed ambiguous reply can be reconciled by reads.
                observed = audio.verify(record["binding"], True)
            else:
                observed = audio.verify(record["binding"], True)
        record["phase"] = "on"
        store.save(record)
        return summary(record, observed, action)
    if action != "teardown":
        raise ValueError("unknown profile action")
    if previous is None:
        return summary(None, observed, action)
    record = dict(previous, desired="off", phase="teardown_pending", bundle=str(bundle))
    store.save(record)
    if same and record["owned"] and observed["enabled"]:
        try:
            audio.set(record["binding"], False)
        except UnknownOutcome:
            raise
        except Conflict:
            observed = audio.verify(record["binding"], False)
        else:
            observed = audio.verify(record["binding"], False)
    record.update(phase="off", owned=False)
    store.save(record)
    result = summary(record, observed, action)
    result["expired_previous_instance"] = not same
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "status", "teardown"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--owner", default=os.environ.get("HC_TERMINAL_ID") or "oc-" + str(os.getpid()))
    parser.add_argument("--solicit-prompt", action="store_true")
    parser.add_argument("--deadline", type=float, default=40)
    args = parser.parse_args(argv)
    if not 0 < args.deadline <= 60:
        parser.error("deadline must be >0 and <=60 seconds")
    if not args.live:
        print(json.dumps(dict(outcome="dry_run_not_executed", action=args.action,
                              profile=PROFILE, live=False, executed=False,
                              opens_port=False, modifies_device=False, state_written=False,
                              planned_state_path=str(args.state), startup_hook_installed=False,
                              message="Preview only. No bench operation ran; no state file was written. Use --live with a fresh --bundle and known connection state to execute.")))
        return 0
    if args.bundle is None or not args.owner:
        parser.error("live requires a fresh --bundle and a nonempty owner label")
    bundle = Bundle(args.bundle, "bench profile " + args.action, args.owner, mode="live")
    bundle.save("profile.py", Path(__file__).read_bytes())
    bundle.meta["profile_code_sha256"] = digest(Path(__file__).read_bytes())
    port = session = None
    outcome, error, code = "failed", None, 1
    try:
        with AdapterLock(owner=args.owner, purpose="bench profile " + args.action):
            try:
                store = Store(args.state)
                prior = store.load()  # refuse damaged receipt before any device mutation
                bundle.save("state-before.json", json.dumps(prior, indent=2).encode())
                port = open_adapter(bundle)
                deadline = time.monotonic() + args.deadline
                session = Session(port, bundle, timeout=args.deadline, output_cap=1048576)
                session.observe_prompt(solicit=args.solicit_prompt)
                session.timeout = max(0.001, deadline - time.monotonic())
                session.identify()
                result = transition(args.action, Audio(session, deadline), store, bundle.path)
                bundle.save("profile-result.json", json.dumps(result, indent=2).encode())
                bundle.meta["bench_profile"] = result
                outcome, code = "verified", 0
            finally:
                if port is not None:
                    port.close()
                bundle.meta["port_closed"] = True
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        error = type(exc).__name__ + ": " + str(exc)
        if isinstance(exc, UnknownOutcome) or (session is not None and session.state == "uncertain"):
            outcome, code = "unknown", 2
    finally:
        bundle.finish(outcome, error)
    print(json.dumps(dict(outcome=outcome, error=error, bundle=str(bundle.path),
                          bench_profile=bundle.meta.get("bench_profile"))))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
