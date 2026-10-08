"""Portable public Life journal checks; no fresh gameplay claim from replay."""
import hashlib

from recovery_life_effect import verify_life_effect
from recovery_menu import integer, require
from tactics_policy import evaluate, validate_policy


def validate_life_recovery(journal,ledger,*,confirmed=False):
    require(journal['schema']=='ffta-life-recovery-turn/1','Life journal schema differs')
    writes=journal['gameplay_writes']
    observed=[{k:v for k,v in row.items() if k!='event'} for row in ledger
              if row.get('event')=='key_write' and journal['started_t']<=row['t']<=journal['ended_t']]
    require(writes==observed and [{k:v for k,v in r.items() if k!='event'}
            for r in journal['raw_writes']]==writes,'public Life raw ledger differs')
    require(not journal['fixture_writes'] and not journal['life_engine_errors'],'public Life altered fixture/trace failed')
    transport=journal['transport']
    if writes or confirmed:
        require(transport[0]['event']=='halt' and transport[1]['event']=='trace_suspended'
                and transport[-1]['event']=='trace_restored'
                and transport[-1]['write_count']==journal['write_start']+len(writes)
                and sum(e['event']=='trace_suspended' for e in transport)==1
                and sum(e['event']=='trace_restored' for e in transport)==1,'public Life trace lifecycle differs')
    require(all(e['event'] in ('halt','trace_suspended','trace_restored') for e in transport),
            'public Life transport lifecycle error')
    require(all(isinstance(e.get('reply'),str) and e['reply'][:1] in ('S','T')
                and len(e['reply'])>=3 and e['reply'][1:3]!='04'
                and all(c in '0123456789abcdefABCDEF' for c in e['reply'][1:3])
                for e in transport if e['event']=='halt'),'public Life halt differs')
    for group_name in ('final_gate_events','Wait_events'):
        events=journal.get(group_name,[])
        require(sum(e['event']=='final_input_requested' for e in events)<=1
                and sum(e['event']=='final_input_delivered' for e in events)<=1,'duplicate public Life/Wait final')
    policy=validate_policy(journal['policy_document'])
    partial_policies=[e for name in ('final_gate_events','Wait_events') for e in journal.get(name,[])
                      if e['event'] in ('policy','final_policy','revalidated_final_policy')]
    require(len(partial_policies)==len(journal['policy_observations']),
            'partial public Life policy observations missing/repeated')
    for event,observation in zip(partial_policies,journal['policy_observations']):
        snapshot=event['snapshot'];decision=evaluate(snapshot,policy)
        require(event['policy']==policy and event['evaluation']==decision
                and observation=={'snapshot':snapshot,'evaluation':decision},
                'partial public Life policy/adapter differs')
        actor=snapshot['actor'];candidate=snapshot['candidates']
        require(actor['id']==5 and actor['hp']==241 and actor['tile']==[5,10] and len(candidate)==1,
                'partial public Life policy actor/candidates differ')
        if candidate[0]['kind']=='ability':
            hp_max,mp_max,mp=241,221,221
        else:
            unit=bytes.fromhex(journal['effect_units_after']['33554824'])
            hp_max,mp_max,mp=integer(unit,0x1A,2),integer(unit,0x1E,2),211
        require(actor=={'name':journal['owner']['name_text'],'id':5,'job_id':5,'side':'player',
            'hp':241,'max_hp':hp_max,'mp':mp,'max_mp':mp_max,'tile':[5,10]},
            'partial public Life actor identity/resources differ')
        if candidate[0]['kind']=='ability':
            require(candidate[0]=={'id':'life-ally','kind':'ability','action_id':5,'legal':True,'cost':10,
                'ability_name':'Life','relation':'ally','target':{'kind':'unit','id':7},'target_hp':0,
                'target_max_hp':442,'target_mp':85} and actor['mp']==221,
                'partial public Life legal candidate differs')
        else:
            require(candidate==[{'id':'wait','kind':'wait','action_id':10,'legal':True,'cost':0}]
                    and actor['mp']==211,'partial public Life Wait candidate differs')
    for name,flag in [('final_gate_events','final_confirmation'),('Wait_events','Wait_final_attempted')]:
        events=journal.get(name,[]);requested=any(e['event']=='final_input_requested' for e in events)
        require(bool(journal.get(flag,False))==requested,'partial public final-attempt latch differs')
        if requested:
            policies=[e for e in events if 'snapshot' in e]
            expected='life-ally' if name=='final_gate_events' else 'wait'
            require(policies and (policies[-1]['evaluation'].get('decision') or {}).get('candidate_id')==expected,
                    'partial public final input lacks policy authorization')
    if journal.get('effect_attribution'):
        before_units={int(a):bytes.fromhex(u) for a,u in journal['effect_units_before'].items()}
        after_units={int(a):bytes.fromhex(u) for a,u in journal['effect_units_after'].items()}
        pins={p['id']:p for p in journal['party']}
        require(verify_life_effect(before_units,after_units,journal['life_engine_hits'],pins[5],pins[7])
                ==journal['effect_attribution'],'partial public native Life effect differs')
    if not confirmed and journal.get('status')!='confirmed':return
    require(journal['status']=='confirmed' and writes,'public Life completion/inputs missing')
    owner=journal['owner'];party=journal['party'];roles={p['id']:p for p in party}
    require(len(party)==2 and set(roles)=={5,7} and owner['id']==5
            and roles[5]['canonical']==0x02000188 and roles[7]['canonical']==0x02000080
            and roles[5]['tile']==[5,10] and roles[7]['tile']==[4,10]
            and roles[5]['hp']==241 and roles[5]['mp']==221 and roles[7]['hp']==0
            and roles[7]['mp']==85,'public Life bounded pins differ')
    before={int(a):bytes.fromhex(u) for a,u in journal['effect_units_before'].items()}
    after={int(a):bytes.fromhex(u) for a,u in journal['effect_units_after'].items()}
    for pin in party:
        unit=before[pin['canonical']]
        require(hashlib.sha256(unit).hexdigest()==pin['canonical_sha256']
                and integer(unit,0)==pin['name'] and unit[0x104]==pin['id'],
                'public Life pre-action raw identity differs')
    require(verify_life_effect(before,after,journal['life_engine_hits'],roles[5],roles[7])
            ==journal['effect_attribution'],'public Life native effect/growth differs')
    policy=validate_policy(journal['policy_document'])
    policy_events=[e for name in ('final_gate_events','Wait_events') for e in journal[name]
                   if e['event'] in ('policy','final_policy','revalidated_final_policy')]
    require(len(policy_events)==4 and len(journal['policy_observations'])==4,
            'public Life adapter decisions missing/repeated')
    for event,observation in zip(policy_events,journal['policy_observations']):
        snapshot=event['snapshot'];decision=evaluate(snapshot,policy)
        require(event['policy']==policy and event['evaluation']==decision
                and observation=={'snapshot':snapshot,'evaluation':decision},
                'public Life policy adapter/snapshot differs')
        actor=snapshot['actor'];candidate=snapshot['candidates']
        require(actor['id']==5 and actor['hp']==241 and actor['tile']==[5,10],
                'public Life policy actor differs')
        if candidate[0]['kind']=='ability':
            require(len(candidate)==1 and candidate[0]=={'id':'life-ally','kind':'ability','action_id':5,
                'legal':True,'cost':10,'ability_name':'Life','relation':'ally','target':{'kind':'unit','id':7},
                'target_hp':0,'target_max_hp':442,'target_mp':85} and actor['mp']==221
                and decision['decision']['candidate_id']=='life-ally','public Life candidate authorization differs')
        else:
            require(candidate==[{'id':'wait','kind':'wait','action_id':10,'legal':True,'cost':0}]
                    and actor['mp']==211 and decision['decision']['candidate_id']=='wait',
                    'public Life Wait authorization differs')
    require([e['event'] for e in journal['final_gate_events']]==
        ['policy','final_policy','final_input_requested','final_input_delivered']
        and [e['event'] for e in journal['Wait_events']]==
        ['final_policy','revalidated_final_policy','final_input_requested','final_input_delivered']
        and journal['final_confirmation'] and journal['Wait_final_attempted'],
        'public Life final delivery lifecycle differs')
    for name in ('final_gate_events','Wait_events'):
        require(journal[name][-2]['mask']==1 and journal[name][-1]['hits']==5,'public Life final pulse differs')
    masks=[n['mask'] for n in journal['navigation'] if n['before']['mp']==221]+[0x20,1,1,1]
    masks += [n['mask'] for n in journal['navigation'] if n['before']['mp']==211]+[1]
    require(len(writes)==5*len(masks),'public Life input request count differs')
    for i,mask in enumerate(masks):
        group=writes[i*5:i*5+5]
        require([r['hits'] for r in group]==list(range(1,6)) and all(r['val']==mask for r in group),
                'public Life raw input pulse differs')
    effect=journal['Life_effect'];continuation=effect['continuation']
    require(effect['wait']=='delivered' and continuation['relation']=='enemy'
            and continuation['source']=='canonical driver / restored eight-unit roster / own cursor'
            and continuation['actor']['id'] not in (5,7) and continuation['actor']['side_bit']
            and continuation['canonical'] not in before
            and continuation['wrapper']!=journal['Wait_facing']['actor_wrapper'],
            'public Life next actor attribution differs')
    baseline=journal['post_Life_roster']
    require(len(baseline)==8 and {r['id'] for r in baseline}==set(range(8))
            and next(r for r in baseline if r['id']==5)['level']==41,'public Life restored roster/growth missing')
    later={p['id']:p for p in continuation['party_after']}
    require(set(later)=={5,7} and later[5]['hp']==241 and later[5]['mp']==211
            and later[7]['hp']==221 and later[7]['mp']==85,'public Life continuation resources differ')
    for pin in effect['after']:
        unit=after[pin['canonical']]
        require(hashlib.sha256(unit).hexdigest()==pin['canonical_sha256']
                and pin['hp']==integer(unit,0x18,2) and pin['mp']==integer(unit,0x1C,2)
                and pin['max_hp']==integer(unit,0x1A,2) and pin['max_mp']==integer(unit,0x1E,2),
                'public Life effect raw/metadata resources differ')
