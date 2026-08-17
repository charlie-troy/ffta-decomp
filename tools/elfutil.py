"""Minimal ELF32 little-endian reader for verifying agbcc objects.

Only enough to pull .text out of a relocatable object and apply R_ARM_ABS32
relocations, which is what a function referencing a global needs before its
bytes can be compared against the ROM.
"""
import re
import struct

SHT_SYMTAB = 2
SHT_REL = 9
R_ARM_ABS32 = 2

SYM_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9a-fA-F]+)\s*;")


def load_symbols(path):
    """Parse data/symbols.txt into {name: address}."""
    out = {}
    with open(path) as fh:
        for line in fh:
            m = SYM_RE.match(line)
            if m:
                out[m.group(1)] = int(m.group(2), 0)
    return out


class Elf:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        d = self.data
        if d[:4] != b"\x7fELF":
            raise ValueError(f"not an ELF file: {path}")
        self.shoff = struct.unpack_from("<I", d, 0x20)[0]
        self.shentsize = struct.unpack_from("<H", d, 0x2E)[0]
        self.shnum = struct.unpack_from("<H", d, 0x30)[0]
        self.shstrndx = struct.unpack_from("<H", d, 0x32)[0]
        self.sections = [self._section(i) for i in range(self.shnum)]
        stroff = self.sections[self.shstrndx]["offset"]
        for s in self.sections:
            end = d.index(b"\x00", stroff + s["name_off"])
            s["name"] = d[stroff + s["name_off"]:end].decode("ascii", "replace")

    def _section(self, i):
        off = self.shoff + i * self.shentsize
        (name_off, stype, _flags, _addr, offset, size,
         link, info, _align, entsize) = struct.unpack_from("<10I", self.data, off)
        return {"name_off": name_off, "type": stype, "offset": offset,
                "size": size, "link": link, "info": info, "entsize": entsize}

    def by_name(self, name):
        for s in self.sections:
            if s.get("name") == name:
                return s
        return None

    def symbol_names(self, symtab):
        """Return a list of symbol names indexed by symbol table index."""
        strtab = self.sections[symtab["link"]]
        names = []
        count = symtab["size"] // 16
        for i in range(count):
            off = symtab["offset"] + i * 16
            name_off = struct.unpack_from("<I", self.data, off)[0]
            base = strtab["offset"] + name_off
            end = self.data.index(b"\x00", base)
            names.append(self.data[base:end].decode("ascii", "replace"))
        return names

    def text_relocated(self, symaddrs):
        """Return .text with R_ARM_ABS32 relocations applied.

        Returns (bytes, unresolved) where unresolved lists any symbol whose
        address is not known.
        """
        text = self.by_name(".text")
        if text is None:
            return None, []
        out = bytearray(self.data[text["offset"]:text["offset"] + text["size"]])

        rel = self.by_name(".rel.text")
        if rel is None:
            return bytes(out), []

        symtab = None
        for s in self.sections:
            if s["type"] == SHT_SYMTAB:
                symtab = s
                break
        if symtab is None:
            return bytes(out), []
        names = self.symbol_names(symtab)

        unresolved = []
        count = rel["size"] // 8
        for i in range(count):
            off = rel["offset"] + i * 8
            r_offset, r_info = struct.unpack_from("<II", self.data, off)
            rtype = r_info & 0xFF
            sym = r_info >> 8
            if rtype != R_ARM_ABS32:
                continue
            name = names[sym] if sym < len(names) else ""
            if name not in symaddrs:
                unresolved.append(name)
                continue
            addend = struct.unpack_from("<I", out, r_offset)[0]
            value = (addend + symaddrs[name]) & 0xFFFFFFFF
            struct.pack_into("<I", out, r_offset, value)

        return bytes(out), unresolved
