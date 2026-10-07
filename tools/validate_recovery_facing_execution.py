"""Replay bounded facing confirmation and independently join later actors.

This validates retained research captures; it does not launch fresh gameplay.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import read_roster, STRIDE, ROSTER, SIDE_BIT
from recovery_menu import PLAYER_DRIVER, integer, require
from validate_recovery_menu import Memory

MASKS = {"A": 1, "B": 2, "DOWN": 128, "UP": 64}


def continuation(directory, tag, rom):
    raw = (directory / f"{tag}-ewram.bin").read_bytes()
    memory = Memory(raw)
    get = lambda address, size=4: integer(memory.read_mem(address, size), 0, size)
    wrapper = get(PLAYER_DRIVER + 4)
    member = get(wrapper)
    unit = memory.read_mem(member, STRIDE)
    roster = read_roster(memory, rom=rom)
    require(roster["struct_count"] == roster["live_count"] == 7
            and roster["ids_distinct"] and roster["live_contiguous"], "roster not restored")
    matches = [r for r in roster["slots"] if r["live"]
               and r["name"] == integer(unit, 0) and r["id"] == unit[0x104]]
    require(len(matches) == 1, "driver actor missing or ambiguous in restored roster")
    row = matches[0]
    tile = [unit[0xF6], unit[0xF7]]
    mirror = ROSTER + STRIDE * row["slot"]
    require(list(memory.read_mem(mirror + 0xF6, 2)) == tile
            and row["job"] == unit[7] and row["side_raw"] == integer(unit, 0x28, 2),
            "driver actor differs from restored battle identity")
    require(get(PLAYER_DRIVER + 8) == wrapper, "driver wrappers disagree")
    return {"tag": tag, "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "driver_state": get(PLAYER_DRIVER + 0xDC, 2),
            "wrapper": wrapper, "canonical": member,
            "actor": row | {"tile": tile}, "target_tile": list(memory.read_mem(0x0200FFC9, 2))}


def validate(run, later):
    require(run["status"] == "observed", "incomplete run")
    final = run["facing_confirmation"]
    keys, guards, raw = run["keys"], run["menu_guards"], run["key_writes"]
    require(final["before_key"] == len(keys) == len(guards) and keys[-1]["key"] == "A",
            "missing final or post-final input")
    require(raw and all(k["hits"] > 0 for k in keys), "missing delivered input")
    require([g["before_key"] for g in guards] == list(range(1, len(keys) + 1))
            and [g["key"] for g in guards] == [k["key"] for k in keys], "input guards disagree")
    expected = [MASKS[k["key"]] for k in keys for _ in range(k["hits"])]
    require([w["val"] for w in raw] == expected
            and not any(w["manual"] for w in raw)
            and [w["t"] for w in raw] == sorted(w["t"] for w in raw), "raw input differs")
    facts = final["facts"]
    require(guards[-1]["facts"] == facts, "final guard differs")
    require(facts["state"] == "facing" and facts["driver_state"] == 47
            and facts["target_processor"] == facts["ui_active"] == 0
            and facts["facing_direction"] in range(4), "owned facing missing")
    owner = run["owner"]
    require(facts["member"] == int(run["member_addr"], 16)
            and facts["target_tile"] == [owner["x"], owner["y"]], "final actor or tile differs")
    require(len(later) == 2 and later[0]["actor"]["id"] != later[1]["actor"]["id"],
            "distinct continuing actors missing")
    for entry in later:
        actor = entry["actor"]
        require(entry["wrapper"] != facts["actor_wrapper"] and entry["canonical"] != facts["member"]
                and actor["id"] != owner["id"] and actor["side_raw"] & SIDE_BIT
                and actor["hp"] > 0 and entry["target_tile"] == actor["tile"],
                "continuation is not an independently joined enemy")
        phase = next(p for p in run["phases"] if p["tag"] == entry["tag"])
        require(phase["player_driver"]["actor_wrapper"] == f"{entry['wrapper']:08x}"
                and phase["player_driver"]["state"] == entry["driver_state"], "live and bulk driver disagree")
        own = phase["actor"]
        require(own and own["id"] == owner["id"] and own["name"] == owner["name"]
                and own["hp"] == facts["hp"] and own["mp"] == facts["mp"]
                and [own["x"], own["y"]] == [owner["x"], owner["y"]],
                "Wait changed actor resources or position")
        require(phase["member"]["hp"] == facts["hp"] and phase["member"]["mp"] == facts["mp"],
                "canonical resources disagree")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a6-wait-facing-commit-02")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    rom = Path(args.rom).read_bytes()
    later = [continuation(directory, tag, rom) for tag in ("12-A", "99-settled")]
    validate(run, later)
    rejected = []

    def change_final(receipt, **values):
        receipt["facing_confirmation"]["facts"].update(values)
        receipt["menu_guards"][-1]["facts"].update(values)

    for name, mutate in [
        ("empty raw input", lambda r, c: r.update(key_writes=[])),
        ("post-final input with matching guards", lambda r, c: (r["keys"].append(r["keys"][-1]),
                                                             r["menu_guards"].append(r["menu_guards"][-1]))),
        ("wrong facing actor", lambda r, c: change_final(r, member=0)),
        ("cached active callback", lambda r, c: change_final(r, ui_active=1)),
        ("same continuing actor", lambda r, c: c[1].update(actor=c[0]["actor"])),
        ("continuation still owner", lambda r, c: c[0].update(wrapper=r["facing_confirmation"]["facts"]["actor_wrapper"])),
        ("enemy cursor differs", lambda r, c: c[0].update(target_tile=[0, 0])),
        ("Wait spent MP", lambda r, c: r["phases"][-1]["actor"].update(mp=0)),
        ("canonical HP differs", lambda r, c: r["phases"][-1]["member"].update(hp=1)),
    ]:
        changed, control = copy.deepcopy(run), copy.deepcopy(later)
        mutate(changed, control)
        try:
            validate(changed, control)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"artifact mutation survived: {name}")
    result = {"status": "pass", "scope": __doc__, "capture": str(directory),
              "probe_sha256": hashlib.sha256((directory / "probe.json").read_bytes()).hexdigest(),
              "continuation": later, "rejections": rejected,
              "limits": "fixed research route, no policy fallback/public-runner acceptance"}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Facing continuation: two restored-roster enemy actors, {len(rejected)} rejected mutations; pass")


if __name__ == "__main__":
    main()
