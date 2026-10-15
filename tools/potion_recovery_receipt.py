"""Validate bounded public Potion effect, policy, input and continuation claims."""
from copy import deepcopy
from recovery_menu import require
from tactics_policy import evaluate
from validate_consumable_use import audit
from consumable_policy import POTION_CANDIDATE


def validate_potion_journal(j,ledger,*,confirmed=False):
    require(j['schema']=='ffta-potion-recovery-turn/1','Potion journal schema differs')
    observed=[{k:v for k,v in r.items() if k!='event'} for r in ledger
        if r.get('event')=='key_write' and j['started_t']<=r['t']<=j['ended_t']]
    require(observed==j['gameplay_writes'] and observed==[{k:v for k,v in r.items() if k!='event'} for r in j['raw_writes']],
            'public Potion raw ledger missing/changed')
    require(not j['fixture_writes'] and not j['potion_engine_errors'],'public Potion fixture/trace tainted')
    transport=j.get('transport_events',j['transport'])
    if observed or confirmed:
        require(transport[0]['event']=='halt' and transport[1]['event']=='trace_suspended'
            and transport[-1]=={'event':'trace_restored','write_count':j['write_start']+len(observed)}
            and sum(e['event']=='trace_restored' for e in transport)==1,'public Potion trace restore differs')
    require(all(e['event'] in ('halt','trace_suspended','trace_restored') for e in transport),'public Potion transport failed')
    require(all(isinstance(e.get('reply'),str) and len(e['reply'])>=3 and e['reply'][0] in 'ST'
        and e['reply'][1:3]!='04' and all(c in '0123456789abcdefABCDEF' for c in e['reply'][1:3])
        for e in transport if e['event']=='halt'),'public Potion halt reply invalid')


def validate_potion_turn(turn):
    j=turn['recovery'];require(j['schema']=='ffta-potion-recovery-turn/1' and j['status']=='confirmed'
        and not j['potion_engine_errors'],'public Potion transaction incomplete')
    d=deepcopy(j);d['status']='observed-Potion-use-Wait-and-next-actor';d['inputs_unchanged']=True
    audit(d)
    t=j['Potion_final_token']
    require(t['law_matches']==[[1,0],[82,0],[42,0]] and t['law_control']==[20,1],'Potion laws not discriminated')
    policy=j['policy_document'];require(policy['schema']=='ffta-tactics-policy/2' and policy.get('consumables') is True,
        'Potion lacks explicit consumables policy')
    require(len(j['policy_observations'])==2,'Potion final policy was not revalidated')
    for o in j['policy_observations']:
        s=o['snapshot'];c=s['candidates']
        require(len(c)==1 and c[0]['id']==POTION_CANDIDATE and c[0]['count']==t['count']
            and c[0]['target_hp']==t['hp'] and s['actor']['hp']==t['hp'],'Potion policy source resources differ')
        require((s['actor']['id'],s['actor']['name'],s['actor']['job_id'],s['actor']['side'])==(5,j['owner']['name_text'],5,'player')
            and s['actor']['tile']==[5,10] and s['actor']['max_hp']==241 and s['actor']['mp']==221,
            'Potion policy actor is not native source')
        require(c[0]['kind']=='item' and c[0]['item_name']=='Potion' and c[0]['target']=={'kind':'unit','id':5}
            and c[0]['relation']=='self' and c[0]['legal'] is True and c[0]['cost']==0,'Potion policy candidate is foreign')
        require(evaluate(s,policy)==o['evaluation'] and o['evaluation']['decision']['candidate_id']==POTION_CANDIDATE,
                'Potion policy did not choose native candidate')
    require(j['potion_engine_hits']==j['Potion_after']['native_hits'],'public native trace differs')
    waits=j['Potion_Wait_events']
    require([e['event'] for e in waits]==['final_policy','revalidated_final_policy','final_input_requested','final_input_delivered']
        and waits[-2:]==[{'event':'final_input_requested','mask':1},{'event':'final_input_delivered','hits':5}],
        'Potion Wait confirmation missing/duplicated')
    for e in waits[:2]:
        require(e['policy']==policy and evaluate(e['snapshot'],policy)==e['evaluation']
            and e['evaluation']['decision']['candidate_id']=='wait','Potion Wait policy differs')
    require([w for w in j['raw_writes'] if w.get('event')=='key_write']==[{'event':'key_write',**w} for w in j['gameplay_writes']],
            'public Potion raw ledger differs')
    actual={r['id']:r for r in j['Potion_party_after']}
    require(actual[5]['hp']==j['Potion_after']['hp'] and actual[5]['mp']==j['Potion_after']['mp']
        and actual[7]['hp']==0,'Potion party result contradicts native effect')
    rows=turn['engine_result']['players_after']
    require({r['id'] for r in rows}=={5,7} and all(r==actual[r['id']] for r in rows),'Potion party result differs')
