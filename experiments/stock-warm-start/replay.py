#!/usr/bin/env python3
"""Private saved-RX replay only. Never opens UART/camera or sends bytes."""
from pathlib import Path
import hashlib
import json
import sys
import observe


def replay(bundle):
    bundle=Path(bundle)
    manifest=json.loads((bundle/'manifest.json').read_text())
    raw=(bundle/'rx.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest['artifacts']['rx.bin']['sha256']
    rows=[json.loads(s) for s in (bundle/'events.jsonl').read_text().splitlines()]
    requests=[r for r in rows if r['kind']=='restart_request']
    assert len(requests)==1
    request=requests[0]['monotonic_ns']
    received=[r for r in rows if r['kind']=='bytes' and r['direction']=='rx']
    assert b''.join(bytes.fromhex(r['hex']) for r in received)==raw
    offset=sum(r['length'] for r in received if r['monotonic_ns']<request)
    gate=observe.BootGate();events=[];failure=None
    for r in received:
        if r['monotonic_ns']<request:continue
        try:
            event=gate.feed(bytes.fromhex(r['hex']))
            if event:events.append(dict(transition=event,source_monotonic_ns=r['monotonic_ns']))
        except RuntimeError as exc:
            failure=str(exc);break
    return dict(mode='OFFLINE_RX_REPLAY_ONLY',source_manifest=str(bundle/'manifest.json'),
                source_manifest_sha256=hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest(),
                source_rx_sha256=hashlib.sha256(raw).hexdigest(),source_rx_bytes=len(raw),
                request_rx_offset=offset,corrected_source_sha256=hashlib.sha256(Path(observe.__file__).read_bytes()).hexdigest(),
                kernel_recognized=gate.kernel_seen,kernel_records=len(list(observe.KERNEL_BANNER.finditer(observe.ANSI.sub(b'',raw[offset:])))),
                accepted_prompt_events=events,parser_stage=gate.stage,parser_refusal=failure,
                actual_TX=0,hardware_opened=False,original_outcome_unchanged=manifest['outcome'],
                interpretation='Replay tests boot recognition only; no live login, identity, automated success, repeat reboot or readiness claim.')

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: replay.py PRIVATE_ORIGINAL_BUNDLE NEW_RESULT_JSON')
    result=replay(sys.argv[1]);out=Path(sys.argv[2])
    with out.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
