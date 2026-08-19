"""Find every direct job-table getter and the offset it reads.

A getter is recognisable as an idiom: multiply an index by the 0x34 stride,
add the table base from a literal pool, add a constant offset, load a byte.
Scanning for it ROM-wide finds readers that no accessor field id covers, which
is what the remaining unnamed offsets need.
"""
import os
import re
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
TABLE = 0x08521A14
END = 0x360000
rom = open(ROM, "rb").read()


def pool_at(addr):
    """Value of the pc-relative literal a `ldr rX, [pc, #n]` refers to."""
    return None


found = []
# Walk instruction-aligned windows; the idiom is short and never crosses far.
for off in range(0, END, 2):
    h = int.from_bytes(rom[off:off + 2], "little")
    # movs rX, #0x34
    if (h & 0xF800) != 0x2000 or (h & 0xFF) != 0x34:
        continue
    ins = romlib.disasm(rom, off, min(off + 28, END))
    if len(ins) < 5:
        continue
    txt = [(i.mnemonic, i.op_str, i.address) for i in ins]
    if not any(m == "muls" for m, _, _ in txt[:3]):
        continue
    # the literal pool load that follows must be the table base
    base_ok = False
    for m, o, a in txt[:6]:
        if m == "ldr" and "pc" in o:
            mo = re.search(r"#(0x[0-9a-fA-F]+|\d+)", o)
            if not mo:
                continue
            # disasm reports addresses based at 0x08000000; rom is indexed
            # by file offset, so drop the base before reading the pool word.
            p = (((a + 4) & ~3) + int(mo.group(1), 0)) - 0x08000000
            if int.from_bytes(rom[p:p + 4], "little") == TABLE:
                base_ok = True
            break
    if not base_ok:
        continue
    # the constant offset added before the load
    field = 0
    load = None
    for m, o, a in txt:
        if m == "adds" and re.match(r"^r\d+, #", o):
            field = int(re.search(r"#(0x[0-9a-fA-F]+|\d+)", o).group(1), 0)
        if m in ("ldrb", "ldrh", "ldr", "ldrsb", "ldrsh") and "pc" not in o:
            mo = re.search(r"\[(\w+)(?:,\s*#(0x[0-9a-fA-F]+|\d+))?\]", o)
            if mo:
                load = (m, int(mo.group(2), 0) if mo.group(2) else 0)
                break
    if load is None:
        continue
    total = field + load[1]
    found.append((0x08000000 + off, total, load[0]))

byoff = collections.defaultdict(list)
for addr, o, w in found:
    byoff[o].append((addr, w))

UNNAMED = {0x02, 0x06, 0x09, 0x0a, 0x0c, 0x0f, 0x2c, 0x31, 0x33}
print(f"direct job-table getters found: {len(found)}\n")
print(f"{'offset':>7} {'n':>3}  width  getter start(s)")
print("-" * 66)
for o in sorted(byoff):
    sites = byoff[o]
    mark = "  <-- unnamed" if o in UNNAMED else ""
    print(f"  {o:#05x} {len(sites):>3}  {sites[0][1]:<5}  " +
          " ".join(f"{a:#010x}" for a, _ in sites[:4]) + mark)

with open("build/job_getters.json", "w", newline="\n") as fh:
    json.dump({hex(o): [hex(a) for a, _ in v] for o, v in sorted(byoff.items())},
              fh, indent=1)
print("\nwrote build/job_getters.json")
