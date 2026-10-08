"""Guarded Life research stages, with an explicit single-cast opt-in.

Independent research path. No final-confirmation, targeting-legality or revival
authority follows from capturing bytes alone. Final cast input requires the
separate single-attempt target/policy gate; existing Cure readers are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession
from probe_recovery_ko_lifecycle import source_dependencies
from recovery_menu import require
from recovery_transport import RecoveryTransport
from recovery_life_trace import LifeExecutionProbe
from life_recovery_transaction import drive_life_transaction
from tactics_policy import load_policy_file


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--scenario', default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--move-to-KO', action='store_true')
    ap.add_argument('--accept-target', action='store_true',
                    help='One guarded KO target-selection A only; never confirms a cast')
    ap.add_argument('--inspect-final-prompt', action='store_true',
                    help='Advance the guarded Life preview once, then stop before final cast input')
    ap.add_argument('--execute-Life', action='store_true',
                    help='One gated research cast; Wait requires its separate explicit option')
    ap.add_argument('--policy', default='configs/tactics/healer.json')
    ap.add_argument('--inspect-Wait', action='store_true',help='After Life, select enabled Wait; stop at facing')
    ap.add_argument('--execute-Wait', action='store_true',help='After Life, confirm one owned Wait and observe next actor')
    ap.add_argument('--stop-at-stage',choices=('navigation','Life-final','Wait-final'),
                    help='Drop the real STOP file at a named research boundary')
    ap.add_argument('--expect-reserve-refusal',action='store_true',help='Capture a policy refusal as the intended result')
    args = ap.parse_args()
    require(not (args.inspect_Wait or args.execute_Wait) or args.execute_Life,'Wait requires the single Life cast')
    require(args.stop_at_stage!='Wait-final' or args.execute_Wait,'Wait STOP requires explicit Wait execution')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths = [args.state, args.rom, args.scenario, args.policy] + source_dependencies('probe_recovery_life_overlay')
    result = {'status': 'unknown', 'scope': __doc__, 'source_sha256': {p: sha(p) for p in paths},
              'raw_writes': [], 'navigation': [], 'phases': [], 'target_acceptance': False,
              'final_confirmation': False}
    policy = load_policy_file(args.policy)
    result['policy_document'] = json.loads(Path(args.policy).read_text())
    expect = json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    probe = None
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out/'session')) as session:
            probe = LifeExecutionProbe(session, verbose=False)
            probe.life_log_path = str(out/'Life-engine.jsonl')
            owner = verified_owner(session, probe)
            result.update(pid=session.pid, owner=owner)
            with RecoveryTransport(probe, log_input=result['raw_writes'].append) as transport:
                drive_life_transaction(session,probe,owner,transport,policy,args,out,result)
            session.screenshot(str(out/'Life-overlay.png'))
            probe.disarm(strict=True)
            require(not session.writes, 'Life overlay research wrote unit RAM')
        result['status'] = ('observed-Life-Wait-continuation' if args.execute_Wait else
                            'observed-Life-and-Wait-facing-only' if args.inspect_Wait else
                            'observed-Life-effect-only' if args.execute_Life else
                            'captured-Life-final-prompt-only' if args.inspect_final_prompt else
                            'captured-Life-target-selection-only' if args.accept_target else
                            'captured-Life-KO-cursor-only' if args.move_to_KO else 'captured-Life-overlay-only')
    except BaseException as exc:
        result['error'] = repr(exc)
        if result.get('STOP_observed') and 'STOP observed;' in str(exc):
            require(len(probe.key_write_log)==result['STOP_observed']['input_write_count'],
                    'input was written after STOP')
            result['status']='observed-STOP-refusal'
        elif (args.expect_reserve_refusal and str(exc)=='policy declined Life; no final input'
              and not result['final_confirmation']):
            result['status']='observed-policy-reserve-refusal'
        else:raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe, 'key_write_log', []), fixture_writes=probe.s.writes,
                          life_engine_hits=probe.life_hits,life_engine_errors=probe.life_errors)
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'Life-overlay.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'])


if __name__ == '__main__':
    main()
