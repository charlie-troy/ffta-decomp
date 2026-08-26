"""Dump the unit stat table: stat id -> struct offset and width.

sub_080C7EA4 dispatches on a stat id through a 69-entry jump table. Each case
is a short stub that either loads one field or returns its address. Reading
every case gives the numeric layout of the unit struct without running the
game; behavior-backed names are overlaid separately below.

Usage:
    python tools/dump_stats.py <rom.gba> [--md]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

TABLE_POOL = 0x0C7EBC
N = 0x45
EXPECTED_POINTERS = (0x09, 0x1C, 0x22, 0x27, 0x38, 0x44)
LOAD = re.compile(r"^(ldrb|ldrh|ldr|ldrsb|ldrsh)$")
MEM = re.compile(r"\[(\w+)(?:,\s*#(0x[0-9a-fA-F]+|\d+)|,\s*\w+)?\]")
IMM = re.compile(r"#(0x[0-9a-fA-F]+|\d+)")

WIDTH = {"ldrb": "u8", "ldrsb": "s8", "ldrh": "u16", "ldrsh": "s16", "ldr": "u32"}
KNOWN = {
    0x01: "unit_type",
    0x02: "base_job_id",
    0x03: "race_id",
    0x04: "active_job_id",
    0x05: "secondary_job_id",
    0x06: "level",
    0x07: "experience",
    0x08: "innate_element_id",
    0x0A: "neutral_resistance",
    0x0B: "fire_resistance",
    0x0C: "wind_resistance",
    0x0D: "earth_resistance",
    0x0E: "water_resistance",
    0x0F: "ice_resistance",
    0x10: "lightning_resistance",
    0x11: "holy_resistance",
    0x12: "dark_resistance",
    0x13: "current_hp",
    0x14: "max_hp",
    0x15: "current_mp",
    0x16: "max_mp",
    0x17: "attack",
    0x18: "defense",
    0x19: "magic_power",
    0x1A: "resistance",
    0x1B: "persistent_status_flags",
    0x1D: "equipped_item_0",
    0x1E: "equipped_item_1",
    0x1F: "equipped_item_2",
    0x20: "equipped_item_3",
    0x21: "equipped_item_4",
    0x23: "charge_time",
    0x24: "speed",
    0x25: "charge_time_carry",
    0x26: "judge_points",
    0x28: "zombie_revive_countdown",
    0x29: "doom_countdown",
    0x2A: "haste_duration",
    0x2B: "slow_duration",
    0x2C: "stop_duration",
    0x2D: "shell_duration",
    0x2E: "protect_duration",
    0x2F: "sleep_duration",
    0x30: "silence_duration",
    0x31: "confuse_duration",
    0x32: "charm_duration",
    0x33: "immobilize_duration",
    0x34: "disable_duration",
    0x35: "addle_duration",
    0x36: "status_link_id",
    0x37: "recent_target_ids",
    0x39: "ko_inflicted_count",
    0x3A: "ko_suffered_count",
    0x3B: "other_removal_count",
    0x3C: "parley_removal_count",
    0x3D: "oust_removal_count",
    0x3E: "tile_x",
    0x3F: "tile_y",
    0x40: "tile_height",
    0x41: "saved_tile_x",
    0x42: "saved_tile_y",
    0x43: "battle_list_index",
    0x09: "elemental_resistance_array",
    0x1C: "equipment_array",
    0x27: "status_state_array",
    0x38: "live_status_flags",
}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    rom = romlib.load(argv[0])
    md = "--md" in argv

    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    table = w(TABLE_POOL) - 0x08000000
    rows = []
    for sid in range(N):
        tgt = (w(table + sid * 4) & ~1) - 0x08000000
        ins = romlib.disasm(rom, tgt, tgt + 16)
        body = []
        for i in ins:
            body.append(i)
            if i.mnemonic == "b":
                break
        off = width = None
        address_off = 0
        for i in body:
            if i.mnemonic == "adds" and i.op_str.startswith("r0, #"):
                m = IMM.search(i.op_str)
                if m:
                    address_off += int(m.group(1), 0)
            if LOAD.match(i.mnemonic):
                m = MEM.search(i.op_str)
                if m:
                    extra = int(m.group(2), 0) if m.group(2) else 0
                    off = (address_off if m.group(1) == "r0" else 0) + extra
                    width = WIDTH.get(i.mnemonic, "?")
                break
        if width is None:
            off, width = address_off, "ptr"
        first = "; ".join(f"{i.mnemonic} {i.op_str}" for i in body[:2])
        rows.append((sid, off, width, first))

    values = sum(1 for r in rows if r[2] != "ptr")
    pointers = len(rows) - values
    pointer_ids = tuple(r[0] for r in rows if r[2] == "ptr")
    if pointer_ids != EXPECTED_POINTERS:
        print(f"ERROR: pointer ids {pointer_ids}, expected {EXPECTED_POINTERS}")
        return 1
    if md:
        print("| stat | offset | width | meaning |")
        print("|---|---|---|---|")
        for sid, off, width, _ in rows:
            print(f"| `{sid:#04x}` | `+{off:#x}` | {width} | "
                  f"{KNOWN.get(sid, '')} |")
    else:
        print(f"{'stat':>5} {'offset':>7} {'w':>4}  first instructions")
        print("-" * 62)
        for sid, off, width, first in rows:
            o = f"+{off:#x}" if off is not None else "-"
            print(f"{sid:>#5x} {o:>7} {width or '-':>4}  {first[:40]}")
        print(f"\n{values} scalar loads; {pointers} address returns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
