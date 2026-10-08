"""Audit live research STOP/reserve refusals and reject post-terminal input."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_life_target import LifeOverlayReader
from recovery_menu import require
from recovery_menu_list import ResearchMenuList
from tactics_policy import evaluate, validate_policy
from validate_recovery_life_menu import Memory
from probe_recovery_ko_lifecycle import source_dependencies


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(directory,doc,rom):
    stop=doc['status']=='observed-STOP-refusal'
    require(stop or doc['status']=='observed-policy-reserve-refusal','not an identified Life refusal')
    require(doc['inputs_unchanged'] and not doc['fixture_writes'],'refusal source/write authority differs')
    require(set(source_dependencies('probe_recovery_life_overlay'))<=set(doc['source_sha256']),
            'refusal source closure missing')
    for p,h in doc['source_sha256'].items():require(sha(p)==h,'refusal source differs: '+p)
    for n,h in doc.get('capture_sha256',{}).items():require(sha(directory/n)==h,'refusal capture differs: '+n)
    writes=doc['raw_writes'];require(writes and len(writes)%5==0,'missing/incomplete refusal input ledger')
    require([{k:v for k,v in r.items() if k!='event'} for r in writes]==doc['gameplay_writes'],
            'refusal raw/gameplay ledgers differ')
    require(all(a['t']<b['t'] for a,b in zip(writes,writes[1:])),'refusal input time ordering differs')
    for i in range(0,len(writes),5):
        group=writes[i:i+5]
        require([r['hits'] for r in group]==list(range(1,6)) and len({r['val'] for r in group})==1
                and all(r['event']=='key_write' and r['manual'] is False for r in group),
                'refusal input pulse differs')
    if stop:
        observed,injected=doc['STOP_observed'],doc['STOP_injected'];stage=injected['stage']
        require(stage in ('navigation','Life-final','Wait-final') and injected['t']<=observed['t']
                and len(writes)==observed['input_write_count']==injected['input_write_count']
                and writes[-1]['t']<=observed['t'] and 'STOP observed;' in doc['error'],
                'post-STOP input or wrong refusal')
        require((directory/'STOP').read_text().strip()==stage,'real STOP file missing')
        require(not doc.get('Wait_final_attempted',False),'STOP still attempted final Wait')
        if stage=='Wait-final':
            require(doc['final_confirmation'] and doc['effect_attribution']
                    and doc['Wait_facing'] and not doc.get('Wait_events'), 'Wait STOP boundary missing')
        else:
            require(not doc['final_confirmation'] and not doc.get('effect_attribution')
                    and not doc['life_engine_hits'],'STOP still cast Life')
        if stage=='navigation':
            require(len(doc['navigation'])==1 and len(writes)==5
                    and not doc.get('final_gate_events'),'navigation STOP evidence differs')
            return {'status':'pass-live-STOP-refusal','stage':stage,'input_presses':1,'post_STOP_writes':0}
    else:
        require(not doc['final_confirmation'] and not doc.get('Wait_final_attempted',False)
                and not doc.get('STOP_observed') and not doc['life_engine_hits']
                and doc['error']=="RecoveryStateError('policy declined Life; no final input')",
                'reserve refusal executed or failed elsewhere')
        stage='reserve'
    expected_count=len(doc['navigation'])+(4 if stage=='Wait-final' else 3)
    require(len(writes)==5*expected_count,'refusal contains an unrequested/post-terminal input pulse')
    # Both final Life refusals have actual native Do it RAM and full policy.
    if stage in ('Life-final','reserve'):
        raw=(directory/'final-prompt-second-ewram.bin').read_bytes();g=Memory(raw)
        caster=next(p for p in doc['party'] if p['id']==5)
        menu=ResearchMenuList(g,rom,doc['owner'],caster['canonical'])
        units={p['canonical']:g.read_mem(p['canonical'],STRIDE) for p in doc['party']}
        reader=LifeOverlayReader(g,menu,doc['party'],units,clock=lambda:1)
        snapshot=reader.policy_snapshot(reader.confirmation_snapshot())
        require(len(doc['final_gate_events'])==1 and doc['final_gate_events'][0]['event']=='policy',
                'refusal requested or repeated final input')
        event=doc['final_gate_events'][0]
        require(any(json.loads(Path(p).read_text())==doc['policy_document'] for p in doc['source_sha256']
                    if p.endswith('.json')),'refusal full policy source document missing')
        require(event['policy']==validate_policy(doc['policy_document'])
                and event['snapshot']|{'age_seconds':0}==snapshot|{'age_seconds':0}
                and evaluate(event['snapshot'],event['policy'])==event['evaluation'],
                'refusal full policy differs from native prompt')
        candidate=(event['evaluation'].get('decision') or {}).get('candidate_id')
        if stage=='reserve':
            rules=event['policy']['assignments']['party']['player']['rules']
            require(rules[0]['when']['remaining_mp_after_cost']=={'gte':212}
                    and snapshot['actor']['mp']==221 and snapshot['candidates'][0]['cost']==10
                    and candidate!='life-ally','reserve212 did not decline actual remaining211')
        else:require(candidate=='life-ally','STOP did not interrupt an authorized Life decision')
    return {'status':'pass-live-refusal','stage':stage,'input_presses':len(writes)//5,
            'final_Life_attempted':doc['final_confirmation'],'final_Wait_attempted':False,'post_STOP_writes':0 if stop else None}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True)
    args=ap.parse_args();directory=Path(args.capture);path=directory/'Life-overlay.json'
    doc=json.loads(path.read_text());rom=Path(args.rom).read_bytes();result=audit(directory,doc,rom)
    rejected=[]
    def reject(label,edit):
        changed=deepcopy(doc);edit(changed)
        try:audit(directory,changed,rom)
        except (ValueError,KeyError,TypeError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted refusal mutation: '+label)
    for key,value in [('status','unknown'),('inputs_unchanged',False),('fixture_writes',[{}]),
                      ('raw_writes',[]),('gameplay_writes',[]),('Wait_final_attempted',True),
                      ('error','unexpected transport failure')]:
        reject(key,lambda d,k=key,v=value:d.__setitem__(k,v))
    reject('post-terminal-input',lambda d:d['raw_writes'].append(deepcopy(d['raw_writes'][-1])))
    reject('source-hash',lambda d:d['source_sha256'].__setitem__('tools/recovery_life_final.py','0'*64))
    reject('missing-source-closure',lambda d:d['source_sha256'].clear())
    def extra_pulse(d):
        pulse=deepcopy(d['raw_writes'][-5:]);last=d['raw_writes'][-1]['t']
        for i,r in enumerate(pulse):r['t']=last+i+1
        d['raw_writes'].extend(pulse)
        d['gameplay_writes'].extend({k:v for k,v in r.items() if k!='event'} for r in pulse)
        if d.get('STOP_observed'):
            d['STOP_observed']['input_write_count']+=5
            d['STOP_injected']['input_write_count']+=5
            d['STOP_observed']['t']=d['STOP_injected']['t']=last+10
    reject('coherent-extra-final-pulse',extra_pulse)
    if doc['status']=='observed-STOP-refusal':
        reject('missing-STOP',lambda d:d.pop('STOP_observed'))
        reject('wrong-terminal-count',lambda d:d['STOP_observed'].__setitem__('input_write_count',0))
    else:reject('empty-policy',lambda d:d.__setitem__('policy_document',{}))
    result.update(scope=__doc__,rejected=rejected,source_sha256={'tools/audit_recovery_life_refusal.py':sha(__file__)},
        evidence_sha256={str(path):sha(path)},limitations=['Audits captured live refusal; not a new run.'])
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life refusal:',len(rejected),'receipt mutations')


if __name__=='__main__':main()
