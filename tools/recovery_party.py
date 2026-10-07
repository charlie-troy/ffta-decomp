"""Pure pre-targeting party joins for the bounded A6.2 research fixture.

This identifies two living canonical allies while the battle mirror is still
valid. It grants no menu input and makes no claim about modal target fields.
"""
import hashlib

from fixture_guard import STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, integer, require


def pin_party(roster, members, rows, read_name):
    require(len(roster) == 8 * STRIDE and len(members) == MEMBER_COUNT * STRIDE,
            "short party baseline")
    require(len(rows) == 2 and {r["id"] for r in rows} == {5, 7}
            and len({r["name"] for r in rows}) == 2, "unexpected or aliased party")
    require({roster[i * STRIDE + 0x104] for i in range(8)} == set(range(8)),
            "battle identities differ from eight-unit fixture")
    pins = []
    for row in rows:
        require(type(row["slot"]) is int and row["slot"] in range(8), "party slot bounds")
        mirror = roster[row["slot"] * STRIDE:(row["slot"] + 1) * STRIDE]
        require(integer(mirror, 0) == row["name"] and mirror[0x104] == row["id"],
                "battle row no longer belongs to party identity")
        units = [(MEMBERS + i * STRIDE, members[i * STRIDE:(i + 1) * STRIDE])
                 for i in range(MEMBER_COUNT)]
        matches = [(a, u) for a, u in units if integer(u, 0) == row["name"] and u[0x104] == row["id"]]
        require(len(matches) == 1, "canonical party identity missing or ambiguous")
        address, unit = matches[0]
        require(sum(integer(u, 0) == row["name"] for _, u in units) == 1
                and sum(u[0x104] == row["id"] for _, u in units) == 1,
                "canonical party name or id alias")
        offsets = [(0, 4), (4, 6), (0x18, 8), (0x28, 2), (0xF6, 2), (0x104, 1)]
        require(all(unit[o:o+n] == mirror[o:o+n] for o, n in offsets),
                "canonical party and battle mirror differ")
        hp, max_hp, mp, max_mp = [integer(unit, o, 2) for o in (0x18, 0x1A, 0x1C, 0x1E)]
        require(0 < hp <= max_hp <= 999 and 0 <= mp <= max_mp <= 999, "party resource bounds")
        require(integer(unit, 0x28, 2) & 0x9000 == 0 and unit[4] != 20
                and unit[7] == 5 and unit[6] == 1, "party side/job/race differs")
        require(all(v < 64 for v in unit[0xF6:0xF8]), "party tile bounds")
        name = read_name(row["name"])
        require(len(name) == 32, "short party name read")
        pins.append({"canonical": address, "name": row["name"], "name_text": row["name_text"],
                     "id": row["id"], "slot": row["slot"], "job": unit[7], "race": unit[6],
                     "secondary_job": unit[8], "hp": hp, "max_hp": max_hp, "mp": mp,
                     "max_mp": max_mp, "tile": list(unit[0xF6:0xF8]),
                     "name_sha256": hashlib.sha256(name).hexdigest()})
    require(len({tuple(p["tile"]) for p in pins}) == 2, "party tile alias")
    return pins
