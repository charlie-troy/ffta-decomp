"""Mutate a real public Life run through the full public runtime validator."""
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
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'baseline public Life run fails: '+str(validate(str(root))))
    run=json.loads((root/'run.json').read_text())
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    turn=next(i for i,e in enumerate(events) if e['kind']=='turn')
    journal=lambda e:e[turn]['recovery']
    def changed_ledger(e,l):
        extra=deepcopy(next(r for r in l if r.get('event')=='key_write'))
        extra['t']=events[-1]['t']+1;l.append(extra)
    controls=[
        ('missing journal',lambda r,e,l:e[turn].__setitem__('recovery',None)),
        ('missing adapter',lambda r,e,l:journal(e).__setitem__('policy_observations',[])),
        ('wrong adapter target',lambda r,e,l:journal(e)['policy_observations'][0]['snapshot']['candidates'][0]['target'].__setitem__('id',5)),
        ('wrong adapter actor',lambda r,e,l:journal(e)['policy_observations'][0]['snapshot']['actor'].__setitem__('id',7)),
        ('stale Life policy',lambda r,e,l:journal(e)['final_gate_events'][1]['snapshot'].__setitem__('age_seconds',999)),
        ('missing full policy',lambda r,e,l:journal(e).__setitem__('policy_document',{})),
        ('empty raw journal',lambda r,e,l:journal(e).__setitem__('gameplay_writes',[])),
        ('empty request journal',lambda r,e,l:journal(e).__setitem__('raw_writes',[])),
        ('empty ledger',lambda r,e,l:l.clear()),
        ('truncated ledger',lambda r,e,l:l.pop(next(i for i,x in enumerate(l) if x.get('event')=='key_write'))),
        ('post terminal',lambda r,e,l:changed_ledger(e,l)),
        ('duplicate Life final',lambda r,e,l:journal(e)['final_gate_events'].extend(deepcopy(journal(e)['final_gate_events'][-2:]))),
        ('duplicate Wait final',lambda r,e,l:journal(e)['Wait_events'].extend(deepcopy(journal(e)['Wait_events'][-2:]))),
        ('missing native trace',lambda r,e,l:journal(e).__setitem__('life_engine_hits',[])),
        ('native error',lambda r,e,l:journal(e).__setitem__('life_engine_errors',['injected'])),
        ('fixture write',lambda r,e,l:journal(e).__setitem__('fixture_writes',[{}])),
        ('missing before raw unit',lambda r,e,l:journal(e).__setitem__('effect_units_before',{})),
        ('missing after raw unit',lambda r,e,l:journal(e).__setitem__('effect_units_after',{})),
        ('changed raw growth',lambda r,e,l:journal(e)['effect_units_after'].__setitem__('33554824','00')),
        ('invented revived HP',lambda r,e,l:journal(e)['effect_attribution'].__setitem__('target_hp',[0,999])),
        ('invented EXP',lambda r,e,l:next(h for h in journal(e)['life_engine_hits'] if h['phase']=='EXP-award').__setitem__('awarded_exp',0)),
        ('missing level-up',lambda r,e,l:journal(e).__setitem__('life_engine_hits',[h for h in journal(e)['life_engine_hits'] if h['phase']!='level-up-after'])),
        ('wrong action',lambda r,e,l:e[turn]['selected_action'].__setitem__('ability_id',6)),
        ('wrong target',lambda r,e,l:e[turn]['selected_target'].__setitem__('id',5)),
        ('target MP spent',lambda r,e,l:next(p for p in e[turn]['engine_result']['players_after'] if p['id']==7).__setitem__('mp',75)),
        ('caster no MP spent',lambda r,e,l:next(p for p in e[turn]['engine_result']['players_after'] if p['id']==5).__setitem__('mp',221)),
        ('stale Wait actor',lambda r,e,l:journal(e)['Wait_events'][0]['snapshot']['actor'].__setitem__('mp',221)),
        ('invented next player',lambda r,e,l:journal(e)['Life_effect']['continuation'].__setitem__('relation','ally')),
        ('stale next canonical',lambda r,e,l:journal(e)['Life_effect']['continuation'].__setitem__('canonical',33554824)),
        ('stale next wrapper',lambda r,e,l:journal(e)['Life_effect']['continuation'].__setitem__('wrapper',journal(e)['Wait_facing']['actor_wrapper'])),
        ('no restored roster',lambda r,e,l:journal(e).__setitem__('post_Life_roster',[])),
        ('stale baseline level',lambda r,e,l:next(p for p in journal(e)['post_Life_roster'] if p['id']==5).__setitem__('level',40)),
        ('wrong trace count',lambda r,e,l:journal(e)['transport'][-1].__setitem__('write_count',0)),
        ('wrong halt',lambda r,e,l:journal(e)['transport'][0].__setitem__('reply','S04')),
        ('source changed',lambda r,e,l:r.__setitem__('inputs_unchanged',False)),
        ('missing source proof',lambda r,e,l:r.pop('inputs_unchanged')),
        ('empty source closure',lambda r,e,l:r.__setitem__('input_sha256',{})),
        ('changed source after',lambda r,e,l:r.__setitem__('input_sha256_after',{})),
    ]
    rejected=[]
    with tempfile.TemporaryDirectory(prefix='ffta-public-Life-mutations-') as directory:
        path=Path(directory)
        for label,edit in controls:
            r,e,l=deepcopy(run),deepcopy(events),deepcopy(ledger);edit(r,e,l)
            (path/'run.json').write_text(json.dumps(r),encoding='utf-8')
            (path/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in e),encoding='utf-8')
            (path/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in l),encoding='utf-8')
            errors=validate(str(path));require(bool(errors),'public Life mutation survived: '+label)
            rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-public-Life-receipt-mutations','scope':__doc__,'run':str(root),'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ('tools/validate_life_recovery_runtime.py','tools/life_recovery_receipt.py',
                                         'tools/validate_autobattle_runtime.py')},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ('run.json','events.jsonl','input-log.jsonl')},
        'limitations':['Retained public validator audit; not a fresh public battle.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS public Life:',len(rejected),'receipt mutations')


if __name__=='__main__':main()
