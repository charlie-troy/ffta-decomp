"""Find call sites of the job-table accessor and recover the constant field id.

sub_080C8570(index, ?, fieldId). The field id is in r2, so a call site that
uses a constant sets it with `movs r2, #imm` shortly before the BL. Grouping
call sites by field id says which code cares about which field, which is how a
numbered offset acquires a meaning.
"""
import os
import re
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
ACC = 0x080C8570
WINDOW = 12          # instructions to look back for the r2 set

rom = open(ROM, "rb").read()

# Thumb BL is a pair of halfwords; decode every aligned pair targeting ACC.
sites = []
for off in range(0, 0x360000, 2):
    h1 = int.from_bytes(rom[off:off + 2], "little")
    h2 = int.from_bytes(rom[off + 2:off + 4], "little")
    if (h1 & 0xF800) != 0xF000 or (h2 & 0xF800) != 0xF800:
        continue
    hi = h1 & 0x7FF
    if hi & 0x400:
        hi -= 0x800
    target = (0x08000000 + off + 4) + (hi << 12) + ((h2 & 0x7FF) << 1)
    if target == ACC:
        sites.append(0x08000000 + off)

print(f"call sites of sub_080C8570: {len(sites)}")

byfield = collections.defaultdict(list)
unknown = []
for site in sites:
    start = max(0, site - 0x08000000 - WINDOW * 2)
    ins = romlib.disasm(rom, start, site - 0x08000000)
    fid = None
    for i in reversed(ins):
        if re.match(r"^(movs?|mov)$", i.mnemonic) and i.op_str.startswith("r2,"):
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", i.op_str)
            if m:
                fid = int(m.group(1), 0)
            break
        if i.mnemonic in ("bl", "blx"):
            break
    if fid is None:
        unknown.append(site)
    else:
        byfield[fid].append(site)

print(f"  resolved to a constant field id: {sum(len(v) for v in byfield.values())}")
print(f"  field id not a nearby constant : {len(unknown)}\n")

print(f"{'field':>6} {'sites':>6}  call sites")
print("-" * 66)
for fid in sorted(byfield):
    s = byfield[fid]
    print(f"  {fid:#04x} {len(s):>6}  " +
          " ".join(f"{a:#010x}" for a in s[:6]) +
          ("  ..." if len(s) > 6 else ""))

with open("build/field_callers.json", "w", newline="\n") as fh:
    json.dump({hex(k): [hex(a) for a in v] for k, v in sorted(byfield.items())},
              fh, indent=1)
print("\nwrote build/field_callers.json")
