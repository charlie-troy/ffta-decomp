"""A5.1 offline identity, rejection, and public-entry-point regressions.

Synthetic RAM tests certify guard/control flow only, never ROM semantics.
Use --cli to exercise the real runner with the recorded transport model.
"""
import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch

from autobattle_identity import ActorAdapter, IdentityError, key
from autobattle_runtime import BattleRuntime
from fixture_guard import ROSTER, STRIDE, BATTLE_STRUCT, read_roster
from probe_control_handoff import CMD_CURSOR, TARGET_X, TARGET_Y
from validate_transport_paths import FakeSession, FakeWorld
from validate_autobattle_runtime import validate


def write_int(g, addr, value, size=1):
    for i, b in enumerate(value.to_bytes(size, "little")):
        g.mem[addr+i] = b


def name(g, slot, text):
    ptr = 0x02001000 + slot * 32
    write_int(g, ROSTER + STRIDE*slot, ptr, 4)
    data = []
    for c in text:
        data.extend((0x80, (0xB0+ord(c)-ord('A') if c.isupper() else 0xCA+ord(c)-ord('a'))))
    for i, b in enumerate(data+[0]):
        g.mem[ptr+i] = b


class Memory:
    def __init__(self, mem):
        self.mem = dict(mem)
    def read_mem(self, addr, size):
        return bytes(self.mem.get(addr+i, 0) for i in range(size))


