#!/usr/bin/env python3
"""Short native bench-status dialog. Dry-run default; existing lifecycle/transport."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import secrets
import shlex
import sys

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/'experiments/ui001'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(UI))
import invoke as lifecycle
from open_connect.session import wrap_command
DEFAULT_TEXT='55.00.750B | UART root | 2 files'


def render(run_id,seconds=12,title='BENCH STATUS',text=DEFAULT_TEXT):
    if not re.fullmatch('[0-9a-f]{32}',run_id):raise ValueError('run ID must be32 lowercase hex')
    if type(seconds) is not int or not 10<=seconds<=15:raise ValueError('seconds must be an integer10..15')
    for name,value,limit,lines in [('title',title,24,1),('text',text,160,3)]:
        if not isinstance(value,str) or not value.strip() or len(value)>limit or not value.isascii():
            raise ValueError(name+' must be short nonempty ASCII')
        if len(value.split('\n'))>lines or any(ord(c)<32 and c!='\n' for c in value) or '\x7f' in value:
            raise ValueError(name+' has unsupported controls/line count')
    caption=title+' '+run_id[:8]
    template=(UI/'watchdog.sh.in').read_text()
    values={'RUN_ID':run_id,'PROFILE':'ui001','TOOL':'/jci/tools/jci-dialog','DURATION':str(seconds),'SLEEP_SECONDS':'0',
            'SETUP':'_title='+shlex.quote(caption)+'\n_text='+shlex.quote(text),
            'EXPECTED':"_raw=$(printf '%s\\000' \"$_tool\" --info --no-cancel \"--title=$_title\" \"--text=$_text\" | od -An -tx1 -v) || exit 72",
            'LAUNCH':'"$_tool" --info --no-cancel "--title=$_title" "--text=$_text" &'}
    body=template
    for key,value in values.items():body=body.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',body):raise ValueError('unresolved lifecycle token')
    command='timeout -t '+str(seconds+7)+' -s 15 /bin/sh -c '+shlex.quote(body)
    wire=wrap_command(command,'a'*32)
    plan=dict(run_id=run_id,title=caption,text=text,seconds=seconds,term_grace=3,remote_term_timeout=seconds+7,
              host_deadline=35,command_sha256=hashlib.sha256(command.encode()).hexdigest(),
              template_sha256=hashlib.sha256(template.encode()).hexdigest(),wire_bytes=len(wire),max_line_bytes=max(map(len,wire.splitlines())),
              lifecycle='unchanged UI001 template, TERM only, PID/start/PPID/full-argv checks',
              target_files=[],browser_actions=[],heartbeat_calls=[],additional_gates=False)
    return command,plan


def verify(bundle,command,run_id,seconds):
    output,proof=lifecycle.completed_output(bundle,command)
    rows=lifecycle.records(output,run_id)
    identity=lifecycle.one(rows,'IDENTITY');ready=lifecycle.one(rows,'READY')
    term_id=lifecycle.one(rows,'TERM_ID');term=lifecycle.one(rows,'TERM');wait=lifecycle.one(rows,'WAIT');result=lifecycle.one(rows,'RESULT')
    pid=identity['pid']
    if any(term_id.get(k)!=identity.get(k) for k in ('pid','ppid','start','cmdline_hex')):raise ValueError('owned identity changed')
    if identity.get('cmdline_hex')!=identity.get('expected_hex'):raise ValueError('full argv mismatch')
    if ready!={'pid':pid,'watchdog_seconds':str(seconds)} or term!={'pid':pid,'rc':'0'} or wait!={'pid':pid,'rc':'143'}:
        raise ValueError('ready/owned TERM/reap status mismatch')
    for k,v in dict(profile='ui001',reason='watchdog_expired',cleanup='term_exit_verified',cleanup_rc='0',dialog_rc='143',wrapper_rc='0',ready='1',pid=pid).items():
        if result.get(k)!=v:raise ValueError('cleanup result mismatch: '+k)
    return dict(proof,pid=int(pid),start=identity['start'],lifecycle_passed=True,visual_acceptance='operator must inspect fresh appearance/removal images')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=int,default=12);p.add_argument('--run-id',default=None)
    p.add_argument('--title',default='BENCH STATUS');p.add_argument('--text',default=DEFAULT_TEXT)
    p.add_argument('--live',action='store_true');p.add_argument('--bundle');p.add_argument('--owner',default='t14')
    a=p.parse_args(argv)
    try:command,plan=render(a.run_id or secrets.token_hex(16),a.seconds,a.title,a.text)
    except ValueError as exc:p.error(str(exc))
    if not a.live:
        print(json.dumps(dict(mode='dry_run',opens_port=False,plan=plan,command=command),indent=2));return 0
    if not a.bundle:p.error('--live needs a new --bundle')
    pins=json.loads((ROOT/'docs/history/uart/operator-ready-paced-tx.json').read_text())['source_sha256']
    for name,expected in pins.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:p.error('paced source changed: '+name)
    print(json.dumps({'overlay_plan':plan}),flush=True)
    runner=runpy.run_path(str(ROOT/'src/open_connect/uart.py'))
    rc=runner['main'](['--live','--action','command','--command',command,'--solicit-prompt','--deadline','35','--bundle',a.bundle,'--owner',a.owner])
    if rc==0:
        try:proof=verify(a.bundle,command,plan['run_id'],a.seconds)
        except (ValueError,KeyError,OSError) as exc:
            print(json.dumps({'lifecycle_validation_failed':str(exc)}));return 4
        print(json.dumps({'overlay_lifecycle':proof}),flush=True)
    return rc


if __name__=='__main__':raise SystemExit(main())
