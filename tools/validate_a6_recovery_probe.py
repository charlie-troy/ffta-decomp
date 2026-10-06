"""Validate retained A6 self-Cure research facts, not public-runner acceptance."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from probe_a6_action_menu import KEYS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(run, cast, cancel=False):
    require(run.get("status") == "observed" and "error" not in run, "unfinished probe")
    phases = run["phases"]
    require(len({p["tag"] for p in phases}) == len(phases), "duplicate phases")
    by_tag = {p["tag"]: p for p in phases}
    first, menu, selected, final = [by_tag[t] for t in ["00-initial", "05-A", "06-A", "99-settled"]]
    owner = run["owner"]
    expected_route = ["DOWN", "A", "DOWN", "DOWN", "A", "A"] + (
        ["A"] * 3 if cast else ["B"] * 2 if cancel else [])
    require([k["key"] for k in run["keys"]] == expected_route, "wrong research route")
    require(all(k["hits"] == 5 for k in run["keys"]), "incomplete input delivery")
    log = run.get("key_writes", [])
    require(len(log) == len(expected_route) * 5, "missing or extra input log")
    require(all(a["t"] <= b["t"] for a, b in zip(log, log[1:])), "input times reversed")
    for i, name in enumerate(expected_route):
        group = log[i * 5:i * 5 + 5]
        require([k["hits"] for k in group] == list(range(1, 6))
                and all(k["val"] == KEYS[name] for k in group), "input does not match route")
    member = int(run["member_addr"], 16)
    mirror = int(owner["addr"], 16)
    mp = 85 if cast else 6 if cancel else 5
    expected_writes = {(base + offset, width, value.to_bytes(width, "little").hex())
                       for base in [member, mirror]
                       for offset, width, value in [(8, 1, 7), (0x18, 2, 100), (0x1C, 2, mp)]}
    writes = run["writes"]
    require(len(writes) == 6 and {(int(w["addr"], 16), w["width"], w["new"]) for w in writes}
            == expected_writes and all(w["reply"] == "OK" for w in writes), "unexpected fixture writes")
    require(first["member"]["hp"] == 100 and first["member"]["mp"] == mp, "wrong starting resources")
    require(menu["menu_context"]["mode"] == 7 and menu["menu_list"]["race"] == 1
            and menu["menu_list"]["rows"] == list(range(58, 67))
            and menu["menu_list"]["cursor"] == menu["menu_list"]["scroll"] == 0,
            "wrong White Magic list")
    require(menu["menu_list"]["enabled"][0] == int(cast or cancel), "Cure enable gate mismatch")
    if cast:
        context = selected["menu_context"]
        require(context["selected_ability"] == 1 and context["unit"] == context["peer"] == run["member_addr"],
                "wrong ability or self target")
        require(selected["target_cursor"] == [owner["x"], owner["y"]], "wrong target tile")
        require(selected["member"]["hp"] == 100 and selected["member"]["mp"] == 85, "precast effect")
        require(100 < final["member"]["hp"] <= owner["max_hp"] and final["member"]["mp"] == 79,
                "missing heal or incorrect MP consumption")
        require(final["menu_context"]["mode"] == 4 and final["menu_list"]["enabled"][1] == 0,
                "Action not consumed / fresh command list not restored")
    elif cancel:
        context = selected["menu_context"]
        require(context["selected_ability"] == 1
                and context["unit"] == context["peer"] == run["member_addr"], "wrong cancellation preview")
        require(final["member"]["hp"] == 100 and final["member"]["mp"] == 6,
                "cancellation changed resources")
        require(final["menu_context"]["mode"] == 5, "cancellation did not restore Action group")
        # This research control proves resource preservation only. The live
        # guard still rejects the borrowed roster after cancellation; do not
        # turn that observation into a safe-return claim.
        require(final["actor"] is None and final.get("roster_rejected") == "roster outside verified fixture bounds",
                "unexpected post-cancel roster observation")
        return
    else:
        require(final["menu_context"]["mode"] == 7 and final["menu_context"]["selected_ability"] == 0,
                "insufficient-MP confirmation advanced")
        require(final["member"]["hp"] == 100 and final["member"]["mp"] == 5,
                "rejected action changed resources")
    for field in ["name_text", "id", "job", "race", "side_bit", "slot", "x", "y"]:
        require(final["actor"][field] == owner[field], "actor changed")
    require(final["actor"]["hp"] == final["member"]["hp"]
            and final["actor"]["mp"] == final["member"]["mp"], "member/mirror disagree")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cast", required=True)
    parser.add_argument("--low-mp", required=True)
    parser.add_argument("--cancel", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cast, low, cancel = [json.loads(Path(p).read_text()) for p in [args.cast, args.low_mp, args.cancel]]
    require(cast["state_sha256"] == low["state_sha256"] == cancel["state_sha256"], "different source fixtures")
    validate(cast, True)
    validate(low, False)
    validate(cancel, False, cancel=True)
    mutations = [
        ("missing input log", True, lambda r: r.update(key_writes=[])),
        ("wrong selected ability", True, lambda r: r["phases"][6]["menu_context"].update(selected_ability=5)),
        ("wrong target", True, lambda r: r["phases"][6]["menu_context"].update(peer="02000188")),
        ("unspent MP", True, lambda r: r["phases"][-1]["member"].update(mp=85)),
        ("no healing", True, lambda r: r["phases"][-1]["member"].update(hp=100)),
        ("enabled at five MP", False, lambda r: r["phases"][5]["menu_list"]["enabled"].__setitem__(0, 1)),
        ("extra resource write", True, lambda r: r["writes"].append(r["writes"][2])),
    ]
    rejected = []
    for name, is_cast, mutate in mutations:
        altered = copy.deepcopy(cast if is_cast else low)
        mutate(altered)
        try:
            validate(altered, is_cast)
        except ValueError:
            rejected.append(name)
        else:
            raise ValueError(f"mutation survived: {name}")
    for name, mutate in [
        ("cancellation spends MP", lambda r: r["phases"][-1]["member"].update(mp=0)),
        ("cancellation remains modal", lambda r: r["phases"][-1]["menu_context"].update(mode=12))]:
        altered = copy.deepcopy(cancel)
        mutate(altered)
        try:
            validate(altered, False, cancel=True)
        except ValueError:
            rejected.append(name)
        else:
            raise ValueError(f"mutation survived: {name}")
    result = {"scope": "retained self-Cure research artifacts, not fresh gameplay or policy acceptance",
              "cast": args.cast, "low_mp": args.low_mp, "cancel": args.cancel, "positive_controls": 3,
              "rejected_mutations": rejected, "status": "pass"}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("A6 research artifacts: 3 positive controls, 9 rejected mutations; pass")


if __name__ == "__main__":
    main()
