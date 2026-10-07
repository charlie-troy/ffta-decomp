"""Pinned ally preview reader; authorizes no cast or policy candidate.

The bounded research caller may use a revalidated token only to advance from
the Cure description to the final prompt, then stop and observe.
"""
from dataclasses import dataclass
import hashlib

from fixture_guard import BATTLE_STRUCT, STRIDE
from recovery_menu import exact, integer, require, PLAYER_DRIVER, MEMBERS, MEMBER_COUNT
from recovery_ally_target import AllyOverlayReader, canonical_facts, ACCEPTANCE_CURSOR
from probe_control_handoff import TARGET_X


@dataclass(frozen=True)
class AllyPreviewToken:
    caster: int
    target: int
    target_wrapper: int
    tile: tuple[int, int]
    resource_digest: str


class AllyPreviewReader(AllyOverlayReader):
    def preview_snapshot(self):
        g = self.g
        menu_token = self.menu.snapshot()
        require(menu_token.state == "description" and menu_token.selected_ability == 1
                and menu_token.peer == self.caster, "not the bounded ally description preview")
        require(menu_token.target_state == 10 and menu_token.target_flags == 0x6C
                and integer(exact(g,PLAYER_DRIVER+0x60,4),0) == BATTLE_STRUCT,
                "preview processor state differs")
        header = exact(g,BATTLE_STRUCT,0xA4)
        caster_wrapper, target_wrapper = integer(header,0), integer(header,8)
        require(integer(header,4) == caster_wrapper and target_wrapper != caster_wrapper
                and integer(header,0x50) == target_wrapper and integer(header,0x54) == caster_wrapper
                and header[0xA2] == 2 and header[0xA1] == 0,
                "preview wrapper table differs")
        reads = [(BATTLE_STRUCT,header)]
        for wrapper, member in [(caster_wrapper,self.caster),(target_wrapper,self.target)]:
            data = exact(g,wrapper,0x10)
            require(integer(data,0) == member, "preview wrapper does not join canonical party")
            reads.append((wrapper,data))
        units = {}
        for member in self.pins:
            unit = exact(g,member,STRIDE)
            require(canonical_facts(unit) == self.facts[member], "party changed during preview")
            units[member] = unit
            reads.append((member,unit))
        for i in range(MEMBER_COUNT):
            address = MEMBERS+i*STRIDE
            if address not in self.pins:
                other = exact(g,address,STRIDE)
                require(all(integer(other,0) != p["name"] and other[0x104] != p["id"]
                            for p in self.pins.values()), "canonical party alias appeared in preview")
        display = exact(g,TARGET_X,2)
        x,y = exact(g,ACCEPTANCE_CURSOR,2),exact(g,ACCEPTANCE_CURSOR+4,2)
        committed = exact(g,BATTLE_STRUCT+0x109,2)
        tile = (integer(x,0,2),integer(y,0,2))
        require(tile == tuple(display) == tuple(committed) == tuple(self.pins[self.target]["tile"]),
                "preview coordinate sources disagree")
        reads.extend([(TARGET_X,display),(ACCEPTANCE_CURSOR,x),(ACCEPTANCE_CURSOR+4,y),
                      (BATTLE_STRUCT+0x109,committed)])
        self.menu.revalidate(menu_token)
        require(all(exact(g,a,len(data)) == data for a,data in reads), "preview changed during observation")
        digest = hashlib.sha256(repr(sorted((m,canonical_facts(u)) for m,u in units.items())).encode()).hexdigest()
        return AllyPreviewToken(self.caster,self.target,target_wrapper,tile,digest)

    def revalidate_preview(self,token):
        require(isinstance(token,AllyPreviewToken) and self.preview_snapshot() == token,
                "stale or foreign ally preview token")
        return token
