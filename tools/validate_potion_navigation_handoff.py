"""Public navigation STOP/window menu toggle/same-PID player command result."""
import argparse,json,hashlib,tempfile
from pathlib import Path
from copy import deepcopy
from recovery_menu import require
from recovery_source_versions import verify_source_versions
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'resumed public validator failed: '+str(validate(str(root))))
    r=json.loads((root/'run.json').read_text());paused=json.loads((root/'paused-run.json').read_text());m=json.loads((root/'manual-Potion-navigation.json').read_text())
    events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()];raw=[json.loads(x) for x in (root/'input-log.jsonl').read_text().splitlines()]
    pid=paused['emulator_pid'];require(paused['bounded_self_potion'] and paused['final_state']=='paused' and paused['turns']==0
        and paused['emulator_handoff']=='left-running-for-player','navigation public pause absent')
    require(m['status']=='verified-manual-Potion-navigation' and m['pid']==pid and m['inputs_unchanged'] is True
        and m['stub_gameplay_writes']==0 and m['input_channel']=='verified owned window; GDB reads/control only',
        'native manual window command missing')
    require([k['key'] for k in m['keys']] in (['B','A'],['B','B','A'])
        and all(k['window']['pid']==pid and k['window']['foreground_verified'] for k in m['keys']),'manual keys/focus differ')
    require([s['mode'] for s in m['states']] in ([4,0,4],[5,4,0,4])
        and all(s['roster']['struct_count']==s['roster']['live_count']==8 and s['roster']['ids_distinct'] for s in m['states']),
        'manual menu did not preserve native eight-unit guard')
    require(m['states'][-1]['command']['state']=='command' and m['states'][-1]['command']['hp']==100
        and m['states'][-1]['command']['mp']==221,'manual command/resources not restored')
    require(r.get('resumed') and r['previous_leg']==paused and r['emulator_pid']==pid and r['adopt']['pid']==pid
        and r['adopt']['roster_guard_ok'] and r['adopt']['match_receipt_handoff_pid'] and r['turns']==1
        and r['inputs_unchanged'] is True and not r['bounded_self_potion'],'same-PID resumed player result missing')
    turns=[e for e in events if e['kind']=='turn'];require(len(turns)==1 and turns[0]['selected_action']['kind'] in ('identified-wait','identified-move')
        and turns[0]['engine_result']['verified'],'no attributed ordinary player result')
    manual=[x for x in raw if x.get('event')=='manual_key_write'];stop=next(x['t'] for x in raw if x.get('event')=='stop_requested');resume=next(x['t'] for x in raw if x.get('event')=='resume')
    require(len(manual)==len(m['keys']) and [x['val'] for x in manual]==[2 if k['key']=='B' else 1 for k in m['keys']]
        and all(stop<x['t']<resume for x in manual) and not any(x.get('event')=='key_write' and stop<x['t']<resume for x in raw),
        'manual gap ledger contains automation or differs from window keys')
    closure=verify_source_versions(m['source_sha256'],'manual_potion_navigation_handoff')
    mutations=[('resume missing',lambda r,e,l:r.update(resumed=False)),('wrong PID',lambda r,e,l:r['adopt'].update(match_receipt_handoff_pid=False)),
        ('guard missing',lambda r,e,l:r['adopt'].update(roster_guard_ok=False)),('old source tainted',lambda r,e,l:r['previous_leg'].update(inputs_unchanged=False)),
        ('old closure missing',lambda r,e,l:r['previous_leg'].update(input_sha256={})),
        ('resume ledger missing',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('event')!='resume']))]
    def leak(r,e,l):
        x=deepcopy(next(x for x in l if x.get('event')=='key_write'));x['t']=(stop+resume)/2;l.append(x)
    mutations.append(('automation in manual gap',leak));rejected=[]
    with tempfile.TemporaryDirectory(prefix='Potion-navigation-audit-') as tmp:
        p=Path(tmp)
        for label,mutate in mutations:
            run,ev,ledger=deepcopy(r),deepcopy(events),deepcopy(raw);mutate(run,ev,ledger)
            (p/'run.json').write_text(json.dumps(run),encoding='utf-8');(p/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in ev),encoding='utf-8')
            (p/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in ledger),encoding='utf-8')
            errors=validate(str(p));require(errors,'navigation handoff mutation survived: '+label);rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-public-Potion-navigation-handoff','scope':__doc__,'pid':pid,'rejected':rejected,'manual_closure':closure,
        'source_sha256':{p:sha(p) for p in ['tools/validate_potion_navigation_handoff.py','tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/f):sha(root/f) for f in ['run.json','paused-run.json','manual-Potion-navigation.json','events.jsonl','input-log.jsonl']},
        'limitations':['Navigation manual boundary only. Actual item use is independently captured; post-use Wait resume defeated the party and post-Item cancel failed native adoption. Neither failed boundary is promoted.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS public Potion navigation handoff:',len(rejected),'mutations; same PID',pid)


if __name__=='__main__':main()
