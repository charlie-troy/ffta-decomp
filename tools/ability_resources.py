"""Read effective MP cost using the decoded retail 0812ED98 contract.

Cost alone does not establish learned status, menu availability, or target
legality. This reader is not yet part of the live candidate adapter.
"""
from __future__ import annotations

import ability_table

RACE_TABLE = 0x51BA84


def effective_mp_cost(rom: bytes, ability_id: int, unit: bytes | None) -> int:
    if isinstance(ability_id, bool) or not isinstance(ability_id, int):
        raise ValueError("ability id must be an integer")
    if not 0 <= ability_id < ability_table.COUNT:
        raise ValueError("ability outside decoded table")
    if ability_id == 0:
        return 0
    end = ability_table.BASE + ability_table.COUNT * ability_table.STRIDE
    if len(rom) < end:
        raise ValueError("ROM is shorter than the decoded tables")
    cost = ability_table.read(rom, ability_id, 4, 1)
    if unit is None:
        return cost
    if len(unit) < 0x3C:
        raise ValueError("incomplete unit record")
    support = unit[0x3B]
    if support == 0:
        return cost
    race = unit[6]
    if race > 6:
        raise ValueError("race outside decoded ability-pointer table")
    start = int.from_bytes(rom[RACE_TABLE + race * 4:RACE_TABLE + race * 4 + 4], "little") - 0x08000000
    stop = int.from_bytes(rom[RACE_TABLE + race * 4 + 4:RACE_TABLE + race * 4 + 8], "little") - 0x08000000
    entry = start + support * 8
    if not 0 <= start <= entry or not entry + 8 <= stop <= len(rom):
        raise ValueError("support index outside the race table")
    effect = rom[entry + 4]  # 080CD50C reads the low byte, not the u16.
    if effect == 4:
        return cost * 2
    if effect == 10:
        return (cost + 1) // 2
    return cost
