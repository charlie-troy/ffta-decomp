"""Boot mGBA on a battle fixture and verify the live state before any write.

A2.4a rewrite. The previous version validated two stale addresses (slot1 was
called "name0"; a turn-scratch record was called "slot6" and its class byte
was checked as if it were Marche's) and cleaned up with a global
`taskkill /IM mgba.exe`, which is unsafe on a shared machine.

Current behaviour:

* accepts explicit `--rom`, `--state`/positional fixture, `--emulator`,
  `--work-dir`, `--save` and copies the ROM plus battery save into a scratch
  directory, so the user's `baserom.sav` is never written;
* owns exactly the process it launches and terminates only that PID;
* refuses to start when the GDB stub port already has a listener, because
  mGBA 0.10.5 has no CLI/config override for the stub port and attaching to
  (or killing) another worker's or the user's emulator is forbidden;
* connects once, halts, and verifies the live fixture with
  `tools/fixture_guard.py` (slot0 identity, live roster bounds, both sides,
  CT, scene), read-only, before anything is allowed to write.

The guard is a prerequisite, not a guarantee: a rejected fixture means the
savestate does not hold the state the packet claims, and no memory write may
happen until it is reconciled.

Usage:
    python tools/boot_fixture_gdb.py [fixture] [options]

For an experiment that needs the same connection through boot *and* the
experiment, import `FixtureSession` from `tools/fixture_guard.py` instead of
re-attaching: reconnection after this CLI exits is not depended on anywhere.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixture_guard import (  # noqa: E402
    DEFAULT_EMULATOR, DEFAULT_FIXTURE_DIR, DEFAULT_ROM, DEFAULT_SAVE,
    FixtureSession, write_receipt,
)

# `a2-battle-start.ss0` (the old default) fails the A2.4a guard: it does not
# hold the battle roster. The verified fixture is `battle-start.ss0`; see
# docs/battle-fixtures.md.
DEFAULT_FIXTURE = "battle-start.ss0"


def resolve_state(state):
    if not state:
        return None
    if os.path.isabs(state) or "/" in state or "\\" in state:
        return state
    return os.path.join(DEFAULT_FIXTURE_DIR, state)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fixture", nargs="?", default=DEFAULT_FIXTURE,
                    help=f"fixture name in {DEFAULT_FIXTURE_DIR} or a path "
                         f"(default {DEFAULT_FIXTURE})")
    ap.add_argument("--state", help="explicit savestate path (overrides fixture)")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="path to baserom.gba")
    ap.add_argument("--emulator", default=DEFAULT_EMULATOR, help="mGBA executable")
    ap.add_argument("--save", default=DEFAULT_SAVE, help="battery save to copy")
    ap.add_argument("--work-dir", default=None, help="scratch dir for copies")
    ap.add_argument("--port", type=int, default=2345, help="GDB stub port")
    ap.add_argument("--expect-slot0-id", type=int, default=None,
                    help="require this unit id in slot0")
    ap.add_argument("--expect-live-units", type=int, default=None,
                    help="require this many live (ROM-name) roster records")
    ap.add_argument("--expect-struct-count", type=int, default=None)
    ap.add_argument("--exact-ct", action="store_true",
                    help="treat the slot0 CT value as a required check")
    ap.add_argument("--no-rom-check", action="store_true",
                    help="skip the ROM SHA1 guard (never for control runs)")
    ap.add_argument("--leave-running", action="store_true",
                    help="keep the emulator process after verification")
    ap.add_argument("--json", default=None, help="write the receipt JSON here")
    args = ap.parse_args()

    expect = {"slot0_id": args.expect_slot0_id,
              "live_units": args.expect_live_units,
              "struct_count": args.expect_struct_count}
    state = args.state or resolve_state(args.fixture)
    session = FixtureSession(
        state=state, rom=args.rom, emulator=args.emulator, save=args.save,
        work_dir=args.work_dir, port=args.port, expect=expect,
        exact_ct=args.exact_ct, verify_rom=not args.no_rom_check)
    keep_process = False
    try:
        try:
            receipt = session.start()
        except Exception as exc:
            print(f"BOOT FAILED: {exc}")
            return 1

        r = receipt["roster"]
        print(f"fixture: {state}")
        print(f"struct count={r['struct_count']} units={r['live_count']} "
              f"slots={r['live_slots']}")
        print(f"roster: {list(zip(r['live_slots'], r['live_names']))}")
        print(f"side 0x8000 set={r['side_bit_set']} clear={r['side_bit_clear']} "
              f"unaffiliated={r['unaffiliated']} "
              f"ram-named={r['ram_named_units']} scratch={r['scratch_slots']}")
        print(f"scene: {receipt['scene']}")
        for c in receipt["checks"]:
            mark = {True: "ok  ", False: "FAIL", None: "info"}[c["ok"]]
            print(f"  [{mark}] {c['check']}: {c['detail']}")
        print(f"writes so far: {len(session.writes)}")
        if args.json:
            print(f"receipt: {write_receipt(args.json, session.summary())}")
        ok = receipt["ok"]
        print("READY (fixture verified live)" if ok else "FIXTURE REJECTED")
        if ok and args.leave_running:
            print("note: leaving pid running and closing this connection; "
                  "reconnection is untested, prefer FixtureSession in-process")
        keep_process = bool(ok and args.leave_running)
        return 0 if ok else 2
    finally:
        # Always reclaim the process this session launched, including on an
        # unexpected error: a leaked mGBA would hold the hardcoded stub port.
        session.stop(keep_process=keep_process)


if __name__ == "__main__":
    sys.exit(main())
