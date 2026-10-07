"""Construct a NEW local A6.2 party fixture; construction is not gameplay.

Never modifies the original ROM/save/state. Both canonical and battle copies
are ledgered; owned-window export is independently reloaded by the party probe.
No Cure or gameplay key is executed by this builder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from autobattle_identity import ActorAdapter, IdentityError
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, RecoveryMenu, exact, require
from recovery_party import pin_party
from recovery_transport import RecoveryTransport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="outputs/lua-nav/a4-multi-ally-battle-start.ss0")
    parser.add_argument("--scenario", default="configs/battle-scenarios/a4-two-player.json")
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    paths = [args.state, args.scenario, args.rom] + ["tools/" + name for name in (
        "build_party_recovery_fixture.py", "probe_recovery_party.py", "recovery_party.py",
        "recovery_menu.py", "recovery_transport.py", "save_owned_mgba_state.ps1",
        "autobattle_identity.py", "fixture_guard.py", "probe_control_handoff.py")]
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    hashes = {p: sha(p) for p in paths}
    result = {"status": "unknown", "scope": __doc__, "source_sha256": hashes}
    expect = json.loads(Path(args.scenario).read_text())["guard_expectations"]
    expect["slot0_name"] = int(expect["slot0_name"], 0)
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out / "session")) as session:
            probe, owner = Probe(session, verbose=False), None
            adapter = ActorAdapter(session)
            deadline = time.monotonic() + 100
            while owner is None and time.monotonic() < deadline:
                probe.pump(2, "party-construction", sample_every=60)
                try:
                    owner = adapter.observe(probe, adapter.snapshot())
                except IdentityError:
                    adapter.prior = None
            require(owner is not None and owner["id"] == 7, "construction caster differs")
            adapter.revalidate(owner, probe)
            rom = session.read_rom_bytes()
            with RecoveryTransport(probe) as transport:
                g = transport.g
                def read_name(address):
                    if 0x08000000 <= address and address + 32 <= 0x08000000 + len(rom):
                        return rom[address-0x08000000:address-0x08000000+32]
                    return exact(g, address, 32)
                pins = pin_party(block(g, ROSTER, 8*STRIDE), block(g, MEMBERS, MEMBER_COUNT*STRIDE),
                                 adapter.expected, read_name)
                caster = next(p for p in pins if p["id"] == 7)
                ally = next(p for p in pins if p["id"] == 5)
                require(ally["max_hp"] == 241 and caster["mp"] >= 14, "construction resources differ")
                require(RecoveryMenu(g, rom, owner).snapshot().state == "command", "caster menu not owned")
                for base in (caster["canonical"], ROSTER + caster["slot"]*STRIDE):
                    session.write_u8(base+8, 7, "A6.2 scratch caster secondary White Mage")
                for base in (ally["canonical"], ROSTER + ally["slot"]*STRIDE):
                    session.write_bytes(base+0x18, (100).to_bytes(2,"little"), "A6.2 scratch living ally HP")
                result.update(pid=session.pid, before=pins, writes=list(session.writes))
            halt = session.g.interrupt()
            require(halt and halt[:1] in ("S", "T") and halt[:3] not in ("S04", "T04"), "export halt failed")
            probe.disarm(strict=True)
            session.g.cont()
            slot = Path(session.work_paths["rom"]).with_suffix(".ss2")
            require(not slot.exists(), "scratch export slot already exists")
            sent = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File",
                                   "tools/save_owned_mgba_state.ps1", "-ProcId", str(session.pid)],
                                  capture_output=True, text=True, timeout=40, creationflags=subprocess.CREATE_NO_WINDOW)
            require(sent.returncode == 0, "owned export failed: " + sent.stdout + sent.stderr)
            result["save_hotkey"] = sent.stdout.strip()
            deadline, previous = time.monotonic()+12, None
            while time.monotonic() < deadline:
                size = slot.stat().st_size if slot.exists() else 0
                if size > 40000 and size == previous:
                    break
                previous = size
                time.sleep(0.1)
            require(slot.exists() and slot.stat().st_size > 40000, "export absent or short")
            state = out / "party-recovery.ss0"
            with state.open("xb") as handle:
                handle.write(slot.read_bytes())
            result["state_sha256"] = sha(state)
            require(not getattr(probe, "key_write_log", []), "construction delivered gameplay keys")
        subprocess.run([sys.executable, "tools/probe_recovery_party.py", "--state", str(state),
                        "--scenario", args.scenario, "--rom", args.rom, "--out", str(out / "reload")], check=True)
        reloaded = json.loads((out / "reload/baseline.json").read_text())
        caster = next(p for p in reloaded["party"] if p["id"] == 7)
        ally = next(p for p in reloaded["party"] if p["id"] == 5)
        require(caster["secondary_job"] == 7 and caster["mp"] == 85 and ally["hp"] == 100,
                "independent reload differs from constructed resources")
        result["status"] = "pass-construction-and-independent-reload"
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        result["inputs_unchanged"] = all(sha(p) == h for p,h in hashes.items())
        (out / "fixture.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print("PASS party fixture construction/reload; target legality remains unknown")


if __name__ == "__main__":
    main()
