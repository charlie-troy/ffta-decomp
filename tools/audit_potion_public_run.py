"""Audit a real public Potion turn and corruptions through the public validator."""
import argparse,json,hashlib,tempfile
from copy import deepcopy
from pathlib import Path
from validate_autobattle_runtime import validate
from recovery_menu import require
from recovery_source_versions import verify_source_versions
from validate_consumable_menu import Memory
from consumable_menu import OwnedItemList
from consumable_final import PotionFinalPromptReader


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--source-dir',action='append',default=[]);ap.add_argument('--source-ref',action='append',default=[]);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'baseline public Potion validator failed: '+str(validate(str(root))))
    r=json.loads((root/'run.json').read_text());events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(x) for x in (root/'input-log.jsonl').read_text().splitlines()];index=next(i for i,e in enumerate(events) if e['kind']=='turn')
    require(r['bounded_self_potion'] and r['turns']==1 and r['inputs_unchanged'] is True,'public opt-in/source/turn count differs')
    j=events[index]['recovery'];capture=Path(j['capture_dir']);rom=Path('baserom.gba').read_bytes();sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    pins={p:h for p,h in r['input_sha256'].items() if p.startswith('tools/') and p.endswith('.py')}
    closure=verify_source_versions(pins,'potion_recovery_runtime',args.source_ref,args.source_dir)
    require(r['input_sha256']==r['input_sha256_after'],'public launch closure changed')
    for p,h in r['input_sha256'].items():
        if p not in pins:require(sha(p)==h,'public source asset changed')
    for name,h in j['capture_sha256'].items():require(sha(capture/name)==h,'raw native capture changed')
    g=Memory((capture/'Item-list-ewram.bin').read_bytes());menu=OwnedItemList(g,rom,j['owner'],0x02000188);origin=menu.snapshot()
    reader=PotionFinalPromptReader(menu,origin);g.raw=bytearray((capture/'Potion-final-prompt-ewram.bin').read_bytes())
    require(json.loads(json.dumps(reader.snapshot().receipt()))==j['Potion_final_token'],'raw final context differs')
    trace=capture/'Potion-engine.jsonl';require([json.loads(x) for x in trace.read_text().splitlines()]==j['potion_engine_hits'],'raw native trace differs')
    journal=lambda e:e[index]['recovery']
    controls=[('missing journal',lambda r,e,l:e[index].update(recovery=None)),
        ('foreign policy target',lambda r,e,l:journal(e)['policy_observations'][0]['snapshot']['candidates'][0]['target'].update(id=7)),
        ('foreign policy actor',lambda r,e,l:journal(e)['policy_observations'][0]['snapshot']['actor'].update(id=7)),
        ('default items disabled',lambda r,e,l:journal(e)['policy_document'].update(consumables=False)),
        ('missing policy revalidation',lambda r,e,l:journal(e)['policy_observations'].pop()),
        ('law forbids',lambda r,e,l:journal(e)['Potion_final_token']['law_matches'][0].__setitem__(1,1)),
        ('native wrong item',lambda r,e,l:journal(e)['Potion_after']['native_hits'][0].update(item=363)),
        ('native foreign HP',lambda r,e,l:journal(e)['Potion_after']['native_hits'][3].update(canonical=0x02000080)),
        ('count not consumed',lambda r,e,l:journal(e)['Potion_after'].update(count=2)),
        ('native trace missing',lambda r,e,l:journal(e).update(potion_engine_hits=[])),
        ('duplicate use',lambda r,e,l:journal(e)['Potion_use_events'].extend(deepcopy(journal(e)['Potion_use_events']))),
        ('duplicate Wait',lambda r,e,l:journal(e)['Potion_Wait_events'].extend(deepcopy(journal(e)['Potion_Wait_events'][-2:]))),
        ('ledger truncated',lambda r,e,l:l.pop(next(i for i,x in enumerate(l) if x.get('event')=='key_write'))),
        ('journal ledger empty',lambda r,e,l:journal(e).update(raw_writes=[])),
        ('trace restore missing',lambda r,e,l:journal(e)['transport_events'].pop()),
        ('next actor stale',lambda r,e,l:journal(e)['Potion_continuation'].update(canonical=0x02000188)),
        ('raw capability forged',lambda r,e,l:r.update(ordinary_raw_input=True)),
        ('source changed',lambda r,e,l:r.update(inputs_unchanged=False)),
        ('source proof missing',lambda r,e,l:r.pop('inputs_unchanged')),
        ('closure empty',lambda r,e,l:r.update(input_sha256={})),
        ('closure changed after',lambda r,e,l:r.update(input_sha256_after={}))]
    rejected=[]
    with tempfile.TemporaryDirectory(prefix='Potion-public-audit-') as tmp:
        path=Path(tmp)
        for label,mutate in controls:
            run,ev,raw=deepcopy(r),deepcopy(events),deepcopy(ledger);mutate(run,ev,raw)
            (path/'run.json').write_text(json.dumps(run),encoding='utf-8');(path/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in ev),encoding='utf-8')
            (path/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in raw),encoding='utf-8')
            errors=validate(str(path));require(errors,'public Potion mutation survived: '+label);rejected.append({'case':label,'errors':errors})
    output={'status':'pass','scope':__doc__,'closure':closure,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/audit_potion_public_run.py','tools/potion_recovery_receipt.py','tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/f):sha(root/f) for f in ['run.json','events.jsonl','input-log.jsonl']},
        'limitations':['Bounded one-turn public CLI witness; turn budget is not whole-battle acceptance. STOP/manual/resume separate.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS public Potion:',len(rejected),'mutations; native final replay and exact source closure')


if __name__=='__main__':main()
