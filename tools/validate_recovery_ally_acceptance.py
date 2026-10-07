"""Retained raw joins for ally selection into preview; no final cast proof."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from recovery_menu import DESCRIPTION, RecoveryStateError, integer, require
from validate_recovery_ally_overlay import audit as audit_overlay


def audit(doc, captures):
    require(doc["status"] == "captured-target-selection-only" and doc["inputs_unchanged"], "incomplete selection")
    require(doc["target_selection_requested"] is True and doc["target_selection_delivered"] is True,
            "missing target-selection delivery")
    require(len(doc["raw_writes"]) == 40 and all(w["val"] == 1 for w in doc["raw_writes"][-5:]),
            "selection terminal ledger differs")
    prior = copy.deepcopy(doc)
    prior.update(status="captured-overlay-only", phases=prior["phases"][:2], raw_writes=prior["raw_writes"][:35])
    audit_overlay(prior, captures)
    require(len(doc["phases"]) == 3 and not doc["final_confirmation"], "selection falsely claims cast")
    token = doc["ally_overlay_token"]
    require(token["target_id"] == 5 and token["target"] == 0x02000188
            and token["target_wrapper"] == 0x0202270C and token["tile"] == [5,10], "wrong pre-selection ally token")
    for phase in doc["phases"]:
        require(phase["cursor"] == phase["acceptance_coordinates"], "coordinate sources disagree")
    selected = doc["phases"][-1]
    processor = captures["selected-processor.bin"]
    root, callback = captures["selected-root.bin"], captures["selected-callback.bin"]
    require(integer(processor,0) == integer(processor,4) == 0x0202267C
            and integer(processor,8) == token["target_wrapper"], "preview actor/target wrappers differ")
    require(integer(processor,0x50) == token["target_wrapper"] and processor[0xA2] == 2,
            "preview target not first in reordered table")
    require(integer(processor,0xEC,2) == 1 and integer(processor,0x1118,2) == 10
            and integer(processor,0x1112,2) == 0x6C, "preview processor differs")
    require(root[4] == selected["root_mode"] == 12 and integer(callback,0) == selected["handler"] == DESCRIPTION
            and integer(callback,0x14,2) == selected["controller_state"] == 0x102, "wrong preview callback")
    require(integer(root,0x18) == integer(root,0x1C) == 0x02000080,
            "cached peer incorrectly upgraded to ally target")
    for member in (0x02000080,0x02000188):
        before = captures[f"after-unit-{member:08x}.bin"]
        after = captures[f"selected-unit-{member:08x}.bin"]
        require(after[0x18:0x20] == before[0x18:0x20], "selection changed resources")
    wrapper = captures["selected-wrapper-0202270c.bin"]
    require(integer(wrapper,0) == token["target"], "selected wrapper does not join canonical ally")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    folder=Path(args.capture)
    doc=json.loads((folder/"probe.json").read_text())
    captures={p.name:p.read_bytes() for p in folder.glob("*.bin")}
    for name,digest in doc["capture_sha256"].items():
        assert hashlib.sha256(captures[name]).hexdigest()==digest,name
    for path,digest in doc["source_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    audit(doc,captures)
    rejected=[]
    for label,change in [
        ("wrong-target-token",lambda d:d["ally_overlay_token"].update(target_id=7)),
        ("wrong-target-wrapper",lambda d:d["ally_overlay_token"].update(target_wrapper=0x0202267C)),
        ("wrong-acceptance-coordinate",lambda d:d["phases"][1].update(acceptance_coordinates=[4,10])),
        ("false-final-cast",lambda d:d.update(final_confirmation=True)),
        ("missing-selection-delivery",lambda d:d.update(target_selection_delivered=False)),
        ("extra-post-selection-input",lambda d:d["raw_writes"].append(copy.deepcopy(d["raw_writes"][-1]))),
        ("missing-preview",lambda d:d.update(phases=d["phases"][:2])),
        ("wrong-preview-handler",lambda d:d["phases"][-1].update(handler=0)),
    ]:
        changed=copy.deepcopy(doc);change(changed)
        try:audit(changed,captures)
        except (RecoveryStateError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError("accepted "+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"status":"pass","scope":__doc__,"mutations_rejected":rejected,
                              "preview_target":"processor+8 joins canonical Montblanc",
                              "final_cast":"unknown"},indent=2)+"\n",encoding="utf-8",newline="\n")
    print("PASS ally-selection preview joins; 8 rejected mutations; final cast unknown")


if __name__=="__main__":main()
