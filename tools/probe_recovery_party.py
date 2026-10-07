"""Read-only A6.2 party baseline on an owned eight-unit fixture.

No gameplay key, fixture RAM edit or state export is performed. This captures
the independent pre-targeting joins; it does not identify a modal ally target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter, IdentityError
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, exact, integer, require
from recovery_transport import RecoveryTransport
from recovery_party import pin_party


def block(g, address, size):
    # mGBA 0.10.5 drops larger RSP memory replies. Never accept a prefix.
    return b"".join(exact(g, address + offset, min(0x200, size - offset))
                    for offset in range(0, size, 0x200))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="outputs/lua-nav/a4-multi-ally-battle-start.ss0")
    parser.add_argument("--scenario", default="configs/battle-scenarios/a4-two-player.json")
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    files = [args.state, args.rom, args.scenario] + ["tools/" + name for name in (
        "probe_recovery_party.py", "recovery_party.py", "autobattle_identity.py", "fixture_guard.py",
        "probe_control_handoff.py", "recovery_menu.py", "recovery_transport.py")]
    hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
    result = {"schema": "ffta-recovery-party-baseline/1", "status": "unknown",
              "scope": __doc__, "source_sha256": hashes, "gameplay_keys": [],
              "target_identity": "unknown; no targeting entered"}
    scenario = json.loads(Path(args.scenario).read_text())
    expect = dict(scenario["guard_expectations"])
    expect["slot0_name"] = int(expect["slot0_name"], 0)
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out / "session")) as session:
            result["pid"] = session.pid
            probe = Probe(session, verbose=False)
            adapter = ActorAdapter(session)
            owner = None
            deadline = time.monotonic() + 100
            while owner is None and time.monotonic() < deadline:
                probe.pump(2, "party-baseline", sample_every=60)
                try:
                    owner = adapter.observe(probe, adapter.snapshot())
                except IdentityError as exc:
                    adapter.prior = None
                    result.setdefault("passive_rejections", []).append(str(exc))
            require(owner is not None, "no independently verified fresh owner")
            adapter.revalidate(owner, probe)
            result["owner"] = owner
            with RecoveryTransport(probe) as transport:
                g = transport.g
                roster = block(g, ROSTER, 8 * STRIDE)
                members = block(g, MEMBERS, MEMBER_COUNT * STRIDE)
                context_bytes = exact(g, MENU_ROOT, 4)
                context = integer(context_bytes, 0)
                root = exact(g, context, 0x30)
                driver = exact(g, PLAYER_DRIVER, 0xE0)
                wrapper = integer(driver, 4)
                wrapper_data = exact(g, wrapper, 0x10)
                rows = adapter.expected
                rom = session.read_rom_bytes()
                names = {}
                def read_name(address):
                    if 0x08000000 <= address and address + 32 <= 0x08000000 + len(rom):
                        data = rom[address - 0x08000000:address - 0x08000000 + 32]
                    else:
                        data = exact(g, address, 32)
                    names[address] = data
                    return data
                pins = pin_party(roster, members, rows, read_name)
                for address, data in names.items():
                    path = out / f"name-{address:08x}.bin"
                    path.write_bytes(data)
                    result.setdefault("capture_sha256", {})[path.name] = hashlib.sha256(data).hexdigest()
                caster = next(p for p in pins if p["id"] == owner["id"])
                require(integer(root, 0x18) == caster["canonical"] == integer(wrapper_data, 0)
                        and integer(driver, 4) == integer(driver, 8), "menu/driver caster mismatch")
                for address, data in [(ROSTER, roster), (MEMBERS, members), (MENU_ROOT, context_bytes),
                                      (context, root), (PLAYER_DRIVER, driver), (wrapper, wrapper_data)]:
                    require(block(g, address, len(data)) == data, "halted party capture changed")
                    path = out / f"{address:08x}.bin"
                    path.write_bytes(data)
                    result.setdefault("capture_sha256", {})[path.name] = hashlib.sha256(data).hexdigest()
                result.update(party=pins, expected_party=rows, menu={"context": context, "mode": root[4],
                              "member": integer(root, 0x18), "peer": integer(root, 0x1C),
                              "wrapper": wrapper}, transport=transport.events)
            result["gameplay_writes"] = list(getattr(probe, "key_write_log", []))
            require(not result["gameplay_writes"], "read-only baseline unexpectedly wrote a gameplay key")
            result["fixture_writes"] = list(session.writes)
            session.screenshot(str(out / "party-baseline.png"))
        result["status"] = "pass-pre-targeting-baseline"
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        result["inputs_unchanged"] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
        (out / "baseline.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS read-only party baseline; ally target remains unknown")


if __name__ == "__main__":
    main()
