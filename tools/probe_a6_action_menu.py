"""Bounded A6 menu research on an owned, disposable fixture session.

Record screenshots, roster facts and LOCAL-ONLY RAM sweeps after each menu
input. A secondary-job/HP edit constructs a research fixture, not gameplay
acceptance. No ROM or save is edited. The script never saves the emulator.
The route is explicit research input; no ability is advertised to the public
adapter on the basis of a cursor or a learned-ability byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter, IdentityError, key
from c2_menu_probe import sweep
from fixture_guard import FixtureSession, ROSTER, STRIDE, u8, u16, u32
from probe_control_handoff import Probe

KEYS = {"A": 1, "B": 2, "DOWN": 0x80, "UP": 0x40,
        "RIGHT": 0x10, "LEFT": 0x20}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="outputs/lua-nav/battle-start.ss0")
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    parser.add_argument("--secondary-job", type=int)
    parser.add_argument("--hp", type=int)
    parser.add_argument("--mp", type=int)
    parser.add_argument("--edit-members", action="store_true",
                        help="also edit the unique matching clan-member record; research only")
    parser.add_argument("--settle-end", type=float, default=0.0)
    parser.add_argument("--route", default="DOWN,A,DOWN,DOWN,A,DOWN,UP,B,B")
    args = parser.parse_args()
    route = args.route.split(",") if args.route else []
    if any(k not in KEYS for k in route):
        parser.error("route contains an unsupported key")
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=False)
    result = {"scope": "menu research only; fixture edits are not engine actions",
              "state": args.state, "rom": args.rom,
              "state_sha256": hashlib.sha256(Path(args.state).read_bytes()).hexdigest(),
              "phases": [], "writes": [], "keys": [], "status": "unknown"}
    result["engine_calls"] = []
    started = time.time()
    try:
        with FixtureSession(args.state, rom=args.rom, quiet=True) as session:
            result["writes"] = session.writes
            result["pid"] = session.pid
            probe = Probe(session, intervene="none")
            adapter = ActorAdapter(session)
            # Two matching fresh-menu observations, with the engine running
            # between them. Cursor ownership, not a numeric CT threshold.
            for _ in range(2):
                probe.pump(2.0, "a6-owner", sample_every=60.0)
                rows = adapter.snapshot()
                owner = adapter.observe(probe, rows)
            if owner is None:
                raise RuntimeError("fixture has no verified fresh-menu owner")
            probe.active_player_slot = owner["slot"]
            result["owner"] = owner
            adapter.revalidate(owner, probe)
            base = ROSTER + STRIDE * owner["slot"]
            member = None
            if args.edit_members:
                matches = [0x02000080 + STRIDE * i for i in range(14)
                           if u32(session.g, 0x02000080 + STRIDE * i) == owner["name"]
                           and u8(session.g, 0x02000080 + STRIDE * i + 0x104) == owner["id"]
                           and u8(session.g, 0x02000080 + STRIDE * i + 7) == owner["job"]]
                if len(matches) != 1:
                    raise RuntimeError("no unique matching clan member for fixture edit")
                member = matches[0]
                result["member_addr"] = f"{member:08x}"
            edit_bases = [base] + ([member] if member is not None else [])
            if args.secondary_job is not None:
                if not 0 <= args.secondary_job < 116:
                    raise ValueError("secondary job outside decoded table")
                for edit_base in edit_bases:
                    session.write_u8(edit_base + 8, args.secondary_job,
                                     "A6 disposable research fixture: secondary job")
            if args.hp is not None:
                if not 0 < args.hp <= owner["max_hp"]:
                    raise ValueError("HP must be living and within actor max")
                for edit_base in edit_bases:
                    session.write_bytes(edit_base + 0x18, args.hp.to_bytes(2, "little"),
                                        "A6 disposable research fixture: wounded actor")
            if args.mp is not None:
                if not 0 <= args.mp <= owner["max_mp"]:
                    raise ValueError("MP must be within actor bounds")
                for edit_base in edit_bases:
                    session.write_bytes(edit_base + 0x1C, args.mp.to_bytes(2, "little"),
                                        "A6 disposable research fixture: actor MP")

            def phase(tag):
                probe.disarm()
                # press() re-arms router hooks; a pending stop can precede
                # the menu redraw. Run untraced before taking a halted,
                # screenshot-matched snapshot, rather than pairing old RAM
                # with the next visible frame.
                session.g.cont()
                time.sleep(0.5)
                # Served reads halt the core (DE-029). Bulk sweeps occur in
                # one halted window; the raw game bytes stay local/untracked.
                data = sweep(session.g)
                for lo, hi, name in ((0x02000000, 0x02030000, "ewram"),
                                     (0x03000000, 0x03008000, "iwram")):
                    if any(a not in data for a in range(lo, hi)):
                        raise RuntimeError(f"incomplete {name} sweep")
                    (root / f"{tag}-{name}.bin").write_bytes(
                        bytes(data[a] for a in range(lo, hi)))
                try:
                    row = next(r for r in adapter.snapshot() if key(r) == key(owner))
                    transient = None
                except IdentityError as exc:
                    row, transient = None, str(exc)
                entry = {"tag": tag, "elapsed": round(time.time() - started, 3),
                         "actor": row, "command_cursor": probe.read_cmd_cursor(),
                         "target_cursor": probe.read_target_cursor(),
                         "action_cursor": [u8(session.g, 0x0202DF5D),
                                           u8(session.g, 0x0202DF5E)]}
                # Research offsets from 08028970/080287C4/08028A70.
                # Retain raw values even outside the ability list; these
                # fields do not establish a public-adapter modal contract.
                read = lambda addr, width: int.from_bytes(
                    bytes(data[addr + i] for i in range(width)), "little")
                context = read(0x0200F438, 4)
                if 0x02000000 <= context <= 0x0202FFCC:
                    entry["menu_context"] = {
                        "addr": f"{context:08x}",
                        "selection": read(context, 2),
                        "mode": read(context + 4, 1),
                        "selected_ability": read(context + 0x14, 4),
                        "unit": f"{read(context + 0x18, 4):08x}",
                        "peer": f"{read(context + 0x1C, 4):08x}"}
                    callback = read(context + 0x28, 4)
                    obj = callback + 0x18
                    if 0x02000000 <= callback and obj <= 0x0202FF60:
                        count = read(obj + 0x50, 2)
                        rows_ptr = read(obj + 0x94, 4)
                        enabled_ptr = read(obj + 0x98, 4)
                        if (read(callback, 4) == 0x08028DE1
                                and 0 < count <= 32
                                and 0x02000000 <= rows_ptr <= 0x02030000 - count * 4
                                and 0x02000000 <= enabled_ptr <= 0x02030000 - count):
                            entry["menu_list"] = {
                                "object": f"{obj:08x}", "race": read(obj + 0xA, 1),
                                "cursor": read(obj + 0x69, 1),
                                "scroll": read(obj + 0x52, 2),
                                "rows": [read(rows_ptr + i * 4, 4) for i in range(count)],
                                "enabled": [read(enabled_ptr + i, 1) for i in range(count)]}
                if transient is not None:
                    entry["roster_rejected"] = transient
                if member is not None:
                    entry["member"] = {"addr": f"{member:08x}",
                                       "secondary_job": u8(session.g, member + 8),
                                       "hp": u16(session.g, member + 0x18),
                                       "mp": u16(session.g, member + 0x1C)}
                shot = root / f"{tag}.png"
                session.screenshot(str(shot))
                entry["screenshot"] = str(shot)
                result["phases"].append(entry)
                (root / "probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
                print(json.dumps(entry), flush=True)
                session.g.cont()

            phase("00-initial")
            for i, name in enumerate(route, 1):
                hits = probe.press(KEYS[name], tag=f"a6-research:{name}", pause=1.2)
                result["keys"].append({"key": name, "hits": hits})
                if hits < 1:
                    raise RuntimeError(f"key {name} was not delivered")
                phase(f"{i:02d}-{name}")
            if args.settle_end:
                probe.pump(args.settle_end, "a6-settle", sample_every=10.0)
                phase("99-settled")
            probe.disarm()
            result["writes"] = session.writes
            result["key_writes"] = probe.key_write_log
            result["status"] = "observed"
    except Exception as exc:
        result["error"] = repr(exc)
        raise
    finally:
        (root / "probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
