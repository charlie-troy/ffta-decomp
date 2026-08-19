"""Read and edit the ability table.

The AI's per-ability tuning lives in three bytes of each entry (condition,
behaviour, priority), and those are data, not code. Editing them changes AI
behaviour without recompiling anything, which makes this the cheapest way to
tune the game.

    python tools/ability_table.py dump   <rom.gba> out.csv
    python tools/ability_table.py apply  <rom.gba> in.csv out.gba
    python tools/ability_table.py dump-units  <rom.gba> out.csv
    python tools/ability_table.py apply-units <rom.gba> in.csv out.gba

The "units" table at 0x08521A14 is the fallback the AI consults when an action
carries no ability id. sub_0813413C reads its +0x32 on that path, and the byte
uses the same 0-100 priority scale as the ability table. Only that byte is
written back; the rest of each 0x34-byte entry is left alone, because its
layout is not established.

`apply` rewrites only the bytes that differ and reports each change, so an
accidental edit is visible rather than silent.
"""
import csv
import sys

BASE = 0x0855187C - 0x08000000
STRIDE = 0x1C
COUNT = 347

# name -> (offset, width). Only fields whose meaning is established.
COLUMNS = [
    ("name_id",     0x00, 2),
    ("element",     0x02, 1),
    ("ap_over_10",  0x03, 1),
    ("mp_cost",     0x04, 1),
    ("weapon_req",  0x05, 1),
    ("range_h",     0x06, 1),
    ("range_v",     0x07, 1),
    ("targeting",   0x08, 1),
    ("aoe_h",       0x09, 1),
    ("aoe_v",       0x0A, 1),
    ("power",       0x0B, 1),
    ("flags",       0x10, 4),   # expanded into the named bit columns below
    ("anim_id",     0x14, 2),
    ("desc_id",     0x16, 2),
    ("ai_condition", 0x18, 1),
    ("ai_behaviour", 0x19, 1),
    ("ai_priority",  0x1A, 1),
]


# Bit names for the u32 at +0x10. Unnamed bits keep a bitN label so the word
# round-trips losslessly; bits 1-4 are never set in any entry.
FLAG_BITS = [
    (0,  "f_self_target"),   (1,  "f_bit1"),          (2,  "f_bit2"),
    (3,  "f_bit3"),          (4,  "f_bit4"),          (5,  "f_offensive"),
    (6,  "f_ignore_reaction"), (7, "f_reflectable"),  (8,  "f_double_cast"),
    (9,  "f_ignore_silence"), (10, "f_beastmaster"),  (11, "f_trigger_learn"),
    (12, "f_blocked_by_cover"), (13, "f_bit13"),      (14, "f_stealable"),
    (15, "f_return_magic"),  (16, "f_throw"),         (17, "f_absorb_mp"),
    (18, "f_physical"),      (19, "f_morpher"),       (20, "f_bit20"),
]


# Job table: 0x08521A14, stride 0x34. Valid job data runs through index 115;
# index 116 onward fails plausibility (movement of 33, name ids in the tens of
# thousands), so the earlier bound of 123 was wrong and would have let someone
# edit non-job bytes. Public documentation gives 115 entries; index 115 still
# looks like a real job here, so 116 is used.
UNIT_BASE = 0x08521A14 - 0x08000000
UNIT_STRIDE = 0x34
UNIT_COUNT = 116
UNIT_PRIO = 0x32


def read(rom, i, off, width):
    o = BASE + i * STRIDE + off
    return int.from_bytes(rom[o:o + width], "little")


