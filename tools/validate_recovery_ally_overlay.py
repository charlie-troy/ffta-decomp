"""Audit retained overlay observations; this authorizes no target or cast."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from recovery_menu import integer, require, RecoveryStateError


def audit(doc, captures):
    require(doc["status"] == "captured-overlay-only" and doc["inputs_unchanged"], "incomplete overlay")
    require(doc["final_confirmation"] is False, "overlay claims final confirmation")
    require(doc["owner"]["id"] == 7 and doc["owner"]["job"] == 5, "wrong caster")
    writes = doc["raw_writes"]
    require(len(writes) == 35 and all(w["val"] == 0x10 for w in writes[-5:]), "terminal cursor ledger differs")
    require(len(doc["phases"]) == 2, "phase count")
    for phase, cursor in zip(doc["phases"], ([4,10], [5,10])):
        tag = phase["tag"]
        data = captures[f"{tag}-processor.bin"]
        require(len(data) == 0x1120 and integer(data,0xEC,2) == 1
                and integer(data,0x1112,2) == 0 and integer(data,0x1118,2) == 10, "wrong target processor")
        require(phase["cursor"] == cursor and phase["index"] == data[0xA1] == 0
                and phase["count"] == data[0xA2] == 2, "overlay cursor/table differs")
        require(phase["selected_copies"] == [integer(data,12),integer(data,16)] == [0,0], "target already accepted")
        require(len(phase["wrappers"]) == 2, "missing wrapper")
        for i, expected in enumerate([(7,442,[4,10]),(5,100,[5,10])]):
            row = phase["wrappers"][i]
            pointer = integer(data,0x50+4*i)
            require(row["wrapper"] == pointer and (i != 0 or integer(data,0) == pointer), "wrapper table/actor differs")
            wrapper = captures[f"{tag}-wrapper-{pointer:08x}.bin"]
            member = integer(wrapper,0)
            require(member == row["canonical"], "canonical pointer differs")
            unit = captures[f"{tag}-unit-{member:08x}.bin"]
            require((unit[0x104],integer(unit,0x18,2),list(unit[0xF6:0xF8])) == expected, "wrong overlay ally")
            require(row["id"] == unit[0x104] and row["hp"] == integer(unit,0x18,2)
                    and row["tile"] == list(unit[0xF6:0xF8]) and row["name"] == integer(unit,0), "metadata/raw identity differs")
            require(integer(unit,0x28,2)&0x9000 == 0 and unit[7] == 5 and unit[6] == 1, "wrong overlay side/job")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    folder=Path(args.capture); doc=json.loads((folder/"probe.json").read_text())
    captures={p.name:p.read_bytes() for p in folder.glob("*.bin")}
    for name,h in doc["capture_sha256"].items():
        assert hashlib.sha256(captures[name]).hexdigest()==h,name
    for p,h in doc["source_sha256"].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    audit(doc,captures)
    mutants=[]
    for label,change in [
        ("false-cast",lambda d:d.update(final_confirmation=True)),
        ("wrong-caster",lambda d:d["owner"].update(id=5)),
        ("cursor-not-ally",lambda d:d["phases"][1].update(cursor=[4,10])),
        ("index-invented",lambda d:d["phases"][1].update(index=1)),
        ("accepted-wrapper-invented",lambda d:d["phases"][1].update(selected_copies=[1,1])),
        ("ally-alias",lambda d:d["phases"][1]["wrappers"][1].update(id=7)),
        ("missing-raw",lambda d:d.update(raw_writes=[])),
        ("extra-final-input",lambda d:d["raw_writes"].append(copy.deepcopy(d["raw_writes"][-1]))),
    ]:
        changed=copy.deepcopy(doc);change(changed)
        try:audit(changed,captures)
        except (RecoveryStateError,KeyError):mutants.append(label)
        else:raise AssertionError("accepted "+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"mutations_rejected":mutants,
                              "observation":"Cursor reaches ally while index stays0 and selected copies remain empty",
                              "target_acceptance":"unknown"},indent=2)+"\n",encoding="utf-8",newline="\n")
    print("PASS raw overlay joins; 8 rejected mutations; no target/cast acceptance")


if __name__=="__main__":main()
