"""Assertions for the public eight-unit ally recovery transaction journal."""
from recovery_menu import require
from recovery_executor import KEYS
from tactics_policy import evaluate, validate_policy


def validate_party_recovery(journal,ledger,*,confirmed=False):
    require(journal['schema']=='ffta-party-recovery-turn/1','party journal schema')
    writes=journal['raw_writes']
    observed=[{k:v for k,v in row.items() if k!='event'} for row in ledger
              if row.get('event')=='key_write' and journal['started_t']<=row['t']<=journal['ended_t']]
    require(writes==observed,'party raw ledger missing or changed')
    transport=journal['transport']
    if writes or confirmed:require(transport and transport[0]['event']=='halt','party explicit halt missing')
    require(all(isinstance(e.get('reply'),str) and len(e['reply'])>=3
                and e['reply'][0] in 'ST' and e['reply'][1:3]!='04'
                and all(c in '0123456789abcdefABCDEF' for c in e['reply'][1:3])
                for e in transport if e['event']=='halt'),'party halt reply invalid')
    if writes or confirmed:
        require(transport[1]['event']=='trace_suspended' and transport[-1]['event']=='trace_restored'
            and sum(e['event']=='trace_suspended' for e in transport)==1
            and sum(e['event']=='trace_restored' for e in transport)==1
            and all(e['event'] in ('halt','trace_suspended','trace_restored') for e in transport)
            and transport[-1]['write_count']==journal['write_start']+len(writes),'party trace lifecycle differs')
    if not confirmed and journal.get('status') not in ('confirmed','unexecuted-wait'):return
    require(journal['status']=='confirmed' if confirmed else journal['status'] in ('confirmed','unexecuted-wait'),
            'party completion missing')
    wait_confirmed=journal['status']=='confirmed'
    owner=journal['owner'];pins=journal['party_before'];party={p['id']:p for p in pins}
    require((owner['id'],owner['job'],owner['race'],owner['x'],owner['y'])==(7,5,1,4,10)
            and len(pins)==2 and set(party)=={5,7}
            and party[7]['canonical']==0x02000080 and party[5]['canonical']==0x02000188
            and party[7]['tile']==[4,10] and party[5]['tile']==[5,10]
            and len({p['name'] for p in pins})==2,'party fixture pin differs')
    require(all(p['job']==5 and p['race']==1 and 0<p['hp']<=p['max_hp']<=999
                and 0<=p['mp']<=p['max_mp']<=999 for p in pins),'party pin resources invalid')
    cure,finish=journal['recovery'],journal['finish'];before,after=cure['before'],cure['after']
    accepted=cure['outcome']=='accepted-effect-only'
    require(cure['outcome'] in ('accepted-effect-only','declined') and before['state']==after['state']=='command'
            and before['hp']==party[7]['hp'] and before['mp']==party[7]['mp']
            and before['member']==after['member']==party[7]['canonical']
            and before['target_tile']==after['target_tile']==party[7]['tile']
            and before['cure_cost']==6 and after['hp']==before['hp'],'party caster boundary differs')
    require(finish['before']['hp']==after['hp'] and finish['before']['mp']==after['mp'],'party Wait resources differ')
    if accepted:
        require(cure['target_before']==party[5] and cure['target_after']['canonical']==party[5]['canonical']
                and cure['target_after']['id']==5 and party[5]['hp']<cure['target_after']['hp']<=party[5]['max_hp']
                and cure['target_after']['mp']==party[5]['mp'] and after['mp']==before['mp']-6
                and after['rows'].count(9)==1 and not after['enabled'][after['rows'].index(9)],'party effect missing')
    else:require(after['mp']==before['mp'] and cure['fallback']=='unexecuted','declined party Cure spent MP')
    policy=validate_policy(journal['policy_document'])
    observations=journal['policy_observations']
    require(len(observations)==(2 if accepted else 1),'public ally adapter observations missing')
    for observation in observations:
        snapshot=observation['snapshot'];candidate=snapshot['candidates']
        require(snapshot['identity']=='verified' and snapshot['actor']['id']==7
                and snapshot['actor']['name']==owner['name_text'] and snapshot['actor']['job_id']==5
                and snapshot['actor']['side']=='player' and snapshot['actor']['tile']==party[7]['tile']
                and snapshot['actor']['max_hp']==party[7]['max_hp'] and snapshot['actor']['max_mp']==party[7]['max_mp']
                and snapshot['actor']['hp']==before['hp'] and snapshot['actor']['mp']==before['mp']
                and candidate==[{'id':'cure-ally','kind':'ability','action_id':1,'legal':True,'cost':6,
                    'ability_name':'Cure','relation':'ally','target':{'kind':'unit','id':5},
                    'target_hp':party[5]['hp'],'target_max_hp':party[5]['max_hp'],'target_mp':party[5]['mp']}]
                and evaluate(snapshot,policy)==observation['evaluation'],'public ally candidate/policy differs')
        require(((observation['evaluation'].get('decision') or {}).get('candidate_id')=='cure-ally')==accepted,
                'public ally policy did not select reported result')
    groups=[]
    for family,needed,resources in [('cure_events',accepted,before),('wait_events',wait_confirmed,after)]:
        events=journal[family];requests=[e for e in events if e['event']=='input_requested']
        deliveries=[e for e in events if e['event']=='input_delivered']
        require(len(requests)==len(deliveries) and [e['key'] for e in requests]==[e['key'] for e in deliveries],
                'party request/delivery mismatch')
        finals=[e for e in requests if e['final']]
        require(len(finals)==int(needed) and (not finals or (requests[-1]==finals[0]
                and finals[0]['key']=='A')),'party final input differs')
        require(all(e['facts']['member']==before['member'] and e['facts']['actor_wrapper']==before['actor_wrapper']
                    and e['facts']['hp']==resources['hp'] and e['facts']['mp']==resources['mp'] for e in requests),
                'party input owner/resources drifted')
        delivery=iter(deliveries)
        for event in events:
            if event['event']=='ally_overlay':groups.append((16,5))
            elif event['event']=='input_requested':
                delivered=next(delivery);groups.append((KEYS[event['key']],delivered['hits']))
        if needed:
            policies=[e for e in events if e['event'] in ('policy','final_policy')]
            require([e['event'] for e in policies]==['policy','final_policy']
                    and events.index(policies[-1])<events.index(finals[0]),'party final policy missing')
            for entry in policies:
                snapshot=entry['snapshot'];actor=snapshot['actor']
                require(snapshot['identity']=='verified' and actor['id']==7 and actor['name']==owner['name_text']
                        and actor['job_id']==5 and actor['side']=='player' and actor['tile']==party[7]['tile']
                        and actor['hp']==resources['hp'] and actor['mp']==resources['mp']
                        and actor['max_hp']==party[7]['max_hp'] and actor['max_mp']==party[7]['max_mp'],
                        'party policy actor resources differ')
                require(evaluate(snapshot,policy)==entry['evaluation'],'party policy replay differs')
            if family=='cure_events':
                require([e['evaluation'] for e in policies]==[e['evaluation'] for e in observations],
                        'private/public ally policy disagrees')
                require([e['snapshot'] for e in policies]==[e['snapshot'] for e in observations],
                        'private/public ally policy facts disagree')
                token=policies[-1]['target_token']
                require(token['caster']==party[7]['canonical'] and token['target']==party[5]['canonical']
                        and token['target_wrapper']!=before['actor_wrapper'] and token['tile']==party[5]['tile']
                        and token['cost']==6 and finals[0]['facts']['state']=='confirmation'
                        and finals[0]['facts']['cursor']==0,'accepted party target token differs')
            else:
                require(all(e['snapshot']['candidates']==[{'id':'recovery-wait','kind':'wait',
                            'action_id':10,'legal':True,'cost':0}] for e in policies)
                        and policies[-1]['evaluation']['decision']['candidate_id']=='recovery-wait'
                        and finals[0]['facts']['state']=='facing','party Wait not policy selected')
    offset=0
    for mask,hits in groups:
        require(type(hits) is int and 0<hits<=5,'party key delivery ambiguous')
        part=writes[offset:offset+hits]
        require(len(part)==hits and [w['hits'] for w in part]==list(range(1,hits+1))
                and all(w['val']==mask and not w.get('manual',False) for w in part),'party raw press differs')
        offset+=hits
    require(offset==len(writes),'party extra raw input')
    if not wait_confirmed:
        require(finish['outcome']=='unexecuted' and not journal['continuations'],'unselected party Wait executed')
        return
    facing=finish['facing']
    require(finish['outcome']=='confirmed' and facing['state']=='facing' and facing['driver_state']==47
            and facing['member']==before['member'] and facing['hp']==after['hp'] and facing['mp']==after['mp'],
            'party facing differs')
    require(len(journal['continuations'])==1,'party next actor missing')
    later=journal['continuations'][0];actor=later['actor']
    require(later['source']=='canonical driver / restored eight-unit roster / own cursor'
            and later['relation']=='enemy' and actor['id'] not in (5,7) and actor['side_bit']
            and not actor['unaffiliated'] and later['wrapper']!=before['actor_wrapper']
            and later['canonical']!=before['member'] and 0<actor['hp']<=actor['max_hp']<=999
            and all(0<=v<64 for v in actor['tile']),'party independent next enemy differs')
    expected=[{'id':p['id'],'canonical':p['canonical'],'hp':cure['target_after']['hp'] if accepted and p['id']==5
        else after['hp'] if p['id']==7 else p['hp'],'mp':after['mp'] if p['id']==7 else p['mp'],
        'tile':p['tile']} for p in pins]
    require(later['party_after']==expected,'party effect differs at next enemy')
