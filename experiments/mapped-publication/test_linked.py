"""Runs the actual shell transaction against real local files, links and mmap."""
import json,mmap,os,subprocess,tempfile,unittest
from pathlib import Path
import linked
from bench import rt,stock
class LinkedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.r=Path(self.tmp.name).resolve();self.d=self.r/"data";self.d.mkdir(mode=0o700)
  self.p=self.r/"lib.so";self.h=self.r/"holdO";self.c=self.r/"holdC";self.s=self.r/"stage"
  self.o=b"O"*454142;self.new=b"C"*454142
  for p,b in [(self.p,self.o),(self.d/"original",self.o),(self.d/"candidate",self.new)]:
   p.write_bytes(b);p.chmod(0o755)
  (self.d/"state").write_text("prepared|none\n");(self.d/"state").chmod(0o600)
  self.oid=self.sid(self.p)
  text=linked.render(str(self.p),str(self.d),str(self.h),str(self.c),str(self.s),self.oid,{},rt.fp(self.o),rt.fp(self.new))
  # Only OS-boundary shims. All copy/link/move/readback/control logic is unchanged.
  text=text.replace('rootmode() {\n awk \'$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{n++;m=$4}END{if(n!=1)exit 1;print m}\' /proc/mounts\n}',
                    'rootmode() { cat "$TEST_MODE"; }')
  text=text.replace('flush() { timeout -t 8 -s TERM /bin/sync; }','flush() { test ! -e "$TEST_DIR/fail-sync"; }')
  text=text.replace(' timeout -t 8 -s TERM /bin/busybox mount -i -n -t relfs -o remount,"$1",noatime /dev/ffx01p1 /',
   ' test "$1" != ro || test ! -e "$TEST_DIR/fail-ro" || return 1\n printf "%s,noatime\\n" "$1" > "$TEST_MODE"')
  self.script=self.r/"run.sh";self.script.write_text(text)
  self.bin=self.r/"bin";self.bin.mkdir()
  stat=self.bin/"stat"
  stat.write_text('#!'+os.sys.executable+'\n'+r'''
import os,sys
from pathlib import Path
a=sys.argv[1:];fmt=a[0][2:] if a[0].startswith("-c") and a[0]!="-c" else a[1]
p=Path(a[-1]);s=p.stat();mode=s.st_mode&0o777
dev=45826 if str(p).startswith(os.environ["TEST_DIR"]+"/data") else 64785
uid,gid=(1018,3015) if p.is_file() and mode==0o755 else (0,0)
vals={"d":dev,"i":s.st_ino,"Y":int(s.st_mtime),"s":s.st_size,"a":format(mode,"o"),"u":uid,"g":gid,"h":s.st_nlink}
for k,v in vals.items():fmt=fmt.replace("%"+k,str(v))
print(fmt)
''')
  stat.chmod(0o755)
  ident=self.bin/"id";ident.write_text("#!/bin/sh\necho 0\n");ident.chmod(0o755)
  self.mode=self.r/"mount";self.mode.write_text("ro,noatime\n")
  self.env=dict(os.environ,PATH=str(self.bin)+":"+os.environ["PATH"],TEST_DIR=str(self.r),TEST_MODE=str(self.mode))
 def sid(self,p):
  s=p.stat();return f"64785:{s.st_ino}:{int(s.st_mtime)}:{s.st_size}:755:1018:3015"
 def runmode(self,mode,ok=True):
  r=subprocess.run(["/bin/sh",str(self.script),mode],env=self.env,capture_output=True,text=True,timeout=15)
  if ok:self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  else:self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
  return r
 def test_real_mapped_apply_and_undo(self):
  with self.p.open("rb") as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as original_map:
   self.runmode("VERIFY");self.runmode("APPLY");self.runmode("VERIFY")
   self.assertEqual(original_map[:],self.o)
   self.assertEqual(os.fstat(f.fileno()).st_nlink,1)
   self.assertEqual(self.h.stat().st_ino,os.fstat(f.fileno()).st_ino)
   with self.p.open("rb") as c,mmap.mmap(c.fileno(),0,access=mmap.ACCESS_READ) as candidate_map:
    self.runmode("UNDO");self.runmode("VERIFY")
    self.assertEqual(candidate_map[:],self.new);self.assertEqual(os.fstat(c.fileno()).st_nlink,1)
    self.assertEqual(self.c.stat().st_ino,os.fstat(c.fileno()).st_ino)
   self.assertEqual(self.sid(self.p),self.oid)
   self.assertEqual(self.p.read_bytes(),self.o)
   self.assertEqual(self.mode.read_text(),"ro,noatime\n")
 def test_ro_failure_preserves_links_and_rw_undo(self):
  (self.r/"fail-ro").touch();self.runmode("APPLY",False)
  self.assertEqual(self.p.read_bytes(),self.new);self.assertEqual(self.h.read_bytes(),self.o)
  self.assertEqual(self.mode.read_text(),"rw,noatime\n")
  (self.r/"fail-ro").unlink()
  self.runmode("UNDO");self.runmode("VERIFY")
  self.assertEqual(self.mode.read_text(),"ro,noatime\n")
 def test_conflict_refuses_without_writes(self):
  self.runmode("APPLY")
  self.p.write_bytes(b"unknown")
  before=self.p.read_bytes();self.runmode("UNDO",False)
  self.assertEqual(self.p.read_bytes(),before)
  self.assertEqual(self.h.read_bytes(),self.o)
 def test_real_bundle_event_contract(self):
  b=stock.Bundle(self.r/"bundle","test","t6")
  b.event("restart_request",source_kind="C")
  b.event("native_persistent_verified",source_kind="O",writes=0)
  b.finish("offline")
  self.assertEqual(json.loads((b.path/"manifest.json").read_text())["outcome"],"offline")
if __name__=="__main__":unittest.main()
