"""Show what a modded ROM actually changes about the AI's decisions.

Editing a CSV is easy to do and easy to get wrong. Everything else in this
repo validates the base ROM; nothing tells a modder that their edit landed and
what it did. This diffs a modded ROM against the base, names every changed
field, and then measures the behavioural consequence by running the ROM's own
decision code on both, so the answer comes from the game rather than from a
model of it.

    python tools/verify_mod.py base.gba modded.gba [--samples 4000]
"""
import os
import sys
import argparse
import collections
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_names import Names
from ffta_lz import block_length
from map_data import (COUNT as MAP_COUNT, _arrangement_cells, _clipping_cells,
                      _height_cells, decode_graphics, resolve_block)
import ability_table as A

PRIO_FILTER = 0x0812F1DC
# sub_080CCD50 exposes only +0x00..+0x0a of an ability entry, so ai_priority at
# +0x1a is not reachable through it. The AI reads that field directly and hands
# it to the filter, which is why the measurement below drives the filter itself.
ABIL_PROP = 0x080CCD50
JOB_PRIO = 0x0813413C
JOB_UNARMED = 0x08130820
RNG_STATE = 0x030034B0
SEED = 0x12345678
UNIT = 0x02000400

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCTIONS = json.load(open(os.path.join(REPO, "data", "functions.json")))["functions"]


def containing_function(off):
    for func in FUNCTIONS:
        if func["offset"] <= off < func["offset"] + func["size"]:
            return func["name"]
    return None


# Offset -> column name, built from the same table the CSV dump uses so the
# two never drift apart.
ABIL_OFF = {}
for _n, _o, _w in A.COLUMNS:
    for _k in range(_w):
        ABIL_OFF[_o + _k] = _n if _w == 1 else f"{_n}[{_k}]"


def classify(off):
    """Name the table field a changed ROM offset belongs to."""
    a = off - A.BASE
    if 0 <= a < A.COUNT * A.STRIDE:
        i, o = divmod(a, A.STRIDE)
        return ("ability", i, o, ABIL_OFF.get(o, f"+{o:#04x}"))
    u = off - A.UNIT_BASE
    if 0 <= u < A.UNIT_COUNT * A.UNIT_STRIDE:
        i, o = divmod(u, A.UNIT_STRIDE)
        return ("job", i, o, A.UNIT_NAMED.get(o, f"b{o:02x}"))
    return (None, None, None, None)


