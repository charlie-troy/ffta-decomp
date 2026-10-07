"""Compare production continuation reader with independent retained raw joins."""
import argparse
import json
from pathlib import Path

from fixture_guard import ROSTER, STRIDE, COUNT_OFF, BATTLE_STRUCT
from recovery_menu import PLAYER_DRIVER, RecoveryStateError
from recovery_continuation import observe_continuation
from validate_recovery_menu import Memory
from validate_recovery_facing_execution import continuation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a61-scoped-cure-07")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    rom = Path(args.rom).read_bytes()
    facts = run["finish"]["facing"]
    observed = []
    for tag in run["continuation_tags"]:
        memory = Memory((directory / f"{tag}-ewram.bin").read_bytes())
        value = observe_continuation(memory, rom, run["owner"], facts)
        independent = continuation(directory, tag, rom)
        assert all(value[field] == independent[field] for field in
                   ("wrapper", "canonical", "driver_state", "actor", "target_tile"))
        observed.append(value)
    tag = run["continuation_tags"][0]
    raw = (directory / f"{tag}-ewram.bin").read_bytes()
    first = observed[0]
    canonical = first["canonical"]
    mirror = ROSTER + STRIDE * first["actor"]["slot"]
    rejected = []

    def coherent(memory, offset, value, size):
        memory.put(canonical + offset, value, size)
        memory.put(mirror + offset, value, size)

    for name, mutate in [
        ("borrowed roster", lambda m: m.put(BATTLE_STRUCT + COUNT_OFF, 1)),
        ("disagreeing wrappers", lambda m: m.put(PLAYER_DRIVER + 8, 0)),
        ("previous player's wrapper", lambda m: (m.put(PLAYER_DRIVER + 4, facts["actor_wrapper"]), m.put(PLAYER_DRIVER + 8, facts["actor_wrapper"]))),
        ("unreadable canonical pointer", lambda m: m.put(first["wrapper"], 0)),
        ("stale previous cursor", lambda m: m.put(0x0200FFC9, 0, 2)),
        ("coherent enemy HP out of bounds", lambda m: coherent(m, 0x18, 1000, 2)),
        ("coherent enemy job out of bounds", lambda m: coherent(m, 7, 200, 1)),
        ("coherent dead continuing enemy", lambda m: coherent(m, 0x18, 0, 2)),
        ("coherent invalid tile", lambda m: (coherent(m, 0xF6, 0xFFFF, 2), m.put(0x0200FFC9, 0xFFFF, 2))),
        ("enemy-only healing", lambda m: m.put(facts["member"] + 0x18, 100, 2)),
        ("canonical/roster disagreement", lambda m: m.put(canonical + 0x1C, 0, 2)),
    ]:
        memory = Memory(raw)
        mutate(memory)
        try:
            observe_continuation(memory, rom, run["owner"], facts)
        except RecoveryStateError:
            rejected.append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": "retained capture reader checks, not fresh public gameplay",
                              "capture": args.capture, "observed": observed, "rejections": rejected}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"PASS continuation reader: {len(observed)} independent joins, {len(rejected)} rejected mutations")


if __name__ == "__main__":
    main()
