"""Guard ally Cure, Wait and independent next-actor attribution on a fresh reload."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter
from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, ROSTER, STRIDE, read_roster
from probe_control_handoff import Probe
from probe_recovery_party import block
from recovery_menu import RecoveryMenu, MEMBERS, MEMBER_COUNT, exact, require, RecoveryStateError
from recovery_party_continuation import observe_party_continuation
from recovery_party import pin_party
from recovery_transport import RecoveryTransport
from recovery_ally_confirmation import AllyConfirmationReader
from recovery_ally_executor import AllyCureExecutor
from recovery_executor import WaitFacingExecutor, RecoveryStopped
from tactics_policy import load_policy_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state",default="outputs/autobattle/a62-party-fixture-01/party-recovery.ss0")
    parser.add_argument("--policy",default="configs/tactics/healer.json")
    parser.add_argument("--out",required=True)
    parser.add_argument("--stop-file")
    args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    files=[args.state,args.policy,"baserom.gba","configs/battle-scenarios/a4-two-player.json"]
    files += ["tools/"+name for name in ("probe_recovery_ally_turn.py","recovery_party_continuation.py","recovery_ally_executor.py",
        "recovery_ally_confirmation.py","recovery_ally_preview.py","recovery_ally_target.py",
        "recovery_executor.py","recovery_menu.py","recovery_transport.py","recovery_party.py",
        "probe_recovery_party.py","build_recovery_fixture.py","autobattle_identity.py",
        "fixture_guard.py","probe_control_handoff.py","tactics_policy.py","ability_resources.py","trace_mgba.py")]
    hashes={p:sha(p) for p in files}
    result={"status":"unknown","scope":__doc__,"source_sha256":hashes,"raw_writes":[],
            "verified_turns":0,"continuation":"unknown","finish_turn":True,"continuations":[]}
    policy=load_policy_file(args.policy)
    result["policy_document"]=json.loads(Path(args.policy).read_text())
    expect=json.loads(Path("configs/battle-scenarios/a4-two-player.json").read_text())["guard_expectations"]
    expect["slot0_name"]=int(expect["slot0_name"],0)
    def stopped():
        if args.stop_file and Path(args.stop_file).exists():
            result.setdefault("stop_requested_at",time.monotonic())
            result.setdefault("stop_raw_write_count",len(result["raw_writes"]))
            return True
        return False
    try:
        with FixtureSession(args.state,expect=expect,quiet=True,work_dir=str(out/"session")) as session:
            session.g.sock.settimeout(1.0)
            probe=Probe(session,verbose=False)
            owner=verified_owner(session,probe)
            result.update(pid=session.pid,owner=owner)
            with RecoveryTransport(probe,log_input=result["raw_writes"].append) as transport:
                result["transport"]=transport.events
                g,rom=transport.g,session.read_rom_bytes()
                def read_name(address):
                    if 0x08000000 <= address and address+32 <= 0x08000000+len(rom):
                        return rom[address-0x08000000:address-0x08000000+32]
                    return exact(g,address,32)
                pins=pin_party(block(g,ROSTER,8*STRIDE),block(g,MEMBERS,MEMBER_COUNT*STRIDE),
                               ActorAdapter(session).expected,read_name)
                units={p["canonical"]:exact(g,p["canonical"],STRIDE) for p in pins}
                result["party_before"]=pins
                result["baseline_roster"]=[r for r in read_roster(g,rom=rom)['slots'] if r['live']]
                menu=RecoveryMenu(g,rom,owner)
                reader=AllyConfirmationReader(g,menu,pins,units)
                def settle(name):
                    if stopped():raise RecoveryStopped("STOP after research input")
                    transport.cont();time.sleep(0.25)
                def capture(tag):
                    (out/f"{tag}-ewram.bin").write_bytes(block(g,0x02000000,0x30000))
                    session.screenshot(str(out/f"{tag}.png"))
                def before_final(observation):
                    result["confirmation_observed_at"]=time.monotonic()
                    (out/"confirmation-marker.json").write_text(json.dumps({"pid":session.pid,"writes":len(result["raw_writes"])}))
                    capture("confirmation")
                capture("initial")
                executor=AllyCureExecutor(menu,transport,policy,reader,stop_check=stopped,
                                         after_key=settle,before_policy_final=before_final)
                result["events"]=executor.events
                result["recovery"]=executor.run()
                capture("after-cure")
                wait=WaitFacingExecutor(menu,transport,policy,stop_check=stopped,after_key=settle,
                                        before_policy_final=lambda observation:capture("facing"))
                result["wait_events"]=wait.events
                result["wait"]=wait.run()
                require(result['wait']['outcome'] == 'confirmed','Wait remains unexecuted')
                capture("after-wait")
                deadline=time.monotonic()+25
                while time.monotonic() < deadline:
                    if stopped():raise RecoveryStopped("STOP during continuation")
                    transport.cont();time.sleep(0.25);transport.interrupt()
                    try:
                        observed=observe_party_continuation(g,rom,owner,result['wait']['facing'],
                                                           pins,units,result['baseline_roster'])
                    except RecoveryStateError as exc:
                        result.setdefault('continuation_rejections',[]).append(str(exc));continue
                    result['continuations'].append(observed)
                    capture('continuation')
                    result.update(verified_turns=1,continuation='independent-next-actor')
                    break
                require(result['verified_turns'] == 1,'independent eight-unit continuation not established')
                result["fixture_writes"]=list(session.writes)
            result["status"]="observed-effect-wait-and-next-actor"
    except Exception as exc:
        result["error"]=repr(exc)
        raise
    finally:
        result["inputs_unchanged"]=all(sha(p)==h for p,h in hashes.items())
        result["capture_sha256"]={p.name:sha(p) for p in out.glob("*.bin")}
        (out/"probe.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(result["status"])


if __name__=="__main__":main()
