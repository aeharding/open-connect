#!/usr/bin/env python3
"""Review only by default; future live execution delegates to frozen harness."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(ROOT))
from prepare import render,CAP_RUN
from cmu_bench.session import wrap_command


def sha(data): return hashlib.sha256(data).hexdigest()


def completed_output(path,command):
    folder=Path(path)
    m=json.loads((folder/'manifest.json').read_text())
    expected=dict(uid=0,user='root',firmware='55.00.750B',flavor='cmu150_NA')
    if m.get('mode')!='live' or m.get('outcome')!='completed' or m.get('identity')!=expected or not m.get('port_closed'):
        raise ValueError('completed live command, expected identity and closed port required')
    ops=[op for op in m.get('operations',[]) if op.get('command')==command and op.get('outcome')=='completed' and op.get('exit_status')==0]
    if len(ops)!=1: raise ValueError('one exact completed request required')
    token=ops[0]['nonce']
    if not re.fullmatch('[0-9a-f]{32}',token): raise ValueError('invalid operation nonce')
    name=token+'.output.bin'
    data=(folder/name).read_bytes(); entry=m['artifacts'][name]
    if len(data)!=entry['bytes'] or sha(data)!=entry['sha256']:
        raise ValueError('output checksum mismatch')
    return data,dict(bundle=str(folder),manifest_sha256=sha((folder/'manifest.json').read_bytes()),output_sha256=sha(data))


def records(output,token):
    prefix=('UI001 '+token+' ').encode()
    rows={}
    for line in output.replace(b'\r\n',b'\n').splitlines():
        if line.startswith(prefix):
            fields=line[len(prefix):].decode('ascii').split()
            kind=fields[0]
            values={}
            for field in fields[1:]:
                if '=' not in field: raise ValueError('malformed UI001 field')
                k,v=field.split('=',1)
                if k in values: raise ValueError('duplicate UI001 key')
                values[k]=v
            rows.setdefault(kind,[]).append(values)
    return rows


def one(rows,kind):
    values=rows.get(kind,[])
    if len(values)!=1: raise ValueError('one actual '+kind+' record required')
    return values[0]


def verify_capability_bundle(path):
    command,plan=render(CAP_RUN,'sleep4')
    if (HERE/'capability-probe.sh').read_text()!=command:
        raise ValueError('capability request differs from current reviewed lifecycle')
    data,proof=completed_output(path,command)
    rows=records(data,CAP_RUN)
    prep=one(rows,'PREP'); identity=one(rows,'IDENTITY'); term=one(rows,'TERM')
    wait=one(rows,'WAIT'); result=one(rows,'RESULT'); ready=one(rows,'READY')
    term_id=one(rows,'TERM_ID')
    if prep.get('profile')!='sleep4' or prep.get('sleep_seconds')!='4' or prep.get('tool')!='/bin/sleep':
        raise ValueError('only reviewed4-second sleep profile accepted')
    expected=(b'/bin/sleep'+bytes([0])+b'4'+bytes([0])).hex()
    pid=identity['pid']
    if (identity.get('ppid')!=prep.get('parent') or int(identity['start'])<1
            or identity.get('cmdline_hex')!=expected or identity.get('expected_hex')!=expected):
        raise ValueError('PID/start/parent/full-argv evidence disagrees')
    if any(term_id.get(k)!=identity.get(k) for k in ('pid','ppid','start','cmdline_hex')):
        raise ValueError('immediate pre-TERM identity differs')
    if ready.get('pid')!=pid or ready.get('watchdog_seconds')!='1':
        raise ValueError('reviewed sleep4 lifecycle did not become ready')
    if term!={'pid':pid,'rc':'0'} or wait!={'pid':pid,'rc':'143'}:
        raise ValueError('owned TERM0 and actual wait143 required')
    for key,value in dict(profile='sleep4',cleanup='term_exit_verified',cleanup_rc='0',dialog_rc='143',wrapper_rc='0',ready='1',pid=pid).items():
        if result.get(key)!=value: raise ValueError('incomplete verified cleanup: '+key)
    proof.update(profile='sleep4',sleep_seconds=4,remote_term_timeout=plan['independent_remote_term_timeout'],pid=int(pid),start=int(identity['start']))
    return proof


def verify_ui_lifecycle(path,run_id):
    command,_=render(run_id)
    output,proof=completed_output(path,command)
    rows=records(output,run_id)
    ready=one(rows,'READY'); result=one(rows,'RESULT'); wait=one(rows,'WAIT')
    if result.get('profile')!='ui001' or result.get('ready')!='1' or result.get('wrapper_rc')!='0' or result.get('cleanup_rc')!='0':
        raise ValueError('UI readiness/cleanup did not complete')
    if result.get('cleanup') not in ('term_exit_verified','already_exited') or result.get('dialog_rc')=='unknown':
        raise ValueError('verified child exit required')
    if ready.get('pid')!=result.get('pid') or wait.get('pid')!=result.get('pid') or wait.get('rc')!=result.get('dialog_rc'):
        raise ValueError('UI child readiness/status identity disagrees')
    proof.update(lifecycle_ready_and_cleaned=True,visible_pass=False,visible_acceptance='requires separately inspected before/during/after camera evidence')
    return proof


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=('capability','ui'),required=True)
    p.add_argument('--prepared'); p.add_argument('--capability-bundle')
    p.add_argument('--live',action='store_true'); p.add_argument('--bundle'); p.add_argument('--owner',default='t14')
    a=p.parse_args(argv)
    run_id=None
    if a.phase=='capability':
        command,plan=render(CAP_RUN,'sleep4')
        if (HERE/'capability-probe.sh').read_text()!=command: p.error('regenerate/review capability request')
    else:
        if not a.prepared: p.error('--phase ui requires --prepared')
        folder=Path(a.prepared); saved=json.loads((folder/'plan.json').read_text())
        run_id=saved['run_id']; command,plan=render(run_id)
        if command!=(folder/'command.sh').read_text() or sha(command.encode())!=saved['command_sha256']:
            p.error('prepared command differs from current template/metadata')
    if not a.live:
        print(json.dumps(dict(mode='review_only',opens_port=False,phase=a.phase,command=command,plan=plan,live_ui_authorized=False),indent=2))
        return 0
    if not a.bundle: p.error('--live requires new --bundle')
    frozen=json.loads((ROOT/'examples/operator-ready-exception-fix.json').read_text())['source_sha256']
    for name,expected in frozen.items():
        if sha((ROOT/name).read_bytes())!=expected: p.error('reviewed harness changed: '+name)
    if a.phase=='ui':
        if not a.capability_bundle: p.error('live UI requires reviewed capability bundle and separate t6 authorization')
        print(json.dumps({'capability_proof':verify_capability_bundle(a.capability_bundle)}),flush=True)
    runner=runpy.run_path(str(ROOT/'scripts/cmu-session.py'))
    rc=runner['main'](['--live','--action','command','--command',command,'--deadline',str(plan['host_deadline']),
                       '--solicit-prompt','--owner',a.owner,'--bundle',a.bundle])
    if rc==0:
        try:
            proof=verify_capability_bundle(a.bundle) if a.phase=='capability' else verify_ui_lifecycle(a.bundle,run_id)
        except (ValueError,KeyError,OSError) as exc:
            print(json.dumps({'workflow_validation_failed':str(exc),'experiment_pass':False}),flush=True)
            return 4
        print(json.dumps({'validated_lifecycle':proof,'experiment_visible_pass':False}),flush=True)
    return rc


if __name__=='__main__': raise SystemExit(main())
