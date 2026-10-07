"""Read-only pre-acceptance ally overlay token for the A6.2 research fixture.

The token permits only the research target-selection step. It is not a legal
policy candidate and cannot authorize a final Cure confirmation.
"""
from dataclasses import dataclass
import hashlib

from fixture_guard import BATTLE_STRUCT, STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, PLAYER_DRIVER, exact, integer, require
from probe_control_handoff import TARGET_X

ACCEPTANCE_CURSOR = 0x0200F3B8


@dataclass(frozen=True)
class AllyOverlayToken:
    caster: int
    target: int
    target_id: int
    target_wrapper: int
    tile: tuple[int, int]
    index: int
    table: tuple[int, ...]
    resource_digest: str


def canonical_facts(unit):
    return (integer(unit, 0), *unit[4:10], integer(unit, 0x18, 2),
            integer(unit, 0x1A, 2), integer(unit, 0x1C, 2), integer(unit, 0x1E, 2),
            integer(unit, 0x28, 2), unit[0x3B], unit[0xF6], unit[0xF7], unit[0x104])


class AllyOverlayReader:
    def __init__(self, g, menu, pins, units):
        require({p["id"] for p in pins} == {5, 7} and menu.owner["id"] == 7,
                "ally overlay fixture differs")
        self.g, self.menu = g, menu
        self.pins = {p["canonical"]: dict(p) for p in pins}
        self.facts = {address: canonical_facts(unit) for address, unit in units.items()}
        require(set(self.pins) == set(self.facts), "missing canonical baseline")
        self.caster = next(p["canonical"] for p in pins if p["id"] == 7)
        self.target = next(p["canonical"] for p in pins if p["id"] == 5)
        require(menu.member == self.caster, "menu caster differs from party pin")

    def snapshot(self):
        g = self.g
        menu_token = self.menu.snapshot()
        require(menu_token.state == "target-overlay" and menu_token.selected_ability == 1
                and menu_token.peer == self.caster, "not the pre-acceptance Cure overlay")
        processor = integer(exact(g, PLAYER_DRIVER + 0x60, 4), 0)
        require(processor == BATTLE_STRUCT and menu_token.target_state == 10
                and menu_token.target_flags == 0, "overlay processor differs")
        header = exact(g, processor, 0xA4)
        require(header[0xA2] == 2 and header[0xA1] < 2, "overlay target list bounds")
        require(integer(header, 12) == integer(header, 16) == 0,
                "overlay already has accepted target copies")
        table = tuple(integer(header, 0x50 + 4*i) for i in range(2))
        require(len(set(table)) == 2, "target wrapper alias")
        reads = [(processor, header)]
        wrappers = {}
        for pointer in table:
            wrapper = exact(g, pointer, 0x10)
            member = integer(wrapper, 0)
            require(member in self.pins and member not in wrappers, "target canonical alias or foreign unit")
            wrappers[member] = pointer
            reads.append((pointer, wrapper))
        require(set(wrappers) == set(self.pins) and integer(header, 0) == wrappers[self.caster],
                "target table does not join pinned party/caster")
        units = {}
        for member, pin in self.pins.items():
            unit = exact(g, member, STRIDE)
            require(canonical_facts(unit) == self.facts[member], "pinned party changed before target acceptance")
            require(integer(unit, 0x28, 2) & 0x9000 == 0 and integer(unit, 0x18, 2) > 0,
                    "target party is not living player side")
            units[member] = unit
            reads.append((member, unit))
        for i in range(MEMBER_COUNT):
            member = MEMBERS + i*STRIDE
            if member not in self.pins:
                other = exact(g, member, STRIDE)
                require(all(integer(other, 0) != p["name"] and other[0x104] != p["id"]
                            for p in self.pins.values()), "canonical party alias appeared")
        display = exact(g, TARGET_X, 2)
        x = exact(g, ACCEPTANCE_CURSOR, 2)
        y = exact(g, ACCEPTANCE_CURSOR + 4, 2)
        tile = (integer(x, 0, 2), integer(y, 0, 2))
        require(tile == tuple(display) == tuple(self.pins[self.target]["tile"]),
                "display/acceptance/canonical target tile disagreement")
        require(tile != tuple(self.pins[self.caster]["tile"]), "ally target aliases caster tile")
        reads.extend([(TARGET_X, display), (ACCEPTANCE_CURSOR, x), (ACCEPTANCE_CURSOR + 4, y)])
        self.menu.revalidate(menu_token)
        require(all(exact(g, address, len(data)) == data for address, data in reads),
                "ally overlay changed during observation")
        digest = hashlib.sha256(repr(sorted((m, canonical_facts(u)) for m,u in units.items())).encode()).hexdigest()
        return AllyOverlayToken(self.caster, self.target, self.pins[self.target]["id"],
                                wrappers[self.target], tile, header[0xA1], table, digest)

    def revalidate(self, token):
        require(isinstance(token, AllyOverlayToken) and self.snapshot() == token,
                "stale or foreign ally overlay token")
        return token
