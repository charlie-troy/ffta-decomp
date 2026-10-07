"""Execute ROM menu-state dispatch; derived opening snapshots authorize no input."""
import argparse
import json
from pathlib import Path

from unicorn import UC_HOOK_CODE

from emulate import Gba
from recovery_menu import RecoveryMenu, RecoveryTransient, RecoveryStateError
from validate_recovery_menu import Memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a61-scoped-cure-03")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    gba = Gba(args.rom)
    boundaries = {0x08028E5E, 0x08028ECC, 0x08028F02}
    destinations = []

    def stop_dispatch(uc, address, size, user):
        if address in boundaries:
            destinations.append(address)
            uc.emu_stop()

    hook = gba.uc.hook_add(UC_HOOK_CODE, stop_dispatch)
    executed = []
    for state, expected in [(0x100, 0x08028E5E), (0x101, 0x08028ECC), (0x102, 0x08028F02)]:
        destinations.clear()
        gba.write32(0x02030000, state)
        gba.run_range(0x08028DE0, 0x08028FE8, {"r0": 0, "r1": 0x02030000, "r2": 0x02030100})
        assert destinations == [expected], (state, destinations)
        executed.append({"state": state, "dispatch": expected})
    gba.uc.hook_del(hook)
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    rejected = []
    for state in (0x100, 0x101):
        memory = Memory((directory / "00-initial-ewram.bin").read_bytes())
        reader = RecoveryMenu(memory, gba.rom, run["owner"])
        original = reader.snapshot()
        memory.put(reader.callback + 0x14, state, 2)
        try:
            reader.snapshot()
        except RecoveryTransient:
            rejected.append(f"derived opening {state:04x} returns no snapshot")
        else:
            raise AssertionError("opening authorized a snapshot")
        try:
            reader.revalidate(original)
        except RecoveryTransient:
            rejected.append(f"derived opening {state:04x} cannot authorize prior token")
        else:
            raise AssertionError("opening authorized stale command token")
        memory.put(reader.member + 0x104, 0xFF, 1)
        try:
            reader.snapshot()
        except RecoveryTransient:
            raise AssertionError("invalid identity softened into passive opening")
        except RecoveryStateError:
            rejected.append(f"invalid identity remains hard rejection in {state:04x}")
        else:
            raise AssertionError("invalid opening owner accepted")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "executed_dispatch": executed,
                              "derived_rejections": rejected,
                              "limits": "Stops before external helpers; derived reader checks are not atomic live captures"}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"PASS opening: {len(executed)} ROM dispatch cases; {len(rejected)} derived rejection controls")


if __name__ == "__main__":
    main()
