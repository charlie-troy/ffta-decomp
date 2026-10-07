"""Audit a bounded research ally Cure/Wait and one independently attributed next actor.

This gate does not certify public integration, two later enemies or battle completion.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_menu import RecoveryMenu, RecoveryStateError, exact, require
from recovery_party_continuation import observe_party_continuation
from tactics_policy import evaluate
from validate_recovery_menu import Memory
from validate_recovery_ally_execution import audit as audit_effect


def audit(doc,captures,rom):
    require(doc['status'] == 'observed-effect-wait-and-next-actor'
            and doc['verified_turns'] == 1 and doc['continuation'] == 'independent-next-actor'
            and doc['finish_turn'], 'incomplete bounded turn')
    # Audit the independently captured effect phase with its original scope.
    effect=copy.deepcopy(doc)
    effect.update(status='observed-effect-and-wait-only',verified_turns=0,continuation='unknown')
    audit_effect(effect,captures,rom)
    raw=doc['raw_writes']
    require(len(raw) == 70 and [w['val'] for w in raw[50::5]] == [128,128,1,1]
            and all([w['hits'] for w in raw[i:i+5]] == [1,2,3,4,5]
                    and len({w['val'] for w in raw[i:i+5]}) == 1
                    and all(not w['manual'] and w['event'] == 'key_write' for w in raw[i:i+5])
                    for i in range(50,70,5))
            and all(a['t'] <= b['t'] for a,b in zip(raw,raw[1:])), 'Wait raw ledger differs')
    initial=Memory(captures['initial-ewram.bin'])
    facing_memory=Memory(captures['facing-ewram.bin'])
    menu=RecoveryMenu(initial,rom,doc['owner']);menu.g=facing_memory
    facing=menu.snapshot()
    require(facing.state == 'facing' and facing.driver_state == 47
            and facing.hp == doc['recovery']['after']['hp']
            and facing.mp == doc['recovery']['after']['mp'], 'wrong Wait-facing capture')
    for field in ('member','actor_wrapper','state','selection','hp','mp','facing_direction'):
        require(facing.receipt()[field] == doc['wait']['facing'][field], 'reported facing differs')
    events=doc['wait_events']
    finals=[e for e in events if e['event'] == 'input_requested' and e.get('final')]
    require(len(finals) == 1 and finals[0]['key'] == 'A' and finals[0]['facts']['state'] == 'facing',
            'missing single Wait final')
    policies=[e for e in events if e['event'] == 'final_policy']
    require(len(policies) == 1 and evaluate(policies[0]['snapshot'],doc['policy_document'])
            == policies[0]['evaluation'] == doc['wait']['decision']
            and doc['wait']['decision']['decision']['candidate_id'] == 'recovery-wait'
            and doc['wait']['outcome'] == 'confirmed', 'Wait policy differs')
    units={p['canonical']:exact(initial,p['canonical'],STRIDE) for p in doc['party_before']}
    observed=observe_party_continuation(Memory(captures['continuation-ewram.bin']),rom,doc['owner'],
                                       doc['wait']['facing'],doc['party_before'],units,doc['baseline_roster'])
    require(doc['continuations'] == [observed] and observed['relation'] == 'enemy',
            'independent enemy continuation differs')
    require(observed['party_after'] == [
        {'id':p['id'],'canonical':p['canonical'],'hp':doc['recovery']['target_after']['hp'] if p['id']==5
         else doc['recovery']['after']['hp'],'mp':p['mp'] if p['id']==5 else doc['recovery']['after']['mp'],
         'tile':p['tile']} for p in doc['party_before']], 'party resources differ before next enemy')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.capture)
    doc=json.loads((folder/'probe.json').read_text())
    captures={p.name:p.read_bytes() for p in folder.glob('*.bin')}
    for name,digest in doc['capture_sha256'].items():
        assert hashlib.sha256(captures[name]).hexdigest()==digest,name
    for path,digest in doc['source_sha256'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    rom=Path('baserom.gba').read_bytes();audit(doc,captures,rom)
    rejected=[]
    for label,mutate in [
        ('extra-input',lambda d:d['raw_writes'].append(d['raw_writes'][-1])),
        ('missing-Wait-final',lambda d:d.update(wait_events=[e for e in d['wait_events']
            if not(e['event']=='input_requested' and e.get('final'))])),
        ('wrong-Wait-policy',lambda d:d['wait']['decision']['decision'].update(candidate_id='cure-ally')),
        ('wrong-facing',lambda d:d['wait']['facing'].update(member=0x02000188)),
        ('missing-continuation',lambda d:d.update(continuations=[])),
        ('wrong-next-actor',lambda d:d['continuations'][0]['actor'].update(id=7)),
        ('false-two-turns',lambda d:d.update(verified_turns=2)),
        ('STOP',lambda d:d.update(stop_requested_at=1)),
    ]:
        changed=copy.deepcopy(doc);mutate(changed)
        try:audit(changed,captures,rom)
        except (RecoveryStateError,KeyError,IndexError,ValueError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'capture':args.capture,
        'ally_hp_after':doc['recovery']['target_after']['hp'],'caster_mp_after':doc['recovery']['after']['mp'],
        'raw_writes':len(doc['raw_writes']),'next_actor':doc['continuations'][0]['actor'],
        'mutations_rejected':rejected},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS ally Cure / Wait / next enemy; {len(rejected)} rejected receipt mutations')


if __name__=='__main__':main()
