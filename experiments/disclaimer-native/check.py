"""Build and check ONE private native candidate; preserve pre-test sources and all outcomes."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import struct,subprocess,sys
import build as b
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    out=ROOT/'runs'/('t12-native-host-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    out.mkdir(mode=0o700)
    (out/'sources').mkdir()
    names=['native.c','build.py','host_test.c','test_native.py','check.py']
    pins={}
    for name in names:
        data=(HERE/name).read_bytes();(out/'sources'/name).write_bytes(data)
        pins[str((HERE/name).relative_to(ROOT))]=sha(data)
    status=1;error=None
    try:
        profile=b.build(out/'candidate')
        # Actual captured table words remain private; no OEM fixture bytes in tracked code.
        original=(out/'candidate/original.bin').read_bytes()
        words=lambda va,n:struct.unpack_from('<'+'I'*n,original,va-0x8000)
        assert words(0x5abe8,11)[5]==1010
        fixture='static const u32 rule80[11]={'+','.join(hex(x) for x in words(0x5abe8,11))+'};\n'
        fixture+='static const u32 rules194[9][11]={\n'
        for i in range(9):fixture+='{'+','.join(hex(x) for x in words(0x5d370+i*44,11))+'},\n'
        fixture+='};\n'
        (out/'fixture.h').write_text(fixture)
        sdk=subprocess.check_output(['/usr/bin/xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
        cmd=[b.CLANG,'-isysroot',sdk,'-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+str(HERE),'-I'+str(out),
             str(HERE/'host_test.c'),'-o',str(out/'host-contract')]
        r=subprocess.run(cmd,capture_output=True)
        (out/'host-compile.stdout').write_bytes(r.stdout);(out/'host-compile.stderr').write_bytes(r.stderr)
        (out/'host-compile.json').write_text(json.dumps(dict(command=cmd,returncode=r.returncode),indent=2)+'\n')
        if r.returncode:raise RuntimeError('host compile failed: '+r.stderr.decode())
        env={**os.environ,'CMU_NATIVE_CHECK_DIR':str(out),'PYTHONDONTWRITEBYTECODE':'1'}
        r=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_native'],cwd=HERE,
                         capture_output=True,env=env,timeout=90)
        (out/'stdout.txt').write_bytes(r.stdout);(out/'stderr.txt').write_bytes(r.stderr)
        sys.stdout.buffer.write(r.stdout);sys.stdout.buffer.write(r.stderr);status=r.returncode
    except BaseException as exc:
        error=repr(exc);(out/'failure.txt').write_text(error+'\n');print(error)
    manifest=dict(scope='HOST C semantic contract plus compiled ARM ELF/PIC relocation checks; no hardware or ARM execution',
                  returncode=status,error=error,source_sha256=pins,
                  artifacts={str(p.relative_to(out)):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
                             for p in out.rglob('*') if p.is_file()})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if status==0:
        ready=dict(schema='NATIVE_INTRO_HOST_REVIEW_V1',status='HOST_CHECKS_PASS',live_authority=False,
                   profile=str(out/'candidate/profile.json'),manifest=str(out/'manifest.json'),source_pins=pins)
        (HERE/'host-ready.json').write_text(json.dumps(ready,indent=2)+'\n')
    print('EVIDENCE',out,flush=True);print('PASS',status==0,flush=True)
    return status
if __name__=='__main__':raise SystemExit(main())
