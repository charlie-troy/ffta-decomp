"""Build and reload a disposable self-Cure fixture for the real public CLI.

Edits only copied-session RAM, exports a NEW local state with the existing
owned-window save hotkey, and verifies a fresh reload. Never edits the source
ROM, save or state. Construction is not an engine action or legal Cure proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from autobattle_identity import ActorAdapter
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from recovery_menu import RecoveryMenu, require
from recovery_transport import RecoveryTransport


def verified_owner(session, probe):
    adapter = ActorAdapter(session)
    owner = None
    for _ in range(2):
        probe.pump(2.0, "recovery-fixture-owner", sample_every=60)
        owner = adapter.observe(probe, adapter.snapshot())
    require(owner is not None, "fixture has no independently verified fresh owner")
    probe.active_player_slot = owner["slot"]
    adapter.revalidate(owner, probe)
    return owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="outputs/lua-nav/battle-start.ss0")
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    parser.add_argument("--hp", type=int, default=100)
    parser.add_argument("--mp", type=int, default=85)
    args = parser.parse_args()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    state = output / "recovery.ss0"
    result = {"scope": __doc__, "status": "unknown", "source_state": args.state,
              "source_sha256": hashlib.sha256(Path(args.state).read_bytes()).hexdigest(),
              "constructed": {"hp": args.hp, "mp": args.mp, "secondary_job": 7}}
    try:
        with FixtureSession(args.state, rom=args.rom, quiet=True, work_dir=str(output / "build-session")) as session:
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            require(0 < args.hp <= owner["max_hp"] and 0 <= args.mp <= owner["max_mp"], "fixture resource bounds")
            with RecoveryTransport(probe) as transport:
                menu = RecoveryMenu(transport.g, session.read_rom_bytes(), owner)
                require(menu.snapshot().state == "command", "fixture is not at command menu")
                for base in (ROSTER + STRIDE * owner["slot"], menu.member):
                    session.write_u8(base + 8, 7, "disposable recovery fixture: secondary White Mage")
                    session.write_bytes(base + 0x18, args.hp.to_bytes(2, "little"), "disposable recovery fixture: HP")
                    session.write_bytes(base + 0x1C, args.mp.to_bytes(2, "little"), "disposable recovery fixture: MP")
                result["writes"] = list(session.writes)
            halt = session.g.interrupt()
            require(halt and halt[:1] in ("S", "T") and halt != "S04", "export halt not established")
            probe.disarm(strict=True)
            session.g.cont()
            session.screenshot(str(output / "before-export.png"))
            slot = Path(session.work_paths["rom"]).with_suffix(".ss2")
            require(not slot.exists(), "refusing a pre-existing scratch state slot")
            command = ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File",
                       "tools/save_owned_mgba_state.ps1", "-ProcId", str(session.pid)]
            sent = subprocess.run(command, capture_output=True, text=True, timeout=40,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            require(sent.returncode == 0, "owned-window state export failed: " + sent.stdout + sent.stderr)
            result["save_hotkey"] = {"pid": session.pid, "output": sent.stdout.strip(),
                                     "scope": "emulator state export only; no gameplay key injection"}
            session.screenshot(str(output / "after-export.png"))
            deadline = time.monotonic() + 12
            previous_size = None
            while time.monotonic() < deadline:
                current_size = slot.stat().st_size if slot.exists() else None
                if current_size is not None and current_size > 40000 and current_size == previous_size:
                    break
                previous_size = current_size
                time.sleep(0.1)
            require(slot.exists() and slot.stat().st_size > 40000, "state export absent or short")
            payload = slot.read_bytes()
            with state.open("xb") as handle:
                handle.write(payload)
        with FixtureSession(str(state), rom=args.rom, quiet=True, work_dir=str(output / "reload-session")) as session:
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            with RecoveryTransport(probe) as transport:
                menu = RecoveryMenu(transport.g, session.read_rom_bytes(), owner)
                facts = menu.snapshot()
                require(facts.state == "command" and menu.identity[6] == 7
                        and (facts.hp, facts.mp) == (args.hp, args.mp), "fresh fixture reload differs")
                result["reload"] = {"owner": owner, "canonical": menu.member, "menu": facts.receipt()}
            session.screenshot(str(output / "reloaded.png"))
        result["fixture"] = str(state)
        result["fixture_sha256"] = hashlib.sha256(state.read_bytes()).hexdigest()
        result["status"] = "verified-constructed-fixture"
    except BaseException as exc:
        result["error"] = repr(exc)
        raise
    finally:
        (output / "fixture.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Verified disposable fixture: {state}")


if __name__ == "__main__":
    main()
