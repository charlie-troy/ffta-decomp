"""Audit live research STOP/reserve/zero refusal and zero writes after latch."""
import argparse,json,hashlib,copy
from pathlib import Path
from recovery_menu import require
from recovery_source_versions import verify_source_versions


def audit(d,case):
    require(d['inputs_unchanged'] and not d['fixture_writes'] and d.get('owned_process_closed') is True,
            'tainted evidence or owned process not closed')
    require(d['transport_events'][-1]['event']=='terminal_trace_disarmed','terminal hooks not strictly disarmed')
    error=d.get('error','');writes=d['gameplay_writes']
    if case.startswith('STOP-'):
        phase=case[5:];expected={'final-use':40,'post-effect':45,'Wait-final':60}[phase]
        require('STOP observed' in error and d['stop_injection']['phase']==phase,'wrong refusal reason')
        require(d['stop_injection']['write_count']==d['stop_requested']['write_count']==len(writes)==expected,
                'writes after STOP observation or wrong boundary')
        require(d['stop_requested']['t']-d['stop_injection']['t']<=2,'STOP observation latency exceeds two seconds')
        if phase=='final-use':
            r=d['Potion_final_refusal'];require(r['started'] and not r['attempted'] and r['hp']==100
                and r['inventory']==d['inventory_before']['raw'] and not d['Potion_use_events'],'STOP spent item or health changed')
        else:
            a=d['Potion_after'];require(a['count']==1 and a['hp']>100 and a['mp']==221,'post-use STOP lost actual effect')
            require('Potion_Wait' not in d,'STOP allowed Wait final input')
    elif case=='last-item':
        require('violates reserve' in error and len(writes)==40,'reserve refusal wrong reason/input count')
        require(d['Potion_final_token']['count']==1,'reserve fixture is not last item')
        r=d['Potion_final_refusal'];require(r['started'] and not r['attempted'] and r['hp']==100
            and r['inventory']==d['inventory_before']['raw'] and not d['Potion_use_events'],'last item consumed')
    else:
        require(case=='zero' and 'error' in d and len(writes)==25,'zero item unexpectedly selected/input count')
        require(d['native_counts']['362']==0 and 1 not in d['raw_list']['rows'] and 'Potion_use_events' not in d,
                'zero count produced Potion candidate')
    return {'case':case,'writes':len(writes),'owned_process_closed':True}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--case',choices=('STOP-final-use','STOP-post-effect','STOP-Wait-final','last-item','zero'),required=True)
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.capture);p=root/'inventory.json'
    d=json.loads(p.read_text());result=audit(d,args.case);sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    pins={p:h for p,h in d['source_sha256'].items() if p.startswith('tools/')}
    closure=verify_source_versions(pins,'probe_consumable_inventory')
    for f,h in d['source_sha256'].items():
        if f not in pins:require(sha(f)==h,'source asset changed')
    for f,h in d['capture_sha256'].items():require(sha(root/f)==h,'raw capture changed')
    for label,mutate in [('extra input',lambda x:x['gameplay_writes'].append(x['gameplay_writes'][-1])),
                          ('process alive',lambda x:x.update(owned_process_closed=False)),
                          ('source tainted',lambda x:x.update(inputs_unchanged=False))]:
        bad=copy.deepcopy(d);mutate(bad)
        try:audit(bad,args.case)
        except ValueError:pass
        else:raise AssertionError('accepted '+label)
    out={'status':'pass','scope':__doc__,'observation':result,'closure':closure,'mutations_rejected':3,
         'source_sha256':{'tools/validate_consumable_refusal.py':sha('tools/validate_consumable_refusal.py')},
         'evidence_sha256':{str(p):sha(p)},'limitations':['Research CLI and actual STOP file only; not public leave-running/manual/resume acceptance.']}
    Path(args.out).write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS live refusal:',result)


if __name__=='__main__':main()
