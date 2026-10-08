"""Independently reload and observe a KO fixture; no unit or gameplay writes."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter, IdentityError
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_recovery_ko_lifecycle import joined_party, source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, exact, integer, require
from recovery_transport import RecoveryTransport
from recovery_ko_trace import KOLifecycleProbe




def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--scenario', default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=60)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    paths = [args.state, args.rom, args.scenario] + source_dependencies('probe_recovery_ko_reload')
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result = {'schema': 'ffta-KO-independent-reload/1', 'status': 'unknown', 'scope': __doc__,
              'source_sha256': {p: sha(p) for p in paths}}
    expect = json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out/'session')) as session:
            result['pid'] = session.pid
            probe = KOLifecycleProbe(session, verbose=False)
            adapter = ActorAdapter(session)
            probe.arm(strict=True)
            owner = None
            deadline = time.monotonic()+args.seconds
            while time.monotonic() < deadline:
                probe.pump(2, 'KO-independent-reload', sample_every=60)
                try:
                    owner = adapter.observe(probe, adapter.snapshot())
                except IdentityError:
                    adapter.prior = None
                if owner is not None:
                    break
            require(owner is not None and owner['id'] in (5, 7), 'fresh living caster menu was not independently joined')
            adapter.revalidate(owner, probe)
            with RecoveryTransport(probe) as transport:
                roster = block(transport.g, ROSTER, 8*STRIDE)
                members = block(transport.g, MEMBERS, MEMBER_COUNT*STRIDE)
                party = joined_party(roster, members, adapter.expected)
                target = next(p for p in party if p['id'] != owner['id'])
                caster = next(p for p in party if p['id'] == owner['id'])
                require(target['hp'] == 0 and target['ko_suffered'] > 0
                        and not any(target['statuses'].values()) and caster['hp'] > 0,
                        'reload lacks the expected living caster and independent KO ally')
                context = integer(exact(transport.g, MENU_ROOT, 4), 0)
                root = exact(transport.g, context, 0x30)
                callback, manager = integer(root, 0x28), integer(root, 0x20)
                controller = exact(transport.g, callback, 0x18)
                driver = exact(transport.g, PLAYER_DRIVER, 0xE0)
                wrapper = integer(driver, 4)
                require(root[4] == 4 and integer(controller, 0) == 0x08028DE1
                        and integer(controller, 0x14, 2) == 0x102
                        and integer(root, 0x18) == caster['canonical']
                        and integer(driver, 8) == wrapper
                        and integer(exact(transport.g, wrapper, 4), 0) == caster['canonical']
                        and integer(driver, 0xDC, 2) == 0x25 and integer(driver, 0x60) == 0
                        and integer(exact(transport.g, manager+4, 4), 0) == callback,
                        'reload is not a fresh owned command boundary')
                menu = {'state': 'command', 'context': context, 'member': caster['canonical'],
                        'callback': callback, 'manager': manager, 'wrapper': wrapper,
                        'mode': root[4], 'driver_state': integer(driver, 0xDC, 2)}
                for address, data in ((ROSTER, roster), (MEMBERS, members),
                                      (MENU_ROOT, exact(transport.g, MENU_ROOT, 4)),
                                      (PLAYER_DRIVER, exact(transport.g, PLAYER_DRIVER, 0xE0))):
                    require(block(transport.g, address, len(data)) == data, 'halted KO reload capture changed')
                    path = out/f'{address:08x}.bin'
                    path.write_bytes(data)
                    result.setdefault('capture_sha256', {})[path.name] = sha(path)
                result.update(owner=owner, party=party, menu=menu)
            result.update(ko_tail_hits=[h for h in probe.lifecycle_hits if h['phase'].startswith('tail')],
                          lifecycle_hits=probe.lifecycle_hits, engine_turns=probe.turns,
                          seeds=probe.seeds, gameplay_writes=getattr(probe, 'key_write_log', []),
                          fixture_writes=session.writes)
            require(not result['gameplay_writes'] and not result['fixture_writes'], 'read-only reload wrote input or RAM')
            session.screenshot(str(out/'reloaded-ko.png'))
            probe.disarm(strict=True)
        result['status'] = 'pass-independent-KO-command-reload'
    except BaseException as exc:
        result['error'] = repr(exc)
        raise
    finally:
        result['inputs_unchanged'] = all(sha(p) == h for p,h in result['source_sha256'].items())
        (out/'reload.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['status'], 'KO tail hits', len(result['ko_tail_hits']))


if __name__ == '__main__':
    main()
