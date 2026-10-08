"""Prepare a disposable Life fixture only from an audited genuine engine KO.

Preserves the KO target byte-for-byte. Ledgers the living caster's positive HP
and secondary White Mage setup; independently reloads the exported state.
Construction is not engine availability, target acceptance or revival proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from autobattle_identity import ActorAdapter
from audit_recovery_ko_observations import audit
from build_recovery_fixture import verified_owner
from emulate import Gba, STOP
from unicorn.arm_const import UC_ARM_REG_PC
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import joined_party, export_owned_state, source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, exact, require
from recovery_menu_list import ResearchMenuList
from recovery_transport import RecoveryTransport


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine-run', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--scenario', default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--rebuild-ability-state', action='store_true',
                    help='Rebuild primary/secondary ability-set bytes through the native job accessor')
    args = ap.parse_args()
    engine = json.loads((Path(args.engine_run)/'research.json').read_text())
    proof = audit(args.engine_run)
    require(engine['status'] == 'observed-KO-candidate' and proof['interactive_KO_loop_skips']
            and proof['native_HP_zero_stores'], 'genuine KO lifecycle prerequisite missing')
    state = engine['export']['path']
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths = [state, args.rom, args.scenario, str(Path(args.engine_run)/'research.json')] + source_dependencies('build_life_recovery_fixture')
    result = {'status': 'unknown', 'scope': __doc__, 'source_sha256': {p: sha(p) for p in paths},
              'engine_run': args.engine_run, 'engine_KO_target': engine['ko_target_id']}
    expect = json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    try:
        with FixtureSession(state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out/'build-session')) as session:
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            adapter = ActorAdapter(session)
            with RecoveryTransport(probe) as transport:
                party = joined_party(block(transport.g, ROSTER, 8*STRIDE),
                                     block(transport.g, MEMBERS, MEMBER_COUNT*STRIDE), adapter.expected)
                caster = next(p for p in party if p['id'] == owner['id'])
                target = next(p for p in party if p['id'] != owner['id'])
                require(target['id'] == engine['ko_target_id'] and target['hp'] == 0
                        and caster['hp'] > 0 and not any(target['statuses'].values()), 'KO fixture differs')
                require(ResearchMenuList(transport.g, session.read_rom_bytes(), owner, caster['canonical']).snapshot().state == 'command',
                        'construction lacks an owned command menu')
                target_before = exact(transport.g, target['canonical'], STRIDE)
                caster_before = exact(transport.g, caster['canonical'], STRIDE)
                ability_state = None
                if args.rebuild_ability_state:
                    gba = Gba(args.rom)
                    primary = gba.call(0x080C8570, [caster_before[5], caster_before[7], 0x0C])
                    require(gba.uc.reg_read(UC_ARM_REG_PC) == STOP, 'primary accessor did not return')
                    secondary = gba.call(0x080C8570, [7, 7, 0x0C])
                    require(gba.uc.reg_read(UC_ARM_REG_PC) == STOP and 0 < primary < 256
                            and secondary == 9, 'native ability-set property differs')
                    ability_state = bytes((primary, secondary))
                    result['ability_state_rebuild'] = {
                        'accessor': '080c8570', 'property': 12,
                        'before': list(caster_before[0x35:0x37]), 'after': list(ability_state)}
                for address in (caster['canonical'], ROSTER+caster['slot']*STRIDE):
                    session.write_u8(address+8, 7, 'A6.4 living caster secondary White Mage; KO target untouched')
                    if ability_state is not None:
                        session.write_bytes(address+0x35, ability_state,
                                            'A6.4 native primary/secondary ability-set reconstruction')
                    session.write_bytes(address+0x18, caster['max_hp'].to_bytes(2, 'little'),
                                        'A6.4 living caster positive HP restore; KO target untouched')
                require(exact(transport.g, target['canonical'], STRIDE) == target_before,
                        'construction changed the genuine KO target')
                require(all(w['reply'] == 'OK' and w['new'] == w['requested'] for w in session.writes),
                        'construction write not verified')
                result.update(before=party, writes=session.writes, pid=session.pid,
                              target_sha256=hashlib.sha256(target_before).hexdigest())
            fixture = out/'life-recovery.ss0'
            result['export'] = export_owned_state(session, probe, fixture)
            require(not getattr(probe, 'key_write_log', []), 'construction sent gameplay input')
        subprocess.run([sys.executable, 'tools/probe_recovery_ko_reload.py', '--state', str(fixture),
                        '--rom', args.rom, '--scenario', args.scenario, '--out', str(out/'reload')], check=True)
        reload = json.loads((out/'reload/reload.json').read_text())
        require(reload['status'] == 'pass-independent-KO-command-reload' and reload['inputs_unchanged'], 'Life fixture reload failed')
        target = next(p for p in reload['party'] if p['id'] == engine['ko_target_id'])
        caster = next(p for p in reload['party'] if p['id'] != engine['ko_target_id'])
        require(target['hp'] == 0 and caster['hp'] == caster['max_hp'], 'Life fixture reload resources differ')
        if ability_state is not None:
            capture = (out/'reload'/f'{MEMBERS:08x}.bin').read_bytes()
            offset = caster['canonical']-MEMBERS
            require(capture[offset+0x35:offset+0x37] == ability_state,
                    'independent reload lost the reconstructed ability-state')
        result['status'] = 'pass-Life-fixture-construction-and-reload'
    except BaseException as exc:
        result['error'] = repr(exc)
        raise
    finally:
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'fixture.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'])


if __name__ == '__main__':
    main()
