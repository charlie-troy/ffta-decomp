"""Guarded Life research stages, with an explicit single-cast opt-in.

Independent research path. No final-confirmation, targeting-legality or revival
authority follows from capturing bytes alone. Final cast input requires the
separate single-attempt target/policy gate; existing Cure readers are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from ability_resources import effective_mp_cost
from autobattle_identity import ActorAdapter
from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, ROSTER, STRIDE, BATTLE_STRUCT, read_roster
from probe_control_handoff import Probe, TARGET_X
from probe_recovery_ko_lifecycle import joined_party, source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, exact, integer, require, RecoveryTransient
from recovery_menu_list import ResearchMenuList
from recovery_life_target import LifeOverlayReader
from recovery_transport import RecoveryTransport
from recovery_life_final import LifeFinalGate
from recovery_life_trace import LifeExecutionProbe
from recovery_life_effect import verify_life_effect
from recovery_life_wait import LifeWaitBoundary
from recovery_party_continuation import observe_party_continuation
from tactics_policy import evaluate, load_policy_file


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
    args = ap.parse_args()
    require(not (args.inspect_Wait or args.execute_Wait) or args.execute_Life,'Wait requires the single Life cast')
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
                g, rom = transport.g, session.read_rom_bytes()
                members_before = block(g, MEMBERS, MEMBER_COUNT*STRIDE)
                expected = ActorAdapter(session).expected
                party = joined_party(block(g, ROSTER, 8*STRIDE),members_before,expected)
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
                if args.move_to_KO or args.accept_target or args.inspect_final_prompt or args.execute_Life:
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
                    if args.accept_target or args.inspect_final_prompt or args.execute_Life:
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
                        if args.inspect_final_prompt or args.execute_Life:
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
                            token = overlay_reader.confirmation_snapshot()
                            overlay_reader.revalidate(token,at_target=True)
                            result['Life_final_token'] = token.receipt()
                            result['policy_snapshot'] = overlay_reader.policy_snapshot(token)
                            result['policy_evaluation'] = evaluate(result['policy_snapshot'],policy)
                            if args.execute_Life:
                                gate = LifeFinalGate(overlay_reader,transport,policy,stop_check=stopped)
                                result['final_gate_events'] = gate.events
                                try:
                                    result['final_delivery'] = gate.commit(token)
                                finally:
                                    result['final_confirmation'] = gate.final_attempted
                                # Observe native effect paths before permitting any further input.
                                transport.interrupt()
                                probe.arm(strict=True)
                                probe.pump(20,'a64-Life-post-final-native',
                                    stop_when=lambda p:any(h['phase']=='level-up-after' and h.get('unit')
                                        and h['unit']['id']==5 for h in p.life_hits))
                                transport.halted = False
                                transport.interrupt()
                                probe.disarm(strict=True)
                                require(not probe.life_errors,'Life native trace had an observation error')
                                canonical_after = {a:exact(g,a,STRIDE) for a in units}
                                result['effect_attribution'] = verify_life_effect(
                                    units,canonical_after,probe.life_hits,caster,target)
                                # Rebind only after the native growth witness verifies the new identity.
                                menu = ResearchMenuList(g,rom,owner,caster['canonical'])
                                deadline = time.monotonic()+30
                                while time.monotonic() < deadline:
                                    stopped()
                                    try:
                                        post = menu.snapshot()
                                    except ValueError as exc:
                                        rejections = result.setdefault('post_effect_rejections',[])
                                        if str(exc) not in rejections:
                                            path=out/('post-effect-rejection-'+str(len(set(rejections)))+'-ewram.bin')
                                            path.write_bytes(block(g,0x02000000,0x40000))
                                            result.setdefault('capture_sha256',{})[path.name]=sha(path)
                                            current=exact(g,caster['canonical'],STRIDE)
                                            result.setdefault('post_effect_caster_differences',[]).append({
                                                'reason':str(exc),'differences':[{'offset':i,'before':b,'after':a}
                                                    for i,(b,a) in enumerate(zip(units[caster['canonical']],current)) if b!=a]})
                                        rejections.append(str(exc))
                                        transport.cont();time.sleep(0.25)
                                        continue
                                    if post.state == 'command':
                                        break
                                    transport.cont();time.sleep(0.25)
                                else:
                                    raise TimeoutError('Life did not restore the owned command menu; never retry final input')
                                require(post.rows.count(9)==1 and not post.enabled[post.rows.index(9)]
                                        and post.rows.count(10)==1 and post.enabled[post.rows.index(10)],
                                        'Life did not consume Action and leave Wait available')
                                after = joined_party(block(g,ROSTER,8*STRIDE),
                                                     block(g,MEMBERS,MEMBER_COUNT*STRIDE),expected)
                                living = next(p for p in after if p['id']==5)
                                revived = next(p for p in after if p['id']==7)
                                require(living['hp']==caster['hp'] and living['mp']==caster['mp']-10
                                        and 0 < revived['hp'] <= target['max_hp'] and revived['mp']==target['mp'],
                                        'Life causal HP/MP result differs')
                                for before,current in zip(party,after):
                                    require(all(before[k]==current[k] for k in ('canonical','id','name','tile','side_flags',
                                        'ko_suffered')), 'Life party identity/KO counter changed')
                                    if before['id'] != 5:
                                        require(all(before[k]==current[k] for k in ('max_hp','max_mp')),
                                                'Life target resource maxima changed')
                                members_after = block(g,MEMBERS,MEMBER_COUNT*STRIDE)
                                for i in range(MEMBER_COUNT):
                                    address = MEMBERS+i*STRIDE
                                    if address not in units:
                                        require(members_after[i*STRIDE+0x18:i*STRIDE+0x20] ==
                                                members_before[i*STRIDE+0x18:i*STRIDE+0x20],
                                                'Life changed another canonical member resource')
                                result.update(Life_effect={'before':party,'after':after,'command':post.receipt(),
                                    'wait':'unexecuted','continuation':'unknown'},life_engine_hits=probe.life_hits)
                                path=out/'after-Life-ewram.bin'
                                path.write_bytes(block(g,0x02000000,0x40000))
                                result.setdefault('capture_sha256',{})[path.name]=sha(path)
                                if args.inspect_Wait or args.execute_Wait:
                                    post_units={a:exact(g,a,STRIDE) for a in units}
                                    baseline=[r for r in read_roster(g,rom=rom)['slots'] if r['live']]
                                    require(len(baseline)==8,'post-Life baseline roster missing')
                                    result['post_Life_roster']=baseline
                                    select('command',10)
                                    boundary=LifeWaitBoundary(g,menu,post_units)
                                    deadline=time.monotonic()+8
                                    while time.monotonic()<deadline:
                                        stopped()
                                        try:
                                            facing=boundary.snapshot()
                                            boundary.revalidate(facing)
                                            break
                                        except ValueError:
                                            transport.cont();time.sleep(0.25)
                                    else:raise TimeoutError('Life Wait facing did not settle; no final Wait input')
                                    result['Wait_facing']=facing.receipt()
                                    path=out/'Wait-facing-ewram.bin'
                                    path.write_bytes(block(g,0x02000000,0x40000))
                                    result.setdefault('capture_sha256',{})[path.name]=sha(path)
                                    if args.execute_Wait:
                                        pins=[]
                                        for p in after:
                                            address=p['name']
                                            name=(rom[address-0x08000000:address-0x08000000+32]
                                                  if 0x08000000<=address<0x08000000+len(rom)
                                                  else exact(g,address,32))
                                            pins.append(p|{'name_sha256':hashlib.sha256(name).hexdigest()})
                                        result['Wait_events']=boundary.events
                                        try:
                                            result['Wait_delivery']=boundary.commit(facing,transport,policy,stopped)
                                        finally:result['Wait_final_attempted']=boundary.final_attempted
                                        deadline=time.monotonic()+30
                                        while time.monotonic()<deadline:
                                            stopped()
                                            try:
                                                continuation=observe_party_continuation(g,rom,owner,facing.receipt(),
                                                    pins,post_units,baseline)
                                                break
                                            except ValueError as exc:
                                                result.setdefault('continuation_rejections',[]).append(str(exc))
                                                transport.cont();time.sleep(0.25)
                                        else:raise TimeoutError('Life Wait has no attributed next actor; never retry')
                                        result['Life_effect'].update(wait='delivered',continuation=continuation)
                                        path=out/'after-Wait-ewram.bin'
                                        path.write_bytes(block(g,0x02000000,0x40000))
                                        result.setdefault('capture_sha256',{})[path.name]=sha(path)
                result['transport'] = transport.events
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
        raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe, 'key_write_log', []), fixture_writes=probe.s.writes,
                          life_engine_hits=probe.life_hits,life_engine_errors=probe.life_errors)
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'Life-overlay.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'])


if __name__ == '__main__':
    main()
