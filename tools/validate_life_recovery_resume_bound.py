"""Audit a failed Life resume without promoting adoption to player-control proof."""
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
    require(not validate(str(root)), 'resumed bounded baseline failed')
    run=json.loads((root/'run.json').read_text())
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    require(run['resumed'] and run['previous_leg']['bounded_ally_life'] and run['turns']==0
            and run['final_state']=='stalled' and run['adopt']['match_receipt_handoff_pid'],
            'expected same-PID adoption with no resumed player turn')
    stop=next(r['t'] for r in ledger if r.get('event')=='stop_requested')
    resume=next(r['t'] for r in ledger if r.get('event')=='resume')
    edits=[('old source changed',lambda r,e,l:r['previous_leg'].__setitem__('inputs_unchanged',False)),
           ('old closure absent',lambda r,e,l:r['previous_leg'].__setitem__('input_sha256',{})),
           ('old after-pins absent',lambda r,e,l:r['previous_leg'].__setitem__('input_sha256_after',{})),
           ('PID mismatch',lambda r,e,l:r['adopt'].__setitem__('match_receipt_handoff_pid',False))]
    def leak(r,e,l):
        row=deepcopy(next(x for x in l if x.get('event')=='key_write'))
        row['t']=(stop+resume)/2;l.append(row)
    edits.append(('automated input in manual gap',leak));rejected=[]
    with tempfile.TemporaryDirectory(prefix='ffta-Life-resume-bound-') as directory:
        p=Path(directory)
        for label,edit in edits:
            r,e,l=deepcopy(run),deepcopy(events),deepcopy(ledger);edit(r,e,l)
            (p/'run.json').write_text(json.dumps(r),encoding='utf-8')
            for name,rows in [('events',e),('input-log',l)]:
                (p/(name+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
            errors=validate(str(p));require(bool(errors),'bounded resume mutation survived: '+label)
            rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-bounded-resume-audit','acceptance':'same-PID-player-control-UNKNOWN',
        'scope':__doc__,'turns':0,'pid':run['emulator_pid'],'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/validate_life_recovery_resume_bound.py','tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','events.jsonl','input-log.jsonl']},
        'limitations':['Adoption and truthful bounded stop only; no resumed player turn or completed battle.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS failed-resume audit:',len(rejected),'mutations; player-control UNKNOWN')


if __name__=='__main__':main()
