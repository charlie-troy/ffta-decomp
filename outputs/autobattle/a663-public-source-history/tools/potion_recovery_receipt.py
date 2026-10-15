"""Validate bounded public Potion effect, policy, input and continuation claims."""
from copy import deepcopy
from recovery_menu import require
from tactics_policy import evaluate
from validate_consumable_use import audit
from consumable_policy import POTION_CANDIDATE


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
        require(evaluate(s,policy)==o['evaluation'] and o['evaluation']['decision']['candidate_id']==POTION_CANDIDATE,
                'Potion policy did not choose native candidate')
    require(j['potion_engine_hits']==j['Potion_after']['native_hits'],'public native trace differs')
    require([w for w in j['raw_writes'] if w.get('event')=='key_write']==[{'event':'key_write',**w} for w in j['gameplay_writes']],
            'public Potion raw ledger differs')
    actual={r['id']:r for r in j['Potion_party_after']}
    rows=turn['engine_result']['players_after']
    require({r['id'] for r in rows}=={5,7} and all(r==actual[r['id']] for r in rows),'Potion party result differs')
