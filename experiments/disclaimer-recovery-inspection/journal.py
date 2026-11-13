"""Strict parser for the ONE existing WARM1 retained record; never executes data."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'runs/20261113T051316-0600-t14-warm-real-roundtrip-v2/retained-journal.exact.bin'
WARM=ROOT/'experiments/disclaimer-warm-roundtrip/warm.sh.in'
AUTHORITY=ROOT/'experiments/disclaimer-warm-roundtrip/checks/20261113T104206.713237Z/manifest.json'
KEYS=('registry','pending','phase','goal','initial','directory','original','candidate','cstage','ostage')
STATES={'prepared':('disabled','ENABLE'),'staged':('disabled','ENABLE'),
 'candidate_verified':('enabled','none'),'planned_restore':('enabled','DISABLE'),
 'restoring_O':('enabled','DISABLE'),'original_restored':('disabled','none'),
 'original_present':('disabled','none')}


def sha(data):return hashlib.sha256(data).hexdigest()


def identity(value,device,size,mtime=None):
 if not re.fullmatch(r'(?:0|[1-9][0-9]*)(?::(?:0|[1-9][0-9]*)){7}',value):raise ValueError('bad identity syntax')
 fields=value.split(':')
 if fields[0]!=str(device) or int(fields[1])<1 or fields[3:]!=[str(size),'755','1018','3015','1']:
  raise ValueError('unsupported identity profile')
 if mtime is not None and fields[2]!=str(mtime):raise ValueError('wrong mtime')
 return fields


def parse(data):
 if not 0<len(data)<=2048 or not data.endswith(b'\n') or data.count(b'\n')!=1 or b'\0' in data:
  raise ValueError('one bounded exact LF record required')
 fields=data[:-1].decode('ascii').split('|')
 if len(fields)!=12 or fields[0]!='WARM1' or not re.fullmatch('[0-9a-f]{32}',fields[1]):raise ValueError('wrong header/fields')
 out={'nonce':fields[1]}
 for key,field in zip(KEYS,fields[2:]):
  if not field.startswith(key+'='):raise ValueError('wrong field order/key')
  out[key]=field[len(key)+1:]
 if out['goal']!='O' or STATES.get(out['phase'])!=(out['registry'],out['pending']):raise ValueError('invalid intent/state')
 identity(out['initial'],64785,94058,1433953097)
 if not re.fullmatch(r'45826:[1-9][0-9]*',out['directory']):raise ValueError('wrong directory')
 identity(out['original'],45826,94058,1433953097)
 c=identity(out['candidate'],45826,94055)
 for key,size,mtime in [('cstage',94055,c[2]),('ostage',94058,'1433953097')]:
  if out[key]!='none':identity(out[key],64785,size,mtime)
 if out['phase'] in ('staged','candidate_verified','planned_restore','restoring_O','original_restored') and ('none' in (out['cstage'],out['ostage'])):
  raise ValueError('missing recorded stages')
 return out


def retained_profile(data=None):
 data=FIXTURE.read_bytes() if data is None else data
 out=parse(data)
 out['journal_bytes']=len(data);out['journal_md5']=hashlib.md5(data).hexdigest()
 out['journal_sha256']=sha(data)
 return out


def helpers():
 text=WARM.read_text();authority=json.loads(AUTHORITY.read_text())
 if sha(text.encode())!=authority['source_sha256']['warm.sh.in']:raise ValueError('passed warm guards changed')
 selected=[]
 for name in ('canon','_id','_root_mode','_source_route','_persist_route','_backup_guard',
              '_image_path','_verify','_verify_o','_verify_c','_backups'):
  match=re.search(r'^'+re.escape(name)+r'\(\) \{',text,re.M)
  if not match:raise ValueError('missing frozen guard '+name)
  line_end=text.index('\n',match.start())
  end=line_end if text[match.start():line_end].rstrip().endswith('}') else text.index('\n}\n',match.start())+2
  selected.append(text[match.start():end]+'\n')
 return '\n'.join(selected)
