"""One owner, lossless evidence, nonce-framed commands; no login or action retries."""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import secrets
import shlex
import stat
import time
from pathlib import Path

IDENTITY = (0x0403, 0x6001, "A9048JM0")
TX_CHUNK_BYTES = 64
TX_GAP_SECONDS = 0.020
SETTINGS = dict(
    baudrate=115200,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=0.05,
    write_timeout=1,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
    exclusive=True,
)
ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]")
PROMPT = re.compile(rb"(?:^|[\r\n])(?:/[^\r\n]{0,160}|~|(?:root|user)@cmu:[^\r\n]{0,160}) [#$] ")
LOGIN = re.compile(rb"(?:^|[\r\n])(?:cmu )?login:\s*", re.I)
CONTINUATION = re.compile(rb"(?:^|[\r\n])> ")
PASSWORD = re.compile(rb"(?:^|[\r\n])password:\s*", re.I)


class BenchError(Exception):
    pass


class ProtocolError(BenchError):
    pass


class UnknownOutcome(BenchError):
    """TX may have executed. The connection must not be used for more actions."""


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def nonce():
    return secrets.token_hex(16)


def check_nonce(value):
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("nonce must be 128-bit lowercase hex")
    return value


class AdapterLock:
    """Persistent inode, flock held until close; never unlink a lock file."""

    def __init__(self, directory=None, owner="unspecified", purpose="capture"):
        self.directory = Path(directory or (Path("/tmp") / f"cmu-bench-locks-{os.getuid()}"))
        self.owner, self.purpose, self.fd = owner, purpose, None
        self.path = self.directory / (digest(repr(IDENTITY).encode()) + ".lock")

    def __enter__(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise BenchError("lock directory must be owned, private, and not a symlink")
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise BenchError("unsafe lock inode")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = fd
            metadata = dict(
                pid=os.getpid(),
                process_instance=nonce(),
                owner=self.owner,
                acquired_at=utcnow(),
                identity=IDENTITY,
                purpose=self.purpose,
            )
            os.ftruncate(fd, 0)
            os.write(fd, (json.dumps(metadata) + "\n").encode())
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            self.fd = None
            raise
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def resolve_adapter(enumerator=None):
    if enumerator is None:
        from serial.tools import list_ports

        enumerator = list_ports.comports
    found = [p for p in enumerator() if (p.vid, p.pid, p.serial_number) == IDENTITY]
    if len(found) != 1:
        raise BenchError("FTDI 0403:6001/A9048JM0 must enumerate uniquely")
    port = found[0]
    # This production entry point has no PTY/device override.
    if not port.device.startswith("/dev/cu.usbserial-"):
        raise BenchError("expected macOS USB callout device, refusing arbitrary path")
    return dict(
        device=port.device,
        vid=port.vid,
        pid=port.pid,
        serial_number=port.serial_number,
        location=port.location,
    )


def open_adapter(bundle):
    """Caller must hold AdapterLock through serial.close AND bundle.finish."""
    import serial

    before = resolve_adapter()
    bundle.meta.update(adapter_observed=True, adapter_before_open=before)
    after = resolve_adapter()
    if before != after:
        raise BenchError("adapter changed during re-enumeration; no port opened")
    bundle.meta["adapter"] = after
    port = serial.Serial(port=None, **SETTINGS)
    try:
        port.dtr = False
        port.rts = False
        port.port = after["device"]
        port.open()
        bundle.meta["serial_port_opened"] = True
        if resolve_adapter() != after:
            raise BenchError("adapter changed while opening; no TX permitted")
        return port
    except BaseException:
        port.close()
        raise


class Bundle:
    def __init__(self, path, intent, owner, mode="offline"):
        self.path = Path(path)
        self.path.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.streams = {}
        for name in ("rx.bin", "tx.bin", "events.jsonl"):
            fd = os.open(self.path / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            self.streams[name] = os.fdopen(fd, "wb")
        self.started = time.monotonic_ns()
        self.closed = False
        code = {}
        for p in sorted(Path(__file__).parent.glob("*.py")):
            code[str(p)] = digest(p.read_bytes())
        cli = Path(__file__).with_name("uart.py")
        if cli.exists():
            code[str(cli)] = digest(cli.read_bytes())
        self.meta = dict(
            schema=1,
            run_id=nonce(),
            intent=intent,
            owner=owner,
            mode=mode,
            started_at=utcnow(),
            python=os.sys.version,
            code_sha256=code,
            settings=SETTINGS,
            operations=[],
            outcome="in_progress",
            live_requested=(mode == "live"),
            adapter_observed=False,
            serial_port_opened=False,
            port_closed=False,
        )

    def event(self, kind, **data):
        row = dict(
            at=utcnow(),
            monotonic_ns=time.monotonic_ns(),
            elapsed_ns=time.monotonic_ns() - self.started,
            kind=kind,
            **data,
        )
        f = self.streams["events.jsonl"]
        f.write((json.dumps(row, sort_keys=True) + "\n").encode())
        f.flush()

    def record(self, direction, data):
        if direction not in ("rx", "tx"):
            raise ValueError(direction)
        f = self.streams[direction + ".bin"]
        f.write(data)
        f.flush()
        self.event("bytes", direction=direction, length=len(data), hex=data.hex())

    def save(self, name, data):
        if Path(name).name != name:
            raise ValueError("artifact must be a basename")
        fd = os.open(self.path / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

    def finish(self, outcome, error=None):
        if self.closed:
            return
        self.meta.update(
            outcome=outcome,
            error=error,
            ended_at=utcnow(),
            elapsed_ns=time.monotonic_ns() - self.started,
        )
        self.event("finish", outcome=outcome, error=error)
        for f in self.streams.values():
            f.flush()
            os.fsync(f.fileno())
            f.close()
        files = {}
        for p in sorted(self.path.iterdir()):
            if p.is_file():
                data = p.read_bytes()
                files[p.name] = dict(bytes=len(data), sha256=digest(data))
        self.meta["artifacts"] = files
        self.save(
            "manifest.json", (json.dumps(self.meta, indent=2, sort_keys=True) + "\n").encode()
        )
        self.closed = True


def prompt_state(data):
    clean = ANSI.sub(b"", data)
    matches = []
    for state, pattern in (
        ("shell", PROMPT),
        ("login", LOGIN),
        ("password", PASSWORD),
        ("continuation", CONTINUATION),
    ):
        matches.extend((m.start(), state) for m in pattern.finditer(clean))
    return max(matches)[1] if matches else "unknown"


def wrap_command(command, token):
    check_nonce(token)
    if "\x00" in command or not command.strip():
        raise ValueError("empty/NUL command")
    # Format and nonce are separate arguments: echoed TX contains no complete frame.
    text = (
        "printf '\\nCMU1 %s BEGIN\\n' "
        + shlex.quote(token)
        + "; sh -c "
        + shlex.quote(command)
        + "; _cmu_rc=$?; printf '\\nCMU1 %s END %s\\n' "
        + shlex.quote(token)
        + ' "$_cmu_rc"\r'
    )
    wire = text.encode("utf-8")
    if any(len(line) > 600 for line in wire.splitlines()) or len(wire) > 32768:
        raise ValueError(
            "TX exceeds 600 bytes/physical line or 32 KiB total; split the command explicitly"
        )
    return wire


class CommandDecoder:
    def __init__(self, token):
        self.token = check_nonce(token).encode()
        self.prefix = b"CMU1 " + self.token + b" "
        self.buffer = bytearray()
        self.output = bytearray()
        self.started = False
        self.exit_status = None
        self.after_end = bytearray()

    def feed(self, data):
        if self.exit_status is not None:
            self.after_end.extend(data)
            # Still check complete extra lines for duplicate frames.
        self.buffer.extend(data)
        if len(self.buffer) > 262144:
            raise ProtocolError("overlong unterminated line")
        while b"\n" in self.buffer:
            raw, _, rest = self.buffer.partition(b"\n")
            self.buffer[:] = rest
            line = bytes(raw).removesuffix(b"\r")
            if line.startswith(self.prefix):
                suffix = line[len(self.prefix) :]
                if suffix == b"BEGIN" and not self.started and self.exit_status is None:
                    self.started = True
                elif (
                    re.fullmatch(rb"END (?:0|[1-9][0-9]{0,2})", suffix)
                    and self.started
                    and self.exit_status is None
                ):
                    value = int(suffix.split()[1])
                    if value > 255:
                        raise ProtocolError("invalid shell exit status")
                    self.exit_status = value
                    self.after_end[:] = self.buffer
                else:
                    raise ProtocolError("duplicate, malformed, or out-of-order command frame")
            elif self.started and self.exit_status is None:
                self.output.extend(raw + b"\n")

    @property
    def complete(self):
        return self.exit_status is not None and prompt_state(self.after_end) == "shell"


IDENTIFY = """id
uname -a
while IFS= read -r _cmu_line; do
case "$_cmu_line" in
JCI_SW_VER=*|JCI_SW_VER_PATCH=*|JCI_SW_FLAVOR=*) printf '%s\\n' "$_cmu_line";;
esac
done < /jci/version.ini"""


def verify_identity(output):
    lines = output.replace(b"\r\n", b"\n").splitlines()
    ids = [line for line in lines if re.match(rb"uid=[0-9]+\(", line)]
    if len(ids) != 1 or not re.match(rb"uid=0\(root\)(?: |$)", ids[0]):
        raise ProtocolError("fresh unambiguous root id response required")
    expected = {
        b"JCI_SW_VER": b"MAZ_CMU-150_55.00.750",
        b"JCI_SW_VER_PATCH": b"B",
        b"JCI_SW_FLAVOR": b"cmu150_NA",
    }
    for key, value in expected.items():
        observed = [
            line.split(b"=", 1)[1].strip().strip(b'"')
            for line in lines
            if line.startswith(key + b"=")
        ]
        if observed != [value]:
            raise ProtocolError("firmware baseline missing, ambiguous, or changed: " + key.decode())
    return dict(uid=0, user="root", firmware="55.00.750B", flavor="cmu150_NA")


class Session:
    def __init__(self, transport, bundle, timeout=10, output_cap=1048576):
        if not 0 < timeout <= 60 or not 0 < output_cap <= 4 * 1048576:
            raise ValueError("deadline/cap out of range")
        self.transport, self.bundle = transport, bundle
        self.timeout, self.output_cap = timeout, output_cap
        self.state, self.identity = "unknown", None

    def _read(self, received, until=None):
        previous = getattr(self.transport, "timeout", None)
        adjustable = hasattr(self.transport, "timeout")
        if until is not None:
            remaining = until - time.monotonic()
            if remaining <= 0:
                return b""
            if adjustable:
                self.transport.timeout = min(
                    previous if previous is not None else remaining, remaining
                )
        try:
            chunk = self.transport.read(4096)
        finally:
            if adjustable and until is not None:
                self.transport.timeout = previous
        if chunk:
            self.bundle.record("rx", chunk)
            received.extend(chunk)
            if len(received) > self.output_cap:
                raise BenchError("operation RX cap exceeded; evidence retained")
        return chunk

    def _send(self, data, *, deadline, received, on_rx=None, operation=None):
        profile = dict(
            chunk_bytes=TX_CHUNK_BYTES,
            gap_seconds=TX_GAP_SECONDS,
            acknowledgment="host write count, not target acknowledgment",
        )
        self.bundle.meta["tx_profile"] = profile
        request = dict(
            id=nonce(),
            requested_bytes=len(data),
            acknowledged_bytes=0,
            completed_chunks=0,
            write_calls=0,
            gaps=0,
            outcome="unknown",
            started_at=utcnow(),
            **profile,
        )
        self.bundle.meta.setdefault("transmissions", []).append(request)
        if operation is not None:
            operation["tx_request_id"] = request["id"]
        self.bundle.event(
            "tx_requested",
            request_id=request["id"],
            length=len(data),
            sha256=digest(data),
            hex=data.hex(),
            profile=profile,
        )
        sent = 0
        original_write_timeout = getattr(self.transport, "write_timeout", None)
        adjustable_write = hasattr(self.transport, "write_timeout")
        try:
            while sent < len(data):
                chunk_start = sent
                chunk_end = min(sent + TX_CHUNK_BYTES, len(data))
                calls = 0
                # Partial writes finish THIS chunk; they do not add pacing gaps.
                while sent < chunk_end:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("operation deadline during TX")
                    if adjustable_write:
                        self.transport.write_timeout = min(
                            original_write_timeout
                            if original_write_timeout is not None
                            else remaining,
                            remaining,
                        )
                    request["write_calls"] += 1
                    calls += 1
                    n = self.transport.write(data[sent:chunk_end])
                    if n is None or not 0 < n <= chunk_end - sent:
                        raise OSError("invalid/zero write count")
                    self.bundle.record("tx", data[sent : sent + n])
                    sent += n
                    request["acknowledged_bytes"] = sent
                request["completed_chunks"] += 1
                self.bundle.event(
                    "tx_chunk",
                    request_id=request["id"],
                    offset=chunk_start,
                    length=sent - chunk_start,
                    write_calls=calls,
                    acknowledged_total=sent,
                )
                if time.monotonic() >= deadline:
                    raise TimeoutError("operation deadline during TX")
                if sent < len(data):
                    started = time.monotonic()
                    gap_end = started + TX_GAP_SECONDS
                    rx_before = len(received)
                    completed = False
                    try:
                        while time.monotonic() < gap_end:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("operation deadline during TX gap")
                            chunk = self._read(received, until=min(gap_end, deadline))
                            if chunk and on_rx is not None:
                                on_rx(chunk)
                        completed = True
                    finally:
                        request["gaps"] += 1
                        self.bundle.event(
                            "tx_gap",
                            request_id=request["id"],
                            after_acknowledged_bytes=sent,
                            requested_seconds=TX_GAP_SECONDS,
                            actual_seconds=time.monotonic() - started,
                            rx_bytes=len(received) - rx_before,
                            completed=completed,
                        )
            request["outcome"] = "acknowledged_by_host"
        except BaseException:
            self.state, self.identity = "uncertain", None
            self.bundle.event(
                "tx_uncertain",
                request_id=request["id"],
                acknowledged_bytes=sent,
                note="transport may have sent additional bytes before failure",
            )
            raise
        finally:
            request["ended_at"] = utcnow()
            if adjustable_write:
                self.transport.write_timeout = original_write_timeout

    def receive(self, seconds):
        if not 0 < seconds <= 60:
            raise ValueError("receive duration must be >0 and <=60 seconds")
        received = bytearray()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._read(received)
        observed = prompt_state(bytes(received))
        if self.state != "uncertain":
            self.state = observed
        self.bundle.event("state", state=self.state, receive_only=True)
        return bytes(received)

    def observe_prompt(self, solicit=False):
        if self.state == "uncertain":
            raise UnknownOutcome("uncertain session requires separate operator reconciliation")
        received = bytearray()
        # Inspect fresh available RX before considering an explicitly requested CR.
        passive_deadline = time.monotonic() + min(0.2, self.timeout / 4)
        while time.monotonic() < passive_deadline:
            self._read(received)
        self.state = prompt_state(bytes(received))
        if self.state in ("login", "password", "continuation"):
            raise BenchError("unexpected " + self.state + "; no probe or automatic recovery")
        probe_attempted = solicit and self.state != "shell"
        deadline = time.monotonic() + self.timeout
        try:
            if probe_attempted:
                # Caller explicitly asserts a known idle shell; never an automatic probe.
                self._send(b"\r", deadline=deadline, received=received)
            while time.monotonic() < deadline:
                self._read(received)
                self.state = prompt_state(bytes(received))
                if self.state in ("login", "password", "continuation"):
                    raise BenchError("unexpected " + self.state + "; no automatic login/recovery")
                if self.state == "shell":
                    self.bundle.event("state", state="shell", identity_verified=False)
                    return
            raise BenchError("no fresh shell prompt; no task command sent")
        except BaseException:
            if probe_attempted:
                self.state, self.identity = "uncertain", None
            raise

    def execute(self, command, *, identity_probe=False):
        if self.state != "shell":
            raise UnknownOutcome("fresh shell state required; no automatic retry")
        if not identity_probe and self.identity is None:
            raise BenchError("fresh root/firmware identity required before task command")
        token = nonce()
        operation = dict(
            nonce=token,
            command=command,
            started_at=utcnow(),
            deadline_s=self.timeout,
            output_cap=self.output_cap,
            outcome="unknown",
            identity_probe=identity_probe,
        )
        self.bundle.meta["operations"].append(operation)
        self.bundle.save(token + ".command.txt", command.encode())
        wire = wrap_command(command, token)
        self.bundle.save(token + ".wire.bin", wire)
        decoder = CommandDecoder(token)
        received = bytearray()
        self.state = "in_flight"
        try:
            deadline = time.monotonic() + self.timeout
            self._send(
                wire, deadline=deadline, received=received, on_rx=decoder.feed, operation=operation
            )
            while time.monotonic() < deadline:
                if not decoder.complete:
                    chunk = self._read(received, until=deadline)
                    decoder.feed(chunk)
                if decoder.complete:
                    operation.update(
                        outcome="completed",
                        exit_status=decoder.exit_status,
                        ended_at=utcnow(),
                        rx_bytes=len(received),
                        output_sha256=digest(decoder.output),
                    )
                    self.bundle.save(token + ".output.bin", bytes(decoder.output))
                    self.state = "shell"
                    return decoder.exit_status, bytes(decoder.output)
            raise TimeoutError("missing complete nonce END plus fresh shell prompt")
        except BaseException as exc:
            self.state, self.identity = "uncertain", None
            operation.update(
                outcome="unknown",
                error=str(exc),
                ended_at=utcnow(),
                rx_bytes=len(received),
                begin_seen=decoder.started,
                end_status_seen=decoder.exit_status,
            )
            self.bundle.save(token + ".partial-output.bin", bytes(decoder.output))
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise UnknownOutcome(str(exc)) from exc

    def identify(self):
        status, output = self.execute(IDENTIFY, identity_probe=True)
        try:
            if status != 0:
                raise ProtocolError("identity command did not exit 0")
            self.identity = verify_identity(output)
        except BenchError:
            self.identity = None
            self.state = "unknown"
            raise
        self.bundle.meta["identity"] = self.identity
        self.bundle.event("identity", **self.identity)
        return self.identity
