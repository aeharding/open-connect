"""Read little-endian ARM ELF32 metadata for private host validation; no writes or linking."""

import struct


class ELF:
    def __init__(self, data):
        self.data = data
        if len(data) < 52:
            raise ValueError("truncated ELF header")
        self.h = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
        if data[:7] != b"\x7fELF\x01\x01\x01" or self.h[2] != 40:
            raise ValueError("requires little-endian ARM ELF32")
        e_phoff, e_shoff = self.h[5], self.h[6]
        e_phentsize, e_phnum = self.h[9], self.h[10]
        e_shentsize, e_shnum, e_shstrndx = self.h[11], self.h[12], self.h[13]
        if e_phnum and (e_phentsize < 32 or e_phoff + e_phnum * e_phentsize > len(data)):
            raise ValueError("program header table exceeds file bounds")
        if e_shnum and (e_shentsize < 40 or e_shoff + e_shnum * e_shentsize > len(data)):
            raise ValueError("section header table exceeds file bounds")
        self.sections = [
            struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_shentsize)
            for i in range(e_shnum)
        ]
        self.programs = [
            struct.unpack_from("<IIIIIIII", data, e_phoff + i * e_phentsize) for i in range(e_phnum)
        ]
        for s in self.sections:
            if s[1] != 8 and s[4] + s[5] > len(data):
                raise ValueError("section exceeds file bounds")
        for p in self.programs:
            if p[0] == 1 and p[1] + p[4] > len(data):
                raise ValueError("LOAD segment exceeds file bounds")
        if not self.sections or e_shstrndx >= len(self.sections):
            raise ValueError("missing or invalid section name string table")
        names = self.sections[e_shstrndx]
        if names[1] == 8:
            raise ValueError("section name string table has no file backing")
        names_end = names[4] + names[5]
        self.names = [self.string(names[4] + s[0], names_end) for s in self.sections]
        self.symbols = {}
        self.by_table = {}
        for i, s in enumerate(self.sections):
            if s[1] not in (2, 11):
                continue
            if s[6] >= len(self.sections):
                raise ValueError("invalid symbol string table link")
            strings = self.sections[s[6]]
            if strings[1] == 8:
                raise ValueError("symbol string table has no file backing")
            if s[9] < 16 or s[5] % s[9] != 0:
                raise ValueError("invalid symbol table entry size")
            strings_end = strings[4] + strings[5]
            symbols = []
            for a in range(s[4], s[4] + s[5], s[9]):
                name, value, size, info, other, index = struct.unpack_from("<IIIBBH", data, a)
                sym = dict(
                    name=self.string(strings[4] + name, strings_end),
                    value=value,
                    size=size,
                    section=index,
                    info=info,
                )
                symbols.append(sym)
                if sym["name"]:
                    self.symbols[sym["name"]] = sym
            self.by_table[i] = symbols

    def string(self, offset, end=None):
        limit = len(self.data) if end is None else end
        if offset < 0 or offset >= limit:
            raise ValueError("string offset out of bounds")
        nul = self.data.find(b"\0", offset, limit)
        if nul < 0:
            raise ValueError("unterminated string table entry")
        try:
            return self.data[offset:nul].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII string table entry") from exc

    def section(self, name):
        i = self.names.index(name)
        return i, self.sections[i]

    def section_data(self, name):
        _, s = self.section(name)
        if s[1] == 8:
            raise ValueError("SHT_NOBITS section has no file bytes")
        if s[4] + s[5] > len(self.data):
            raise ValueError("section exceeds file bounds")
        return self.data[s[4] : s[4] + s[5]]

    def virtual_data(self, address, length):
        if length < 0:
            raise ValueError("negative virtual_data length")
        for p in self.programs:
            if p[0] == 1 and p[2] <= address and address + length <= p[2] + p[4]:
                offset = p[1] + address - p[2]
                if offset + length > len(self.data):
                    raise ValueError("LOAD segment exceeds file bounds")
                return self.data[offset : offset + length]
        raise ValueError("address is outside file-backed LOAD segments")
