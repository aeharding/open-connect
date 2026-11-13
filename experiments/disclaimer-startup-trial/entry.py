"""Typed one-pass COPY entry rendering; control data is never sourced/evaluated."""
import argparse,json,re
from pathlib import Path

def render(plan,stage,temp):
 run=plan['nonce']
 if not re.fullmatch('[0-9a-f]{32}',run):raise ValueError('nonce')
 if plan['mode']!='COPY_ONLY_PERSISTENT_RECOVERY' or plan['real_root_authority'] is not False:raise ValueError('copy profile only')
 if not re.fullmatch('/tmp/cmu-bench-copy-payload-[0-9a-f]{32}',temp):raise ValueError('owned temp path')
 identity=stage['code_identity'];fields=identity.split(':')
 if len(fields)!=8 or not all(re.fullmatch('[0-9]+',x) for x in fields):raise ValueError('code identity')
 if fields[0]!='45826' or fields[3:]!=[str(plan['command_bytes']),'600','0','0','1']:raise ValueError('code metadata')
 if stage['execution'] is not False or stage['core_rc']!=0 or stage['temp_delivery_absent'] is not True:raise ValueError('verified DATA-only stage required')
 for key in ('count','md5','crc'):
  expected=plan['command_bytes' if key=='count' else 'command_'+key]
  if stage['code_'+key]!=expected:raise ValueError('code '+key)
 if not re.fullmatch('[0-9a-f]{32}',plan['command_md5']):raise ValueError('MD5')
 directory=plan['context']['directory']
 if not re.fullmatch('45826:[1-9][0-9]*',directory):raise ValueError('directory')
 # All values are validated scalars. No replacement passes or placeholder tokens.
 return f'''d=/tmp/mnt/data_persist/cmu-bench-probe-{run}
p="$d/recovery.sh"
t={temp}
test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
test "$(stat -c '%d:%i:%a:%u:%g' "$d")" = {directory}:700:0:0 || exit 71
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = {identity} || exit 73
test "$(wc -c < "$p")" = {plan['command_bytes']} || exit 74
test "$(md5sum < "$p")" = '{plan['command_md5']}  -' || exit 75
test "$(cksum < "$p")" = '{plan['command_crc']} {plan['command_bytes']}' || exit 76
test ! -e "$t" && test ! -L "$t" || exit 77
printf 'COPYREC_INDEPENDENCE persistentcode=1 tmp_delivery_absent=1 freshprocesses=3\\n'
/bin/sh "$p" && /bin/sh "$p" RESTORE_ORIGINAL && /bin/sh "$p"
'''

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--temp',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 text=render(json.loads(a.plan.read_text()),json.loads(a.stage.read_text()),a.temp)
 with a.out.open('x') as f:f.write(text)
 print(a.out)
