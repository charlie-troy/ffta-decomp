"""Bounded research ally-Cure executor; public self-only runtime is unchanged.

Navigation and final policy use independent target tokens. Final input is
latched before transport and never retried. Wait/continuation are separate.
"""
from dataclasses import asdict

from recovery_executor import SelfCureExecutor
from recovery_menu import exact, integer, require, RecoveryTransient
from recovery_ally_target import canonical_facts
from tactics_policy import evaluate


class AllyCureExecutor(SelfCureExecutor):
    def __init__(self,menu,probe,policy,reader,**kwargs):
        super().__init__(menu,probe,policy,**kwargs)
        self.reader=reader

    def validate_final(self,name,verified):
        require(name == "A" and verified.state == "confirmation" and verified.cursor == 0,
                "final ally input is not Do-it")
        self.reader.confirmation_snapshot()

    def run(self):
        before=self.observe("command")
        require(self.menu.owner["id"] == 7 and self.menu.owner["job"] == 5
                and self.menu.identity[6] == 7, "unsupported ally caster")
        require(self.select("command",9), "Action unavailable")
        require(self.select("action-group",10), "secondary action unavailable")
        require(self.select("ability-list",1,ability=True), "Cure unavailable")
        overlay=self.observe("target-overlay")
        require(overlay.target_tile == (4,10), "initial cursor not caster")
        self.menu.revalidate(overlay)
        self.check_stop()
        hits=self.probe.press(0x10,tag="a62-ally:RIGHT",stop_check=self.check_stop)
        require(hits > 0, "ally cursor input delivery unknown")
        self.after_key("RIGHT")
        token=self.reader.snapshot()
        self.events.append({"event":"ally_overlay","token":asdict(token)})
        self.reader.revalidate(token)
        self.press("A",self.observe("target-overlay"))
        preview=self.reader.preview_snapshot()
        self.events.append({"event":"ally_preview","token":asdict(preview)})
        self.reader.revalidate_preview(preview)
        self.press("A",self.observe("description"))
        final=self.reader.confirmation_snapshot()
        snapshot=self.reader.policy_snapshot(final,clock=self.clock)
        decision=evaluate(snapshot,self.policy)
        self.events.append({"event":"policy","snapshot":snapshot,"evaluation":decision,
                            "target_token":asdict(final)})
        require((decision.get("decision") or {}).get("candidate_id") == "cure-ally",
                "policy declined ally Cure; no final input")
        self.before_policy_final(self.observe("confirmation"))
        self.check_stop()
        final=self.reader.revalidate_confirmation(final)
        final_snapshot=self.reader.policy_snapshot(final,clock=self.clock)
        final_decision=evaluate(final_snapshot,self.policy)
        require((final_decision.get("decision") or {}).get("candidate_id") == "cure-ally",
                "policy changed before ally final input")
        self.events.append({"event":"final_policy","snapshot":final_snapshot,
                            "evaluation":final_decision,"target_token":asdict(final)})
        self.press("A",self.observe("confirmation"),final=True)
        deadline=self.clock()+20
        while self.clock() < deadline:
            self.passive_tick()
            try:obs=self.observe()
            except RecoveryTransient:continue
            if obs.state != "command":
                require(obs.state in ("description","confirmation","settling"), "unknown post-Cure state")
                continue
            units={member:exact(self.menu.g,member,0x108) for member in self.reader.pins}
            for member,unit in units.items():
                current=canonical_facts(unit)
                original=self.reader.facts[member]
                require(all(a == b for i,(a,b) in enumerate(zip(current,original)) if i not in (7,9)),
                        "party identity changed after ally Cure")
            target=units[self.reader.target]
            target_before=self.reader.pins[self.reader.target]
            require(obs.hp == before.hp and obs.mp == before.mp-final.cost
                    and target_before["hp"] < integer(target,0x18,2) <= target_before["max_hp"]
                    and integer(target,0x1C,2) == target_before["mp"], "ally Cure effect/resources differ")
            require(9 in obs.rows and not obs.enabled[obs.rows.index(9)], "caster Action not consumed")
            return {"outcome":"accepted-effect-only","before":before.receipt(),"after":obs.receipt(),
                    "target_before":target_before,"target_after":{"canonical":self.reader.target,
                    "id":target[0x104],"hp":integer(target,0x18,2),"mp":integer(target,0x1C,2)},
                    "decision":decision,"wait":"unexecuted","continuation":"unknown"}
        raise TimeoutError("ally Cure did not settle; final input will not be retried")
