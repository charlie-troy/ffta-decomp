"""Research enabled Life and effective cost on a reloaded genuine KO fixture.

Reuses only the proven command/group/list reader. Stops before selecting Life,
so this does not claim a Life target, preview, final prompt or revival.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from ability_resources import effective_mp_cost
from build_recovery_fixture import verified_owner
from emulate import Gba
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import joined_party, source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, RecoveryMenu, RecoveryTransient, exact, require
from recovery_transport import RecoveryTransport
from recovery_menu_list import ResearchMenuList


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--scenario', default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--group-row', type=int, help='Explicit research Action-group row; identified before input')
    ap.add_argument('--inspect-groups', action='store_true', help='Capture Action groups without selecting one')
    args = ap.parse_args()
    require(args.inspect_groups or args.group_row is not None, 'select an explicit group row or inspect groups first')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths = [args.state, args.rom, args.scenario] + source_dependencies('probe_recovery_life_menu')
    result = {'schema': 'ffta-Life-menu-research/1', 'status': 'unknown', 'scope': __doc__,
              'requested_group_row': args.group_row,
              'source_sha256': {p: sha(p) for p in paths}, 'observations': [], 'inputs': []}
    expect = json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    probe = None
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out/'session')) as session:
            result['pid'] = session.pid
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            with RecoveryTransport(probe) as transport:
                roster = block(transport.g, ROSTER, 8*STRIDE)
                members = block(transport.g, MEMBERS, MEMBER_COUNT*STRIDE)
                party = joined_party(roster, members, session.receipt['roster']['slots'][5:6]
                                     + session.receipt['roster']['slots'][7:8])
                target = next(p for p in party if p['id'] != owner['id'])
                caster = next(p for p in party if p['id'] == owner['id'])
                require(target['hp'] == 0 and caster['hp'] > 0
                        and not any(target['statuses'].values()), 'Life menu fixture identity/KO differs')
                result.update(owner=owner, party=party)
                menu = ResearchMenuList(transport.g, session.read_rom_bytes(), owner, caster['canonical'])
                def stopped():
                    require(not (out/'STOP').exists(), 'STOP observed; research input forbidden')
                    return False
                def observe(kind):
                    for _ in range(20):
                        stopped()
                        try:
                            token = menu.snapshot()
                            require(token.state == kind, f'expected {kind}; observed {token.state}')
                            result['observations'].append(token.receipt())
                            return token
                        except RecoveryTransient:
                            transport.cont()
                            time.sleep(0.25)
                        except (ValueError, AssertionError):
                            path = out/'rejected-menu-ewram.bin'
                            path.write_bytes(block(transport.g, 0x02000000, 0x40000))
                            result.setdefault('capture_sha256', {})[path.name] = sha(path)
                            raise
                    raise TimeoutError('Life list did not settle')
                def press(mask, token):
                    stopped()
                    menu.revalidate(token)
                    stopped()
                    hits = transport.press(mask, tag='a64-Life-list-only', stop_check=stopped)
                    require(hits == 5, 'Life list navigation input incomplete')
                    result['inputs'].append({'mask': mask, 'hits': hits, 'before': token.receipt()})
                def select(kind, row):
                    for _ in range(34):
                        token = observe(kind)
                        require(token.rows.count(row) == 1, 'navigation row missing/ambiguous')
                        index = token.rows.index(row)
                        require(token.enabled[index], 'navigation row disabled')
                        current = token.scroll+token.cursor
                        if current == index:
                            press(1, token)
                            return
                        press(0x80 if current < index else 0x40, token)
                    raise TimeoutError('Life list navigation exceeded bounds')
                before = observe('command')
                require(exact(transport.g, caster['canonical']+8, 1)[0] == 7, 'secondary White Mage required')
                select('command', 9)
                if args.inspect_groups:
                    token = observe('action-group')
                    result.update(status='pass-action-group-observation', menu=token.receipt())
                    path = out/'action-group-ewram.bin'
                    path.write_bytes(block(transport.g, 0x02000000, 0x40000))
                    result.setdefault('capture_sha256', {})[path.name] = sha(path)
                    session.screenshot(str(out/'action-groups.png'))
                    print(result['status'], token.rows)
                    return
                select('action-group', args.group_row)
                token = observe('ability-list')
                require(token.ability_ids.count(5) == 1, 'Life row missing or ambiguous')
                index = token.ability_ids.index(5)
                unit = exact(transport.g, caster['canonical'], STRIDE)
                cost = effective_mp_cost(session.read_rom_bytes(), 5, unit)
                gba = Gba(args.rom)
                gba.uc.mem_write(caster['canonical'], unit)
                actual = gba.call(0x0812ED98, [caster['canonical'], 5])
                require(actual == cost, 'Life cost reader differs from actual ROM accessor')
                for pin in party:
                    offset = pin['canonical']-MEMBERS
                    require(exact(transport.g, pin['canonical'], STRIDE) == members[offset:offset+STRIDE],
                            'party changed while observing Life menu')
                require((token.hp, token.mp) == (before.hp, before.mp), 'opening Life menu spent resources')
                for name, data in (('members', members), ('caster', unit),
                                   ('ewram', block(transport.g, 0x02000000, 0x40000))):
                    path = out/(name+'.bin')
                    path.write_bytes(data)
                    result.setdefault('capture_sha256', {})[path.name] = sha(path)
                result.update(party=party, menu=token.receipt(), life={'id': 5, 'index': index,
                    'enabled': bool(token.enabled[index]), 'effective_cost': cost,
                    'actual_ROM_cost': actual, 'cost_accessor': '0812ed98', 'caster_mp': token.mp},
                    gameplay_writes=getattr(probe, 'key_write_log', []), fixture_writes=session.writes)
                require(not session.writes, 'Life menu probe changed unit RAM')
            session.screenshot(str(out/'Life-list.png'))
            probe.disarm(strict=True)
        result['status'] = 'pass-enabled-Life-and-cost' if result['life']['enabled'] else 'observed-disabled-Life'
    except BaseException as exc:
        result['error'] = repr(exc)
        raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe, 'key_write_log', []), fixture_writes=probe.s.writes)
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'Life-menu.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'], result['life'])


if __name__ == '__main__':
    main()
