"""Read-only final ally-Cure candidate facts for bounded A6.2 research.

Only the engine-owned Do-it prompt can supply a candidate. No input or policy
decision lives in this reader; callers must revalidate after observations.
"""
from dataclasses import dataclass
import hashlib
import time

from fixture_guard import BATTLE_STRUCT, STRIDE
from recovery_menu import exact, integer, require, PLAYER_DRIVER, MEMBERS, MEMBER_COUNT
from recovery_ally_preview import AllyPreviewReader
from recovery_ally_target import canonical_facts, ACCEPTANCE_CURSOR
from probe_control_handoff import TARGET_X
from tactics_policy import SNAPSHOT_SCHEMA2


@dataclass(frozen=True)
class AllyConfirmationToken:
    observed_at: float
    caster: int
    target: int
    target_wrapper: int
    tile: tuple[int, int]
    cost: int
    resource_digest: str


class AllyConfirmationReader(AllyPreviewReader):
    def confirmation_snapshot(self):
        g = self.g
        obs = self.menu.snapshot()
        require(obs.state == "confirmation" and obs.cursor == 0 and obs.selected_ability == 1
                and obs.peer == self.caster and obs.target_state == 2 and obs.target_flags == 0x20,
                "not the engine-owned ally Do-it prompt")
        require(obs.cure_cost == 6 and obs.mp >= obs.cure_cost, "unsupported or unaffordable Cure cost")
        require(integer(exact(g,PLAYER_DRIVER+0x60,4),0) == BATTLE_STRUCT, "confirmation allocation differs")
        header = exact(g,BATTLE_STRUCT,0xA4)
        caster_wrapper,target_wrapper = integer(header,0),integer(header,8)
        require(integer(header,4) == integer(header,12) == caster_wrapper
                and integer(header,16) == 0 and target_wrapper != caster_wrapper
                and integer(header,0x50) == target_wrapper and integer(header,0x54) == caster_wrapper
                and header[0xA2] == 2 and header[0xA1] == 0, "confirmation target table differs")
        reads = [(BATTLE_STRUCT,header)]
        for wrapper,member in [(caster_wrapper,self.caster),(target_wrapper,self.target)]:
            data = exact(g,wrapper,0x10)
            require(integer(data,0) == member, "confirmation wrapper/canonical join differs")
            reads.append((wrapper,data))
        units = {}
        for member in self.pins:
            unit = exact(g,member,STRIDE)
            require(canonical_facts(unit) == self.facts[member], "party changed before final candidate")
            units[member] = unit
            reads.append((member,unit))
        for i in range(MEMBER_COUNT):
            address = MEMBERS+i*STRIDE
            if address not in self.pins:
                other = exact(g,address,STRIDE)
                require(all(integer(other,0) != p["name"] and other[0x104] != p["id"]
                            for p in self.pins.values()), "canonical party alias at final prompt")
        display = exact(g,TARGET_X,2)
        x,y = exact(g,ACCEPTANCE_CURSOR,2),exact(g,ACCEPTANCE_CURSOR+4,2)
        committed = exact(g,BATTLE_STRUCT+0x109,2)
        tile = (integer(x,0,2),integer(y,0,2))
        require(tile == tuple(display) == tuple(committed) == tuple(self.pins[self.target]["tile"])
                and tile != tuple(self.pins[self.caster]["tile"]), "final target coordinate disagreement")
        reads.extend([(TARGET_X,display),(ACCEPTANCE_CURSOR,x),(ACCEPTANCE_CURSOR+4,y),
                      (BATTLE_STRUCT+0x109,committed)])
        self.menu.revalidate(obs)
        require(all(exact(g,a,len(data)) == data for a,data in reads), "final target changed during observation")
        digest = hashlib.sha256(repr(sorted((m,canonical_facts(u)) for m,u in units.items())).encode()).hexdigest()
        return AllyConfirmationToken(obs.observed_at,self.caster,self.target,target_wrapper,tile,obs.cure_cost,digest)

    def revalidate_confirmation(self,token):
        require(isinstance(token,AllyConfirmationToken), "foreign final target token")
        current = self.confirmation_snapshot()
        require(current.__dict__ | {"observed_at":token.observed_at} == token.__dict__, "stale final target token")
        return current

    def policy_snapshot(self,token,clock=time.monotonic):
        require(isinstance(token,AllyConfirmationToken), "foreign policy target token")
        token = self.revalidate_confirmation(token)
        caster,target = self.pins[self.caster],self.pins[self.target]
        return {"schema":SNAPSHOT_SCHEMA2,"identity":"verified",
                "age_seconds":max(0,clock()-token.observed_at),
                "actor":{"name":caster["name_text"],"id":caster["id"],"job_id":caster["job"],
                         "side":"player","hp":caster["hp"],"max_hp":caster["max_hp"],
                         "mp":caster["mp"],"max_mp":caster["max_mp"],"tile":caster["tile"]},
                "candidates":[{"id":"cure-ally","kind":"ability","action_id":1,"legal":True,
                               "cost":token.cost,"ability_name":"Cure","relation":"ally",
                               "target":{"kind":"unit","id":target["id"]},"target_hp":target["hp"],
                               "target_max_hp":target["max_hp"],"target_mp":target["mp"]}]}
