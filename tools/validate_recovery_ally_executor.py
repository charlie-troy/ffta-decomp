"""Synthetic ally executor composition/STOP/policy tests, not gameplay proof."""
from dataclasses import replace
from pathlib import Path
import argparse
import copy
import json

from recovery_ally_executor import AllyCureExecutor
from recovery_ally_confirmation import AllyConfirmationToken
from recovery_ally_target import canonical_facts
from recovery_menu import require, RecoveryStateError
from recovery_executor import RecoveryStopped
from tactics_policy import load_policy_file, SNAPSHOT_SCHEMA2
from validate_recovery_executor import Menu, Probe


class AllyProbe(Probe):
    def __init__(self,menu,units,effect):
        super().__init__(menu)
        self.units=copy.deepcopy(units)
        self.effect=effect
        menu.g=self

    def press(self,mask,**kwargs):
        if mask == 0x10:
            kwargs["stop_check"]()
            require(self.menu.state == "target-overlay", "RIGHT outside overlay")
            self.keys.append(mask)
            for state in ("target-overlay","description","confirmation"):
                self.menu.states[state]=replace(self.menu.states[state],target_tile=(5,10))
            return 5
        return super().press(mask,**kwargs)

    def cont(self):
        if not self.menu.final or self.effect_applied:
            return
        before=self.menu.states["command"]
        mp=85 if self.effect == "unspent" else 79
        hp=492 if self.effect == "wrong-target" else 442
        flags=tuple(0 if row == 9 else flag for row,flag in zip(before.rows,before.enabled))
        self.menu.states["command"]=replace(before,hp=hp,mp=mp,enabled=flags,cursor=0)
        self.menu.state="command"
        caster,target=bytearray(self.units[0x02000080]),bytearray(self.units[0x02000188])
        caster[0x18:0x1A]=hp.to_bytes(2,"little");caster[0x1C:0x1E]=mp.to_bytes(2,"little")
        target[0x18:0x1A]=(100 if self.effect == "wrong-target" else 150).to_bytes(2,"little")
        if self.effect == "target-mp":target[0x1C:0x1E]=(220).to_bytes(2,"little")
        if self.effect == "identity":target[0x104]=7
        self.units.update({0x02000080:bytes(caster),0x02000188:bytes(target)})
        self.effect_applied=True

    def read_mem(self,address,size):
        return self.units[address][:size] if address in self.units else None


class Reader:
    def __init__(self,menu,doc,units):
        self.menu=menu
        self.pins={p["canonical"]:p for p in doc["party_pins"]}
        self.facts={p:canonical_facts(u) for p,u in units.items()}
        self.target=0x02000188

    def snapshot(self):
        require(self.menu.state == "target-overlay" and self.menu.snapshot().target_tile == (5,10), "wrong overlay")
        return self.confirmation_token()

    def revalidate(self,token):
        self.snapshot();return token

    def preview_snapshot(self):
        require(self.menu.state == "description", "wrong preview")
        return self.confirmation_token()

    def revalidate_preview(self,token):
        self.preview_snapshot();return token

    def confirmation_token(self):
        return AllyConfirmationToken(0,0x02000080,self.target,0x0202270C,(5,10),6,"synthetic")

    def confirmation_snapshot(self):
        require(self.menu.state == "confirmation" and self.menu.snapshot().cursor == 0, "wrong final prompt")
        return self.confirmation_token()

    def revalidate_confirmation(self,token):
        require(self.confirmation_snapshot() == token,"stale final token")
        return token

    def policy_snapshot(self,token,clock):
        self.revalidate_confirmation(token)
        return {"schema":SNAPSHOT_SCHEMA2,"identity":"verified","age_seconds":0,
                "actor":{"name":"Marche","id":7,"job_id":5,"side":"player","hp":442,"max_hp":442,
                         "mp":85,"max_mp":85,"tile":[4,10]},
                "candidates":[{"id":"cure-ally","kind":"ability","action_id":1,"legal":True,"cost":6,
                               "ability_name":"Cure","relation":"ally","target":{"kind":"unit","id":5},
                               "target_hp":100,"target_max_hp":241,"target_mp":221}]}


def setup(effect="normal"):
    folder=Path("outputs/autobattle/a62-ally-confirmation-01")
    doc=json.loads((folder/"probe.json").read_text())
    units={p["canonical"]:(folder/f"confirmation-unit-{p['canonical']:08x}.bin").read_bytes() for p in doc["party_pins"]}
    menu=Menu(hp=442)
    menu.owner=doc["owner"]
    probe=AllyProbe(menu,units,effect)
    reader=Reader(menu,doc,units)
    executor=AllyCureExecutor(menu,probe,load_policy_file("configs/tactics/healer.json"),reader,
                             clock=lambda:0,sleep=lambda seconds:None)
    return menu,probe,executor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    checks=[]
    menu,probe,executor=setup()
    result=executor.run()
    assert result["outcome"] == "accepted-effect-only" and result["target_after"]["hp"] == 150
    assert result["after"]["hp"] == 442 and result["after"]["mp"] == 79
    assert len(probe.keys) == 10 and sum(e.get("final",False) for e in executor.events) == 1
    checks.append("ally effect and unchanged caster HP with spent caster MP")
    count=len(probe.keys)
    try:executor.press("A",menu.snapshot())
    except RecoveryStateError:assert len(probe.keys) == count
    else:raise AssertionError("post-final retry")
    checks.append("post-final input rejected")
    for effect in ("wrong-target","unspent","target-mp","identity"):
        menu,probe,executor=setup(effect)
        try:executor.run()
        except RecoveryStateError:checks.append(effect+" rejected after one final input")
        else:raise AssertionError("accepted "+effect)
        assert sum(e.get("final",False) for e in executor.events) == 1
    for boundary in range(10):
        menu,probe,executor=setup()
        executor.stop_check=lambda:len(probe.keys)>=boundary
        try:executor.run()
        except RecoveryStopped:
            assert len(probe.keys)==boundary and not menu.final
            checks.append(f"STOP after {boundary} keys suppresses final/subsequent input")
        else:raise AssertionError("STOP ignored")
    for mode in ("stop","policy-change"):
        menu,probe,executor=setup()
        def callback(observation):
            if mode == "stop":executor.stop_check=lambda:True
            else:executor.policy={"schema":"ffta-tactics-policy/2","fallback":"none","assignments":{}}
        executor.before_policy_final=callback
        try:executor.run()
        except (RecoveryStopped,RecoveryStateError):
            assert not menu.final and len(probe.keys)==9
            checks.append(mode+" after observation prevents final input")
        else:raise AssertionError("observation changed authority")
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"checks":checks},indent=2)+"\n",
                   encoding="utf-8",newline="\n")
    print(f"PASS ally executor composition: {len(checks)} checks")


if __name__=="__main__":main()
