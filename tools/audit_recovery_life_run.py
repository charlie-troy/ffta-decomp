"""Audit retained bounded Life/Wait runs against raw RAM, inputs and policy.

Retained replay is not a new emulator run. Historical source versions must be
available locally or in an explicitly supplied Git ref with identical bytes.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from fixture_guard import STRIDE
from recovery_life_effect import verify_life_effect
from recovery_life_target import LifeOverlayReader
from recovery_life_wait import LifeWaitBoundary
from recovery_menu import require
from recovery_menu_list import ResearchMenuList
from recovery_party_continuation import observe_party_continuation
from tactics_policy import evaluate, validate_policy
from validate_recovery_life_menu import Memory
from probe_recovery_ko_lifecycle import source_dependencies


def digest(data):return hashlib.sha256(data).hexdigest()


def audit(directory,doc,rom,refs):
    require(doc['status']=='observed-Life-Wait-continuation' and doc['inputs_unchanged']
            and not doc['fixture_writes'] and not doc['raw_writes']==[], 'Life run authority differs')
    require(set(source_dependencies('probe_recovery_life_overlay')) <= set(doc['source_sha256'])
            and doc['source_sha256'].get('baserom.gba')==digest(rom), 'Life source closure missing')
    require(doc['policy_document']==json.loads(Path('configs/tactics/healer.json').read_text()),
            'Life full policy differs from its source document')
    for name,expected in doc['source_sha256'].items():
        path=Path(name)
        if path.is_file() and digest(path.read_bytes())==expected:continue
        matched=False
        for ref in refs:
            proc=subprocess.run(['git','show',ref+':'+name],capture_output=True)
            if proc.returncode==0 and digest(proc.stdout)==expected:matched=True;break
        require(matched,'Life source version unavailable: '+name)
    data={}
    for name,expected in doc['capture_sha256'].items():
        data[name]=directory.joinpath(name).read_bytes()
        require(digest(data[name])==expected and len(data[name])==0x40000,'Life raw capture differs: '+name)
    party=doc['party'];caster=next(p for p in party if p['id']==5);target=next(p for p in party if p['id']==7)
    units=lambda raw:{p['canonical']:raw[p['canonical']-0x02000000:p['canonical']-0x02000000+STRIDE] for p in party}
    g=Memory(data['final-prompt-second-ewram.bin']);m=ResearchMenuList(g,rom,doc['owner'],caster['canonical'])
    before=units(data['final-prompt-second-ewram.bin']);reader=LifeOverlayReader(g,m,party,before,clock=lambda:1)
    token=reader.confirmation_snapshot();reader.revalidate(token,at_target=True)
    snapshot=reader.policy_snapshot(token)
    policy_events=[e for e in doc['final_gate_events'] if e['event'] in ('policy','final_policy')]
    require(len(policy_events)==2,'Life policy evaluations missing/repeated')
    normalize=lambda value:value|{'age_seconds':0}
    for event in policy_events:
        require(event['policy']==validate_policy(doc['policy_document']) and normalize(event['snapshot'])==normalize(snapshot),
                'Life full policy snapshot differs from raw prompt')
        require(evaluate(event['snapshot'],event['policy'])==event['evaluation']
                and event['evaluation']['decision']['candidate_id']=='life-ally','Life policy authorization differs')
    require([e['event'] for e in doc['final_gate_events']]==
            ['policy','final_policy','final_input_requested','final_input_delivered']
            and doc['final_gate_events'][-2]['mask']==1 and doc['final_gate_events'][-1]['hits']==5
            and doc['final_confirmation'],'Life final attempt count/delivery differs')
    hits=[json.loads(line) for line in directory.joinpath('Life-engine.jsonl').read_text().splitlines()]
    require(hits==doc['life_engine_hits'] and not doc['life_engine_errors'],'Life engine journal differs')
    after=units(data['after-Life-ewram.bin'])
    effect=verify_life_effect(before,after,hits,caster,target)
    require(effect==doc['effect_attribution'],'Life effect attribution differs')
    g=Memory(data['Wait-facing-ewram.bin']);m=ResearchMenuList(g,rom,doc['owner'],caster['canonical'])
    wait=LifeWaitBoundary(g,m,after,clock=lambda:1);facing=wait.snapshot();wait.revalidate(facing)
    ws=wait.policy_snapshot(facing)
    require(doc['Wait_final_attempted'] and [e['event'] for e in doc['Wait_events']]==
            ['final_policy','revalidated_final_policy','final_input_requested','final_input_delivered']
            and doc['Wait_events'][-2]['mask']==1 and doc['Wait_events'][-1]['hits']==5,
            'Wait final attempt count/delivery differs')
    for event in doc['Wait_events'][:2]:
        require(event['policy']==validate_policy(doc['policy_document']) and normalize(event['snapshot'])==normalize(ws)
                and evaluate(event['snapshot'],event['policy'])==event['evaluation']
                and event['evaluation']['decision']['candidate_id']=='wait','Wait policy authorization differs')
    stages=[('command',9,221),('action-group',9,221),('ability-list',5,221),('command',10,211)]
    stage=0
    for navigation in doc['navigation']:
        require(stage<len(stages),'Life navigation after completed Wait selection')
        kind,value,mp=stages[stage];before_list=navigation['before']
        require(before_list['state']==kind and before_list['mp']==mp and navigation['hits']==5,
                'Life navigation stage/resource differs')
        rows=before_list['ability_ids'] if kind=='ability-list' else before_list['rows']
        require(rows.count(value)==1,'Life navigation action identity ambiguous')
        index=rows.index(value);current=before_list['scroll']+before_list['cursor']
        require(before_list['enabled'][index]==1 and navigation['mask']==
                (1 if current==index else 0x80 if current<index else 0x40),
                'Life navigation input is not the enabled desired row')
        if current==index:stage+=1
    require(stage==len(stages),'Life navigation never selected all required states')
    pre=[n['mask'] for n in doc['navigation'] if n['before']['mp']==221]
    post=[n['mask'] for n in doc['navigation'] if n['before']['mp']==211]
    expected_masks=pre+[0x20,1,1,1]+post+[1]
    writes=doc['raw_writes'];require(len(writes)==len(expected_masks)*5,'Life input ledger count differs')
    require([{k:v for k,v in r.items() if k!='event'} for r in writes]==doc['gameplay_writes'],
            'Life raw/gameplay input ledgers differ')
    require(all(a['t']<b['t'] for a,b in zip(writes,writes[1:])),'Life input time ordering differs')
    for i,mask in enumerate(expected_masks):
        group=writes[i*5:i*5+5]
        require([r['hits'] for r in group]==list(range(1,6)) and all(r['event']=='key_write'
                and r['val']==mask and r['manual'] is False for r in group),'Life requested/raw input differs')
    pins=[]
    for pin in doc['Life_effect']['after']:
        address=pin['name']
        name=rom[address-0x08000000:address-0x08000000+32] if address>=0x08000000 else g.read_mem(address,32)
        pins.append(pin|{'name_sha256':digest(name)})
    continuation=observe_party_continuation(Memory(data['after-Wait-ewram.bin']),rom,doc['owner'],
                                           facing.receipt(),pins,after,doc['post_Life_roster'])
    require(continuation==doc['Life_effect']['continuation'] and doc['Life_effect']['wait']=='delivered',
            'Life next-actor continuation differs from raw RAM')
    return {'status':'pass-retained-Life-Wait-continuation','pid':doc['pid'],
            'target_hp':[0,221],'caster_mp':[221,211],'next_actor':continuation['actor']['id'],
            'input_presses':len(expected_masks),'source_versions':refs}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--source-ref',action='append',default=['HEAD'])
    ap.add_argument('--out',required=True);args=ap.parse_args();directory=Path(args.capture)
    path=directory/'Life-overlay.json';doc=json.loads(path.read_text());rom=Path(args.rom).read_bytes()
    result=audit(directory,doc,rom,args.source_ref)
    rejected=[]
    def reject(label,edit):
        changed=deepcopy(doc);edit(changed)
        try:audit(directory,changed,rom,args.source_ref)
        except (ValueError,KeyError,TypeError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted Life receipt mutation: '+label)
    for key,value in [('status','unknown'),('inputs_unchanged',False),('fixture_writes',[{}]),
                      ('raw_writes',[]),('final_confirmation',False),('Wait_final_attempted',False),
                      ('life_engine_hits',[]),('life_engine_errors',['injected'])]:
        reject(key,lambda d,k=key,v=value:d.__setitem__(k,v))
    reject('empty-policy',lambda d:d.__setitem__('policy_document',{}))
    reject('missing-final-policy',lambda d:d['final_gate_events'].pop(1))
    reject('duplicate-final',lambda d:d['final_gate_events'].append(deepcopy(d['final_gate_events'][-1])))
    reject('missing-Wait-policy',lambda d:d['Wait_events'].pop(0))
    reject('extra-input',lambda d:d['raw_writes'].append(deepcopy(d['raw_writes'][-1])))
    reject('altered-input',lambda d:d['raw_writes'][0].__setitem__('val',1))
    reject('lost-input',lambda d:d['gameplay_writes'].pop())
    reject('effect-HP',lambda d:d['effect_attribution'].__setitem__('target_hp',[0,1]))
    reject('unjoined-next-actor',lambda d:d['Life_effect']['continuation'].__setitem__('canonical',0))
    reject('source-hash',lambda d:d['source_sha256'].__setitem__('tools/recovery_life_effect.py','0'*64))
    reject('missing-source-closure',lambda d:d['source_sha256'].clear())
    reject('capture-hash',lambda d:d['capture_sha256'].__setitem__('after-Life-ewram.bin','0'*64))
    reject('duplicate-navigation',lambda d:d['navigation'].append(deepcopy(d['navigation'][-1])))
    reject('wrong-navigation-action',lambda d:d['navigation'][-1]['before']['rows'].__setitem__(2,9))
    result.update(scope=__doc__,rejected=rejected,
        source_sha256={p:digest(Path(p).read_bytes()) for p in ['tools/audit_recovery_life_run.py']},
        evidence_sha256={str(path):digest(path.read_bytes())},limitations=['Retained audit, not a new live run.'])
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS retained Life/Wait:',len(rejected),'receipt mutations')


if __name__=='__main__':main()
