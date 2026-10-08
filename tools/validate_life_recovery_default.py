"""Audit the real no-opt-in control on the exact Life fixture."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from recovery_menu import require
from validate_autobattle_runtime import validate


def check(run, events):
    require(not run.get('bounded_ally_life') and run['inputs_unchanged'], 'default opt-in/source differs')
    turns = [e for e in events if e['kind'] == 'turn']
    require(run['turns'] == 1 and len(turns) == 1, 'default control has no attributed turn')
    turn = turns[0]
    require(turn['selected_action']['kind'] == 'identified-wait' and not turn.get('recovery'),
            'default path used recovery')
    require(turn['tactics']['candidates'] == ['move', 'wait'] and
            [c['kind'] for c in turn['tactics']['snapshot']['candidates']] == ['move', 'wait'],
            'default path offered an ability')
    result = turn['engine_result']
    require(result['verified'], 'default engine result missing')
    for phase in ('players_before', 'players_after'):
        rows = {r['id']: r for r in result[phase]}
        require(set(rows) == {5, 7} and (rows[5]['hp'], rows[5]['mp'], rows[5]['level']) == (241, 221, 40)
                and (rows[7]['hp'], rows[7]['mp']) == (0, 85), 'default control changed Life resources')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', required=True); ap.add_argument('--out', required=True)
    args = ap.parse_args(); root = Path(args.run)
    require(not validate(str(root)), 'default public receipt failed')
    run = json.loads((root/'run.json').read_text())
    events = [json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    check(run, events)
    turn_index = next(i for i, e in enumerate(events) if e['kind'] == 'turn')
    edits = [
        ('opt-in changed', lambda r, e: r.__setitem__('bounded_ally_life', True)),
        ('source changed', lambda r, e: r.__setitem__('inputs_unchanged', False)),
        ('ability offered', lambda r, e: e[turn_index]['tactics']['candidates'].append('life-ally')),
        ('revival invented', lambda r, e: e[turn_index]['engine_result']['players_after'][1].__setitem__('hp', 221)),
        ('MP spent', lambda r, e: e[turn_index]['engine_result']['players_after'][0].__setitem__('mp', 211)),
    ]
    rejected = []
    for label, edit in edits:
        r, e = deepcopy(run), deepcopy(events); edit(r, e)
        try: check(r, e)
        except ValueError: rejected.append(label)
        else: raise AssertionError('default mutation survived: ' + label)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    output = {'status': 'pass-public-Life-default', 'scope': __doc__, 'rejected': rejected,
        'source_sha256': {p: sha(p) for p in ['tools/validate_life_recovery_default.py', 'tools/validate_autobattle_runtime.py']},
        'evidence_sha256': {str(root/n): sha(root/n) for n in ['run.json', 'events.jsonl', 'input-log.jsonl']},
        'limitations': ['One retained no-opt-in fixture control; no arbitrary-party claim.']}
    Path(args.out).write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('PASS default no-Life control:', len(rejected), 'mutations')


if __name__ == '__main__': main()
