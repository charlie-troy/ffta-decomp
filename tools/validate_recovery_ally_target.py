"""Derived ally-overlay reader controls; not live target-selection proof."""
import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from fixture_guard import BATTLE_STRUCT
from recovery_menu import MEMBERS, RecoveryStateError
from recovery_ally_target import AllyOverlayReader, ACCEPTANCE_CURSOR
from probe_control_handoff import TARGET_X


class Memory:
    def __init__(self):
        self.regions = []

    def put(self, address, data):
        self.regions.append((address, bytes(data)))

    def read_mem(self, address, size):
        for base, data in reversed(self.regions):
            if base <= address and address + size <= base + len(data):
                return data[address-base:address-base+size]
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", default="outputs/autobattle/a62-ally-overlay-01")
    parser.add_argument("--baseline", default="outputs/autobattle/a62-party-fixture-01/reload")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    overlay, baseline = Path(args.overlay), Path(args.baseline)
    pins = json.loads((baseline/"baseline.json").read_text())["party"]
    doc = json.loads((overlay/"probe.json").read_text())
    memory = Memory()
    memory.put(MEMBERS, (baseline/"02000080.bin").read_bytes())
    memory.put(BATTLE_STRUCT, (overlay/"after-processor.bin").read_bytes())
    memory.put(0x0200F548, BATTLE_STRUCT.to_bytes(4,"little"))
    units = {}
    for row in doc["phases"][1]["wrappers"]:
        memory.put(row["wrapper"], (overlay/f"after-wrapper-{row['wrapper']:08x}.bin").read_bytes())
        unit = (overlay/f"after-unit-{row['canonical']:08x}.bin").read_bytes()
        memory.put(row["canonical"],unit)
        units[row["canonical"]] = unit
    memory.put(TARGET_X,bytes([5,10]))
    # The acceptance-coordinate agreement is DERIVED, absent from this live capture.
    memory.put(ACCEPTANCE_CURSOR,(5).to_bytes(2,"little"))
    memory.put(ACCEPTANCE_CURSOR+4,(10).to_bytes(2,"little"))
    facts = SimpleNamespace(state="target-overlay",selected_ability=1,peer=0x02000080,
                            target_state=10,target_flags=0)
    menu = SimpleNamespace(owner={"id":7},member=0x02000080,snapshot=lambda:facts,revalidate=lambda token:token)
    reader = AllyOverlayReader(memory,menu,pins,units)
    original = reader.snapshot()
    assert original.target_id == 5 and original.index == 0 and original.tile == (5,10)
    reader.revalidate(original)
    rejected = []
    for label,address,data in [
        ("display-cursor-drift",TARGET_X,bytes([4,10])),
        ("acceptance-x-drift",ACCEPTANCE_CURSOR,(4).to_bytes(2,"little")),
        ("acceptance-y-drift",ACCEPTANCE_CURSOR+4,(9).to_bytes(2,"little")),
        ("missing-processor",0x0200F548,bytes(4)),
        ("target-count",BATTLE_STRUCT+0xA2,bytes([3])),
        ("target-index",BATTLE_STRUCT+0xA1,bytes([2])),
        ("accepted-copies",BATTLE_STRUCT+12,(0x0202270C).to_bytes(4,"little")),
        ("wrapper-alias",BATTLE_STRUCT+0x54,(0x0202267C).to_bytes(4,"little")),
        ("ally-ko",0x02000188+0x18,bytes(2)),
        ("ally-cross-side",0x02000188+0x28,bytes([0,128])),
        ("ally-stale-hp",0x02000188+0x18,(101).to_bytes(2,"little")),
        ("caster-stale-mp",0x02000080+0x1C,(79).to_bytes(2,"little")),
        ("ally-id",0x02000188+0x104,bytes([7])),
        ("target-wrapper-foreign",0x0202270C,(0x02000290).to_bytes(4,"little")),
    ]:
        changed=copy.deepcopy(memory);changed.put(address,data)
        # Mutations override subranges just like live memory.
        class Changed:
            def read_mem(self,base,size):
                prior=memory.read_mem(base,size)
                if prior is None:return None
                result=bytearray(prior)
                lo,hi=max(base,address),min(base+size,address+len(data))
                if lo<hi:result[lo-base:hi-base]=data[lo-address:hi-address]
                return bytes(result)
        mutant=AllyOverlayReader(Changed(),menu,pins,units)
        try:mutant.revalidate(original)
        except RecoveryStateError:rejected.append(label)
        else:raise AssertionError("accepted "+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"rejected":rejected,
                              "derived_acceptance_coordinates":[5,10],"live_agreement":"unknown"},indent=2)+"\n",
                   encoding="utf-8",newline="\n")
    print(f"PASS derived ally overlay token; {len(rejected)} rejected mutations")


if __name__=="__main__":main()
