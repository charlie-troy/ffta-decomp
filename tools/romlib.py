"""Shared ROM analysis helpers for the FFTA decomp.

Function discovery works from call sites: every Thumb BL in the ROM is resolved
to its target, and targets reached from several places that also decode cleanly
as ARMv4T are real functions. Scanning linearly for `push {..., lr}` instead
finds mostly graphics data and is how ROM maps end up full of ghosts.
"""
import collections

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
import thumb

BASE = 0x08000000
DEFAULT_SCAN_END = 0xA3A000

_md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def load(path):
    with open(path, "rb") as f:
        return f.read()


def halfword(rom, off):
    return rom[off] | (rom[off + 1] << 8)


def discover_calls(rom, scan_end=DEFAULT_SCAN_END):
    """Map every BL target that opens with `push {..., lr}` to its call sites."""
    callers = collections.defaultdict(set)
    for o in range(0, scan_end - 4, 2):
        if (halfword(rom, o) & 0xF800) != 0xF000:
            continue
        if (halfword(rom, o + 2) & 0xF800) != 0xF800:
            continue
        tgt = thumb.bl_target(o, halfword(rom, o), halfword(rom, o + 2))
        if 0 <= tgt < scan_end and tgt % 2 == 0:
            if (halfword(rom, tgt) & 0xFF00) == 0xB500:
                callers[tgt].add(o)
    return callers


def disasm(rom, start, end):
    return list(_md.disasm(rom[start:end], BASE + start))


def shape(insns):
    """Canonical form of a function: mnemonics only, constants dropped.

    Two functions with the same shape differ only in struct offsets, immediates
    and registers, so one parameterised C template can cover the whole cluster.
    """
    return "|".join(i.mnemonic for i in insns)


def discover_functions(rom, min_callers=2, max_bytes=64, leaf_only=True,
                       scan_end=DEFAULT_SCAN_END, callers=None):
    """Return a list of function records sorted by size."""
    if callers is None:
        callers = discover_calls(rom, scan_end)

    out = []
    for start, sites in callers.items():
        if len(sites) < min_callers:
            continue
        res = thumb.find_extent(rom, start, max_bytes=max_bytes)
        if res is None:
            continue
        end, is_leaf = res
        if leaf_only and not is_leaf:
            continue
        insns = disasm(rom, start, end)
        if len(insns) * 2 != end - start:
            continue                      # capstone disagreed; treat as suspect
        out.append({
            "offset": start,
            "addr": BASE + start,
            "size": end - start,
            "callers": len(sites),
            "name": f"sub_{BASE + start:08X}",
            "bytes": rom[start:end].hex(),
            "insns": insns,
            "shape": shape(insns),
        })

    out.sort(key=lambda f: (f["size"], -f["callers"]))
    return out


def format_function(f, indent="    "):
    lines = [f"{f['name']}  ({f['addr']:#010x}, file {f['offset']:#08x})  "
             f"{f['size']} bytes  {f['callers']} callers"]
    for i in f["insns"]:
        raw = " ".join(f"{b:02x}" for b in i.bytes)
        lines.append(f"{indent}{i.address:08x}  {raw:<6} {i.mnemonic:<8} {i.op_str}")
    return "\n".join(lines)
