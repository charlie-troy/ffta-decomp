"""Audit bounded native Potion decrement/HP-store evidence; no public acceptance."""
import argparse,json,hashlib,copy
from pathlib import Path
from recovery_menu import require
from recovery_source_versions import verify_source_versions


def audit(d,require_cleanup=False):
    require(d['status'] in ('observed-single-Potion-consumption-and-HP-store-only','observed-Potion-use-Wait-and-next-actor')
            and d['inputs_unchanged'] and not d['fixture_writes'] and 'error' not in d,'incomplete/tainted use capture')
    if require_cleanup:
        require(d.get('strict_trace_disarmed') is True and d.get('owned_process_closed') is True,
                'strict trace cleanup and owned process closure not proved')
        events=d.get('transport_events',[])
        require(events and events[-1]=={'event':'terminal_trace_disarmed','write_count':len(d['gameplay_writes'])},
                'missing terminal strict disarm acknowledgement')
    t,a=d['Potion_final_token'],d['Potion_after']
    require(t['source']==t['target']==0x02000188 and t['ability']==251 and t['item']==362
            and t['count']==2 and t['hp']==100 and a['count']==1 and 100<a['hp']<=241 and a['mp']==221,'foreign item/effect resources')
    require(d['Potion_use_events']==[{'event':'Potion_final_input_requested','mask':1},{'event':'Potion_final_input_delivered','hits':5}], 'final use was not single delivered input')
    hits=a['native_hits'];require(len(hits)==4,'missing or foreign native stores')
    require([h['phase'] for h in hits]==['inventory-decrement-before','inventory-decrement-after','HP-store-before','HP-store-after'],'native store order differs')
    require([h['pc'] for h in hits]==['080caa68','080caa6a','080a2298','080a229a'],'native store sites differ')
    require(all(h['processor_source_wrapper']==0x0202270C and h['Potion_reserved']==0 for h in hits),'foreign source wrapper/reservation')
    require(all(h['item']==362 and h['quantity']==1 and h['record']==0x02001EE4 and h['stored_count']==1 for h in hits[:2])
            and [h['Potion_owned'] for h in hits]==[2,1,1,1],'not a native single-Potion decrement')
    require(all(h['canonical']==t['source'] and h['id']==5 and h['mp']==221 and h['stored_hp']==a['hp'] for h in hits[2:])
            and [h['hp'] for h in hits[2:]]==[100,a['hp']],'foreign or nonhealing HP store')
    before=bytearray.fromhex(d['inventory_before']['raw']);after=bytes.fromhex(a['inventory'])
    before[2]=1;require(bytes(before)==after,'inventory changed beyond one Potion')
    before_unit=bytes.fromhex(d['Potion_final_prompt_raw']['canonical']);after_unit=bytes.fromhex(a['canonical'])
    require(before_unit[10]==before_unit[0x3A]==0 and before_unit[:0x18]+before_unit[0x1A:]==after_unit[:0x18]+after_unit[0x1A:], 'unit changed beyond native HP store')
    split=next(i+1 for i,k in enumerate(d['inputs']) if 'before_Item' in k)
    phases=d['inputs'][:split]+[{'mask':1}]*3+d['inputs'][split:]
    turn=d['status']=='observed-Potion-use-Wait-and-next-actor'
    if turn:
        phases+=[{'mask':1}]
        p=d['Potion_post_command'];require(not p['enabled'][p['rows'].index(9)] and p['enabled'][p['rows'].index(10)],'Action not consumed/Wait disabled')
        c=d['Potion_continuation'];require(c['canonical']!=t['source'] and c['actor']['id']!=5 and c['wrapper']!=0x0202270C,'no independent next actor')
    writes=d['gameplay_writes'];require(len(writes)==5*len(phases),'extra/partial gameplay writes')
    for i,p in enumerate(phases):
        require(all(w['hits']==j+1 and w['val']&p['mask']==p['mask'] and not w['manual'] for j,w in enumerate(writes[i*5:i*5+5])),'raw input ledger differs')
    return {'native_decrement':True,'native_HP_store':True,'Wait_and_next_actor':turn,'raw_writes':len(writes)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--source-ref',action='append',default=[]);ap.add_argument('--source-dir',action='append',default=[])
    ap.add_argument('--require-cleanup',action='store_true')
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.capture);p=root/'inventory.json'
    d=json.loads(p.read_text());result=audit(d,args.require_cleanup);sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    for n,h in d['capture_sha256'].items():require(sha(root/n)==h,'raw capture changed: '+n)
    pins={p:h for p,h in d['source_sha256'].items() if p.startswith('tools/')}
    closure=verify_source_versions(pins,'probe_consumable_inventory',args.source_ref,args.source_dir)
    for f,h in d['source_sha256'].items():
        if f not in pins:require(sha(f)==h,'source asset changed')
    trace=root/'native-Potion-hits.jsonl';require([json.loads(x) for x in trace.read_text().splitlines()]==d['Potion_after']['native_hits'],'raw native trace differs')
    rejected=[]
    mutations=[('count',lambda x:x['Potion_after'].update(count=2)),('foreign HP',lambda x:x['Potion_after']['native_hits'][3].update(canonical=0x02000080)),
        ('foreign item',lambda x:x['Potion_after']['native_hits'][0].update(item=363)),('missing trace',lambda x:x['Potion_after']['native_hits'].pop()),
        ('extra input',lambda x:x['gameplay_writes'].append(x['gameplay_writes'][-1])),('incomplete input',lambda x:x['gameplay_writes'].pop()),
        ('HP no healing',lambda x:x['Potion_after'].update(hp=100)),('MP cost',lambda x:x['Potion_after'].update(mp=211)),
        ('source taint',lambda x:x.update(inputs_unchanged=False)),('foreign wrapper',lambda x:x['Potion_after']['native_hits'][3].update(processor_source_wrapper=0)),
        ('wrong quantity',lambda x:x['Potion_after']['native_hits'][0].update(quantity=2))]
    if args.require_cleanup:
        mutations.extend([('strict cleanup missing',lambda x:x.pop('strict_trace_disarmed')),
                          ('process still alive',lambda x:x.update(owned_process_closed=False)),
                          ('cleanup event missing',lambda x:x.pop('transport_events'))])
    for label,mutate in mutations:
        changed=copy.deepcopy(d);mutate(changed)
        try:audit(changed,args.require_cleanup)
        except ValueError:rejected.append(label)
        else:raise AssertionError('accepted '+label)
    output={'status':'pass','scope':__doc__,'observation':result,'strict_cleanup_required':args.require_cleanup,'closure':closure,'rejected':rejected,
        'source_sha256':{'tools/validate_consumable_use.py':sha('tools/validate_consumable_use.py')},
        'evidence_sha256':{str(p):sha(p),str(trace):sha(trace)},
        'limitations':['Native decrement has global item arguments; actor association uses pinned final context, retained source wrapper and subsequent canonical HP store.',
            'Processor ability field clears before these stores; it is not used as effect-time ability proof.',
            'Bounded research witness only; no public consumable lifecycle acceptance.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS Potion use audit:',result,len(rejected),'mutations')


if __name__=='__main__':main()
