"""Validate public Life refusal/STOP semantics and adversarial partial journals."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

from recovery_menu import require
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--mode',choices=('reserve','navigation','Life-final','Life-Wait-final'),required=True)
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'public refusal baseline fails: '+str(validate(str(root))))
    run=json.loads((root/'run.json').read_text());events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    index=next(i for i,e in enumerate(events) if e.get('recovery'));journal=events[index]['recovery']
    require(run['bounded_ally_life'] and run['inputs_unchanged'] and run['turns']==0
            and journal['schema']=='ffta-life-recovery-turn/1' and journal['gameplay_writes'],
            'public Life refusal/identified input evidence missing')
    require(not journal.get('Wait_final_attempted',False),'public refusal still attempted Wait final')
    if args.mode=='Life-Wait-final':
        require(journal['final_confirmation'] and journal['effect_attribution'] and journal['Wait_facing']
                and journal['Life_effect']['wait']=='unexecuted','public Wait STOP lacks attributed Life/facing')
    else:require(not journal['final_confirmation'] and not journal.get('effect_attribution')
                 and not journal['life_engine_hits'],'public pre-Life refusal still cast')
    if args.mode=='reserve':
        require(run['final_state']=='stalled' and 'policy declined Life; no final input' in run['terminal_reason'],
                'public reserve stopped for another reason')
        require(len(journal['policy_observations'])==1 and len(journal['final_gate_events'])==1,
                'public reserve adapter evidence missing')
        policy=journal['policy_document'];event=journal['final_gate_events'][0]
        require(policy['assignments']['party']['player']['rules'][0]['when']['remaining_mp_after_cost']=={'gte':212}
                and event['evaluation']['decision'] is None and event['snapshot']['actor']['mp']==221
                and event['snapshot']['candidates'][0]['cost']==10,'public reserve did not reject remaining211')
    else:
        require(run['final_state']=='paused' and 'STOP requested during bounded recovery' in run['terminal_reason'],
                'public STOP pause missing')
        require(any(r.get('event')=='stop_requested' for r in ledger),'public STOP latch missing')
        if args.mode=='navigation':require(len(journal['navigation'])<=1,'navigation STOP came too late')
        elif args.mode=='Life-final':
            require(len(journal['final_gate_events'])==len(journal['policy_observations'])==1
                    and journal['policy_observations'][0]['evaluation']['decision']['candidate_id']=='life-ally',
                    'Life final STOP did not interrupt authorized policy')
    mutations=[('missing raw journal',lambda r,e,l:e[index]['recovery'].__setitem__('gameplay_writes',[])),
        ('empty ledger',lambda r,e,l:l.clear()),
        ('missing source proof',lambda r,e,l:r.pop('inputs_unchanged')),
        ('invented final Life',lambda r,e,l:e[index]['recovery'].__setitem__('final_confirmation',not journal['final_confirmation'])),
        ('invented final Wait',lambda r,e,l:e[index]['recovery'].__setitem__('Wait_final_attempted',True)),
        ('duplicate request',lambda r,e,l:e[index]['recovery'].setdefault('Wait_events',[]).extend([
            {'event':'final_input_requested','mask':1},{'event':'final_input_requested','mask':1}])),
        ('wrong trace cleanup',lambda r,e,l:e[index]['recovery']['transport'][-1].__setitem__('write_count',0)),
    ]
    if journal['policy_observations']:
        mutations.extend([
            ('missing adapter',lambda r,e,l:e[index]['recovery'].__setitem__('policy_observations',[])),
            ('wrong legal target',lambda r,e,l:e[index]['recovery']['policy_observations'][0]['snapshot']['candidates'][0]['target'].__setitem__('id',5)),
            ('changed policy',lambda r,e,l:e[index]['recovery'].__setitem__('policy_document',{})),
        ])
    def leak(r,e,l):
        key=deepcopy(next(x for x in l if x.get('event')=='key_write'));key['t']=events[-1]['t']+1;l.append(key)
    mutations.append(('post terminal input',leak))
    rejected=[]
    with tempfile.TemporaryDirectory(prefix='ffta-Life-decline-') as directory:
        p=Path(directory)
        for label,edit in mutations:
            r,e,l=deepcopy(run),deepcopy(events),deepcopy(ledger);edit(r,e,l)
            (p/'run.json').write_text(json.dumps(r),encoding='utf-8')
            (p/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in e),encoding='utf-8')
            (p/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in l),encoding='utf-8')
            errors=validate(str(p));require(bool(errors),'partial public Life mutation survived: '+label)
            rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    output={'status':'pass-public-Life-decline','scope':__doc__,'mode':args.mode,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ('tools/validate_life_recovery_decline.py','tools/life_recovery_receipt.py',
                                         'tools/validate_autobattle_runtime.py')},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ('run.json','events.jsonl','input-log.jsonl')},
        'limitations':['Captured public lifecycle audit only; no new emulator execution.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS public Life',args.mode,':',len(rejected),'partial receipt mutations')


if __name__=='__main__':main()
