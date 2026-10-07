"""Read-only continuation attribution for the seven-unit self-Cure fixture.

Caller owns an explicit debugger halt. A changed wrapper or CT alone cannot
certify continuation: join the active canonical unit to the restored battle
roster and its own cursor, while preserving the completed player's resources.
No input, polling, transport control, or roster-guard relaxation lives here.
"""
from __future__ import annotations

from fixture_guard import read_roster, STRIDE, ROSTER, SIDE_BIT, UNAFFILIATED_BIT
from recovery_menu import exact, integer, require, PLAYER_DRIVER


def observe_continuation(g, rom, owner, facing):
    roster = read_roster(g, rom=rom)
    rows = [r for r in roster["slots"] if r["live"]]
    require(roster["struct_count"] == roster["live_count"] == 7
            and roster["ids_distinct"] and roster["live_contiguous"]
            and {r["id"] for r in rows} == set(range(7)), "continuation roster not restored")
    driver = exact(g, PLAYER_DRIVER, 0x64)
    wrapper = integer(driver, 4)
    require(wrapper == integer(driver, 8) and wrapper != facing["actor_wrapper"],
            "continuation actor has not changed coherently")
    member = integer(exact(g, wrapper, 4), 0)
    require(member != facing["member"], "continuation still names completed player")
    unit = exact(g, member, STRIDE)
    matches = [r for r in rows if r["name"] == integer(unit, 0) and r["id"] == unit[0x104]]
    require(len(matches) == 1, "continuation actor missing or ambiguous in battle roster")
    row = matches[0]
    for field, offset, size in [("type", 4, 1), ("base_job", 5, 1), ("race", 6, 1),
                                ("job", 7, 1), ("level", 9, 1), ("hp", 0x18, 2),
                                ("max_hp", 0x1A, 2), ("mp", 0x1C, 2), ("max_mp", 0x1E, 2),
                                ("side_raw", 0x28, 2)]:
        require(row[field] == integer(unit, offset, size), "canonical/battle continuation identity differs")
    tile = list(exact(g, ROSTER + STRIDE * row["slot"] + 0xF6, 2))
    require(tile == list(unit[0xF6:0xF8]) == list(exact(g, 0x0200FFC9, 2)),
            "continuation actor/cursor tile not coherent")
    require(row["side_raw"] & SIDE_BIT and not row["side_raw"] & UNAFFILIATED_BIT
            and row["id"] != owner["id"] and row["type"] in (1, 2)
            and row["job"] in range(116) and row["base_job"] in range(116)
            and 1 <= row["race"] <= 8 and 1 <= row["level"] <= 50
            and 0 < row["hp"] <= row["max_hp"] <= 999
            and 0 <= row["mp"] <= row["max_mp"] <= 999
            and all(0 <= v < 64 for v in tile), "continuation enemy outside verified bounds")
    own_rows = [r for r in rows if r["name"] == owner["name"] and r["id"] == owner["id"]]
    require(len(own_rows) == 1, "completed player missing or ambiguous")
    own = own_rows[0]
    own_tile = list(exact(g, ROSTER + STRIDE * own["slot"] + 0xF6, 2))
    canonical = exact(g, facing["member"], STRIDE)
    require(own["hp"] == integer(canonical, 0x18, 2) == facing["hp"]
            and own["mp"] == integer(canonical, 0x1C, 2) == facing["mp"]
            and own_tile == list(canonical[0xF6:0xF8]) == [owner["x"], owner["y"]],
            "completed player resources/tile changed")
    for field in ("type", "base_job", "race", "job", "level", "name", "id", "side_bit", "unaffiliated"):
        require(own[field] == owner[field], "completed player identity changed")
    require(integer(canonical, 0) == owner["name"] and canonical[0x104] == owner["id"],
            "completed canonical player identity changed")
    return {"source": "canonical driver / restored roster / own cursor",
            "wrapper": wrapper, "canonical": member,
            "driver_state": integer(exact(g, PLAYER_DRIVER + 0xDC, 2), 0, 2),
            "actor": row | {"tile": tile}, "target_tile": tile,
            "player_after": own | {"x": own_tile[0], "y": own_tile[1]}}