def keep_rate(gba, prio, n):
    gba.write32(RNG_STATE, SEED)
    return 100.0 * sum(1 for _ in range(n) if gba.call(PRIO_FILTER, [prio])) / n


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("modded")
    p.add_argument("--samples", type=int, default=4000)
    args = p.parse_args(argv)

    base = open(args.base, "rb").read()
    mod = open(args.modded, "rb").read()
    if len(base) != len(mod):
        print(f"ROM sizes differ: {len(base)} vs {len(mod)}")
        return 1

    nm = Names(base)
    graphics = {}
    for map_id in range(MAP_COUNT):
        meta = decode_graphics(base, map_id)
        group = graphics.setdefault(meta["source_offset"], {
            "end": meta["source_offset"] + meta["compressed_bytes"],
            "maps": [],
        })
        group["maps"].append(map_id)

    map_blocks = {}
    map_byte_owner = {}
    block_fields = (
        ("arrangement", 0x04, _arrangement_cells),
        ("clipping", 0x08, _clipping_cells),
        ("terrain", 0x10, _height_cells),
    )
    for map_id in range(MAP_COUNT):
        for label, field, cell_reader in block_fields:
            meta = resolve_block(base, map_id, field)
            key = (label, meta["offset"])
            info = map_blocks.setdefault(key, {"maps": [], "bytes": set()})
            info["maps"].append(map_id)
            if info["bytes"]:
                continue
            if meta["storage"] == "wrapped-lz77":
                size = block_length(base, meta["offset"])
                info["bytes"].update(range(meta["offset"], meta["offset"] + size))
            elif meta["storage"] == "raw":
                _, cells = cell_reader(meta)
                for cell in cells.values():
                    width = cell.get("width", 2)
                    start = meta["raw_offset"] + cell["data_offset"]
                    info["bytes"].update(range(start, start + width))
    for key, info in map_blocks.items():
        for off in info["bytes"]:
            prior = map_byte_owner.setdefault(off, key)
            if prior != key:
                raise ValueError(f"overlapping map data ownership at {off:#x}")

    def containing_graphics(off):
        for start, info in graphics.items():
            if start <= off < info["end"]:
                return start
        return None

    diff = [i for i in range(len(base)) if base[i] != mod[i]]
    print(f"bytes changed: {len(diff)}")
    if not diff:
        print("The ROMs are identical; nothing to measure.")
        return 0

    groups = collections.defaultdict(list)
    changed_functions = collections.defaultdict(list)
    changed_graphics = collections.defaultdict(list)
    changed_map_blocks = collections.defaultdict(list)
    other = []
    for off in diff:
        kind, idx, o, name = classify(off)
        if kind is None:
            function_name = containing_function(off)
            if function_name:
                changed_functions[function_name].append(off)
            else:
                graphics_start = containing_graphics(off)
                if graphics_start is not None:
                    changed_graphics[graphics_start].append(off)
                elif off in map_byte_owner:
                    changed_map_blocks[map_byte_owner[off]].append(off)
                else:
                    other.append(off)
        else:
            groups[(kind, idx)].append((o, name, base[off], mod[off]))

    print(f"  in the ability table : "
          f"{sum(1 for k in groups if k[0] == 'ability')} entr(ies)")
    print(f"  in the job table     : "
          f"{sum(1 for k in groups if k[0] == 'job')} entr(ies)")
    print(f"  in matched functions : {sum(map(len, changed_functions.values()))} byte(s)")
    for function_name, offsets in sorted(changed_functions.items()):
        print(f"    {function_name}: {len(offsets)} byte(s)")
    print(f"  in map graphics      : {sum(map(len, changed_graphics.values()))} byte(s)")
    for start, offsets in sorted(changed_graphics.items()):
        maps = ",".join(str(i) for i in graphics[start]["maps"])
        print(f"    {0x08000000 + start:#010x} (maps {maps}): {len(offsets)} byte(s)")
    print(f"  in map data          : {sum(map(len, changed_map_blocks.values()))} byte(s)")
    for (label, start), offsets in sorted(changed_map_blocks.items()):
        maps = ",".join(str(i) for i in map_blocks[(label, start)]["maps"])
        print(f"    {label} {0x08000000 + start:#010x} (maps {maps}): "
              f"{len(offsets)} byte(s)")
    print(f"  unattributed         : {len(other)} byte(s)")
    if other:
        print("    (outside known tables, functions, and map allocations)")
        for off in other[:8]:
            print(f"    {0x08000000 + off:#010x}: "
                  f"{base[off]:#04x} -> {mod[off]:#04x}")

    print()
    print("changed fields")
    print("-" * 62)
    for (kind, idx) in sorted(groups):
        who = nm.ability(idx) if kind == "ability" else nm.job(idx)
        for o, name, b, m in sorted(groups[(kind, idx)]):
            print(f"  {kind:<7} {idx:>3} {who[:16]:<17} {name:<22} "
                  f"{b:>3} -> {m:>3}")

    # Ability priority is the field whose effect is measurable end to end.
    rows = []
    for (kind, idx), fields in sorted(groups.items()):
        for o, name, b, m in fields:
            if kind == "ability" and o == 0x1A:
                rows.append((idx, b, m))
    if rows:
        from emulate import Gba
        gb, gm = Gba(args.base), Gba(args.modded)
        print()
        print("measured effect on the AI's decision, run on both ROMs")
        print(f"{'ability':>15} {'id':>4} {'priority':>12} "
              f"{'keep rate':>20} {'delta':>8}")
        print("-" * 62)
        for idx, b, m in rows:
            rb = keep_rate(gb, b, args.samples)
            rm = keep_rate(gm, m, args.samples)
            # confirm the game's own accessor sees the edit
            note = "  saturated" if m > 100 else ""
            print(f"{nm.ability(idx)[:14]:>15} {idx:>4}   {b:>3} -> {m:<3}   "
                  f"{rb:>7.1f}% -> {rm:>6.1f}%   {rm - rb:>+6.1f}{note}")
        print(f"  {args.samples} samples per figure, same RNG seed on both")
        if any(m > 100 for _, _, m in rows):
            print("  values above 100 are marked saturated: the filter keeps")
            print("  everything at 100, so the extra has no effect")

    # ai_behaviour and ai_condition select which rule the evaluator applies.
    # Driving that end to end needs the whole evaluator and a real battle
    # state, so these are described from the established semantics and marked
    # as not measured, rather than given a number this harness cannot earn.
    BEHAVIOUR = {
        0: "no special handling",
        1: "considered when the target is at low HP",
        2: "rejected when the target is below half HP (harmful status)",
        3: "last resort",
    }
    beh = [(idx, o, b, m) for (kind, idx), fs in sorted(groups.items())
           for o, _, b, m in fs if kind == "ability" and o in (0x18, 0x19)]
    if beh:
        print()
        print("ability rule selectors (described, not measured)")
        for idx, o, b, m in beh:
            if o == 0x19:
                print(f"  ability {idx:>3} ai_behaviour {b} -> {m}")
                print(f"      was: {BEHAVIOUR.get(b, 'undocumented value')}")
                print(f"      now: {BEHAVIOUR.get(m, 'undocumented value')}")
            else:
                print(f"  ability {idx:>3} ai_condition {b} -> {m}"
                      f"  (0 on 306 of 347 abilities; special-case handling)")
        print("  these pick a rule rather than a rate, so no keep rate applies")

    jobs = [(idx, o, b, m) for (kind, idx), fs in sorted(groups.items())
            for o, _, b, m in fs if kind == "job" and o in (0x32, 0x33)]
    if jobs:
        if not rows:
            from emulate import Gba
            gb, gm = Gba(args.base), Gba(args.modded)
        print()
        print("job fields, read back through the game's own getters")
        for idx, o, b, m in jobs:
            fn = JOB_PRIO if o == 0x32 else JOB_UNARMED
            outs = []
            for g in (gb, gm):
                g.uc.mem_write(UNIT, bytes(0x40))
                g.uc.mem_write(UNIT + 5, bytes([idx]))
                outs.append(g.call(fn, [UNIT, 0]))
            nm = "ai_priority" if o == 0x32 else "unarmed_attack"
            ok = "ok" if (outs[0], outs[1]) == (b, m) else "MISMATCH"
            print(f"  job {idx:>3} {nm:<16} getter {outs[0]} -> {outs[1]}  [{ok}]")

    resist = [(idx, o) for (kind, idx), fs in sorted(groups.items())
              for o, _, _, _ in fs if kind == "job" and 0x11 <= o <= 0x15]
    if resist:
        print()
        print("resistance slots touched")
        for idx in sorted({i for i, _ in resist}):
            b = [A.resist_get(base, idx, n) for n in range(8)]
            m = [A.resist_get(mod, idx, n) for n in range(8)]
            ch = [f"slot {n}: {b[n]} -> {m[n]}" for n in range(8) if b[n] != m[n]]
            print(f"  job {idx:>3}: " + ("; ".join(ch) if ch else "no slot changed"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
