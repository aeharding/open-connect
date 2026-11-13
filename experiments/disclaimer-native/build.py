#!/usr/bin/env python3
"""Hash-bound HOST native candidate builder. Full module bytes stay in private runs/backups."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import shutil

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from open_connect.files import posix_cksum
HERE=Path(__file__).resolve().parent
BASE_SHA='acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302'
BASE_LENGTH=454142
TARGET='/jci/mmui/uia/libjciuiasystem.so'
FIRMWARE='55.00.750B/cmu150_NA'
STUB=0x48c00
END=0x49000
SITE=0x7ed4


def metadata(data):
    return dict(bytes=len(data),md5=hashlib.md5(data).hexdigest(),crc=posix_cksum(data),
                sha256=hashlib.sha256(data).hexdigest())


class Rejected(ValueError):pass


def tool(name, explicit=None):
    """Resolve explicit tools or PATH; Apple developer tools also support xcrun."""
    value=str(explicit or name)
    found=shutil.which(value)
    if not found and explicit is None and sys.platform=="darwin":
        r=subprocess.run(["xcrun","--find",name],capture_output=True,text=True)
        if r.returncode==0:
            found=shutil.which(r.stdout.strip())
    if not found:
        raise Rejected(f"missing executable {value}; install LLVM or pass its explicit path")
    return str(Path(found).absolute())


def private_output(output):
    output=Path(output).resolve()
    if not any(output.is_relative_to(ROOT/n) and output!=ROOT/n for n in ("runs","backups")):
        raise Rejected("OEM/candidate bytes must remain private under runs/backups")
    if output.exists():
        raise Rejected("output already exists; choose a new directory")
    return output


class ELF:
    def __init__(self,data):
        self.data=data
        self.h=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
        if data[:7]!=b'\x7fELF\x01\x01\x01' or self.h[2]!=40:
            raise Rejected('requires little-endian ARM ELF32')
        self.sections=[struct.unpack_from('<IIIIIIIIII',data,self.h[6]+i*self.h[11]) for i in range(self.h[12])]
        names=self.sections[self.h[13]]
        self.names=[self.string(names[4]+s[0]) for s in self.sections]
        self.symbols={}
        self.by_table={}
        for i,s in enumerate(self.sections):
            if s[1] not in (2,11):continue
            strings=self.sections[s[6]];symbols=[]
            for a in range(s[4],s[4]+s[5],s[9]):
                name,value,size,info,other,index=struct.unpack_from('<IIIBBH',data,a)
                sym=dict(name=self.string(strings[4]+name),value=value,size=size,section=index,info=info)
                symbols.append(sym)
                if sym['name']:self.symbols[sym['name']]=sym
            self.by_table[i]=symbols
    def string(self,offset):return self.data[offset:self.data.index(b'\0',offset)].decode('ascii')
    def section(self,name):
        i=self.names.index(name);return i,self.sections[i]
    def section_data(self,name):
        _,s=self.section(name);return self.data[s[4]:s[4]+s[5]]


def guard(original,firmware=FIRMWARE):
    if firmware!=FIRMWARE or len(original)!=BASE_LENGTH or metadata(original)['sha256']!=BASE_SHA:
        raise Rejected('unsupported firmware/exact native base; no override/fuzzy patch')
    elf=ELF(original)
    ph=struct.unpack_from('<IIIIIIII',original,elf.h[5])
    if ph!=(1,0,0,0,STUB,STUB,5,0x8000):raise Rejected('unexpected executable LOAD')
    if original[STUB:END]!=bytes(END-STUB):raise Rejected('executable padding is not empty')
    if struct.unpack_from('<I',original,SITE)[0]!=0xebfff32c:raise Rejected('original helper BL mismatch')
    return elf


def branch_target(word,place):
    n=word&0xffffff
    if n&0x800000:n-=1<<24
    return place+8+(n<<2)


def branch_word(original,place,target):
    if original>>24 not in (0xea,0xeb):raise Rejected('not an unconditional ARM B/BL')
    delta=target-place-8
    if delta%4 or not -(1<<25)<=delta<(1<<25):raise Rejected('ARM branch range/alignment')
    return (original&0xff000000)|((delta>>2)&0xffffff)


def link_object(obj,external):
    elf=ELF(obj)
    text_i,text=elf.section('.text');textdata=elf.section_data('.text')
    ro_i,ro=elf.section('.rodata.str1.1');roaddr=STUB+((len(textdata)+3)&~3)
    locations={text_i:STUB,ro_i:roaddr}
    blob=bytearray(textdata+bytes(roaddr-STUB-len(textdata))+elf.section_data('.rodata.str1.1'))
    if len(blob)>END-STUB:raise Rejected(f'compiled PIC stub {len(blob)} exceeds verified1024B padding')
    symbols={}
    def address(sym):
        if sym['section'] in locations:return locations[sym['section']]+sym['value']
        if sym['section']==0 and sym['name'] in external:return external[sym['name']]
        raise Rejected('unsupported/undefined symbol '+sym['name'])
    relocations=[]
    for i,s in enumerate(elf.sections):
        if s[1]!=9:continue
        # .ARM.exidx is compiler cantunwind metadata, not injected executable/data.
        if s[7] not in locations:continue
        for at in range(s[4],s[4]+s[5],s[9]):
            offset,info=struct.unpack_from('<II',obj,at);kind=info&255
            sym=elf.by_table[s[6]][info>>8];target=address(sym)
            place=locations[s[7]]+offset;index=place-STUB
            old=struct.unpack_from('<I',blob,index)[0]
            if kind in (28,29):
                if (kind==28 and old>>24!=0xeb) or (kind==29 and old>>24!=0xea):
                    raise Rejected('unexpected compiler ARM branch relocation form')
                # REL addend is encoded in instruction; compiler's unresolved branch is -8.
                addend=branch_target(old,0)-8
                delta=target+addend-place
                if delta%4 or not -(1<<25)<=delta<(1<<25):raise Rejected('relocation branch range')
                new=(old&0xff000000)|((delta>>2)&0xffffff)
            elif kind==3: # R_ARM_REL32 S+A-P; runtime load base cancels for PC-relative references.
                new=(target+old-place)&0xffffffff
            else:raise Rejected('unsupported relocation '+str(kind))
            struct.pack_into('<I',blob,index,new)
            relocations.append(dict(place=place,kind=kind,symbol=sym['name'],target=target,old=old,new=new))
    for name,sym in elf.symbols.items():
        if sym['section'] in locations:symbols[name]=address(sym)
    return bytes(blob),symbols,relocations


def patch(original,obj,external,firmware=FIRMWARE):
    elf=guard(original,firmware)
    stub,symbols,relocs=link_object(obj,external)
    entry=symbols['cmu_native_process']
    if branch_target(struct.unpack_from('<I',original,SITE)[0],SITE)!=external['cmu_stock_process']:
        raise Rejected('stock helper PLT mismatch')
    candidate=bytearray(original)
    candidate[STUB:STUB+len(stub)]=stub
    # Extend only the original RX LOAD's declared tail into existing zero file padding.
    for offset in (16,20):struct.pack_into('<I',candidate,elf.h[5]+offset,STUB+len(stub))
    struct.pack_into('<I',candidate,SITE,branch_word(0xeb000000,SITE,entry))
    return bytes(candidate),dict(entry=entry,stub_start=STUB,stub_bytes=len(stub),
                                symbols=symbols,relocations=relocs)


def rollback(current,original,expected_candidate):
    guard(original)
    if current!=expected_candidate:raise Rejected('unknown/later module bytes preserved')
    return original


def build(output,original_path,*,clang=None,objdump=None):
    output=private_output(output)
    original_path=Path(original_path).resolve()
    original=original_path.read_bytes();guard(original)
    clang=tool("clang",clang);objdump=tool("llvm-objdump",objdump)
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    (output/'native.c').write_bytes((HERE/'native.c').read_bytes())
    (output/'build.py').write_bytes(Path(__file__).read_bytes())
    cmd=[clang,'--target=armv7-none-eabi','-march=armv7-a','-marm','-mfloat-abi=hard','-mfpu=vfpv3',
         '-Oz','-ffreestanding','-fPIC','-fvisibility=hidden','-fno-unwind-tables',
         '-fno-asynchronous-unwind-tables','-fno-stack-protector','-c',str(output/'native.c'),'-o',str(output/'native.o')]
    r=subprocess.run(cmd,capture_output=True)
    (output/'compile.stdout').write_bytes(r.stdout);(output/'compile.stderr').write_bytes(r.stderr)
    (output/'compile.json').write_text(json.dumps(dict(command=cmd,returncode=r.returncode),indent=2)+'\n')
    if r.returncode:raise Rejected('ARM compiler failed; see retained compile evidence')
    p=subprocess.run([objdump,'-d','-j','.plt',str(original_path)],capture_output=True)
    (output/'original-plt.txt').write_bytes(p.stdout)
    if p.returncode:raise Rejected('PLT disassembly failed')
    labels={m[2]:int(m[1],16) for m in re.finditer(r'^([0-9a-f]+) <([^>]+)>:',p.stdout.decode(),re.M)}
    external={
        'cmu_stock_process':labels['UIAHLP_ProcessContextEvent@plt'],
        'cmu_system':labels['system@plt'],'cmu_copy':labels['memcpy@plt'],
        'cmu_log_allowed':labels['COMMON_Log_Acceptable@plt'],
        'cmu_log_write':labels['COMMON_Log_Write@plt'],
        'cmu_uia_handle':0x6914,'cmu_focused_app':labels['UIAM_GetFocusedApp@plt'],
        'cmu_stop_service':0x187d4,'cmu_image_base':0}
    obj=(output/'native.o').read_bytes();candidate,linked=patch(original,obj,external)
    (output/'original.bin').write_bytes(original);(output/'candidate.bin').write_bytes(candidate)
    blocks=[0,7,72];delta=b''.join(candidate[i*4096:(i+1)*4096] for i in blocks)
    reconstructed=bytearray(original)
    for j,i in enumerate(blocks):reconstructed[i*4096:(i+1)*4096]=delta[j*4096:(j+1)*4096]
    if bytes(reconstructed)!=candidate:raise Rejected('unexpected changes outside three delta blocks')
    (output/'delta-blocks.bin').write_bytes(delta)
    tools={name:dict(path=exe,version=subprocess.check_output([exe,'--version'],text=True).splitlines()[0])
           for name,exe in [('clang',clang),('llvm-objdump',objdump)]}
    profile=dict(tools=tools,schema='NATIVE_INTRO_CANDIDATE_V1',status='HOST_ONLY_UNINSTALLED',live_authority=False,
        firmware=FIRMWARE,target=TARGET,original=metadata(original),candidate=metadata(candidate),
        candidate_path=str(output/'candidate.bin'),
        delta=dict(path=str(output/'delta-blocks.bin'),**metadata(delta),block_size=4096,block_indices=blocks),
        source_pins={str(p.relative_to(ROOT)):metadata(p.read_bytes())['sha256'] for p in [HERE/'native.c',HERE/'build.py']},
        scope=dict(event=1470,current_context=1021,focused_app=1,logo_state=2,
                   unsupported='original stock flow',quick_start=False,cold_start=False),
        manager_dependency=dict(path='/jci/lib/libjciuiamgr.so',bytes=196469,
                   sha256='0c32ab6dc6833d287d363c3ff63998450cce97121ace994930276c4adb28474b',
                   md5='8ce49f8bc9833c48a3a89e5c4c683ddc',crc=552157721),
        linked=linked,external_symbols=external,
        reconstruction=[dict(kind='delta_block',index=0),dict(kind='original_blocks',skip=1,count=6),
          dict(kind='delta_block',index=1),dict(kind='original_blocks',skip=8,count=64),
          dict(kind='delta_block',index=2),dict(kind='original_blocks',skip=73,count=38)],
        restored_bytes_exact=rollback(candidate,original,candidate)==original,
        limits=['host C contract model, not ARM execution or CMU proof',
                'new no-exception C has no injected unwind entries; original metadata retained',
                'same-frame cloned table view relies on synchronous manager consumption',
                'requires paired renderer completion hook for deferred stock DisposeIntroVideo; quickstop only on actual exit'])
    (output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    for name,flags in [('native-object',['-d','-r','-h']),('candidate-headers',['-p','-h'])]:
        inputfile=output/('native.o' if name=='native-object' else 'candidate.bin')
        q=subprocess.run([objdump,*flags,str(inputfile)],capture_output=True)
        (output/(name+'.txt')).write_bytes(q.stdout)
        if q.returncode:raise Rejected(name+' verification failed')
    return profile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original",type=Path,required=True,help="exact private OEM libjciuiasystem.so")
    p.add_argument("--output",type=Path,required=True,help="new directory below runs/ or backups/")
    p.add_argument("--clang",help="ARM-capable Clang executable (default: PATH, then xcrun)")
    p.add_argument("--objdump",help="llvm-objdump executable (default: PATH, then xcrun)")
    a=p.parse_args()
    try:
        profile=build(a.output,a.original,clang=a.clang,objdump=a.objdump)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        p.exit(2,f"build not completed: {exc}\n")
    print(json.dumps(profile,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
