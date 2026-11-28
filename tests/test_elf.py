"""Offline unit tests for tooling/open_connect/elf.py with synthetic ARM ELF32 blobs."""

import struct
import unittest

from open_connect.elf import ELF


def _build_arm_elf(
    *,
    text_bytes: bytes = b"\x00\xf0\x20\xe3\x1e\xff\x2f\xe1",
    sym_name: bytes = b"handler",
    shstr_extra: bytes = b"",
    phentsize: int = 32,
    shentsize: int = 40,
    sym_entsize: int = 16,
    shstrndx: int = 1,
    truncate: int = 0,
) -> bytes:
    """Build a minimal valid little-endian ARM ELF32 with PT_LOAD, .shstrtab, .text, .bss, .strtab, .symtab."""
    shstrtab = b"\x00.shstrtab\x00.text\x00.bss\x00.strtab\x00.symtab\x00" + shstr_extra
    strtab = b"\x00" + sym_name + b"\x00"
    # 2 symbols: NULL + sym_name at vaddr 0x10000
    symtab = struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0) + struct.pack(
        "<IIIBBH", 1, 0x10000, len(text_bytes), 0x12, 0, 2
    )

    phoff = 52
    ph_bytes = struct.pack(
        "<IIIIIIII",
        1,  # PT_LOAD
        0x100,  # p_offset
        0x10000,  # p_vaddr
        0x10000,  # p_paddr
        len(text_bytes),  # p_filesz
        len(text_bytes) + 64,  # p_memsz
        5,  # PF_R | PF_X
        0x1000,  # p_align
    )
    buf = bytearray(0x100)
    buf[phoff : phoff + len(ph_bytes)] = ph_bytes

    text_off = len(buf)
    buf.extend(text_bytes)
    shstr_off = len(buf)
    buf.extend(shstrtab)
    str_off = len(buf)
    buf.extend(strtab)
    while len(buf) % 4:
        buf.append(0)
    sym_off = len(buf)
    buf.extend(symtab)
    while len(buf) % 4:
        buf.append(0)
    shoff = len(buf)

    def shdr(name_off, sh_type, flags, addr, off, size, link=0, info=0, align=1, entsize=0):
        return struct.pack(
            "<IIIIIIIIII", name_off, sh_type, flags, addr, off, size, link, info, align, entsize
        )

    sections = [
        shdr(0, 0, 0, 0, 0, 0),  # 0: NULL
        shdr(1, 3, 0, 0, shstr_off, len(shstrtab)),  # 1: .shstrtab
        shdr(11, 1, 6, 0x10000, text_off, len(text_bytes), align=4),  # 2: .text
        shdr(17, 8, 3, 0x10000 + len(text_bytes), 0xFFFFFF00, 64, align=4),  # 3: .bss (SHT_NOBITS)
        shdr(22, 3, 0, 0, str_off, len(strtab)),  # 4: .strtab
        shdr(30, 2, 0, 0, sym_off, len(symtab), link=4, info=1, align=4, entsize=sym_entsize),
    ]
    for s in sections:
        buf.extend(s)

    ident = b"\x7fELF\x01\x01\x01" + b"\x00" * 9
    ehdr = struct.pack(
        "<16sHHIIIIIHHHHHH",
        ident,
        2,  # ET_EXEC
        40,  # EM_ARM
        1,  # EV_CURRENT
        0x10000,
        phoff,
        shoff,
        0x5000200,
        52,
        phentsize,
        1,
        shentsize,
        len(sections),
        shstrndx,
    )
    buf[0:52] = ehdr
    return bytes(buf[:-truncate]) if truncate else bytes(buf)


class ElfParserTests(unittest.TestCase):
    def test_valid_arm_elf_sections_symbols_and_virtual_data(self):
        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        elf = ELF(_build_arm_elf(text_bytes=payload))
        self.assertEqual(elf.section_data(".text"), payload)
        self.assertEqual(elf.virtual_data(0x10000, 4), payload[:4])
        self.assertEqual(elf.virtual_data(0x10004, 4), payload[4:])
        self.assertIn("handler", elf.symbols)
        self.assertEqual(elf.symbols["handler"]["value"], 0x10000)

    def test_rejects_truncated_malformed_nobits_and_out_of_bounds_elfs(self):
        with self.assertRaises(ValueError):
            ELF(b"\x7fELF" * 4)  # < 52 bytes
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(phentsize=16))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(shentsize=20))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(shstrndx=99))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(sym_entsize=0))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(sym_entsize=8))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(sym_name=b"\xff\xfe"))
        with self.assertRaises(ValueError):
            ELF(_build_arm_elf(truncate=16))

        elf = ELF(_build_arm_elf())
        with self.assertRaises(ValueError):
            elf.section_data(".bss")
        with self.assertRaises(ValueError):
            elf.virtual_data(0x10000, -1)
        with self.assertRaises(ValueError):
            elf.virtual_data(0x10000, 999)


if __name__ == "__main__":
    unittest.main()
