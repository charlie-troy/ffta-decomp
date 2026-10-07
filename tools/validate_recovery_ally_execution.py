"""Audit retained ally-Cure effect and actual final-prompt RAM, not continuation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_menu import RecoveryMenu, RecoveryStateError, exact, integer, require
from recovery_ally_confirmation import AllyConfirmationReader
from recovery_ally_target import canonical_facts
from tactics_policy import evaluate
from validate_recovery_menu import Memory


def audit(doc, captures, rom):
    require(doc['status'] in ('observed-effect-only', 'observed-effect-and-wait-only')
            and doc['inputs_unchanged'] and not doc['fixture_writes'], 'incomplete or mutated run')
    initial = Memory(captures['initial-ewram.bin'])
    memory = Memory(captures['confirmation-ewram.bin'])
    after = Memory(captures['after-cure-ewram.bin'])
    menu = RecoveryMenu(initial, rom, doc['owner'])
    units = {p['canonical']:exact(initial,p['canonical'],STRIDE) for p in doc['party_before']}
    menu.g = memory
    reader = AllyConfirmationReader(memory,menu,doc['party_before'],units)
    token = reader.confirmation_snapshot()
    decision = evaluate(reader.policy_snapshot(token),doc['policy_document'])
    require(decision == doc['recovery']['decision'] and decision['decision']['candidate_id'] == 'cure-ally',
            'retained final policy differs')
    policies = [e for e in doc['events'] if e['event'] == 'final_policy']
    require(len(policies) == 1 and policies[0]['evaluation'] == decision
            and evaluate(policies[0]['snapshot'],doc['policy_document']) == decision,
            'missing fresh final policy')
    finals = [e for e in doc['events'] if e['event'] == 'input_requested' and e.get('final')]
    require(len(finals) == 1 and finals[0]['key'] == 'A'
            and finals[0]['facts']['state'] == 'confirmation' and finals[0]['facts']['cursor'] == 0,
            'missing or duplicate final confirmation')
    raw = doc['raw_writes'][:50]
    require(len(raw) == 50 and all(not w['manual'] and w['event'] == 'key_write' for w in raw),
            'missing raw key ledger')
    require([w['val'] for w in raw[::5]] == [128,1,128,128,1,1,16,1,1,1]
            and all([w['hits'] for w in raw[i:i+5]] == [1,2,3,4,5]
                    and len({w['val'] for w in raw[i:i+5]}) == 1 for i in range(0,50,5))
            and all(a['t'] <= b['t'] for a,b in zip(raw,raw[1:])), 'raw delivery sequence differs')
    require(doc['finish_turn'] or len(doc['raw_writes']) == 50, 'input after final Cure')
    require('stop_requested_at' not in doc, 'STOP run cannot claim effect acceptance')
    require(doc['transport'][-1] == {'event':'trace_restored','write_count':len(doc['raw_writes'])},
            'trace ownership not restored')
    for member, before in units.items():
        current = exact(after,member,STRIDE)
        a,b = canonical_facts(current),canonical_facts(before)
        require(all(x == y for i,(x,y) in enumerate(zip(a,b)) if i not in (7,9)), 'party identity changed')
        old_hp,old_mp = integer(before,0x18,2),integer(before,0x1C,2)
        hp,mp = integer(current,0x18,2),integer(current,0x1C,2)
        if member == reader.caster:
            require(hp == old_hp and mp == old_mp-token.cost, 'caster resource attribution differs')
        else:
            require(old_hp < hp <= integer(before,0x1A,2) and mp == old_mp, 'ally effect attribution differs')
            require(doc['recovery']['target_after'] == {'canonical':member,'id':current[0x104],'hp':hp,'mp':mp},
                    'reported target effect differs')
    menu.g = after
    post = menu.snapshot()
    require(post.state == 'command' and 9 in post.rows and not post.enabled[post.rows.index(9)],
            'Action not consumed')
    require(doc['verified_turns'] == 0 and doc['continuation'] == 'unknown', 'unproven continuation claim')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    folder=Path(args.capture)
    doc=json.loads((folder/'probe.json').read_text())
    captures={p.name:p.read_bytes() for p in folder.glob('*.bin')}
    for name,digest in doc['capture_sha256'].items():
        assert hashlib.sha256(captures[name]).hexdigest() == digest,name
    for path,digest in doc['source_sha256'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest,path
    rom=Path('baserom.gba').read_bytes()
    audit(doc,captures,rom)
    rejected=[]
    mutations=[
        ('missing-ledger',lambda d:d.update(raw_writes=[])),
        ('post-final-input',lambda d:d['raw_writes'].append(d['raw_writes'][-1])),
        ('missing-final-policy',lambda d:d.update(events=[e for e in d['events'] if e['event']!='final_policy'])),
        ('false-continuation',lambda d:d.update(verified_turns=1)),
        ('wrong-target-report',lambda d:d['recovery']['target_after'].update(id=7)),
        ('wrong-policy',lambda d:d['policy_document'].update(assignments={})),
        ('STOP',lambda d:d.update(stop_requested_at=1)),
        ('fixture-write',lambda d:d.update(fixture_writes=[{'address':1}])),
    ]
    for label,mutate in mutations:
        changed=copy.deepcopy(doc);mutate(changed)
        try:audit(changed,captures,rom)
        except (RecoveryStateError,ValueError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    for label,tag,address,value,size in [
        ('self-target','confirmation',0x020159EC,0x0202267C,4),
        ('cancel','confirmation',0x0202DD58+0x18+0x69,1,1),
        ('unspent-MP','after-cure',0x02000080+0x1C,85,2),
        ('no-heal','after-cure',0x02000188+0x18,100,2),
        ('target-MP','after-cure',0x02000188+0x1C,220,2),
        ('alias-ID','confirmation',0x02000290+0x104,5,1),
    ]:
        changed=dict(captures);memory=Memory(changed[tag+'-ewram.bin']);memory.put(address,value,size)
        changed[tag+'-ewram.bin']=bytes(memory.data)
        try:audit(doc,changed,rom)
        except (RecoveryStateError,ValueError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'capture':args.capture,
        'target_before':doc['recovery']['target_before']['hp'],'target_after':doc['recovery']['target_after']['hp'],
        'caster_mp_before':85,'caster_mp_after':79,'mutations_rejected':rejected,
        'continuation':'unknown'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS actual final-prompt and ally effect; {len(rejected)} rejected mutations; continuation unknown')


if __name__=='__main__':main()
