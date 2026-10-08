"""Audit local natural-KO research captures; no fresh-runtime acceptance claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fixture_guard import ROSTER, STRIDE
from probe_recovery_ko_lifecycle import joined_party, source_dependencies
from recovery_menu import MEMBERS, integer, require


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directory):
    directory = Path(directory)
    result = json.loads((directory / 'research.json').read_text())
    observations = [json.loads(line) for line in (directory / 'ko-observations.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
    inputs = [json.loads(line) for line in (directory / 'input-log.jsonl').read_text().splitlines()]
    require(not result.get('error') and not result.get('invalid'), 'research failed or trapped')
    require(result.get('inputs_unchanged') is True, 'research input/source files changed')
    for path in source_dependencies('probe_recovery_ko_lifecycle'):
        require(result['source_sha256'].get(path) == digest(Path(path)), 'runtime source hash mismatch: '+path)
    target_id = result['ko_target_id']
    require(target_id in (5, 7), 'invalid research KO target')
    if result.get('positive_hp_setup') is None:
        require(not result['fixture_writes'], 'research wrote fixture RAM')
    else:
        setup = result['positive_hp_setup']
        require(type(setup) is int and setup > 0, 'setup directly wrote a KO')
        before = next(p for p in result['setup_before'] if p['id'] == result['setup_unit_id'])
        addresses = {f"{before['canonical']+0x18:08x}", f"{ROSTER+before['slot']*STRIDE+0x18:08x}"}
        writes = result['fixture_writes']
        require(len(writes) == 2 and {w['addr'] for w in writes} == addresses,
                'setup wrote outside the two HP fields')
        require(all(w['width'] == 2 and w['new'] == w['requested'] == setup.to_bytes(2, 'little').hex()
                    and w['reply'] == 'OK' and int.from_bytes(bytes.fromhex(w['old']), 'little') > 0
                    for w in writes), 'setup write was not verified positive HP')
    require(all(e['selected_action']['kind'] == 'identified-wait'
                and e['position_before'] == e['position_after'] for e in events if e['kind'] == 'turn'),
            'non-Wait player turn')
    require(all(i['mask'] in (1, 0x80) and i['hits'] == 5 and not i['aborted']
                for i in inputs if i['event'] == 'press'), 'unsupported/partial research input')
    require(sum(e['kind'] == 'stop' for e in events) == 1, 'research terminal event absent or duplicated')
    rows = None
    baseline = None
    last_blobs = {}
    changes = []
    candidates = []
    for index, observation in enumerate(observations):
        if 'party' not in observation:
            require('rejected' in observation, 'unknown observation shape')
            continue
        if rows is None:
            rows = observation['party']
        for name, expected in observation.get('captures', {}).items():
            path = directory / name
            require(digest(path) == expected, 'raw KO capture hash mismatch')
            kind = 'roster' if name.endswith('-roster.bin') else 'members'
            last_blobs[kind] = path.read_bytes()
        require(set(last_blobs) == {'roster', 'members'}, 'missing KO capture pair')
        joined = joined_party(last_blobs['roster'], last_blobs['members'], rows)
        require(joined == observation['party'], 'KO metadata differs from raw captures')
        if baseline is None:
            baseline = joined
            require(all(p['hp'] > 0 for p in baseline), 'missing living baseline')
        for pin in joined:
            start = pin['canonical'] - MEMBERS
            unit = last_blobs['members'][start:start+STRIDE]
            mirror = last_blobs['roster'][pin['slot']*STRIDE:(pin['slot']+1)*STRIDE]
            require(unit[6:8] == bytes((1, 5)) and integer(unit, 0x28, 2) & 0x9000 == 0,
                    'research party job/race/side changed')
            require(unit[0xE8:0xEE] == mirror[0xE8:0xEE]
                    and unit[0xF1:0xF3] == mirror[0xF1:0xF3],
                    'canonical/mirror KO status or counters disagree')
            before = next(p for p in baseline if p['id'] == pin['id'])
            require(all(pin[k] == before[k] for k in ('canonical', 'id', 'name', 'slot', 'max_hp', 'max_mp')),
                    'research identity or max resources changed')
        resources = [(p['id'], p['hp'], p['mp'], p['ko_suffered']) for p in joined]
        if not changes or resources != changes[-1]['resources']:
            changes.append({'observation': index, 't': observation['t'], 'resources': resources})
        target = next(p for p in joined if p['id'] == target_id)
        caster = next(p for p in joined if p['id'] != target_id)
        before = next(p for p in baseline if p['id'] == target_id)
        candidate = (target['hp'] == 0 and caster['hp'] > 0
                     and target['ko_suffered'] > before['ko_suffered']
                     and not any(target['statuses'].values()))
        require(candidate == observation['zero_hp_counter_candidate'], 'KO candidate metadata differs')
        if candidate:
            candidates.append({'index': index, 't': observation['t'], 'party': joined,
                               'captures': observation.get('captures', {})})
    target = next(p for p in baseline if p['id'] == target_id)
    damage_pairs = []
    hp_store_pairs = []
    before_by_context = {}
    before_by_unit = {}
    for hit in result.get('lifecycle_hits', []):
        if hit['phase'] == 'damage-before':
            before_by_context[hit['context']] = hit
        elif hit['phase'] == 'HP-adjust-before':
            before_by_unit[hit['unit']] = hit
        elif hit['phase'] == 'HP-adjust-after' and hit['id'] == target_id and hit['hp'] == 0:
            before = before_by_unit.get(hit['unit'])
            require(before is not None and before['hp'] > 0 and before['store_value'] == hit['store_value'] == 0,
                    'HP-zero store lacks a positive HP precursor')
            require(all(before[k] == hit[k] for k in ('unit', 'name', 'id', 'mp'))
                    and before['name'] == target['name'] and hit['unit'] == f"{target['canonical']:08x}"
                    and before['pc'] == '080a2298' and hit['pc'] == '080a229a',
                    'native HP-zero store identity attribution failed')
            hp_store_pairs.append({'before': before, 'after': hit})
        elif hit['phase'] == 'damage-after' and hit['id'] == target_id and hit['hp'] == 0:
            before = before_by_context.get(hit['context'])
            require(before is not None and before['hp'] > 0, 'KO damage lacks a positive HP precursor')
            require(all(before[k] == hit[k] for k in ('unit', 'name', 'id', 'wrapper', 'context', 'mp'))
                    and before['name'] == target['name'] and hit['unit'] == f"{target['canonical']:08x}"
                    and hit['ko_suffered'] == before['ko_suffered']+1
                    and hit['damage'] >= before['hp'] and hit['result_flags'] & 0x1000,
                    'KO damage identity/resources/counter/flag attribution failed')
            damage_pairs.append({'before': before, 'after': hit})
    native_KO = damage_pairs + hp_store_pairs
    latest_KO = max((p['after']['t'] for p in native_KO), default=None)
    picked_after = [h for h in result.get('lifecycle_hits', [])
                    if h['phase'] == 'battle-driver-picked' and h['hp'] > 0
                    and latest_KO is not None and h['t'] >= latest_KO]
    interactive_skip = [h for h in result.get('lifecycle_hits', [])
                        if h['phase'] == 'tail-loop-skip' and h['caller_lr'] == '0809f870'
                        and h['id'] == target_id and h['hp'] == 0 and h['flags'] & 0x2000 == 0]
    if result['status'] == 'observed-KO-candidate':
        require(len(candidates) >= 2 and native_KO and picked_after,
                'candidate status lacks repeated KO, attributed damage and a live driver pick')
    export = result.get('export')
    if export:
        require(digest(Path(export['path'])) == export['sha256'], 'exported KO state hash differs')
    return {'status': 'pass-retained-KO-observation-audit', 'scope': __doc__,
            'run': str(directory), 'observations': len(observations),
            'positive_hp_setup': result.get('positive_hp_setup'), 'ko_target_id': target_id,
            'verified_wait_turns': sum(e['kind'] == 'turn' for e in events),
            'input_writes': sum(i['event'] == 'key_write' for i in inputs),
            'resource_changes': changes, 'KO_candidates': candidates,
            'attributed_engine_KO_damage': damage_pairs, 'live_driver_picks_after_KO': picked_after,
            'native_HP_zero_stores': hp_store_pairs,
            'interactive_KO_loop_skips': interactive_skip,
            'limitations': ['Retained raw captures and Wait ledgers; no fresh replay performed by this audit.',
                            'A candidate does not certify full scheduling, targeting, reload or revival.']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    result = audit(args.directory)
    result['source_sha256'] = {p: digest(Path(p)) for p in (
        'tools/audit_recovery_ko_observations.py', 'tools/probe_recovery_ko_lifecycle.py',
        'tools/fixture_guard.py', 'tools/recovery_menu.py')}
    result['evidence_sha256'] = {str(p): digest(p) for p in (
        Path(args.directory) / name for name in ('research.json', 'ko-observations.jsonl', 'events.jsonl', 'input-log.jsonl'))}
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f"PASS retained KO audit: {result['observations']} observations, {len(result['KO_candidates'])} candidates")


if __name__ == '__main__':
    main()
