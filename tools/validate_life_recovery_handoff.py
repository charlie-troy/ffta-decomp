"""Audit public post-Life STOP, owned window Wait and same-PID public resume."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

from recovery_menu import require
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'Life resumed baseline fails: '+str(validate(str(root))))
    run=json.loads((root/'run.json').read_text());paused=json.loads((root/'paused-run.json').read_text())
    manual=json.loads((root/'manual-Life-Wait.json').read_text())
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    pid=paused['manual_handoff']['pid']
    require(paused['bounded_ally_life'] and paused['final_state']=='paused'
            and paused['emulator_handoff']=='left-running-for-player' and paused['turns']==0,
            'Life first leg did not establish real handoff')
    require(manual['status']=='verified-manual-Life-Wait' and manual['pid']==pid
            and manual['stub_gameplay_writes']==0 and manual['inputs_unchanged']
            and manual['input_channel']=='verified owned window; GDB reads/control only'
            and len(manual['keys'])==1 and manual['keys'][0]['key']=='A'
            and len(manual['continuations'])==1 and manual['continuations'][0]['relation']=='enemy',
            'Life owned manual Wait/next actor missing')
    require(run['resumed'] and run['previous_leg']==paused and run['emulator_pid']==pid
            and run['adopt']['pid']==pid and run['adopt']['match_receipt_handoff_pid']
            and run['adopt']['roster_guard_ok'] and run['turns']==1 and run['inputs_unchanged'],
            'Life same-PID public resume not proven')
    require(not run.get('bounded_ally_life') and any(e['kind']=='turn' and
            e['selected_action']['kind'] in ('identified-wait','identified-move') for e in events),
            'Life handoff resumed without independent ordinary Move/Wait turn')
    manual_rows=[r for r in ledger if r.get('event')=='manual_key_write']
    require(len(manual_rows)==1 and manual_rows[0]['val']==1,'Life manual input ledger missing')
    stop_t=next(r['t'] for r in ledger if r.get('event')=='stop_requested')
    resume_t=next(r['t'] for r in ledger if r.get('event')=='resume')
    require(stop_t<manual_rows[0]['t']<resume_t and not any(r.get('event')=='key_write'
            and stop_t<r['t']<resume_t for r in ledger),'Life automated input leaked into manual gap')
    rejected=[]
    mutations=[('missing resume',lambda r,e,l:r.__setitem__('resumed',False)),
        ('wrong resumed PID',lambda r,e,l:r['adopt'].__setitem__('match_receipt_handoff_pid',False)),
        ('invented source stability',lambda r,e,l:r['previous_leg'].__setitem__('inputs_unchanged',False)),
        ('missing old source closure',lambda r,e,l:r['previous_leg'].__setitem__('input_sha256',{})),
        ('no resume ledger',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('event')!='resume'])),
    ]
    def leak(r,e,l):
        key=deepcopy(next(x for x in l if x.get('event')=='key_write'));key['t']=(stop_t+resume_t)/2;l.append(key)
    mutations.append(('automation in manual gap',leak))
    with tempfile.TemporaryDirectory(prefix='ffta-Life-handoff-') as directory:
        p=Path(directory)
        for label,edit in mutations:
            r,e,l=deepcopy(run),deepcopy(events),deepcopy(ledger);edit(r,e,l)
            (p/'run.json').write_text(json.dumps(r),encoding='utf-8')
            (p/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in e),encoding='utf-8')
            (p/'input-log.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in l),encoding='utf-8')
            errors=validate(str(p));require(bool(errors),'Life resume mutation survived: '+label)
            rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-Life-public-handoff','scope':__doc__,'pid':pid,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/validate_life_recovery_handoff.py','tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','paused-run.json','events.jsonl',
            'input-log.jsonl','manual-Life-Wait.json']},
        'limitations':['Exact post-Life Wait manual boundary only; no whole-battle completion claim.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life manual/same-PID resume:',len(rejected),'receipt mutations')


if __name__=='__main__':main()
