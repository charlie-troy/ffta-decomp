"""Check retained Wait-facing ownership and execute its ROM input branch.

ROM fragments stop before rendering/audio helpers. This proves input dispatch,
not turn completion. Raw fixture captures stay local.
"""
import argparse
import hashlib
import json
from pathlib import Path

from unicorn import UC_HOOK_CODE

from emulate import Gba, REGS
from recovery_menu import RecoveryMenu, RecoveryStateError, PLAYER_DRIVER, FACING
from validate_recovery_menu import Memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a6-wait-facing-01")
    parser.add_argument("--closing", default="outputs/autobattle/a6-facing-cure-regression-01")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    gba = Gba(args.rom)
    assert int.from_bytes(gba.rom[0x929D4 + 47 * 4:0x929D4 + 48 * 4], "little") == 0x080955E0

    def setup():
        memory = Memory((directory / "00-initial-ewram.bin").read_bytes())
        reader = RecoveryMenu(memory, gba.rom, run["owner"])
        memory.data = bytearray((directory / "11-A-ewram.bin").read_bytes())
        return reader, memory

    reader, memory = setup()
    obs = reader.snapshot()
    assert obs.state == "facing" and obs.driver_state == 47 and obs.facing_direction == 2
    reader.revalidate(obs)
    rejected = []
    for name, mutate in [
        ("wrong main dispatch", lambda r, m: m.put(PLAYER_DRIVER + 0xDC, 37, 2)),
        ("driver flags changed", lambda r, m: m.put(PLAYER_DRIVER + 0xD0, 0x49)),
        ("target processor remains", lambda r, m: m.put(PLAYER_DRIVER + 0x60, 0x020159E4)),
        ("active cached callback", lambda r, m: m.put(r.manager + 4, r.callback)),
        ("facing owner changed", lambda r, m: m.put(FACING, r.wrapper + 4)),
        ("direction invalid", lambda r, m: m.put(FACING + 4, 4, 1)),
        ("saved direction invalid", lambda r, m: m.put(FACING + 5, 255, 1)),
        ("direction disagrees", lambda r, m: m.put(r.wrapper + 0x1F, 1, 1)),
        ("facing disabled", lambda r, m: m.put(FACING + 0x10, 0, 1)),
        ("Wait selection absent", lambda r, m: m.put(r.context, 0, 2)),
        ("cached callback still open", lambda r, m: m.put(r.callback + 0x14, 0x102, 2)),
    ]:
        reader, memory = setup()
        mutate(reader, memory)
        try:
            token = reader.snapshot()
            reader.revalidate(token)
        except RecoveryStateError:
            rejected.append(name)
        else:
            raise AssertionError(f"facing mutation survived: {name}")

    for name, address, value, size in [
        ("main state changes during snapshot", PLAYER_DRIVER + 0xD0, 0x25, 2),
        ("facing owner changes during snapshot", FACING, 0, 4),
    ]:
        reader, memory = setup()
        original = memory.read_mem
        reads = [0]

        def drifting_read(addr, width):
            if addr == address:
                reads[0] += 1
                if reads[0] == 2:
                    memory.put(PLAYER_DRIVER + 0xDC if address == PLAYER_DRIVER + 0xD0 else address,
                               value, size)
            return original(addr, width)

        memory.read_mem = drifting_read
        try:
            reader.snapshot()
        except RecoveryStateError:
            rejected.append(name)
        else:
            raise AssertionError(f"mid-read mutation survived: {name}")

    reader, memory = setup()
    token = reader.snapshot()
    memory.put(FACING + 4, 1, 1)
    memory.put(reader.wrapper + 0x1F, 1, 1)
    try:
        reader.revalidate(token)
    except RecoveryStateError:
        rejected.append("coherent direction changes before input")
    else:
        raise AssertionError("changed facing token survived")

    # Execute the actual direction/confirm/cancel branch without substituting
    # its instructions. Stop at the first external-helper branch boundary.
    boundaries = {0x080A1CB4: "confirm", 0x080A1CDE: "cancel", 0x080A1D14: "waiting"}
    seen = []

    def stop(uc, address, size, data):
        if address in boundaries:
            seen.append(address)
            uc.emu_stop()

    hook = gba.uc.hook_add(UC_HOOK_CODE, stop)
    cases = []
    for direction in range(4):
        for mask in range(256):
            gba.write8(FACING + 4, direction)
            seen.clear()
            gba.run_range(0x080A1C74, 0x080A1D18,
                          {"r5": FACING, "sb": mask}, timeout_insns=100)
            expected = "confirm" if mask & 1 else "cancel" if mask & 2 else "waiting"
            assert seen and boundaries[seen[0]] == expected, (direction, mask, seen)
            wanted = direction
            for bit, value in [(0x80, 0), (0x20, 1), (0x40, 2), (0x10, 3)]:
                if mask & bit:
                    wanted = value
            assert gba.uc.reg_read(REGS["r4"]) == wanted, (direction, mask, wanted)
            cases.append({"initial": direction, "mask": mask, "branch": expected,
                          "direction_register": wanted})
    gba.uc.hook_del(hook)
    closing = Path(args.closing)
    close_run = json.loads((closing / "probe.json").read_text(encoding="utf-8"))
    memory = Memory((closing / "00-initial-ewram.bin").read_bytes())
    reader = RecoveryMenu(memory, gba.rom, close_run["owner"])
    memory.data = bytearray((closing / "09-A-ewram.bin").read_bytes())
    assert "0104" in close_run["phases"][-1]["guarded_menu_error"]
    # Separate live/bulk observations: this is explicitly constructed replay.
    memory.put(reader.callback + 0x14, 0x104, 2)
    closing_obs = reader.snapshot()
    assert closing_obs.state == "settling"
    try:
        reader.revalidate(closing_obs)
    except RecoveryStateError:
        rejected.append("derived closing 0x104 cannot authorize input")
    else:
        raise AssertionError("closing callback authorized input")
    result = {"status": "pass", "scope": __doc__, "capture": str(directory),
              "observation": obs.receipt(), "rejections": rejected,
              "derived_closing": {"capture": str(closing), "facts": closing_obs.receipt(),
                                  "constructed": "callback state from later live rejection; earlier bulk bytes"},
              "rom_dispatch": "080929D4[47] -> 080955E0 -> 080A82C0 -> 080A1BE8",
              "rom_fragment": ["080A1C74", "080A1CB4/080A1CDE/080A1D14"],
              "rom_sha256": hashlib.sha256(gba.rom).hexdigest(),
              "rom_cases": len(cases),
              "rom_cases_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
              "limitations": "input branch only; rendering/audio and main turn-completion path excluded"}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Facing: retained ownership, {len(rejected)} rejections, {len(cases)} ROM input branches; pass")


if __name__ == "__main__":
    main()
