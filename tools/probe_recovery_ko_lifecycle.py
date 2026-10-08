"""Observe natural damage/KO while the existing runtime selects legal Wait.

Research only: optional positive-HP setup is ledgered before observation;
zero HP, status, party and policy are never written. Canonical party joins
remain visible when HP reaches zero; production living-ally guards are intact.
An observed zero alone does not certify targeting, scheduling or revival.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

from autobattle_runtime import BattleRuntime, STALLED
from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, RecoveryStateError, integer, require
from recovery_transport import RecoveryTransport
from recovery_ko_trace import KOLifecycleProbe
from status_flags import STATUS_FLAGS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_dependencies(entry):
    """Pin local import closure instead of unrelated tools edited concurrently."""
    pending, found = [entry], set()
    while pending:
        name = pending.pop()
        path = Path('tools') / (name+'.py')
        if name in found or not path.is_file():
            continue
        found.add(name)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, ast.ImportFrom) and node.module:
                pending.append(node.module.split('.')[0])
            elif isinstance(node, ast.Import):
                pending.extend(a.name.split('.')[0] for a in node.names)
    return ['tools/'+name+'.py' for name in sorted(found)]


def joined_party(roster, members, rows):
    """Research join accepts zero HP but rejects reused/aliased battle bytes."""
    require(len(roster) == 8 * STRIDE and len(members) == MEMBER_COUNT * STRIDE,
            'short KO observation')
    require({roster[i * STRIDE + 0x104] for i in range(8)} == set(range(8)),
            'battle mirror is reused or identities differ')
    require(len(rows) == 2 and {r['id'] for r in rows} == {5, 7}
            and len({r['name'] for r in rows}) == 2, 'aliased research party')
    result = []
    for row in rows:
        mirror = roster[row['slot'] * STRIDE:(row['slot'] + 1) * STRIDE]
        candidates = [(MEMBERS + i * STRIDE, members[i * STRIDE:(i + 1) * STRIDE])
                      for i in range(MEMBER_COUNT)]
        matches = [(a, u) for a, u in candidates
                   if integer(u, 0) == row['name'] and u[0x104] == row['id']]
        require(len(matches) == 1, 'canonical KO identity missing or ambiguous')
        require(sum(integer(u, 0) == row['name'] for _, u in candidates) == 1
                and sum(u[0x104] == row['id'] for _, u in candidates) == 1,
                'canonical KO name or id alias')
        address, unit = matches[0]
        require(integer(mirror, 0) == row['name'] and mirror[0x104] == row['id'],
                'KO mirror identity mismatch')
        for offset, size in ((0, 10), (0x18, 8), (0x28, 2), (0xE8, 6), (0xF1, 2), (0xF6, 2), (0x104, 1)):
            require(unit[offset:offset+size] == mirror[offset:offset+size],
                    'KO canonical/mirror disagreement')
        hp, maximum, mp, max_mp = [integer(unit, o, 2) for o in (0x18, 0x1A, 0x1C, 0x1E)]
        require(0 <= hp <= maximum <= 999 and maximum > 0 and 0 <= mp <= max_mp <= 999,
                'invalid KO resource bounds')
        require(unit[6:8] == bytes((1, 5)) and unit[4] != 20
                and integer(unit, 0x28, 2) & 0x9000 == 0,
                'KO party race/job/side changed')
        require(all(v < 64 for v in unit[0xF6:0xF8]), 'KO party tile bounds')
        statuses = {s['name']: bool(unit[s['offset']] & s['mask']) for s in STATUS_FLAGS
                    if s['name'] in ('petrify', 'auto_life', 'zombie')}
        statuses['persistent_zombie'] = bool(integer(unit, 0x28, 2) & 0x0800)
        result.append({'canonical': address, 'id': row['id'], 'name': row['name'],
                       'name_text': row['name_text'], 'slot': row['slot'],
                       'hp': hp, 'max_hp': maximum, 'mp': mp, 'max_mp': max_mp,
                       'tile': list(unit[0xF6:0xF8]), 'statuses': statuses,
                       'side_flags': integer(unit, 0x28, 2),
                       'ko_inflicted': unit[0xF1], 'ko_suffered': unit[0xF2],
                       'canonical_ct': integer(unit, 0xD0, 2),
                       'mirror_ct': integer(mirror, 0xD0, 2),
                       'canonical_speed': integer(unit, 0xD2, 2),
                       'mirror_speed': integer(mirror, 0xD2, 2),
                       'canonical_sha256': hashlib.sha256(unit).hexdigest(),
                       'mirror_sha256': hashlib.sha256(mirror).hexdigest()})
    return result


def export_owned_state(session, probe, output):
    # A prior reader may already have consumed the halted stop packet.
    # Resume before interrupt so this export owns a fresh, settled halt.
    session.g.cont()
    halt = session.g.interrupt()
    require(halt and halt[:1] in ('S', 'T') and halt[:3] not in ('S04', 'T04'), 'export halt failed')
    probe.disarm(strict=True)
    session.g.cont()
    slot = Path(session.work_paths['rom']).with_suffix('.ss2')
    require(not slot.exists(), 'refusing an existing state export slot')
    sent = subprocess.run(['powershell', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass',
                           '-File', 'tools/save_owned_mgba_state.ps1', '-ProcId', str(session.pid)],
                          capture_output=True, text=True, timeout=40,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    require(sent.returncode == 0, 'owned state export failed: ' + sent.stdout + sent.stderr)
    deadline, previous = time.monotonic() + 12, None
    while time.monotonic() < deadline:
        size = slot.stat().st_size if slot.exists() else None
        if size and size > 40000 and size == previous:
            break
        previous = size
        time.sleep(0.1)
    require(slot.exists() and slot.stat().st_size > 40000, 'short/absent export')
    with output.open('xb') as handle:
        handle.write(slot.read_bytes())
    return {'path': str(output), 'sha256': sha(output), 'pid': session.pid,
            'hotkey': sent.stdout.strip()}


class KOObserverRuntime(BattleRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.research_out = Path(self.events_path).parent
        self.observations = []
        self.baseline = None
        self.zero_count = 0
        self.natural_ko_candidate = False
        self.export = None
        self.ko_target_id = 0

    def observe_party(self):
        rec = {'t': round(time.time() - self.t0, 3), 'turns': self.turn,
               'seeds': len(self.p.seeds), 'router_hits': self.p.router_hits}
        with RecoveryTransport(self.p) as transport:
            roster = block(transport.g, ROSTER, 8 * STRIDE)
            members = block(transport.g, MEMBERS, MEMBER_COUNT * STRIDE)
            try:
                party = joined_party(roster, members, self.adapter.expected)
                rec['party'] = party
                if self.baseline is None:
                    require(all(p['hp'] > 0 for p in party), 'baseline must be living')
                    self.baseline = party
                if self.ko_target_id == 0:
                    dead = [p for p in party if p['hp'] == 0 and not any(p['statuses'].values())
                            and p['ko_suffered'] > next(b['ko_suffered'] for b in self.baseline if b['id'] == p['id'])]
                    if len(dead) == 1 and any(p['hp'] > 0 for p in party):
                        self.ko_target_id = dead[0]['id']
                target = next((p for p in party if p['id'] == self.ko_target_id), None)
                caster = next((p for p in party if p['id'] != self.ko_target_id), None)
                before = next((p for p in self.baseline if p['id'] == self.ko_target_id), None)
                candidate = bool(target and before and target['hp'] == 0 and caster['hp'] > 0
                             and target['ko_suffered'] > before['ko_suffered']
                             and not any(target['statuses'].values()))
                self.zero_count = self.zero_count + 1 if candidate else 0
                changed = not self.observations or party != self.observations[-1].get('party')
                if changed:
                    number = len(self.observations)
                    for name, data in (('roster', roster), ('members', members)):
                        path = self.research_out / f'{number:04d}-{name}.bin'
                        path.write_bytes(data)
                        rec.setdefault('captures', {})[path.name] = sha(path)
                hits = getattr(self.p, 'lifecycle_hits', [])
                damage = [h for h in hits if h['phase'] in ('damage-after', 'HP-adjust-after')
                          and h['id'] == self.ko_target_id and h['hp'] == 0]
                picked = bool(damage and any(h['phase'] == 'battle-driver-picked'
                              and h['hp'] > 0 and h['t'] >= damage[-1]['t'] for h in hits))
                self.natural_ko_candidate = self.zero_count >= 2 and picked
                rec['zero_hp_counter_candidate'] = candidate
            except RecoveryStateError as exc:
                rec['rejected'] = str(exc)
                self.zero_count = 0
        self.observations.append(rec)
        with (self.research_out / 'ko-observations.jsonl').open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(rec) + '\n')
        if rec.get('party'):
            print('KO observation', rec['t'], [(p['name_text'], p['hp'], p['ko_suffered'])
                                              for p in rec['party']], flush=True)
        return rec

    def _classify(self):
        self.observe_party()
        classified = super()._classify()
        if self.natural_ko_candidate and classified == 'takeover' and self.owner['id'] != self.ko_target_id:
            self._terminal_reason_identity = 'research bound: repeated engine KO counter/zero HP candidate; lifecycle not yet certified'
            return STALLED
        return classified

    def _finish(self, state, reason):
        if self.natural_ko_candidate:
            self.export = export_owned_state(self.s, self.p, self.research_out / 'natural-ko.ss0')
        super()._finish(state, reason)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state', default='outputs/autobattle/a62-party-fixture-01/party-recovery.ss0')
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--scenario', default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=900)
    ap.add_argument('--ko-target-id', type=int, choices=(0, 5, 7), default=0, help='0 accepts the first genuinely KO ally')
    ap.add_argument('--damage-target-hp', type=int, help='Optional positive HP setup before actual engine damage')
    ap.add_argument('--setup-unit-id', type=int, choices=(5, 7), help='Unit receiving positive HP setup; defaults to KO target')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    scenario = json.loads(Path(args.scenario).read_text())
    # Observer reads take longer than the public policy freshness window.
    # Use the existing fixed-action seam: both identified actors only Wait.
    # This research does not certify a conditional-policy decision.
    scenario['actor_actions'] = [{'name': 'Marche', 'id': 7, 'action': 'wait'},
                                 {'name': 'Montblanc', 'id': 5, 'action': 'wait'}]
    expect = dict(scenario['guard_expectations'])
    expect['slot0_name'] = int(expect['slot0_name'], 0)
    sources = [args.state, args.rom, args.scenario, 'tools/save_owned_mgba_state.ps1'] + source_dependencies('probe_recovery_ko_lifecycle')
    result = {'schema': 'ffta-natural-ko-research/1', 'scope': __doc__, 'status': 'unknown',
              'source_sha256': {p: sha(p) for p in sources},
              'research_actor_actions': scenario['actor_actions'], 'ko_target_id': args.ko_target_id,
              'setup_unit_id': args.setup_unit_id or args.ko_target_id or 7,
              'positive_hp_setup': args.damage_target_hp}
    runtime = None
    try:
        with FixtureSession(args.state, rom=args.rom, expect=expect, quiet=True,
                            work_dir=str(out / 'session')) as session:
            result['pid'] = session.pid
            # Select a research Probe subclass at construction, leaving the
            # production runtime and Probe methods unchanged.
            with patch('autobattle_runtime.Probe', KOLifecycleProbe):
                runtime = KOObserverRuntime(session, scenario, out.name, str(out),
                                            wall_timeout=args.seconds, verbose=False)
            require(runtime.live_guard(), 'live runtime guard rejected fixture')
            runtime.ko_target_id = args.ko_target_id
            runtime.p.lifecycle_log_path = out/'engine-lifecycle.jsonl'
            if args.damage_target_hp is not None:
                require(args.damage_target_hp > 0, 'setup must remain living')
                verified_owner(session, runtime.p)
                with RecoveryTransport(runtime.p) as transport:
                    party = joined_party(block(transport.g, ROSTER, 8*STRIDE),
                                         block(transport.g, MEMBERS, MEMBER_COUNT*STRIDE),
                                         runtime.adapter.expected)
                    target = next(p for p in party if p['id'] == result['setup_unit_id'])
                    require(args.damage_target_hp <= target['max_hp'], 'setup HP exceeds maximum')
                    for base in (target['canonical'], ROSTER + target['slot']*STRIDE):
                        session.write_bytes(base+0x18, args.damage_target_hp.to_bytes(2, 'little'),
                                            'A6.4 positive-HP setup only; actual engine damage must cause KO')
                    result['setup_before'] = party
            result['runtime_final_state'] = runtime.run()
            result.update(status='observed-KO-candidate' if runtime.natural_ko_candidate else 'bounded-without-KO',
                          ko_target_id=runtime.ko_target_id,
                          terminal_reason=runtime._terminal_reason, turns=runtime.turn,
                          export=runtime.export, fixture_writes=session.writes,
                          seeds=runtime.p.seeds, engine_turns=runtime.p.turns,
                          lifecycle_hits=runtime.p.lifecycle_hits,
                          invalid=runtime.p.invalid)
            result['inputs_unchanged'] = all(sha(p) == h for p, h in result['source_sha256'].items())
    except BaseException as exc:
        result['error'] = repr(exc)
        raise
    finally:
        if runtime:
            result.update(observations=len(runtime.observations), lifecycle_hits=runtime.p.lifecycle_hits,
                          fixture_writes=runtime.s.writes, invalid=runtime.p.invalid,
                          engine_turns=runtime.p.turns, seeds=runtime.p.seeds,
                          ko_target_id=runtime.ko_target_id, export=runtime.export,
                          runtime_final_state=runtime.state, terminal_reason=runtime._terminal_reason,
                          turns=runtime.turn)
        result['inputs_unchanged'] = all(sha(p) == h for p, h in result['source_sha256'].items())
        (out / 'research.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
