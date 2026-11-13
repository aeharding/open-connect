#!/usr/bin/env python3
"""Prepare bounded UI001/sleep4 requests. No serial/camera or execution option."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cmu_bench.session import wrap_command
CAP_RUN = 'ca' * 16


def render(run_id, profile='ui001'):
    if not re.fullmatch(r'[0-9a-f]{32}', run_id) or profile not in ('ui001','sleep4'):
        raise ValueError('invalid32-hex run id or profile')
    if profile == 'ui001':
        config = dict(PROFILE='ui001',TOOL='/jci/tools/jci-dialog',DURATION='40',SLEEP_SECONDS='0',
                      SETUP='_title="CMU bench UI001 $_run"\n_text="Temporary development probe $_run"',
                      EXPECTED="_raw=$(printf '%s\\000' \"$_tool\" --info --no-cancel \"--title=$_title\" \"--text=$_text\" | od -An -tx1 -v) || exit 72",
                      LAUNCH='"$_tool" --info --no-cancel "--title=$_title" "--text=$_text" &')
        remote_timeout, host_deadline = 47,60
    else:
        config = dict(PROFILE='sleep4',TOOL='/bin/sleep',DURATION='1',SLEEP_SECONDS='4',
                      SETUP='# Disposable child auto-exits after4s even if TERM fails.',
                      EXPECTED="_raw=$(printf '%s\\000' \"$_tool\" 4 | od -An -tx1 -v) || exit 72",
                      LAUNCH='"$_tool" 4 &')
        remote_timeout, host_deadline = 6,15
    body = Path(__file__).with_name('watchdog.sh.in').read_text().replace('@RUN_ID@',run_id)
    for key,value in config.items():
        body=body.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',body):
        raise ValueError('unresolved template token')
    # Verified BusyBox option grammar; TERM47s is independent of the inner40s timer.
    command='timeout -t '+str(remote_timeout)+' -s 15 /bin/sh -c '+shlex.quote(body)
    wire=wrap_command(command,'a'*32)
    plan=dict(run_id=run_id,profile=profile,target='55.00.750B cmu150_NA root',
              command_sha256=hashlib.sha256(command.encode()).hexdigest(),
              body_sha256=hashlib.sha256(body.encode()).hexdigest(),
              sample_wire_sha256=hashlib.sha256(wire).hexdigest(),tx_bytes=len(wire),
              physical_lines=len(wire.splitlines()),max_physical_line_bytes=max(map(len,wire.splitlines())),
              child_sleep_seconds=int(config['SLEEP_SECONDS']),watchdog_seconds=int(config['DURATION']),
              term_grace_seconds=3,independent_remote_term_timeout=remote_timeout,host_deadline=host_deadline,
              target_writes=[],signals='TERM only after exact PID/start/PPID/full-cmdline match',
              kill_escalation=False,live_executed=False,
              limitations=['Nominal UI40s+3s grace; independent wrapper TERM47s; host60s.',
                           'Ignoring TERM/identity loss is a reported cleanup failure without escalation.',
                           'No shell-only design can force exit of TERM-ignoring or uninterruptible child without stronger authority.',
                           'Immediate identity guard has a residual check/signal race on Linux3.0.35 without pidfd.',
                           'Hard SIGKILL/power loss cannot trap or guarantee a final record.'])
    return command,plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id')
    p.add_argument('--out',required=True)
    a=p.parse_args()
    command,metadata=render(a.run_id or secrets.token_hex(16))
    out=Path(a.out).resolve()
    allowed=(ROOT/'experiments/ui001/prepared').resolve()
    if allowed not in out.parents:
        p.error('output must be new descendant of experiments/ui001/prepared/')
    out.mkdir(parents=True,mode=0o700,exist_ok=False)
    (out/'command.sh').write_text(command)
    (out/'plan.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(directory=str(out),**metadata),indent=2))


if __name__=='__main__':
    main()
