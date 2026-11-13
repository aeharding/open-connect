#!/usr/bin/env python3
"""DATA-only tmpfs delivery. Default prints a plan; never executes the payload."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from open_connect.files import posix_cksum
from open_connect.session import AdapterLock, Bundle, Session, open_adapter, nonce, wrap_command

LIMIT = 16384
PREFIX = '/tmp/cmu-bench-payload-'


def fingerprint(data):
    return dict(bytes=len(data), md5=hashlib.md5(data).hexdigest(),
                cksum=posix_cksum(data), host_sha256=hashlib.sha256(data).hexdigest())


def source(path):
    """Read a bounded regular, single-link source without following its final symlink."""
    path = Path(path).absolute()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > LIMIT:
            raise ValueError('source must be a regular single-link file <=16 KiB')
        data = b''
        while len(data) <= LIMIT:
            part = os.read(fd, LIMIT + 1 - len(data))
            if not part:
                break
            data += part
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                               s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(data) > LIMIT or len(data) != before.st_size or signature(before) != signature(after):
            raise ValueError('source changed while reading')
        if signature(path.lstat()) != signature(after):
            raise ValueError('source path changed while reading')
        return dict(path=str(path), data=data, signature=signature(after), **fingerprint(data))
    finally:
        os.close(fd)


def unchanged(snapshot):
    now = source(snapshot['path'])
    if now['signature'] != snapshot['signature'] or now['data'] != snapshot['data']:
        raise ValueError('source changed since planning; no delivery attempted')


def checked_nonce(run):
    if not isinstance(run, str) or not re.fullmatch('[0-9a-f]{32}', run):
        raise ValueError('nonce must be 32 lowercase hex digits')
    return run


def identity(value, directory=False):
    fields = value.split(':') if isinstance(value, str) else []
    if len(fields) != (7 if directory else 8) or any(not re.fullmatch('[0-9]+', x) for x in fields):
        raise ValueError('invalid observed identity')
    if int(fields[0]) <= 0 or int(fields[1]) <= 0:
        raise ValueError('invalid device/inode')
    if directory:
        if fields[3:6] != ['700', '0', '0'] or int(fields[6]) < 2:
            raise ValueError('invalid private directory metadata')
    elif fields[4:] != ['600', '0', '0', '1']:
        raise ValueError('invalid DATA file metadata')
    return fields


def descriptor(value):
    required = {'schema', 'kind', 'nonce', 'path', 'bytes', 'md5', 'cksum', 'host_sha256',
                'file_id', 'dir_id', 'observed', 'execution'}
    if set(value) != required or value['schema'] != 1 or value['kind'] != 'cmu_bench_data_stage':
        raise ValueError('not a staged-delivery descriptor')
    run = checked_nonce(value['nonce'])
    if value['path'] != PREFIX + run + '/p' or value['observed'] is not True or value['execution'] is not False:
        raise ValueError('requires observed DATA-only fixed-path stage')
    if type(value['bytes']) is not int or not 0 <= value['bytes'] <= LIMIT:
        raise ValueError('invalid count')
    if type(value['cksum']) is not int or not 0 <= value['cksum'] <= 0xffffffff:
        raise ValueError('invalid POSIX CRC')
    for key, count in [('md5', 32), ('host_sha256', 64)]:
        if not isinstance(value[key], str) or not re.fullmatch('[0-9a-f]{%d}' % count, value[key]):
            raise ValueError('invalid ' + key)
    f, d = identity(value['file_id']), identity(value['dir_id'], True)
    if f[0] != d[0] or f[3] != str(value['bytes']):
        raise ValueError('identity/count/device mismatch')
    return value


def common(run, expected):
    # Only validated scalars enter executable text. Complete emitted records are absent in TX.
    return f'''umask 077
r={checked_nonce(run)}
d={PREFIX}{run}
p="$d/p"
emit() {{ printf 'DELIVERY %s %s\\n' "$r" "$*"; }}
die() {{ emit "REFUSED|$1|preserved=1"; exit 73; }}
canon() {{ test "$(readlink -f "$1")" = "$1" || die canonical; }}
fi_id() {{ stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p"; }}
di_id() {{ stat -c '%d:%i:%Y:%a:%u:%g:%h' "$d"; }}
test "$(id -u)" = 0 || die root
test -d /tmp && test ! -L /tmp || die tmp_type
canon /tmp
test "$(stat -c '%u:%g' /tmp)" = 0:0 || die tmp_owner
awk '$2=="/tmp"{{n++;if($3=="tmpfs")ok++}}END{{exit !(n==1&&ok==1)}}' /proc/mounts || die tmpfs
td=$(stat -c %d /tmp) || die tmp_device
dir_guard() {{
 test -d "$d" && test ! -L "$d" || die directory_type
 canon "$d"
 test "$(stat -c '%a:%u:%g:%d' "$d")" = "700:0:0:$td" || die directory_metadata
}}
file_guard() {{
 dir_guard
 test -f "$p" && test ! -L "$p" || die file_type
 canon "$p"
 test "$(stat -c '%a:%u:%g:%h:%d' "$p")" = "600:0:0:1:$td" || die file_metadata
 test "$(wc -c < "$p")" -eq {expected['bytes']} || die count
 test "$(md5sum < "$p")" = '{expected['md5']}  -' || die md5
 test "$(cksum < "$p")" = '{expected['cksum']} {expected['bytes']}' || die cksum
}}
'''


def stage_command(snapshot, run):
    data = snapshot['data']
    if len(data) > LIMIT or any(snapshot[k] != v for k, v in fingerprint(data).items()):
        raise ValueError('inconsistent source snapshot')
    encoded = base64.b64encode(data).decode('ascii')
    lines = '\n'.join(encoded[i:i+128] for i in range(0, len(encoded), 128))
    command = common(run, snapshot) + f'''test ! -e "$d" && test ! -L "$d" || die already_exists
mkdir -m 700 "$d" || die mkdir
dir_guard
di=$(di_id) || die directory_identity
# Noclobber also refuses a raced preexisting p. Failures are retained, never auto-cleaned.
set -C
base64 -d > "$p" <<'DATA_{run}'
{lines}
DATA_{run}
s=$?
test "$s" = 0 || die decode
file_guard
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = "$(printf '%s' "$di" | cut -d: -f1,2,4,5,6)" || die directory_changed
fi=$(fi_id) || die file_identity
di=$(di_id) || die directory_identity
emit "FILE|$fi"
emit "DIR|$di"
emit "DATA|{snapshot['bytes']}|{snapshot['md5']}|{snapshot['cksum']}"
emit 'END|STAGE|0|execution=0'
'''
    wrap_command(command, '0' * 32)  # Includes all framing/quoting overhead.
    return command


def cleanup_command(stage):
    stage = descriptor(stage)
    command = common(stage['nonce'], stage) + f'''file_guard
test "$(fi_id)" = '{stage['file_id']}' || die file_identity_changed
test "$(di_id)" = '{stage['dir_id']}' || die directory_identity_changed
for x in "$d"/* "$d"/.[!.]* "$d"/..?*; do
 test -e "$x" || test -L "$x" || continue
 test "$x" = "$p" || die unrelated_entry
done
# Recheck immediately before deleting exactly the owned DATA file; no broad rm.
file_guard
test "$(fi_id)" = '{stage['file_id']}' || die file_identity_changed
test "$(di_id)" = '{stage['dir_id']}' || die directory_identity_changed
rm "$p" || die remove_file
dir_guard
test "$(stat -c '%d:%i' "$d")" = '{':'.join(stage['dir_id'].split(':')[:2])}' || die directory_changed
rmdir "$d" || die remove_directory
test ! -e "$d" && test ! -L "$d" || die directory_not_absent
emit 'END|CLEANUP|0|absent=1'
'''
    wrap_command(command, '0' * 32)
    return command


def records(output, run):
    prefix = ('DELIVERY ' + run + ' ').encode()
    rows = []
    for line in output.splitlines(keepends=True):
        if prefix in line:
            if not line.endswith(b'\n'):
                raise ValueError('unterminated delivery record')
            line = line.removesuffix(b'\n').removesuffix(b'\r')
            if not line.startswith(prefix):
                raise ValueError('interleaved delivery record; preserve stage')
            rows.append(line[len(prefix):].decode('ascii'))
    return rows


def stage_result(output, snapshot, run):
    rows = records(output, run)
    if len(rows) != 4 or not rows[0].startswith('FILE|') or not rows[1].startswith('DIR|'):
        raise ValueError('missing/duplicate/out-of-order delivery records')
    if rows[2:] != [f"DATA|{snapshot['bytes']}|{snapshot['md5']}|{snapshot['cksum']}", 'END|STAGE|0|execution=0']:
        raise ValueError('incomplete/malformed DATA verification')
    return descriptor(dict(schema=1, kind='cmu_bench_data_stage', nonce=run, path=PREFIX+run+'/p',
                           **{k: snapshot[k] for k in fingerprint(snapshot['data'])},
                           file_id=rows[0][5:], dir_id=rows[1][4:], observed=True, execution=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('stage', 'cleanup'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--descriptor', type=Path, help='observed stage descriptor for exact cleanup')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--bundle', type=Path, help='new evidence directory; required for live')
    parser.add_argument('--owner', default=os.environ.get('HC_TERMINAL_ID', 'unspecified'))
    parser.add_argument('--solicit-prompt', action='store_true', help='explicit idle-shell assertion; one CR')
    args = parser.parse_args(argv)
    snapshot = None
    try:
        if args.action == 'stage':
            if not args.source or args.descriptor:
                raise ValueError('stage requires --source only')
            snapshot = source(args.source)
            run = nonce()
            command = stage_command(snapshot, run)
        else:
            if not args.descriptor or args.source:
                raise ValueError('cleanup requires --descriptor only')
            stage = descriptor(json.loads(args.descriptor.read_text()))
            run = stage['nonce']
            command = cleanup_command(stage)
        if args.live and not args.bundle:
            raise ValueError('--live requires --bundle (new directory)')
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    if not args.live:
        print(json.dumps(dict(mode='dry_run', action=args.action, opens_port=False, sends_bytes=False,
                              target_observed=False, execution=False, planned_command=command), indent=2))
        return 0
    bundle = Bundle(args.bundle, 'data_' + args.action, args.owner, mode='live')
    bundle.meta['delivery_code_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    bundle.meta['payload_execution'] = False
    port = session = None
    outcome, error, code = 'failed', None, 1
    sent = False
    try:
        with AdapterLock(owner=args.owner, purpose='data_' + args.action):
            try:
                bundle.save('delivery-command.sh', command.encode())
                if snapshot:
                    bundle.save('source.bin', snapshot['data'])
                port = open_adapter(bundle)
                session = Session(port, bundle, timeout=45, output_cap=262144)
                session.observe_prompt(solicit=args.solicit_prompt)
                session.identify()
                if snapshot:
                    unchanged(snapshot)
                sent = True
                status, output = session.execute(command)
                if status:
                    outcome, code = 'remote_refused_preserved', 3
                elif args.action == 'stage':
                    observed = stage_result(output, snapshot, run)
                    bundle.save('stage.json', (json.dumps(observed, indent=2)+'\n').encode())
                    outcome, code = 'staged_data_verified', 0
                else:
                    if records(output, run) != ['END|CLEANUP|0|absent=1']:
                        raise ValueError('cleanup completion missing/duplicated/malformed')
                    outcome, code = 'owned_stage_removed', 0
            except (Exception, KeyboardInterrupt, SystemExit) as exc:
                uncertain = sent or (session is not None and session.state == 'uncertain')
                outcome, code = ('unknown_preserved', 2) if uncertain else ('failed', 1)
                error = str(exc) or type(exc).__name__
            finally:
                try:
                    if port is not None:
                        port.close()
                        bundle.meta['port_closed'] = True
                except Exception as exc:
                    outcome, code, error = 'unknown_preserved', 2, str(exc)
                bundle.finish(outcome, error)
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        outcome = 'unknown_preserved' if sent or (session is not None and session.state == 'uncertain') else 'failed'
        error, code = str(exc) or type(exc).__name__, 2 if outcome == 'unknown_preserved' else 1
        bundle.finish(outcome, error)
    print(json.dumps(dict(bundle=str(bundle.path), outcome=bundle.meta['outcome'], error=error), indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
