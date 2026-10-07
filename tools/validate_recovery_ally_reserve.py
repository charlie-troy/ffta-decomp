"""Audit live reserve-policy refusal at the ally Do-it prompt; no fallback-turn claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from recovery_menu import RecoveryStateError, require
from tactics_policy import evaluate


def audit(doc,normal):
    require(doc['status']=='unknown' and doc['inputs_unchanged'] and doc['verified_turns']==0
            and 'policy declined ally Cure; no final input' in doc['error']
            and 'recovery' not in doc and 'stop_requested_at' not in doc, 'wrong reserve refusal outcome')
    raw=doc['raw_writes'];masks=[128,1,128,128,1,1,16,1,1]
    require(len(raw)==45 and [w['val'] for w in raw[::5]]==masks
            and all([w['hits'] for w in raw[i:i+5]]==[1,2,3,4,5]
                    and all(w['val']==masks[i//5] and not w['manual'] for w in raw[i:i+5])
                    for i in range(0,45,5)), 'reserve raw ledger differs')
    require(doc['transport'][-1]=={'event':'trace_restored','write_count':45}
            and not any(e['event']=='input_requested' and e.get('final') for e in doc['events']),
            'reserve final input or missing cleanup')
    policies=[e for e in doc['events'] if e['event']=='policy']
    require(len(policies)==1, 'missing reserve policy observation')
    event=policies[0];snapshot=event['snapshot']
    require(snapshot['identity']=='verified' and snapshot['actor']['id']==7 and snapshot['actor']['mp']==85
            and snapshot['candidates']==[{'id':'cure-ally','kind':'ability','action_id':1,'legal':True,
                'cost':6,'ability_name':'Cure','relation':'ally','target':{'kind':'unit','id':5},
                'target_hp':100,'target_max_hp':241,'target_mp':221}], 'wrong live reserve candidate')
    require(evaluate(snapshot,doc['policy_document'])==event['evaluation']
            and (event['evaluation'].get('decision') or {}).get('candidate_id')!='cure-ally'
            and evaluate(snapshot,normal)['decision']['candidate_id']=='cure-ally', 'policy comparison differs')
    changed=copy.deepcopy(normal)
    for rule in changed['assignments']['party']['player']['rules']:
        if rule['id']=='heal-wounded-ally':rule['when']['remaining_mp_after_cost']['gte']=80
    require(changed==doc['policy_document'], 'reserve control changed more than one threshold')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.capture);doc=json.loads((folder/'probe.json').read_text())
    for path,digest in doc['source_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    for name,digest in doc['capture_sha256'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
    normal=json.loads(Path('configs/tactics/healer.json').read_text());audit(doc,normal)
    rejected=[]
    for label,mutate in [
        ('post-decline-input',lambda d:d['raw_writes'].append(d['raw_writes'][-1])),
        ('missing-policy',lambda d:d.update(events=[e for e in d['events'] if e['event']!='policy'])),
        ('free-Cure',lambda d:next(e for e in d['events'] if e['event']=='policy')['snapshot']['candidates'][0].update(cost=0)),
        ('wrong-target',lambda d:next(e for e in d['events'] if e['event']=='policy')['snapshot']['candidates'][0]['target'].update(id=7)),
        ('false-turn',lambda d:d.update(verified_turns=1)),
        ('missing-cleanup',lambda d:d['transport'].pop()),
    ]:
        changed=copy.deepcopy(doc);mutate(changed)
        try:audit(changed,normal)
        except (RecoveryStateError,KeyError,IndexError,ValueError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'raw_writes':45,
        'mutations_rejected':rejected,'comparison':'same live candidate: reserve8 selects Cure, reserve80 declines',
        'effect':'No final Cure input; no post-decline RAM resource capture retained'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS live reserve refusal; {len(rejected)} rejected receipts')


if __name__=='__main__':main()
