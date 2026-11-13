"""Meaningful host contract/ELF checks. Does not execute ARM or touch CMU."""
import json
import os
from pathlib import Path
import struct
import subprocess
import unittest
import build as b

OUT=Path(os.environ['CMU_NATIVE_CHECK_DIR'])
PROFILE=json.loads((OUT/'candidate/profile.json').read_text())
O=(OUT/'candidate/original.bin').read_bytes()
C=(OUT/'candidate/candidate.bin').read_bytes()

class NativeTests(unittest.TestCase):
    def test_actual_private_base_exact_delta_and_conflict_refusing_undo(self):
        self.assertEqual(b.metadata(O),PROFILE['original'])
        self.assertEqual(b.metadata(C),PROFILE['candidate'])
        self.assertEqual(len(C),len(O))
        self.assertEqual(b.rollback(C,O,C),O)
        with self.assertRaises(b.Rejected):b.rollback(C+b'x',O,C)
        with self.assertRaises(b.Rejected):b.guard(O,'73.00.000')
        with self.assertRaises(b.Rejected):b.guard(O[:-1]+bytes([O[-1]^1]))
        with self.assertRaises(b.Rejected):b.guard(C)
        delta=(OUT/'candidate/delta-blocks.bin').read_bytes()
        self.assertEqual(len(delta),12288)
        reconstructed=bytearray(O)
        for i,index in enumerate(PROFILE['delta']['block_indices']):
            reconstructed[index*4096:(index+1)*4096]=delta[i*4096:(i+1)*4096]
        self.assertEqual(bytes(reconstructed),C)
        for i,(old,new) in enumerate(zip(O,C)):
            if old!=new:self.assertIn(i//4096,[0,7,72])

    def test_ARM_PIC_calls_and_REL32_math_at_three_load_bases(self):
        p=PROFILE['linked'];self.assertLessEqual(p['stub_bytes'],1024)
        new=struct.unpack_from('<I',C,b.SITE)[0]
        self.assertEqual(b.branch_target(new,b.SITE),p['entry'])
        self.assertEqual(new>>24,0xeb)
        for relocation in p['relocations']:
            place=relocation['place'];target=relocation['target']
            old,new=relocation['old'],relocation['new']
            self.assertEqual(struct.unpack_from('<I',C,place)[0],new)
            for base in (0,0x2b6ad000,0x60000000):
                if relocation['kind'] in (28,29):
                    self.assertEqual(b.branch_target(new,base+place),base+target)
                else:
                    # ELF R_ARM_REL32: S+A-P, independent of actual DSO load base.
                    self.assertEqual((new+base+place)&0xffffffff,(target+base+old)&0xffffffff)
        elf=b.ELF(O);newelf=b.ELF(C)
        oldp=struct.unpack_from('<IIIIIIII',O,elf.h[5]);newp=struct.unpack_from('<IIIIIIII',C,elf.h[5])
        self.assertEqual(newp[:4],oldp[:4]);self.assertEqual(newp[6:],oldp[6:])
        self.assertEqual(newp[4],b.STUB+p['stub_bytes']);self.assertEqual(newp[5],newp[4])
        self.assertLessEqual(newp[4],b.END)
        self.assertEqual(O[elf.h[5]+32:elf.h[5]+4*32],C[elf.h[5]+32:elf.h[5]+4*32])
        self.assertEqual(O[elf.h[6]:],C[elf.h[6]:]) # Symbol/section history retained.
        self.assertEqual(elf.h,newelf.h)

    def test_same_C_wrapper_actual_rule_fixture_host_execution(self):
        r=subprocess.run([str(OUT/'host-contract')],capture_output=True,text=True,timeout=10)
        (OUT/'host.stdout').write_text(r.stdout);(OUT/'host.stderr').write_text(r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(r.stdout.count('PASS '),5)
        self.assertIn('HOST MODEL ONLY',r.stdout)

    def test_public_destination_refused_without_candidate_write(self):
        destination=b.HERE/'SHOULD_NOT_EXIST'
        self.assertFalse(destination.exists())
        with self.assertRaises(b.Rejected):b.build(destination)
        self.assertFalse(destination.exists())

if __name__=='__main__':unittest.main(verbosity=2)
