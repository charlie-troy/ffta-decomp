"""Replay retained local RAM captures and adversarially check modal identity.

These are captured-data reader checks, not a fresh gameplay execution gate.
Raw RAM inputs remain local. The JSON result retains only facts and labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from recovery_menu import RecoveryMenu, RecoveryStateError, MENU_ROOT, MEMBERS, STRIDE, PLAYER_DRIVER, BATTLE_STRUCT


class Memory:
    def __init__(self, data):
        self.data = bytearray(data)

    def read_mem(self, addr, size):
        offset = addr - 0x02000000
        return bytes(self.data[offset:offset + size]) if offset >= 0 else None

    def put(self, addr, value, size=4):
        offset = addr - 0x02000000
        self.data[offset:offset + size] = value.to_bytes(size, "little")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--cast", default="outputs/autobattle/a6-cure-cast-03")
    parser.add_argument("--cancel", default="outputs/autobattle/a6-cure-cancel-02")
    parser.add_argument("--settling", default="outputs/autobattle/a6-modal-cure-02")
    parser.add_argument("--returned-target", default="outputs/autobattle/a6-policy-reserve-02")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rom = Path(args.rom).read_bytes()
    result = {"scope": "retained local RAM replay plus adversarial reader checks; no fresh gameplay claim",
              "observations": [], "rejections": []}
    runs = [(args.cast, {"00-initial": "command", "02-A": "action-group", "05-A": "ability-list",
                        "06-A": "target-overlay", "07-A": "description", "08-A": "confirmation",
                        "09-A": "description", "99-settled": "command"}),
            (args.cancel, {"06-A": "target-overlay", "07-B": "ability-list",
                           "08-B": "action-group", "09-B": "command", "99-settled": "command"})]
    for directory, expected in runs:
        directory = Path(directory)
        owner = json.loads((directory / "probe.json").read_text())["owner"]
        initial = Memory((directory / "00-initial-ewram.bin").read_bytes())
        reader = RecoveryMenu(initial, rom, owner)
        for tag, state in expected.items():
            reader.g = Memory((directory / f"{tag}-ewram.bin").read_bytes())
            observation = reader.snapshot()
            assert observation.state == state, (tag, observation.state, state)
            reader.revalidate(observation)
            if tag == "05-A":
                assert observation.ability_ids == tuple(range(1, 10))
                assert observation.cure_cost == 6
            if tag == "02-A":
                assert observation.rows == (12, 2, 10, 80, 15)
            result["observations"].append({"run": str(directory), "tag": tag,
                                           "facts": observation.receipt()})

    directory = Path(args.settling)
    owner = json.loads((directory / "probe.json").read_text())["owner"]
    memory = Memory((directory / "00-initial-ewram.bin").read_bytes())
    reader = RecoveryMenu(memory, rom, owner)
    memory.data = bytearray((directory / "09-A-ewram.bin").read_bytes())
    # The bulk capture precedes the live guarded observation. Replay its
    # controller state explicitly; do not call these two reads atomic.
    live = json.loads((directory / "probe.json").read_text())
    guarded = next(p["guarded_menu"] for p in live["phases"] if p["tag"] == "09-A")
    assert guarded["state"] == "settling" and guarded["controller_state"] == 3
    memory.put(reader.callback + 0x14, 3, 2)
    observation = reader.snapshot()
    assert observation.state == "settling"
    result["observations"].append({"run": str(directory), "tag": "09-A-derived-settling",
                                   "constructed": "controller state from later live guard",
                                   "facts": observation.receipt()})
    try:
        reader.revalidate(observation)
    except RecoveryStateError:
        result["rejections"].append("settling cannot authorize input")
    else:
        raise AssertionError("settling authorized input")
    memory.put(reader.callback + 0x14, 0x103, 2)
    observation = reader.snapshot()
    assert observation.state == "settling"
    try:
        reader.revalidate(observation)
    except RecoveryStateError:
        result["rejections"].append("flagged settling cannot authorize input")
    else:
        raise AssertionError("flagged settling authorized input")

    directory = Path(args.returned_target)
    owner = json.loads((directory / "probe.json").read_text())["owner"]

    def returned_target():
        memory = Memory((directory / "00-initial-ewram.bin").read_bytes())
        reader = RecoveryMenu(memory, rom, owner)
        memory.data = bytearray((directory / "10-B-ewram.bin").read_bytes())
        return reader, memory

    reader, memory = returned_target()
    observation = reader.snapshot()
    assert observation.state == "target-overlay" and observation.target_state == 10
    reader.revalidate(observation)
    result["observations"].append({"run": str(directory), "tag": "10-B", "facts": observation.receipt()})
    for name, mutate in [
        ("processor allocation changed", lambda m: m.put(PLAYER_DRIVER + 0x60, BATTLE_STRUCT + 4)),
        ("processor actor changed", lambda m: m.put(BATTLE_STRUCT, 0)),
        ("processor ability changed", lambda m: m.put(BATTLE_STRUCT + 0xEC, 5, 2)),
        ("processor not ready", lambda m: m.put(BATTLE_STRUCT + 0x1118, 11, 2)),
        ("processor flags not ready", lambda m: m.put(BATTLE_STRUCT + 0x1112, 0x6C, 2)),
        ("driver actor changed", lambda m: m.put(PLAYER_DRIVER + 4, 0)),
        ("unowned active callback", lambda m: m.put(reader.manager + 4, reader.callback + 4)),
    ]:
        reader, memory = returned_target()
        mutate(memory)
        try:
            token = reader.snapshot()
            reader.revalidate(token)
        except RecoveryStateError:
            result["rejections"].append(name)
        else:
            raise AssertionError(f"processor mutation authorized input: {name}")

    directory = Path(args.cast)
    owner = json.loads((directory / "probe.json").read_text())["owner"]
    baseline = (directory / "00-initial-ewram.bin").read_bytes()
    target = (directory / "08-A-ewram.bin").read_bytes()

    def setup():
        memory = Memory(baseline)
        reader = RecoveryMenu(memory, rom, owner)
        memory.data = bytearray(target)
        return reader, memory

    reader, memory = setup()
    good = reader.snapshot()
    member, context, callback = good.member, good.context, good.callback
    mutations = [
        ("root pointer moved", lambda m: m.put(MENU_ROOT, 0)),
        ("actor pointer changed", lambda m: m.put(context + 0x18, member + STRIDE)),
        ("peer changed", lambda m: m.put(context + 0x1C, member + STRIDE)),
        ("callback allocation changed", lambda m: m.put(context + 0x28, callback + 4)),
        ("UI manager changed", lambda m: m.put(context + 0x20, reader.manager + 4)),
        ("confirmation processor state changed", lambda m: m.put(BATTLE_STRUCT + 0x1118, 10, 2)),
        ("confirmation processor flags changed", lambda m: m.put(BATTLE_STRUCT + 0x1112, 0, 2)),
        ("unknown callback", lambda m: m.put(callback, 0x08029189)),
        ("transient controller", lambda m: m.put(callback + 0x14, 0x101, 2)),
        ("wrong ability", lambda m: m.put(context + 0x14, 5)),
        ("name pointer changed", lambda m: m.put(member, owner["name"] + 2)),
        ("unit ID changed", lambda m: m.put(member + 0x104, 255, 1)),
        ("job changed", lambda m: m.put(member + 7, 5, 1)),
        ("secondary job changed", lambda m: m.put(member + 8, 8, 1)),
        ("support changed", lambda m: m.put(member + 0x3B, 31, 1)),
        ("side changed", lambda m: m.put(member + 0x28, 0x8000, 2)),
        ("max HP changed", lambda m: m.put(member + 0x1A, 999, 2)),
        ("impossible HP", lambda m: m.put(member + 0x18, 1000, 2)),
        ("KO actor", lambda m: m.put(member + 0x18, 0, 2)),
        ("impossible MP", lambda m: m.put(member + 0x1C, 1000, 2)),
        ("tile changed", lambda m: m.put(member + 0xF6, 63, 1)),
        ("invalid confirmation cursor", lambda m: m.put(callback + 0x18 + 0x69, 2, 1)),
        ("duplicate canonical actor", lambda m: m.data.__setitem__(slice(MEMBERS + STRIDE - 0x2000000,
                                MEMBERS + STRIDE * 2 - 0x2000000),
                                m.data[member - 0x2000000:member - 0x2000000 + STRIDE])),
    ]
    for name, mutate in mutations:
        reader, memory = setup()
        mutate(memory)
        try:
            reader.snapshot()
        except RecoveryStateError:
            result["rejections"].append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    ability_data = (directory / "05-A-ewram.bin").read_bytes()
    reader, memory = setup()
    memory.data = bytearray(ability_data)
    ability_obs = reader.snapshot()
    obj = ability_obs.callback + 0x18
    rows_ptr = int.from_bytes(memory.read_mem(obj + 0x94, 4), "little")
    enable_ptr = int.from_bytes(memory.read_mem(obj + 0x98, 4), "little")
    for name, mutate in [
        ("invalid row count", lambda m: m.put(obj + 0x50, 100, 2)),
        ("cursor outside list", lambda m: m.put(obj + 0x69, 255, 1)),
        ("scroll outside list", lambda m: m.put(obj + 0x52, 10, 2)),
        ("row pointer outside RAM", lambda m: m.put(obj + 0x94, 0x08000000)),
        ("row outside race table", lambda m: m.put(rows_ptr, 65535)),
        ("enable byte malformed", lambda m: m.put(enable_ptr, 2, 1)),
        ("list race changed", lambda m: m.put(obj + 0xA, 5, 1)),
        ("short memory read", lambda m: m.data.__delitem__(slice(0x2DD00, None))),
    ]:
        reader, memory = setup()
        memory.data = bytearray(ability_data)
        mutate(memory)
        try:
            reader.snapshot()
        except RecoveryStateError:
            result["rejections"].append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    reader, memory = setup()
    obs = reader.snapshot()
    reader.clock = lambda: obs.observed_at + 3
    try:
        reader.revalidate(obs)
    except RecoveryStateError:
        result["rejections"].append("stale observation")
    else:
        raise AssertionError("stale observation accepted")
    reader, memory = setup()
    obs = reader.snapshot()
    memory.put(member + 0x1C, 84, 2)
    try:
        reader.revalidate(obs)
    except RecoveryStateError:
        result["rejections"].append("resources changed before input")
    else:
        raise AssertionError("changed observation accepted")
    for name, address, change_address, value, width in [
        ("actor changes during snapshot", member, member + 0x1C, 84, 2),
        ("controller changes during snapshot", callback, callback, 0, 4),
        ("cursor changes during snapshot", callback + 0x18,
         callback + 0x18 + 0x69, 1, 1),
        ("processor changes during snapshot", BATTLE_STRUCT + 0x1112,
         BATTLE_STRUCT + 0x1112, 0, 2),
    ]:
        reader, memory = setup()
        original = memory.read_mem
        reads = [0]

        def drifting_read(addr, size):
            if addr == address or (name.startswith("cursor") and addr == change_address):
                reads[0] += 1
                if reads[0] == 2:
                    memory.put(change_address, value, width)
            return original(addr, size)

        memory.read_mem = drifting_read
        try:
            reader.snapshot()
        except RecoveryStateError:
            result["rejections"].append(name)
        else:
            raise AssertionError(f"mid-read mutation survived: {name}")
    result["status"] = "pass"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Modal reader: {len(result['observations']) - 1} captured states + 1 derived settling state, "
          f"{len(result['rejections'])} rejections; pass")


if __name__ == "__main__":
    main()
