"""Retained final-prompt joins; this is not a cast or policy-candidate receipt."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from recovery_menu import CONFIRM, RecoveryStateError, integer, require
from validate_recovery_ally_acceptance import audit as audit_selection


def audit(doc,captures):
    require(doc["status"] == "captured-final-prompt-only" and doc["inputs_unchanged"], "incomplete final prompt")
    require(doc["description_advance_requested"] is True and doc["description_advance_delivered"] is True,
            "missing description advance")
    require(len(doc["raw_writes"]) == 45 and all(w["val"] == 1 for w in doc["raw_writes"][-5:]),
            "description terminal ledger differs")
    previous=copy.deepcopy(doc)
    previous.update(status="captured-target-selection-only",phases=previous["phases"][:3],raw_writes=previous["raw_writes"][:40])
    audit_selection(previous,captures)
    require(len(doc["phases"]) == 4 and not doc["final_confirmation"], "false cast claim")
    phase=doc["phases"][-1]
    data=captures["confirmation-processor.bin"]
    root,callback=captures["confirmation-root.bin"],captures["confirmation-callback.bin"]
    require(root[4] == phase["root_mode"] == 11 and integer(callback,0) == phase["handler"] == CONFIRM
            and integer(callback,0x14,2) == phase["controller_state"] == 0x102, "wrong final prompt")
    require(integer(data,0xEC,2) == 1 and integer(data,0x1118,2) == phase["target_state"] == 2
            and integer(data,0x1112,2) == phase["target_flags"] == 0x20, "wrong confirmation processor")
    require(integer(data,0) == integer(data,4) == integer(data,12) == 0x0202267C
            and integer(data,8) == 0x0202270C and integer(data,16) == 0, "confirmation actor/target pointers differ")
    require(integer(root,0x18) == integer(root,0x1C) == 0x02000080, "cached peer incorrectly treated as ally")
    require(phase["cursor"] == phase["acceptance_coordinates"] == [5,10]
            and list(data[0x109:0x10B]) == [5,10], "final target coordinates differ")
    for member in (0x02000080,0x02000188):
        before=captures[f"after-unit-{member:08x}.bin"]
        after=captures[f"confirmation-unit-{member:08x}.bin"]
        require(after[0x18:0x20] == before[0x18:0x20], "final prompt changed resources")
    require(integer(captures["confirmation-wrapper-0202270c.bin"],0) == 0x02000188,
            "confirmation target canonical join differs")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    folder=Path(args.capture);doc=json.loads((folder/"probe.json").read_text())
    captures={p.name:p.read_bytes() for p in folder.glob("*.bin")}
    for name,digest in doc["capture_sha256"].items():assert hashlib.sha256(captures[name]).hexdigest()==digest,name
    for path,digest in doc["source_sha256"].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    audit(doc,captures)
    rejected=[]
    for label,change in [
        ("false-cast",lambda d:d.update(final_confirmation=True)),
        ("wrong-prompt-mode",lambda d:d["phases"][-1].update(root_mode=12)),
        ("wrong-target-state",lambda d:d["phases"][-1].update(target_state=10)),
        ("wrong-target-flags",lambda d:d["phases"][-1].update(target_flags=0x6C)),
        ("wrong-cursor",lambda d:d["phases"][-1].update(cursor=[4,10])),
        ("extra-final-input",lambda d:d["raw_writes"].append(copy.deepcopy(d["raw_writes"][-1]))),
        ("missing-advance",lambda d:d.update(description_advance_delivered=False)),
        ("missing-final-prompt",lambda d:d.update(phases=d["phases"][:3])),
    ]:
        changed=copy.deepcopy(doc);change(changed)
        try:audit(changed,captures)
        except (RecoveryStateError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError("accepted "+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"mutations_rejected":rejected,
                              "final_cursor":"not retained in callback header; revalidate live before candidate",
                              "cast":"unknown"},indent=2)+"\n",encoding="utf-8",newline="\n")
    print("PASS ally final-prompt joins; 8 rejected mutations; no cast proof")


if __name__=="__main__":main()
