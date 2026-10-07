"""Replay the retained ally preview reader; no live final-prompt proof."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from fixture_guard import BATTLE_STRUCT
from recovery_menu import MEMBERS, RecoveryStateError
from recovery_ally_target import ACCEPTANCE_CURSOR
from recovery_ally_preview import AllyPreviewReader
from probe_control_handoff import TARGET_X
from validate_recovery_ally_target import Memory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",default="outputs/autobattle/a62-ally-acceptance-01")
    parser.add_argument("--baseline",default="outputs/autobattle/a62-party-fixture-01/reload")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    folder,baseline=Path(args.capture),Path(args.baseline)
    doc=json.loads((folder/"probe.json").read_text())
    pins=doc["party_pins"]
    memory=Memory()
    memory.put(MEMBERS,(baseline/"02000080.bin").read_bytes())
    memory.put(BATTLE_STRUCT,(folder/"selected-processor.bin").read_bytes())
    memory.put(0x0200F548,BATTLE_STRUCT.to_bytes(4,"little"))
    units={}
    for row in doc["phases"][-1]["wrappers"]:
        memory.put(row["wrapper"],(folder/f"selected-wrapper-{row['wrapper']:08x}.bin").read_bytes())
        unit=(folder/f"selected-unit-{row['canonical']:08x}.bin").read_bytes()
        memory.put(row["canonical"],unit);units[row["canonical"]]=unit
    memory.put(TARGET_X,bytes([5,10]))
    memory.put(ACCEPTANCE_CURSOR,(5).to_bytes(2,"little"))
    memory.put(ACCEPTANCE_CURSOR+4,(10).to_bytes(2,"little"))
    facts=SimpleNamespace(state="description",selected_ability=1,peer=0x02000080,
                          target_state=10,target_flags=0x6C)
    menu=SimpleNamespace(owner={"id":7},member=0x02000080,snapshot=lambda:facts,revalidate=lambda token:token)
    reader=AllyPreviewReader(memory,menu,pins,units)
    token=reader.preview_snapshot();reader.revalidate_preview(token)
    assert token.target==0x02000188 and token.target_wrapper==0x0202270C
    rejected=[]
    for label,address,data in [
        ("caster-wrapper",BATTLE_STRUCT,(0x0202270C).to_bytes(4,"little")),
        ("caster-copy",BATTLE_STRUCT+4,bytes(4)),
        ("target-copy",BATTLE_STRUCT+8,(0x0202267C).to_bytes(4,"little")),
        ("target-table",BATTLE_STRUCT+0x50,(0x0202267C).to_bytes(4,"little")),
        ("target-count",BATTLE_STRUCT+0xA2,bytes([1])),
        ("target-index",BATTLE_STRUCT+0xA1,bytes([1])),
        ("committed-coordinates",BATTLE_STRUCT+0x109,bytes([4,10])),
        ("display-coordinates",TARGET_X,bytes([4,10])),
        ("acceptance-coordinates",ACCEPTANCE_CURSOR,(4).to_bytes(2,"little")),
        ("target-canonical",0x0202270C,(0x02000080).to_bytes(4,"little")),
        ("target-hp",0x02000188+0x18,(101).to_bytes(2,"little")),
        ("caster-mp",0x02000080+0x1C,(79).to_bytes(2,"little")),
    ]:
        class Changed:
            def read_mem(self,base,size):
                prior=memory.read_mem(base,size)
                if prior is None:return None
                result=bytearray(prior)
                lo,hi=max(base,address),min(base+size,address+len(data))
                if lo<hi:result[lo-base:hi-base]=data[lo-address:hi-address]
                return bytes(result)
        mutant=AllyPreviewReader(Changed(),menu,pins,units)
        try:mutant.revalidate_preview(token)
        except RecoveryStateError:rejected.append(label)
        else:raise AssertionError("accepted "+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"rejected":rejected,
                              "final_prompt":"unknown"},indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"PASS ally preview reader; {len(rejected)} rejected mutations")


if __name__=="__main__":main()
