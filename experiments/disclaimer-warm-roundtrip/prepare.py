"""REVIEW ONLY. Prepare a real-file warm roundtrip; never opens UART or executes it."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import secrets
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from open_connect.session import wrap_command
FREEZE = ROOT / 'experiments/disclaimer/freeze.json'
FREEZE_SHA = '42eb3420551c9d647f58f624cfa53e86e5c379c286443bf5ddf53c0b05a37d6d'
HELP = ROOT / 'runs/20261113T040546-0600-t14-copy-transaction-record/mount-help-output.txt'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def frozen_inputs():
    raw = FREEZE.read_bytes()
    if sha(raw) != FREEZE_SHA:
        raise ValueError('independent freeze changed')
    freeze = json.loads(raw)
    path = ROOT / 'experiments/disclaimer/patch.py'
    if sha(path.read_bytes()) != freeze['code_and_design_sha256']['experiments/disclaimer/patch.py']:
        raise ValueError('independent patch changed')
    spec = importlib.util.spec_from_file_location('frozen_warm_patch', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original = (ROOT / freeze['original']['path']).read_bytes()
    candidate = module.patch_original(original)
    if sha(candidate) != freeze['candidate']['sha256']:
        raise ValueError('frozen candidate mismatch')
    # Reuse exact previously frozen offset; never introduce a second feature patch.
    if original[:83483] + b'0' + original[83487:] != candidate:
        raise ValueError('frozen byte recipe mismatch')
    return freeze


def render(nonce):
    if not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('32 lowercase hexadecimal nonce required')
    return (HERE / 'warm.sh.in').read_text().replace('@RUN@', nonce)


def plan(nonce, command):
    freeze = frozen_inputs()
    wire = wrap_command(command, '0' * 32)
    help_data = HELP.read_bytes()
    if sha(help_data) != '4346a63af4a77f88a28f1af5ed4d87420deadc2a093ecfe09a585f0287ebc54e':
        raise ValueError('actual help evidence changed')
    mount = ['/bin/busybox', 'mount', '-i', '-n', '-t', 'relfs', '-o']
    return {
        'mode': 'review_only', 'coordinator_boundary_review_required': True,
        'operator_handoff_authorized': False, 'opens_uart': False, 'executed': False,
        'nonce': nonce, 'firmware': '55.00.750B/cmu150_NA',
        'target': '/jci/gui/apps/system/js/systemApp.js',
        'retained': '/tmp/mnt/data_persist/cmu-bench-warm-' + nonce,
        'root_stage_names': ['.systemApp.js.cmu-bench-' + nonce + '-candidate',
                             '.systemApp.js.cmu-bench-' + nonce + '-original'],
        'rw_argv': mount + ['remount,rw,noatime', '/dev/ffx01p1', '/'],
        'ro_argv': mount + ['remount,ro,noatime', '/dev/ffx01p1', '/'],
        'sync_argv': ['/bin/sync'],
        'request_wrapper': ['/bin/busybox','timeout','-t','8','-s','15'],
        'sync_order': ['retained backup+pending intent while root RO, before RW',
                       'verified original+disabled/stage cleanup, before paired RO'],
        'mount_switch_assumption': '-i/-n source-supported but omitted from actual help; fail closed, no alternate argv',
        'mount_predicate': 'unique exact physical /dev/ffx01p1 / relfs ro|rw,noatime plus separate rootfs/rw; rc0 alone insufficient',
        'restore_coverage': ['exact original bytes via cmp/MD5/CRC/count','0755','UID1018','GID3015','mtime1433953097 at stat second resolution'],
        'inode': 'replacement changes inode; initial/staged/final identities recorded explicitly',
        'failure_policy': 'known C+valid evidence restores O; O commits disabled without rewrite; OTHER/bad evidence preserves; RO attempt isolated from file-cleanup failure',
        'retention': 'original/candidate/journal remain for review; only verified nonce-owned root stages may be removed',
        'command_sha256': sha(command.encode()), 'command_bytes': len(command.encode()),
        'sample_wire_bytes': len(wire), 'max_physical_line': max(map(len,wire.splitlines())),
        'proposed_host_deadline': 60, 'proposed_output_cap': 131072,
        'freeze': str(FREEZE.relative_to(ROOT)), 'freeze_sha256': FREEZE_SHA,
        'original': freeze['original'], 'candidate': freeze['candidate'],
        'mount_notes': 'notes/remount-preparation.txt', 'actual_help': str(HELP.relative_to(ROOT)),
        'limits': ['NOT executed or sent live to operator','no UI reload/startup/feature behavior test',
                   'sync0/readback are best-effort runtime evidence, not power-loss durability',
                   'timeout is nominal TERM via stock BusyBox watcher; uninterruptible I/O/SIGKILL/host disconnect cannot guarantee cleanup',
                   'single-writer/TOCTOU; no UID/GID/xattr/ACL/inode-identity/full metadata recovery guarantee beyond stated checked fields',
                   'bad control or OTHER may leave candidate/stages, but paired RO is still attempted and unresolved state reported']
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nonce', default=None)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    nonce = args.nonce or secrets.token_hex(16)
    command = render(nonce); record = plan(nonce, command)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / 'command.sh').write_text(command)
        (args.out / 'sample-wire.bin').write_bytes(wrap_command(command, '0'*32))
        (args.out / 'plan.json').write_text(json.dumps(record,indent=2)+'\n')
        command_path = str(args.out / 'command.sh')
        code = ('from pathlib import Path; import runpy; m=runpy.run_path("src/open_connect/uart.py"); '
                'raise SystemExit(m["main"](["--live","--action","command","--command",'
                'Path('+repr(command_path)+').read_text(),"--deadline","60","--output-cap","131072",'
                '"--solicit-prompt","--bundle","runs/NEW_REVIEWED_WARM_BUNDLE","--owner","t14"]))')
        (args.out / 'proposed-invocation.json').write_text(json.dumps({
            'DO_NOT_EXECUTE':'coordinator must review this real-file boundary before operator handoff',
            'hc_prefix':['hc','run','--bg','--name','reviewed-warm-roundtrip','--parent','t14','--cwd',str(ROOT)],
            'program':['.venv/bin/python','-B','-c',code]},indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