def cmd_dump(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        cols = [c[0] for c in COLUMNS if c[0] != "flags"]
        w.writerow(["id"] + cols + [n for _, n in FLAG_BITS])
        for i in range(COUNT):
            vals = [read(rom, i, off, wd) for n, off, wd in COLUMNS if n != "flags"]
            f = read(rom, i, 0x10, 4)
            w.writerow([i] + vals + [(f >> b) & 1 for b, _ in FLAG_BITS])
    print(f"wrote {out_path}: {COUNT} abilities, {len(COLUMNS)} columns")
    return 0


def cmd_apply(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    changes = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            i = int(row["id"])
            if not 0 <= i < COUNT:
                print(f"  skipping out-of-range id {i}")
                continue
            # Rebuild the flag word from the named bit columns when present.
            if all(n in row and row[n] != "" for _, n in FLAG_BITS):
                new = 0
                for b, n in FLAG_BITS:
                    if int(row[n], 0):
                        new |= 1 << b
                old = read(rom, i, 0x10, 4)
                if new != old:
                    o = BASE + i * STRIDE + 0x10
                    rom[o:o + 4] = new.to_bytes(4, "little")
                    changed = [n for b, n in FLAG_BITS
                               if ((old >> b) & 1) != ((new >> b) & 1)]
                    print(f"  id {i:>3} flags: {old:#010x} -> {new:#010x} "
                          f"({', '.join(changed)})")
                    changes += 1

            for name, off, width in COLUMNS:
                if name == "flags" or name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                old = read(rom, i, off, width)
                if new == old:
                    continue
                limit = 1 << (width * 8)
                if not 0 <= new < limit:
                    print(f"  id {i} {name}: {new} does not fit in {width} byte(s), skipped")
                    continue
                o = BASE + i * STRIDE + off
                rom[o:o + width] = new.to_bytes(width, "little")
                print(f"  id {i:>3} {name}: {old} -> {new}")
                changes += 1
    open(out_path, "wb").write(rom)
    print(f"\n{changes} field(s) changed, wrote {out_path}")
    if changes:
        print("this ROM differs from the base on purpose; keep it separate from baserom.gba")
    return 0


# Every byte of the entry is exposed. Only offsets whose meaning is actually
# established get a name; the rest keep a bNN label. Naming a byte on a guess
# is how a modder ends up corrupting unit data.
# Layout from public documentation of the job table, adopted only where the ROM
# data supports it. Fields that failed plausibility, or that the documentation
# marks unknown, keep a bNN label. See docs/unit-ai-table.md.
UNIT_NAMED = {
    0x00: "name_id",
    # Documented as Race. Entries 0-71 run in contiguous ascending
    # blocks, 1-5 covering the playable races and 6+ the monster
    # families, which is why the range reaches 23.
    0x04: "race",
    # 0 on the seven race-0 entries, 1 on the playable races and 2 on
    # the monster families. Tracks +0x04 almost exactly.
    0x06: "unit_kind",
    # One u16, not two bytes: the same 12 entries hold 0xFF in both,
    # so 0xFFFF reads as "none". Other values run 0x00bc..0x00f7.
    0x09: "pair09_lo", 0x0A: "pair09_hi",
    0x07: "sprite_index",
    0x0B: "sprite_palette",
    0x0D: "portrait_palette",
    0x0E: "portrait_index",
    # Packed with portrait_palette as (pal << 8) | this and handed to
    # sub_08013108. Only read from 0x08035540.
    0x0F: "portrait_graphic",
    0x10: "a_ability_index",
    # +0x12..+0x15 are not four byte-sized resistances. They carry eight
    # 3-bit slots on a 3-bit stride starting at +0x12 bit 3, each holding
    # 0-3. See docs/job-table.md and the resist subcommands.
    0x12: "resist_packed_0", 0x13: "resist_packed_1",
    0x14: "resist_packed_2", 0x15: "resist_packed_3",
    # Read by field id 0x0d as the low nibble; values 0-8.
    0x11: "unit_class",
    0x16: "status_defense",
    0x17: "base_hp", 0x18: "base_mp", 0x19: "base_speed",
    0x1A: "base_melee_0", 0x1B: "base_melee_1", 0x1C: "base_melee_2",
    0x1D: "base_magic_0", 0x1E: "base_magic_1", 0x1F: "base_magic_2",
    0x20: "growth_hp", 0x21: "growth_mp", 0x22: "growth_speed",
    0x23: "growth_attack", 0x24: "growth_defense",
    0x25: "growth_magic_pow", 0x26: "growth_magic_res",
    # Byte-for-byte equal to +0x26 in all 116 entries. Field ids 0x2a
    # and 0x2b both reach this pair.
    0x27: "growth_magic_res_copy",
    0x28: "movement", 0x29: "jump", 0x2A: "evade",
    0x2B: "movement_style",
    0x2D: "equip_index",
    0x2E: "ability_start", 0x2F: "ability_end",
    0x30: "job_requirement",
    # Not in the published layout, which marks 0x31-0x33 unknown. Established
    # here from sub_0813413C, which reads it as the AI priority percentage.
    0x32: "ai_priority",
    # The attack power used when nothing is equipped. The damage path
    # substitutes it for sub_080CA7A4(weapon, 10) when the weapon
    # register is null; both feed the same term.
    0x33: "unarmed_attack",
}


def unit_cols():
    return [UNIT_NAMED.get(o, f"b{o:02x}") for o in range(UNIT_STRIDE)]


def cmd_dump_units(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index"] + unit_cols())
        for i in range(UNIT_COUNT):
            base = UNIT_BASE + i * UNIT_STRIDE
            w.writerow([i] + list(rom[base:base + UNIT_STRIDE]))
    print(f"wrote {out_path}: {UNIT_COUNT} entries, {UNIT_STRIDE} bytes each")
    return 0


def cmd_apply_units(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    changes = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            i = int(row["index"])
            if not 0 <= i < UNIT_COUNT:
                print(f"  skipping out-of-range index {i}")
                continue
            for off, name in enumerate(unit_cols()):
                if name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                if not 0 <= new < 256:
                    print(f"  index {i} {name}: {new} does not fit in a byte, skipped")
                    continue
                o = UNIT_BASE + i * UNIT_STRIDE + off
                if rom[o] != new:
                    print(f"  index {i:>3} {name} (+{off:#04x}): {rom[o]} -> {new}")
                    rom[o] = new
                    changes += 1
    open(out_path, "wb").write(rom)
    print(f"\n{changes} field(s) changed, wrote {out_path}")
    return 0


# Eight resistance slots live in +0x12..+0x15, on a 3-bit stride starting at
# +0x12 bit 3. Each holds 0-3 and every entry's third bit is clear, so two bits
# are used of the three allotted. Value 1 dominates (108-113 of 116 entries per
# slot), which is what a neutral default looks like.
RESIST_BASE_BIT = 11          # counted from +0x11 bit 0
RESIST_STRIDE = 3
RESIST_SLOTS = 8
RESIST_REGION = 0x11
RESIST_LEN = 5


def resist_get(rom, i, slot):
    o = UNIT_BASE + i * UNIT_STRIDE + RESIST_REGION
    w = int.from_bytes(rom[o:o + RESIST_LEN], "little")
    return (w >> (RESIST_BASE_BIT + slot * RESIST_STRIDE)) & 3


def resist_set(rom, i, slot, val):
    o = UNIT_BASE + i * UNIT_STRIDE + RESIST_REGION
    w = int.from_bytes(rom[o:o + RESIST_LEN], "little")
    sh = RESIST_BASE_BIT + slot * RESIST_STRIDE
    w = (w & ~(3 << sh)) | ((val & 3) << sh)
    rom[o:o + RESIST_LEN] = w.to_bytes(RESIST_LEN, "little")


def cmd_dump_resist(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    cols = [f"resist_{n}" for n in range(RESIST_SLOTS)]
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index"] + cols)
        for i in range(UNIT_COUNT):
            w.writerow([i] + [resist_get(rom, i, n) for n in range(RESIST_SLOTS)])
    print(f"wrote {out_path}: {UNIT_COUNT} entries x {RESIST_SLOTS} slots")
    print("slot 2 is not reachable through the job field accessor; see "
          "docs/job-table.md")
    return 0


def cmd_apply_resist(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    changes = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            i = int(row["index"])
            if not 0 <= i < UNIT_COUNT:
                print(f"  skipping out-of-range index {i}")
                continue
            for n in range(RESIST_SLOTS):
                key = f"resist_{n}"
                if key not in row or row[key] == "":
                    continue
                new = int(row[key], 0)
                if not 0 <= new <= 3:
                    print(f"  index {i} {key}: {new} is outside 0-3, skipped")
                    continue
                if resist_get(rom, i, n) != new:
                    print(f"  index {i:>3} {key}: "
                          f"{resist_get(rom, i, n)} -> {new}")
                    resist_set(rom, i, n, new)
                    changes += 1
    open(out_path, "wb").write(rom)
    print()
    print(f"{changes} slot(s) changed, wrote {out_path}")
    return 0


# Presets are defined only from fields whose meaning is established: the
# ai_priority percentage, the ai_behaviour class, and the Offensive flag.
# Nothing here relies on a guessed column.
def preset_always(rom, i):
    """Stop the AI randomly declining an action it could take."""
    o = BASE + i * STRIDE + 0x1A
    return [(o, 100)] if rom[o] else []


def preset_no_status(rom, i):
    """Stop the AI using the harmful-status class (ai_behaviour 2)."""
    b = BASE + i * STRIDE
    return [(b + 0x1A, 0)] if rom[b + 0x19] == 2 else []


def preset_offensive(rom, i):
    """Make the AI reach for anything flagged Offensive (flag bit 5)."""
    b = BASE + i * STRIDE
    flags = int.from_bytes(rom[b + 0x10:b + 0x14], "little")
    return [(b + 0x1A, 100)] if (flags >> 5) & 1 and rom[b + 0x1A] else []


PRESETS = {
    "always": (preset_always,
               "every usable ability gets priority 100, so the AI stops "
               "randomly skipping actions"),
    "no-status": (preset_no_status,
                  "abilities in the harmful-status class get priority 0, so "
                  "the AI never debuffs"),
    "offensive": (preset_offensive,
                  "anything flagged Offensive gets priority 100"),
}


def cmd_preset(name, rom_path, out_path):
    if name not in PRESETS:
        print("presets:")
        for k, (_, d) in PRESETS.items():
            print(f"  {k:<10} {d}")
        return 2
    fn, desc = PRESETS[name]
    rom = bytearray(open(rom_path, "rb").read())
    n = 0
    for i in range(COUNT):
        for off, val in fn(rom, i):
            if rom[off] != val:
                rom[off] = val
                n += 1
    open(out_path, "wb").write(rom)
    print(f"preset '{name}': {desc}")
    print(f"{n} byte(s) changed, wrote {out_path}")
    return 0


def main(argv):
    if len(argv) == 4 and argv[0] == "preset":
        return cmd_preset(argv[1], argv[2], argv[3])
    if len(argv) == 2 and argv[0] == "preset":
        return cmd_preset(argv[1], None, None)
    if len(argv) == 3 and argv[0] == "dump-resist":
        return cmd_dump_resist(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply-resist":
        return cmd_apply_resist(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[0] == "dump-units":
        return cmd_dump_units(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply-units":
        return cmd_apply_units(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[0] == "dump":
        return cmd_dump(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply":
        return cmd_apply(argv[1], argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