def fixture():
    world = FakeWorld()
    s = FakeSession(world)
    s.g = Memory(s.g.mem)
    base = ROSTER + STRIDE*6
    ally = ROSTER + STRIDE*7
    for off in range(STRIDE):
        s.g.mem[ally+off] = s.g.mem.get(base+off, 0)
    name(s.g, 7, 'Montblanc')
    write_int(s.g, ally+0x104, 7)
    write_int(s.g, ally+0xF6, 5)
    write_int(s.g, ally+0xF7, 10)
    write_int(s.g, base+0xF6, 4)
    write_int(s.g, base+0xF7, 10)
    write_int(s.g, base+0xD0, 353, 2)
    write_int(s.g, ally+0xD0, 0, 2)
    write_int(s.g, BATTLE_STRUCT, 8, 4)
    write_int(s.g, CMD_CURSOR, 0)
    write_int(s.g, TARGET_X, 4)
    write_int(s.g, TARGET_Y, 10)
    s.receipt = {'ok': True, 'roster': read_roster(s.g, rom=s.read_rom_bytes())}
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cli', action='store_true')
    ap.add_argument('--out-root', default='outputs/autobattle/a51-identity')
    args = ap.parse_args()
    root = Path(args.out_root)
    root.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(label, fn):
        fn()
        checks.append(label)
        print('PASS', label, flush=True)

    s = fixture()
    adapter = ActorAdapter(s)
    runtime = BattleRuntime(s, {'scenario_id': 'synthetic-two-player'}, 'host', str(root), verbose=False)
    runtime.adapter, runtime.g = adapter, s.g
    rows = adapter.snapshot()
    assert adapter.observe(runtime.p, rows) is None
    owner = adapter.observe(runtime.p, rows)
    assert key(owner) == ('Marche', 6) and owner['ct'] == 353
    checks.append('cursor owner above old CT threshold; frozen ally is not owner')
    runtime.owner = owner
    pre = adapter.revalidate(owner, runtime.p)
    post = copy.deepcopy(pre)
    next(r for r in post if key(r) == key(owner))['y'] = 11
    check('actor-linked move result', lambda: adapter.result(owner, pre, post, 'identified-move', (4,11)))

    def reject_result(kind, changed):
        try:
            adapter.result(owner, pre, changed, kind, (4,11))
        except IdentityError:
            return
        raise AssertionError('wrong result accepted')
    wrong = copy.deepcopy(pre)
    wrong[0]['y'] = 11  # depending on order, intentionally choose other actor
    if key(wrong[0]) == key(owner):
        wrong = copy.deepcopy(pre)
        wrong[1]['y'] = 11
    check('other ally movement rejects', lambda: reject_result('identified-move', wrong))
    check('CT-only move rejects', lambda: reject_result('identified-move', pre))
    check('Wait with player movement rejects', lambda: reject_result('identified-wait', post))
    check('unchanged Wait result', lambda: adapter.result(owner, pre, pre, 'identified-wait', None))

    def invalid(label, mutate):
        x = fixture()
        a = ActorAdapter(x)
        mutate(x.g)
        try:
            a.snapshot()
        except IdentityError:
            checks.append(label)
            print('PASS', label, flush=True)
            return
        raise AssertionError(label + ' accepted')
    invalid('duplicate unit id', lambda g: write_int(g, ROSTER+STRIDE*7+0x104, 6))
    invalid('missing player name', lambda g: write_int(g, ROSTER+STRIDE*6, 0, 4))
    invalid('job changed', lambda g: write_int(g, ROSTER+STRIDE*6+7, 3))
    invalid('enemy side changed', lambda g: write_int(g, ROSTER+STRIDE*6+0x28, 0x8000, 2))
    invalid('HP exceeds max', lambda g: write_int(g, ROSTER+STRIDE*6+0x18, 1000, 2))
    invalid('tile out of bounds', lambda g: write_int(g, ROSTER+STRIDE*6+0xF6, 64))

    # Stale and ambiguous cursors cannot issue even the first echo key.
    write_int(s.g, TARGET_X, 5)
    runtime._drive_player_boundary()
    assert not s.write_ledger and not hasattr(runtime.p, 'key_write_log')
    checks.append('stale owner prevents first gameplay input')
    x = fixture()
    write_int(x.g, ROSTER+STRIDE*7+0xF6, 4)
    a = ActorAdapter(x)
    r = BattleRuntime(x, {}, 'ambiguous', str(root), verbose=False)
    assert a.observe(r.p, a.snapshot()) is None
    assert a.observe(r.p, a.snapshot()) is None
    checks.append('ambiguous same-tile owner rejects')
    x = fixture()
    write_int(x.g, ROSTER+STRIDE*6+0x18, 0, 2)
    write_int(x.g, TARGET_X, 5)
    a = ActorAdapter(x)
    r = BattleRuntime(x, {}, 'dead-ally', str(root), verbose=False)
    assert a.observe(r.p, a.snapshot()) is None
    assert key(a.observe(r.p, a.snapshot())) == ('Montblanc', 7)
    r.adapter = a
    assert not r._party_dead()
    checks.append('dead known actor does not suppress distinct ally')
    for label, actions in (
        ('absent assignment', [{'name':'Absent', 'id':99, 'action':'move'}]),
        ('duplicate assignment', [{'name':'Marche', 'id':6, 'action':'move'}]*2),
        ('malformed assignment', [{'name':'Marche', 'id':[], 'action':'move'}]),
        ('unsupported assignment', [{'name':'Marche', 'id':6, 'action':'spell'}]),
    ):
        x = fixture()
        guard = BattleRuntime(x, {'actor_actions':actions}, label, str(root), verbose=False)
        assert not guard.live_guard() and not x.write_ledger
        guard._input_log.close()
        checks.append(label + ' rejects before input')
    for r in (runtime, r):
        r._input_log.close()

    if args.cli:
        import run_autobattle
        world = FakeWorld()
        session = FakeSession(world)
        name(session.g, 6, 'Montblanc')
        session.receipt['roster'] = read_roster(session.g, rom=session.read_rom_bytes())
        session.receipt['roster']['ram_named_slots'] = [6]
        world.identified_move, world.allow_seeds = True, True
        scenario = root/'scenario.json'
        scenario.write_text(json.dumps({'scenario_id': 'renamed-player'}))
        with patch.object(run_autobattle, 'FixtureSession', lambda *a, **kw: session):
            rc = run_autobattle.main(['--scenario', str(scenario), '--out-root', str(root),
                                     '--run-id', 'cli', '--yes', '--max-turns', '1', '--wall-timeout', '60'])
        assert rc == 1  # truthful bounded stop after one action, not completion
        run_dir = root/'cli'
        events = [json.loads(line) for line in (run_dir/'events.jsonl').read_text().splitlines()]
        turns = [e for e in events if e['kind'] == 'turn']
        assert len(turns) == 1 and turns[0]['actor'] == 'Montblanc'
        assert turns[0]['engine_result']['verified'] and not validate(str(run_dir))
        checks.append('public CLI names actual renamed actor with verified result')
        original = (run_dir/'events.jsonl').read_text()
        turns[0]['actor_identity']['id'] = 99
        (run_dir/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
        assert validate(str(run_dir))
        (run_dir/'events.jsonl').write_text(original)
        checks.append('corrupt actor receipt rejects')
    (root/'checks.json').write_text(json.dumps({'checks': checks, 'passed': len(checks),
                                              'scope': 'synthetic control-flow evidence only'}, indent=2))
    print(f'ACTOR IDENTITY PASS: {len(checks)} checks')


if __name__ == '__main__':
    main()
