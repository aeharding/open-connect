#!/usr/bin/env python3
"""Dry-run by default. Explicit live receive, identify, command or exact file export."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cmu_bench.session import (AdapterLock, BenchError, Bundle, Session, UnknownOutcome,
                               IDENTIFY, open_adapter, utcnow, nonce, wrap_command)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true", help="open only the uniquely enumerated known FTDI")
    p.add_argument("--action", choices=("receive", "identify", "command", "export"), default="receive")
    p.add_argument("--command")
    p.add_argument("--path", choices=("/jci/version.ini", "/etc/version"))
    p.add_argument("--encoder", choices=("base64", "hex"), default="base64")
    p.add_argument("--checksum", choices=("sha256", "md5"), default="md5")
    p.add_argument("--seconds", type=float, default=5)
    p.add_argument("--deadline", type=float, default=10, help="per-operation deadline, <=60 s")
    p.add_argument("--output-cap", type=int, default=1048576)
    p.add_argument("--bundle", help="new private bundle path; required for live")
    p.add_argument("--owner", default=os.environ.get("HC_TERMINAL_ID", "unspecified"))
    p.add_argument("--solicit-prompt", action="store_true",
                   help="explicitly assert idle shell and transmit ONE CR; never use with uncertain foreground work")
    args = p.parse_args(argv)
    if not 0 < args.seconds <= 60 or not 0 < args.deadline <= 60:
        p.error("seconds/deadline must be >0 and <=60")
    if not 0 < args.output_cap <= 4 * 1048576:
        p.error("output-cap must be >0 and <=4194304")
    if args.action == "command" and not args.command:
        p.error("--action command requires --command")
    if args.action != "command" and args.command is not None:
        p.error("--command requires --action command")
    if args.action == "export" and not args.path:
        p.error("--action export requires --path")
    if args.action != "export" and args.path is not None:
        p.error("--path requires --action export")
    if args.action == "receive" and args.solicit_prompt:
        p.error("receive is strictly RX-only")
    if args.action == "export":
        from cmu_bench.files import export_command
        planned_command = export_command(args.path, "0" * 32, args.encoder, args.checksum)
    else:
        planned_command = args.command or (IDENTIFY if args.action == "identify" else None)
    if not args.live:
        print(json.dumps(dict(mode="dry_run", opens_port=False, sends_bytes=False,
                              action=args.action, requires_idle_shell=args.solicit_prompt,
                              preflight_identity=(args.action != "receive"),
                              planned_command=planned_command,
                              note="Sample nonce is replaced at execution. No adapter enumeration or files written."), indent=2))
        return 0
    if not args.bundle:
        p.error("--live requires --bundle pointing to a new directory")
    bundle = Bundle(args.bundle, args.action, args.owner, mode="live")
    port = None
    session = None
    outcome, error, result = "failed", None, 1
    # Keep lock held through port close and evidence flush, including failed open.
    try:
        with AdapterLock(owner=args.owner, purpose=args.action) as lock:
            bundle.meta["lock"] = dict(path=str(lock.path), held_until="port close and bundle finalization")
            try:
                port = open_adapter(bundle)
                session = Session(port, bundle, args.deadline, args.output_cap)
                if args.action == "receive":
                    session.receive(args.seconds)
                    outcome, result = "completed", 0
                else:
                    session.observe_prompt(solicit=args.solicit_prompt)
                    session.identify()
                    if args.action == "command":
                        status, _ = session.execute(args.command)
                        outcome, result = ("completed" if status == 0 else "remote_nonzero"), (0 if status == 0 else 3)
                    elif args.action == "export":
                        from cmu_bench.files import capture_file
                        capture_file(session, args.path, args.encoder, args.checksum)
                        outcome, result = "verified_file", 0
                    else:
                        outcome, result = "identity_verified", 0
            except UnknownOutcome as exc:
                outcome, error, result = "unknown", str(exc), 2
            except (Exception, KeyboardInterrupt, SystemExit) as exc:
                uncertain = session is not None and session.state == "uncertain"
                outcome, result = ("unknown", 2) if uncertain else ("failed", 1)
                error = str(exc) or type(exc).__name__
            finally:
                try:
                    if port is not None:
                        port.close()
                    bundle.meta["port_closed"] = True
                except Exception as exc:
                    error = (error or "") + "; close failed: " + str(exc)
                    outcome, result = "unknown", 2
                bundle.finish(outcome, error)
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        error = str(exc) or type(exc).__name__
        uncertain = session is not None and session.state == "uncertain"
        bundle.finish("unknown" if uncertain else "failed", error)
        result = 2 if uncertain else 1
    print(json.dumps(dict(bundle=str(bundle.path), outcome=bundle.meta["outcome"], error=error), indent=2))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
