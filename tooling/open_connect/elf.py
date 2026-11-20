"""Read little-endian ARM ELF32 metadata for private host validation; no writes or linking."""

import struct


class ELF:
    def __init__(self, data):
        self.data = data
        self.h = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
        if data[:7] != b"\x7fELF\x01\x01\x01" or self.h[2] != 40:
            raise ValueError("requires little-endian ARM ELF32")
        self.sections = [
            struct.unpack_from("<IIIIIIIIII", data, self.h[6] + i * self.h[11])
            for i in range(self.h[12])
        ]
        self.programs = [
            struct.unpack_from("<IIIIIIII", data, self.h[5] + i * self.h[9])
            for i in range(self.h[10])
        ]
        names = self.sections[self.h[13]]
        self.names = [self.string(names[4] + s[0]) for s in self.sections]
        self.symbols = {}
        self.by_table = {}
        for i, s in enumerate(self.sections):
            if s[1] not in (2, 11):
                continue
            strings = self.sections[s[6]]
            symbols = []
            for a in range(s[4], s[4] + s[5], s[9]):
                name, value, size, info, other, index = struct.unpack_from("<IIIBBH", data, a)
                sym = dict(
                    name=self.string(strings[4] + name),
                    value=value,
                    size=size,
                    section=index,
                    info=info,
                )
                symbols.append(sym)
                if sym["name"]:
                    self.symbols[sym["name"]] = sym
            self.by_table[i] = symbols

    def string(self, offset):
        return self.data[offset : self.data.index(b"\0", offset)].decode("ascii")

    def section(self, name):
        i = self.names.index(name)
        return i, self.sections[i]

    def section_data(self, name):
        _, s = self.section(name)
        return self.data[s[4] : s[4] + s[5]]

    def virtual_data(self, address, length):
        for p in self.programs:
            if p[0] == 1 and p[2] <= address and address + length <= p[2] + p[4]:
                offset = p[1] + address - p[2]
                return self.data[offset : offset + length]
        raise ValueError("address is outside file-backed LOAD segments")
