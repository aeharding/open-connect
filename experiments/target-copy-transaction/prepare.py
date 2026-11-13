"""One isolated two-phase COPY experiment. Prepares shell requests; never opens UART."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cmu_bench.session import wrap_command
REFERENCE = ROOT / 'runs/20261113T034954-0600-t14-full-file-copy'
ORIGINAL = '94058 584c67f7186ada6bae9aae1be59b5cd0 376717896'
CANDIDATE = '94055 64db9d0df2277e1d95a037929aef30c4 776631029'
STOP_RC = 73


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_nonce(nonce):
    if not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('fresh32 lowercase hexadecimal nonce required')


def borrowed(nonce):
    check_nonce(nonce)
    text = (REFERENCE / 'command.sh').read_text()
    plan = json.loads((REFERENCE / 'plan.json').read_text())
    if sha(text.encode()) != plan['script_sha256']:
        raise ValueError('passed reference script changed')
    text = text.replace(plan['nonce'], nonce)
    # Reuse only the passed guards and bounded full-copy setup, not its old lifecycle.
    head, rest = text.split('\n_sv\n', 1)
    parents, setup = rest.split('test ! -e "$_d"', 1)
    setup = 'test ! -e "$_d"' + setup
    setup = setup.split('cp -p "$_d/original" "$_d/active"', 1)[0]
    # Separate format/nonce in records; echoed TX cannot contain a complete COPYTX record.
    lines = []
    for line in head.splitlines():
        if "printf 'COPYPROBE " + nonce in line:
            line = line.replace('COPYPROBE ' + nonce, 'COPYTX %s')
            line = line.replace("\\n' ", "\\n' \"$_run\" ", 1)
        lines.append(line)
    head = '_run=' + nonce + '\n' + '\n'.join(lines) + '\n'
    head += "_emit() { printf 'COPYTX %s %s\\n' \"$_run\" \"$*\"; }\n"
    # Remaining borrowed records are diagnostic; namespace them consistently.
    for old in ('COPYPROBE ' + nonce,):
        parents = parents.replace(old, 'COPYTX ' + nonce)
        setup = setup.replace(old, 'COPYTX ' + nonce)
    return head, parents, setup


CONTROL = r'''
_control() {
_cf=$1;_want=$2
_guard
case $_cf in "$_d/journal"|"$_d/journal.new") ;;*) _die control_path;;esac
test -f "$_cf" && test ! -L "$_cf" || _die control_type
test "$(readlink -f "$_cf")" = "$_cf" || _die control_route
test "$(stat -c '%F|%a|%u|%g|%h|%d' "$_cf")" = "regular file|600|0|0|1|$_pd" || _die control_metadata
_cn=$(wc -c < "$_cf") || _die control_size
test "$_cn" -eq "$((${#_want}+1))" || _die control_length
_text=$(cat "$_cf") || _die control_read
test "$_text" = "$_want" || _die control_data
_eh=$(printf '%s\n' "$_want" | md5sum) || _die control_expected_hash
set -- $_eh;_eh=$1
_ah=$(md5sum "$_cf") || _die control_hash
set -- $_ah
test "$1" = "$_eh" || _die control_bytes
_emit 'CONTROL verified=1'
}
_states() {
_tail="|dir=$_di|o=94058:584c67f7186ada6bae9aae1be59b5cd0:376717896|c=94055:64db9d0df2277e1d95a037929aef30c4:776631029|meta=755:1018:3015:1"
_enabled="COPYTX1|$_run|registry=enabled|pending=none$_tail"
_pending="COPYTX1|$_run|registry=enabled|pending=DISABLE$_tail"
_disabled="COPYTX1|$_run|registry=disabled|pending=none$_tail"
}
_publish_control() {
_next=$1;_previous=$2
_guard
_control "$_d/journal" "$_previous"
test ! -e "$_d/journal.new" && test ! -L "$_d/journal.new" || _die control_stage_exists
printf '%s\n' "$_next" > "$_d/journal.new"
_s WRITE_CONTROL_STAGE "$?"
_control "$_d/journal.new" "$_next"
mv -f "$_d/journal.new" "$_d/journal"
_s COMMIT_CONTROL "$?"
_control "$_d/journal" "$_next"
}
_active_id() {
_now=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$_d/active") || _die active_identity
}
'''


def stop_script(nonce):
    head, parents, setup = borrowed(nonce)
    body = r'''
_states
test ! -e "$_d/journal" && test ! -L "$_d/journal" || _die journal_exists
printf '%s\n' "$_enabled" > "$_d/journal"
_s WRITE_ENABLED "$?"
_control "$_d/journal" "$_enabled"
cp -p "$_d/candidate" "$_d/active"
_s COPY_ENABLED "$?"
_v "$_d/active" @CANDIDATE@
_publish_control "$_pending" "$_enabled"
_emit 'INTENT registry=enabled pending=DISABLE'
cp -p "$_d/original" "$_d/restore"
_s STAGE_ORIGINAL "$?"
_v "$_d/restore" @ORIGINAL@
mv -f "$_d/restore" "$_d/active"
_s RESTORE_OWNED_ORIGINAL "$?"
_v "$_d/active" @ORIGINAL@
cmp "$_d/original" "$_d/active"
_s CMP_RESTORED "$?"
_control "$_d/journal" "$_pending"
_sv
_active_id
_emit "RESTORED dir_id=$_di active_id=$_now"
_u=$(id -u) || _die uid
test "$_u" = 0 || _die not_root
_emit 'STOP intent=DISABLE registry=enabled pending=DISABLE rc=73'
exit 73
'''
    return head + CONTROL + '\n_sv\n' + parents + setup + body.replace('@CANDIDATE@', CANDIDATE).replace('@ORIGINAL@', ORIGINAL)


def complete_script(nonce, directory_id, active_id):
    if not re.fullmatch('[0-9]+:[0-9]+', directory_id) or not re.fullmatch('[0-9]+(?::[0-9]+){7}', active_id):
        raise ValueError('strict numeric identity evidence required')
    head, parents, _ = borrowed(nonce)
    body = r'''
_guard
_states
_entries=$(ls -A "$_d") || _die list
test "$_entries" = "$(printf 'active\ncandidate\njournal\noriginal')" || _die unexpected_entry
_control "$_d/journal" "$_pending"
_v "$_d/original" @ORIGINAL@
_v "$_d/candidate" @CANDIDATE@
_v "$_d/active" @ORIGINAL@
_active_id
test "$_now" = "$_expected_active" || _die active_changed
_emit "BEFORE_COMPLETE active_id=$_now"
cmp "$_d/original" "$_d/active"
_s CMP_BEFORE_COMPLETE "$?"
# Only control data is changed. No image copy/rename/chmod/chown occurs here.
_publish_control "$_disabled" "$_pending"
_v "$_d/active" @ORIGINAL@
_active_id
test "$_now" = "$_expected_active" || _die active_rewritten
cmp "$_d/original" "$_d/active"
_s CMP_AFTER_COMPLETE "$?"
_control "$_d/journal" "$_disabled"
_emit "COMMIT registry=disabled pending=none active_id=$_now no_rewrite=1"
_guard
_entries=$(ls -A "$_d") || _die cleanup_list
test "$_entries" = "$(printf 'active\ncandidate\njournal\noriginal')" || _die cleanup_unknown
_v "$_d/original" @ORIGINAL@
_v "$_d/candidate" @CANDIDATE@
_control "$_d/journal" "$_disabled"
rm "$_d/active" "$_d/candidate" "$_d/original" "$_d/journal"
_s REMOVE_WHITELIST "$?"
_guard
rmdir "$_d"
_s RMDIR "$?"
test ! -e "$_d" && test ! -L "$_d" || _die cleanup_remains
_emit 'END rc=0 registry=disabled pending=none cleanup=absent'
'''
    # Mark parent contract explicitly so host tests can substitute its known-volume fixture.
    return (head + CONTROL + '\n_di=' + directory_id + '\n_expected_active=' + active_id
            + '\n# PARENT_CONTRACT_BEGIN\n' + parents + '# PARENT_CONTRACT_END\n'
            + body.replace('@ORIGINAL@', ORIGINAL).replace('@CANDIDATE@', CANDIDATE))


def phase1_evidence(folder, prepared):
    folder, prepared = Path(folder), Path(prepared)
    plan = json.loads((prepared / 'plan.json').read_text())
    command = (prepared / 'stop.sh').read_text()
    if sha(command.encode()) != plan['command_sha256']:
        raise ValueError('prepared phase1 changed')
    m = json.loads((folder / 'manifest.json').read_text())
    expected = dict(uid=0, user='root', firmware='55.00.750B', flavor='cmu150_NA')
    if m.get('mode') != 'live' or m.get('outcome') != 'remote_nonzero' or m.get('identity') != expected or not m.get('port_closed'):
        raise ValueError('known completed phase1 nonzero/root55/closed port required; UNKNOWN refuses')
    ops = [o for o in m['operations'] if o.get('command') == command and o.get('outcome') == 'completed' and o.get('exit_status') == STOP_RC]
    if len(ops) != 1:
        raise ValueError('one exact completed exit73 required')
    name = ops[0]['nonce'] + '.output.bin'
    data = (folder / name).read_bytes(); artifact = m['artifacts'][name]
    if sha(data) != artifact['sha256'] or len(data) != artifact['bytes']:
        raise ValueError('phase1 output integrity mismatch')
    prefix = ('COPYTX ' + plan['nonce'] + ' ').encode()
    lines = [line[len(prefix):].decode('ascii') for line in data.replace(b'\r\n', b'\n').splitlines() if line.startswith(prefix)]
    stop = 'STOP intent=DISABLE registry=enabled pending=DISABLE rc=73'
    restored = [line for line in lines if line.startswith('RESTORED ')]
    if lines.count(stop) != 1 or len(restored) != 1 or lines[-1] != stop or any('FAIL:' in line for line in lines):
        raise ValueError('intended stop/restored records missing, duplicate or conflicting')
    match = re.fullmatch(r'RESTORED dir_id=([0-9]+:[0-9]+) active_id=([0-9]+(?::[0-9]+){7})', restored[0])
    if not match or match[1].split(':')[0] != '45826' or match[2].split(':')[3:] != ['94058','755','1018','3015','1']:
        raise ValueError('phase1 identity/profile mismatch')
    return plan['nonce'], match[1], match[2], {'bundle': str(folder), 'manifest_sha256': sha((folder/'manifest.json').read_bytes())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=('stop', 'complete'), required=True)
    p.add_argument('--nonce'); p.add_argument('--out', required=True)
    p.add_argument('--phase1-bundle'); p.add_argument('--phase1-prepared')
    a = p.parse_args()
    if a.phase == 'stop':
        if not a.nonce: p.error('stop requires fresh --nonce')
        command = stop_script(a.nonce); proof = None
        nonce = a.nonce
    else:
        if not a.phase1_bundle or not a.phase1_prepared: p.error('complete requires known phase1 evidence/prepared')
        nonce, di, ai, proof = phase1_evidence(a.phase1_bundle, a.phase1_prepared)
        command = complete_script(nonce, di, ai)
    wire = wrap_command(command, '0'*32)
    folder = Path(a.out); folder.mkdir(parents=True, exist_ok=False)
    (folder/(a.phase+'.sh')).write_text(command)
    plan = dict(mode='review_only', nonce=nonce, phase=a.phase, opens_uart=False,
                scratch='/tmp/mnt/data_persist/cmu-bench-probe-'+nonce,
                command_sha256=sha(command.encode()), command_bytes=len(command.encode()),
                sample_wire_bytes=len(wire), max_physical_line=max(map(len,wire.splitlines())),
                deadline=40 if a.phase=='stop' else 30, output_cap=65536,
                expected_remote_rc=STOP_RC if a.phase=='stop' else 0,
                expected_host_rc=3 if a.phase=='stop' else 0, phase1_proof=proof,
                source_reference=str(REFERENCE/'command.sh'),
                scope='owned writable-volume COPIES/process exit only; no real GUI write or durability/recovery policy')
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(plan,indent=2))


if __name__ == '__main__':
    main()
