#!/usr/bin/env python3
"""TEST ONLY: portable synthetic /proc and short-lived fake dialog. No UI/serial."""
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

root = Path(os.environ["UI001_FAKE_ROOT"])
mode = os.environ.get("UI001_FAKE_MODE", "normal")
pid, parent = os.getpid(), os.getppid()
process = root / "proc" / str(pid)
process.mkdir(parents=True)
events = root / "fake-events.jsonl"


def event(kind, **kw):
    with events.open("a") as f:
        f.write(json.dumps(dict(kind=kind, pid=pid, parent=parent, **kw)) + "\n")


def term(_signal, _frame):
    event("term_received")
    if mode == "ignore_term":
        return
    raise SystemExit(143)


def write_stat(start="123456", ppid=None):
    fields = ["S", str(parent if ppid is None else ppid)] + ["0"] * 17 + [start]
    (process / "stat").write_text(str(pid) + " (fake (dialog)) " + " ".join(fields) + "\n")


signal.signal(signal.SIGTERM, term)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
try:
    write_stat(ppid=999999 if mode == "wrong_parent" else None)
    args = [os.fsencode(arg) for arg in sys.argv]
    content = b"\x00".join(args) + b"\x00"
    if mode == "wrong_cmdline":
        content = b"unrelated\x00process\x00"
    (process / "cmdline").write_bytes(content)
    event("ready", args=sys.argv, mode=mode)
    if mode in ("early_exit", "early_failure"):
        raise SystemExit(7 if mode == "early_failure" else 0)
    deadline = time.monotonic() + 2.5
    changed = False
    while time.monotonic() < deadline:
        if mode == "changed_start" and not changed and deadline - time.monotonic() < 2.1:
            write_stat(start="999999")
            changed = True
            event("start_changed")
        time.sleep(0.005)
    event("self_expired")
finally:
    shutil.rmtree(process, ignore_errors=True)
    event("exited")
