"""Retained KO research joins and mutation guards; no live lifecycle claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from probe_recovery_ko_lifecycle import joined_party
from recovery_menu import MEMBERS, RecoveryStateError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    directory = Path(args.capture)
    observations = [json.loads(line) for line in (directory / 'ko-observations.jsonl').read_text().splitlines()]
    baseline = next(o for o in observations if 'party' in o and 'captures' in o)
    rows = baseline['party']
    paths = {kind: directory / next(n for n in baseline['captures'] if n.endswith('-'+kind+'.bin'))
             for kind in ('roster', 'members')}
    roster, members = (paths[k].read_bytes() for k in ('roster', 'members'))
    assert all(hashlib.sha256((directory/n).read_bytes()).hexdigest() == h
               for n, h in baseline['captures'].items())
    assert joined_party(roster, members, rows) == rows
    rejected = []
    def reject(name, r=roster, m=members, expected=rows):
        try:
            joined_party(r, m, expected)
        except (RecoveryStateError, KeyError):
            rejected.append(name)
        else:
            raise AssertionError('accepted KO join mutation: '+name)
    reject('short-roster', r=roster[:-1])
    reject('short-members', m=members[:-1])
    reject('missing-party-row', expected=rows[:1])
    aliased = copy.deepcopy(rows)
    aliased[1]['id'] = aliased[0]['id']
    reject('expected-id-alias', expected=aliased)
    aliased = copy.deepcopy(rows)
    aliased[1]['name'] = aliased[0]['name']
    reject('expected-name-alias', expected=aliased)
    positive_zero_controls = []
    for pin in rows:
        start = pin['canonical']-MEMBERS
        mirror_start = pin['slot']*STRIDE
        for label, offset, value in (
                ('name', 0, 0), ('id', 0x104, 42), ('job', 7, 6), ('race', 6, 2),
                ('tile', 0xF6, 64), ('HP', 0x18, 255), ('MP', 0x1C, 255),
                ('Petrify', 0xE9, 1), ('KO-counter', 0xF2, 77)):
            changed = bytearray(members)
            changed[start+offset] = value
            reject(f"{pin['id']}-canonical-{label}", m=bytes(changed))
        for label, offset, value in (('enemy', 0x29, 0x80), ('unaffiliated', 0x29, 0x10),
                                     ('job', 7, 6), ('race', 6, 2), ('tile', 0xF6, 64)):
            changed_r, changed_m = bytearray(roster), bytearray(members)
            changed_r[mirror_start+offset] = changed_m[start+offset] = value
            reject(f"{pin['id']}-coherent-{label}", r=bytes(changed_r), m=bytes(changed_m))
        for label, offset, count in (('name-alias', 0, 4), ('id-alias', 0x104, 1)):
            changed = bytearray(members)
            alias_start = 13*STRIDE
            changed[alias_start+offset:alias_start+offset+count] = members[start+offset:start+offset+count]
            reject(f"{pin['id']}-{label}", m=bytes(changed))
        changed_r, changed_m = bytearray(roster), bytearray(members)
        changed_r[mirror_start+0x18:mirror_start+0x1A] = b'\0\0'
        changed_m[start+0x18:start+0x1A] = b'\0\0'
        joined = joined_party(bytes(changed_r), bytes(changed_m), rows)
        assert next(p for p in joined if p['id'] == pin['id'])['hp'] == 0
        positive_zero_controls.append(pin['id'])
    result = {'status': 'pass-retained-KO-join-guards', 'scope': __doc__, 'rejected': rejected,
              'synthetic_zero_hp_join_controls': positive_zero_controls,
              'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
                  'tools/validate_recovery_ko_join.py', 'tools/probe_recovery_ko_lifecycle.py',
                  'tools/recovery_menu.py', 'tools/fixture_guard.py')},
              'capture_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
              'limitations': ['Synthetic zero-HP mutations test identity joins only; they do not create genuine KO evidence.',
                              'No public living-only guard was relaxed; no targeting or revival input.']}
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'PASS retained KO joins: {len(rejected)} mutations rejected, 2 zero-HP join controls')


if __name__ == '__main__':
    main()
