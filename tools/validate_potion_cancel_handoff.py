"""Actual pre-use STOP/window cancel/same-PID resumed player result acceptance."""
import argparse,json,hashlib,tempfile
from copy import deepcopy
from pathlib import Path
from recovery_menu import require
from validate_autobattle_runtime import validate
from recovery_source_versions import verify_source_versions


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--manual',default='manual-Potion-cancel.json');ap.add_argument('--source-dir',action='append',default=[]);ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.run);require(not validate(str(root)),'resumed public baseline fails: '+str(validate(str(root))))
    r=json.loads((root/'run.json').read_text());paused=json.loads((root/'paused-run.json').read_text());m=json.loads((root/args.manual).read_text())
    ev=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()];ledger=[json.loads(x) for x in (root/'input-log.jsonl').read_text().splitlines()]
    pid=paused['manual_handoff']['pid']
    require(paused['bounded_self_potion'] and paused['final_state']=='paused' and paused['turns']==0
        and paused['emulator_handoff']=='left-running-for-player','first leg was not a public handoff')
    require(m['status']=='verified-manual-Potion-cancel' and m['pid']==pid and m['stub_gameplay_writes']==0 and m['inputs_unchanged'] is True
        and m['input_channel']=='verified owned window; GDB reads/control only' and len(m['keys'])==5
        and all(k['key']=='B' and k['window']['foreground_verified'] and k['window']['pid']==pid for k in m['keys']),
        'owned native window cancellation missing')
    require([s['mode'] for s in m['states']]==[11,12,12,7,5,4] and m['states'][-1]['command']['state']=='command',
        'manual cancel did not traverse observed menus to native command')
    j=next(e['recovery'] for e in reversed(ev) if e.get('recovery'))
    require(m['final_unit']==j['Potion_final_prompt_raw']['canonical'] and j['Potion_final_token']['count']==2
        and not j['Potion_use_events'],'manual cancellation changed unit or consumed Potion')
    require(r['resumed'] and r['previous_leg']==paused and r['emulator_pid']==pid and r['adopt']['pid']==pid
        and r['adopt']['match_receipt_handoff_pid'] and r['adopt']['roster_guard_ok'] and r['turns']==1
        and r['inputs_unchanged'] is True and not r['bounded_self_potion'],'same-PID ordinary player result missing')
    turns=[e for e in ev if e['kind']=='turn'];require(len(turns)==1 and turns[0]['selected_action']['kind'] in ('identified-wait','identified-move')
        and turns[0]['engine_result']['verified'],'resume did not execute attributed player command')
    manual=[x for x in ledger if x.get('event')=='manual_key_write'];require(len(manual)==5 and all(x['val']==2 for x in manual),'manual B ledger differs')
    stop=next(x['t'] for x in ledger if x.get('event')=='stop_requested');resume=next(x['t'] for x in ledger if x.get('event')=='resume')
    require(all(stop<x['t']<resume for x in manual) and not any(x.get('event')=='key_write' and stop<x['t']<resume for x in ledger),
            'automation leaked into manual interval')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    closure=verify_source_versions(m['source_sha256'],'manual_potion_cancel_handoff',directories=args.source_dir)
    if m.get('continued_from'):
        prior=Path(m['continued_from']);require(sha(prior)==m['continued_from_sha256'],'manual prefix changed')
        old=json.loads(prior.read_text());verify_source_versions({p:h for p,h in old['source_sha256'].items() if p.endswith('.py')},
            'manual_potion_cancel_handoff',directories=args.source_dir)
        require(m['keys'][:len(old['keys'])]==old['keys'],'manual prefix key history changed')
    mutations=[('missing resume',lambda r,e,l:r.update(resumed=False)),('wrong PID',lambda r,e,l:r['adopt'].update(match_receipt_handoff_pid=False)),
        ('source changed',lambda r,e,l:r['previous_leg'].update(inputs_unchanged=False)),('source missing',lambda r,e,l:r['previous_leg'].update(input_sha256={})),
        ('resume ledger missing',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('event')!='resume']))]
    def leak(r,e,l):
        key=deepcopy(next(x for x in l if x.get('event')=='key_write'));key['t']=(stop+resume)/2;l.append(key)
    mutations.append(('automation in manual gap',leak));rejected=[]
    with tempfile.TemporaryDirectory(prefix='Potion-cancel-handoff-') as tmp:
        p=Path(tmp)
        for label,mutate in mutations:
            run,events,raw=deepcopy(r),deepcopy(ev),deepcopy(ledger);mutate(run,events,raw)
            (p/'run.json').write_text(json.dumps(run),encoding='utf-8');(p/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events),encoding='utf-8')
            (p/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in raw),encoding='utf-8')
            errors=validate(str(p));require(errors,'handoff mutation survived: '+label);rejected.append({'case':label,'errors':errors})
    output={'status':'pass-pre-use-Potion-manual-cancel-resume','scope':__doc__,'pid':pid,'rejected':rejected,'manual_closure':closure,
        'source_sha256':{p:sha(p) for p in ['tools/validate_potion_cancel_handoff.py','tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/f):sha(root/f) for f in ['run.json','paused-run.json','events.jsonl','input-log.jsonl',args.manual]},
        'limitations':['Manual boundary is pre-use cancellation. Actual use/Wait is independently proven. Post-use Wait test defeated the party before resumed player input and remains excluded.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS public Potion pre-use cancel/resume:',len(rejected),'mutations; same PID',pid)


if __name__=='__main__':main()
