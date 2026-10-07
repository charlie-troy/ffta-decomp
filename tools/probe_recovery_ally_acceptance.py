"""Observe one guarded ally target-selection step; NEVER cast.

Research navigation only. Public self-only guards are preserved. After the
single RIGHT and target-selection A, read raw facts and terminate the owned session.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, BATTLE_STRUCT, ROSTER, STRIDE
from probe_control_handoff import Probe, TARGET_X
from probe_recovery_party import block
from recovery_menu import RecoveryMenu, exact, integer, PLAYER_DRIVER, MEMBERS, MEMBER_COUNT, MENU_ROOT
from recovery_party import pin_party
from autobattle_identity import ActorAdapter
from recovery_ally_target import AllyOverlayReader, ACCEPTANCE_CURSOR
from dataclasses import asdict
from recovery_executor import SelfCureExecutor
from recovery_transport import RecoveryTransport
from tactics_policy import load_policy_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="outputs/autobattle/a62-party-fixture-01/party-recovery.ss0")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    files = [args.state, "baserom.gba", "configs/battle-scenarios/a4-two-player.json"] + ["tools/"+name for name in (
        "probe_recovery_ally_acceptance.py", "recovery_ally_target.py", "recovery_party.py", "recovery_executor.py", "recovery_menu.py", "recovery_transport.py",
        "probe_control_handoff.py", "fixture_guard.py", "build_recovery_fixture.py", "probe_recovery_party.py")]
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    hashes = {p: sha(p) for p in files}
    result = {"status": "unknown", "scope": __doc__, "source_sha256": hashes,
              "raw_writes": [], "final_confirmation": False, "phases": []}
    expect = json.loads(Path("configs/battle-scenarios/a4-two-player.json").read_text())["guard_expectations"]
    expect["slot0_name"] = int(expect["slot0_name"], 0)
    try:
        with FixtureSession(args.state, expect=expect, quiet=True, work_dir=str(out / "session")) as session:
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            result.update(pid=session.pid, owner=owner)
            with RecoveryTransport(probe, log_input=result["raw_writes"].append) as transport:
                g = transport.g
                rom = session.read_rom_bytes()
                rows = ActorAdapter(session).expected
                def read_name(address):
                    if 0x08000000 <= address and address + 32 <= 0x08000000+len(rom):
                        return rom[address-0x08000000:address-0x08000000+32]
                    return exact(g,address,32)
                pins = pin_party(block(g,ROSTER,8*STRIDE),block(g,MEMBERS,MEMBER_COUNT*STRIDE),rows,read_name)
                units = {p["canonical"]:exact(g,p["canonical"],STRIDE) for p in pins}
                result["party_pins"] = pins
                menu = RecoveryMenu(g,rom,owner)
                reader = AllyOverlayReader(g,menu,pins,units)
                def settle(name):
                    transport.cont()
                    time.sleep(0.25)
                executor = SelfCureExecutor(menu, transport, load_policy_file("configs/tactics/healer.json"), after_key=settle)
                result["navigation"] = executor.events
                assert executor.select("command", 9)
                assert executor.select("action-group", 10)
                assert executor.select("ability-list", 1, ability=True)
                overlay = executor.observe("target-overlay")
                def capture(tag):
                    g = transport.g
                    processor = integer(exact(g, PLAYER_DRIVER+0x60, 4), 0)
                    assert processor == BATTLE_STRUCT
                    data = block(g, processor, 0x1120)
                    cursor = list(exact(g, TARGET_X, 2))
                    acceptance = [integer(exact(g,ACCEPTANCE_CURSOR+offset,2),0,2) for offset in (0,4)]
                    context = integer(exact(g,MENU_ROOT,4),0)
                    root = exact(g,context,0x30)
                    callback = integer(root,0x28)
                    callback_data = exact(g,callback,0x18)
                    for name,payload in [("root",root),("callback",callback_data)]:
                        (out/f"{tag}-{name}.bin").write_bytes(payload)
                    wrappers = []
                    count = data[0xA2]
                    assert 0 < count <= 20
                    for i in range(count):
                        address = integer(data, 0x50+4*i)
                        wrapper = exact(g, address, 0x30)
                        member = integer(wrapper, 0)
                        unit = exact(g, member, 0x108)
                        for name, payload in [(f"wrapper-{address:08x}", wrapper), (f"unit-{member:08x}", unit)]:
                            path=out/f"{tag}-{name}.bin"; path.write_bytes(payload)
                        wrappers.append({"wrapper": address, "canonical": member, "name": integer(unit,0),
                                         "id": unit[0x104], "hp": integer(unit,0x18,2), "tile":list(unit[0xF6:0xF8])})
                    path=out/f"{tag}-processor.bin"; path.write_bytes(data)
                    result["phases"].append({"tag":tag,"cursor":cursor,"acceptance_coordinates":acceptance,
                                             "root_peer":integer(root,0x1C),"root_member":integer(root,0x18),
                                             "root_mode":root[4],"handler":integer(callback_data,0),
                                             "controller_state":integer(callback_data,0x14,2),
                                             "target_state":integer(data,0x1118,2),"target_flags":integer(data,0x1112,2),
                                             "index":data[0xA1],"count":count,
                                             "selected_copies":[integer(data,12),integer(data,16)],"wrappers":wrappers,
                                             "processor_sha256":hashlib.sha256(data).hexdigest()})
                capture("before")
                menu.revalidate(overlay)
                hits=transport.press(0x10, tag="a62-research-single-RIGHT")
                assert hits > 0
                settle("RIGHT")
                capture("after")
                token = reader.snapshot()
                result["ally_overlay_token"] = asdict(token)
                reader.revalidate(token)
                result["target_selection_requested"] = True
                hits = transport.press(1,tag="a62-research-single-target-selection-A")
                assert hits > 0
                result["target_selection_delivered"] = True
                settle("A")
                time.sleep(0.75)
                capture("selected")
                # No input follows these observations, including on rejection.
                result["transport"] = transport.events
            session.screenshot(str(out/"overlay-after.png"))
        result["status"] = "captured-target-selection-only"
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        result["inputs_unchanged"] = all(sha(p)==h for p,h in hashes.items())
        result["capture_sha256"] = {p.name:sha(p) for p in out.glob("*.bin")}
        (out/"probe.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print("Captured target-selection step only; final Cure remains unknown")


if __name__ == "__main__":
    main()
