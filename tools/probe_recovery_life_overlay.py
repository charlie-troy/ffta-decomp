"""Open Life research targeting; optionally accept one guarded KO target.

Independent research path. No final-confirmation, targeting-legality or revival
authority follows from capturing these bytes. Never sends a final cast input;
existing Cure readers are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from ability_resources import effective_mp_cost
from autobattle_identity import ActorAdapter
from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, ROSTER, STRIDE, BATTLE_STRUCT
from probe_control_handoff import Probe, TARGET_X
from probe_recovery_ko_lifecycle import joined_party, source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, exact, integer, require, RecoveryTransient
from recovery_menu_list import ResearchMenuList
from recovery_life_target import LifeOverlayReader
from recovery_transport import RecoveryTransport


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
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths = [args.state, args.rom, args.scenario] + source_dependencies('probe_recovery_life_overlay')
    result = {'status': 'unknown', 'scope': __doc__, 'source_sha256': {p: sha(p) for p in paths},
              'raw_writes': [], 'navigation': [], 'phases': [], 'target_acceptance': False,
              'final_confirmation': False}
    expect = json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    probe = None
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out/'session')) as session:
            probe = Probe(session, verbose=False)
            owner = verified_owner(session, probe)
            result.update(pid=session.pid, owner=owner)
            with RecoveryTransport(probe, log_input=result['raw_writes'].append) as transport:
                g, rom = transport.g, session.read_rom_bytes()
                party = joined_party(block(g, ROSTER, 8*STRIDE),
                                     block(g, MEMBERS, MEMBER_COUNT*STRIDE), ActorAdapter(session).expected)
                caster = next(p for p in party if p['id'] == owner['id'])
                target = next(p for p in party if p['id'] != owner['id'])
                require(owner['id'] == 5 and target['id'] == 7 and target['hp'] == 0
                        and caster['hp'] > 0 and not any(target['statuses'].values()), 'Life fixture differs')
                units = {p['canonical']: exact(g, p['canonical'], STRIDE) for p in party}
                result['party'] = party
                menu = ResearchMenuList(g, rom, owner, caster['canonical'])
                overlay_reader = LifeOverlayReader(g, menu, party, units)
                def stopped():
                    require(not (out/'STOP').exists(), 'STOP observed; Life research input forbidden')
                    return False
                def observe(kind):
                    for _ in range(24):
                        stopped()
                        try:
                            token = menu.snapshot()
                            require(token.state == kind, f'expected {kind}, got {token.state}')
                            return token
                        except RecoveryTransient:
                            transport.cont()
                            time.sleep(0.25)
                    raise TimeoutError('Life list did not settle')
                def press(mask, token):
                    stopped()
                    menu.revalidate(token)
                    stopped()
                    hits = transport.press(mask, tag='a64-Life-overlay-list', stop_check=stopped)
                    require(hits == 5, 'Life list input incomplete')
                    result['navigation'].append({'mask': mask, 'hits': hits, 'before': token.receipt()})
                def select(kind, value, ability=False):
                    for _ in range(34):
                        token = observe(kind)
                        rows = token.ability_ids if ability else token.rows
                        require(rows.count(value) == 1, 'Life navigation row missing or ambiguous')
                        index = rows.index(value)
                        require(token.enabled[index], 'Life navigation row disabled')
                        current = token.scroll+token.cursor
                        if current == index:
                            if ability:
                                require(value == 5 and effective_mp_cost(rom, 5, exact(g, caster['canonical'], STRIDE)) == 10
                                        and token.mp >= 10, 'Life effective cost or resources differ')
                                for address, data in units.items():
                                    require(exact(g, address, STRIDE) == data, 'party changed before Life selection')
                            press(1, token)
                            return
                        press(0x80 if current < index else 0x40, token)
                    raise TimeoutError('Life list navigation exceeded bounds')
                select('command', 9)
                select('action-group', 9)
                select('ability-list', 5, ability=True)
                # Raw observation only: do not call a Cure reader or assume its
                # target-state predicates authorize any further gameplay input.
                transport.cont()
                time.sleep(1)
                def capture(tag):
                    stopped()
                    context = integer(exact(g, MENU_ROOT, 4), 0)
                    root = exact(g, context, 0x30)
                    driver = exact(g, PLAYER_DRIVER, 0xE0)
                    callback = integer(root, 0x28)
                    controller = exact(g, callback, 0x18)
                    processor = integer(driver, 0x60)
                    require(processor == BATTLE_STRUCT, 'Life processor allocation is unknown')
                    data = block(g, processor, 0x1120)
                    count = data[0xA2]
                    require(0 < count <= 20, 'Life target table bounds unknown')
                    wrappers = []
                    for i in range(count):
                        address = integer(data, 0x50+4*i)
                        wrapper = exact(g, address, 0x30)
                        member = integer(wrapper, 0)
                        unit = exact(g, member, STRIDE)
                        wrappers.append({'wrapper': address, 'canonical': member, 'id': unit[0x104],
                            'name': integer(unit, 0), 'hp': integer(unit, 0x18, 2),
                            'mp': integer(unit, 0x1C, 2), 'side_flags': integer(unit, 0x28, 2),
                            'tile': list(unit[0xF6:0xF8])})
                    phase = {'tag': tag, 'context': context, 'mode': root[4],
                        'selection': integer(root, 0, 2), 'selected_ability': integer(root, 0x14),
                        'member': integer(root, 0x18), 'peer': integer(root, 0x1C),
                        'callback': callback, 'handler': integer(controller, 0),
                        'controller_state': integer(controller, 0x14, 2),
                        'active_callback': integer(exact(g, integer(root, 0x20)+4, 4), 0),
                        'driver_state': integer(driver, 0xDC, 2), 'processor': processor,
                        'processor_actor': integer(data, 0), 'processor_ability': integer(data, 0xEC, 2),
                        'target_state': integer(data, 0x1118, 2), 'target_flags': integer(data, 0x1112, 2),
                        'index': data[0xA1], 'count': count,
                        'selected_copies': [integer(data, 12), integer(data, 16)],
                        'cursor': list(exact(g, TARGET_X, 2)),
                        'acceptance_xy': [integer(exact(g, 0x0200F3B8+o, 2), 0, 2) for o in (0, 4)],
                        'wrappers': wrappers}
                    result['phases'].append(phase)
                    for address, unit in units.items():
                        require(exact(g, address, STRIDE) == unit, 'canonical party changed opening Life overlay')
                    require(integer(root, 0x14) == integer(data, 0xEC, 2) == 5,
                            'native selected Life identity differs')
                    path = out/(tag+'-ewram.bin')
                    path.write_bytes(block(g, 0x02000000, 0x40000))
                    result.setdefault('capture_sha256', {})[path.name] = sha(path)
                    transport.cont()
                    time.sleep(0.5)
                for tag in ('overlay-first', 'overlay-second'):
                    capture(tag)
                if args.move_to_KO or args.accept_target or args.inspect_final_prompt:
                    token = overlay_reader.snapshot()
                    require(token.cursor == tuple(caster['tile'])
                            and token.target_tile == (token.cursor[0]-1,token.cursor[1]),
                            'Life research navigation is outside the established adjacent LEFT')
                    stopped()
                    overlay_reader.revalidate(token)
                    stopped()
                    hits = transport.press(0x20, tag='a64-Life-single-LEFT-to-KO', stop_check=stopped)
                    require(hits == 5, 'Life KO navigation input incomplete')
                    transport.cont()
                    time.sleep(0.5)
                    for tag in ('KO-cursor-first', 'KO-cursor-second'):
                        capture(tag)
                        token = overlay_reader.snapshot()
                        overlay_reader.revalidate(token,at_target=True)
                        result.setdefault('KO_cursor_tokens',[]).append(token.receipt())
                    if args.accept_target or args.inspect_final_prompt:
                        stopped()
                        token = overlay_reader.snapshot()
                        overlay_reader.revalidate(token,at_target=True)
                        stopped()
                        result['target_acceptance'] = True
                        hits = transport.press(1,tag='a64-Life-single-KO-target-selection-A',stop_check=stopped)
                        require(hits == 5, 'Life target-selection input incomplete')
                        result['target_selection_delivered'] = True
                        transport.cont()
                        time.sleep(1)
                        capture('selected-first')
                        capture('selected-second')
                        token = overlay_reader.preview_snapshot()
                        overlay_reader.revalidate(token,at_target=True)
                        result['Life_preview_token'] = token.receipt()
                        if args.inspect_final_prompt:
                            stopped()
                            token = overlay_reader.preview_snapshot()
                            overlay_reader.revalidate(token,at_target=True)
                            stopped()
                            result['description_advance_requested'] = True
                            hits = transport.press(1,tag='a64-Life-single-description-A',stop_check=stopped)
                            require(hits == 5, 'Life description input incomplete')
                            result['description_advance_delivered'] = True
                            transport.cont()
                            time.sleep(1)
                            capture('final-prompt-first')
                            capture('final-prompt-second')
                result['transport'] = transport.events
            session.screenshot(str(out/'Life-overlay.png'))
            probe.disarm(strict=True)
            require(not session.writes, 'Life overlay research wrote unit RAM')
        result['status'] = ('captured-Life-final-prompt-only' if args.inspect_final_prompt else
                            'captured-Life-target-selection-only' if args.accept_target else
                            'captured-Life-KO-cursor-only' if args.move_to_KO else 'captured-Life-overlay-only')
    except BaseException as exc:
        result['error'] = repr(exc)
        raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe, 'key_write_log', []), fixture_writes=probe.s.writes)
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'Life-overlay.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'])


if __name__ == '__main__':
    main()
