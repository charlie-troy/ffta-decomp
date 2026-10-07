"""Reject invented healing or policy selection in a real public ally decline."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.run)
    assert not validate(str(root)),validate(str(root))
    run=json.loads((root/'run.json').read_text());events=[json.loads(l) for l in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(l) for l in (root/'input-log.jsonl').read_text().splitlines()]
    i=next(i for i,e in enumerate(events) if e['kind']=='turn');assert events[i]['recovery']['recovery']['outcome']=='declined'
    def journal(e):return e[i]['recovery']
    def escaped(e,l):
        l.append({**next(r for r in l if r['event']=='key_write'),'t':events[-1]['t']+1})
    controls=[
        ('missing adapter refusal',lambda e,l:journal(e).update(policy_observations=[])),
        ('invented adapter selection',lambda e,l:journal(e)['policy_observations'][0]['evaluation'].update(decision={'candidate_id':'cure-ally'})),
        ('wrong legal target',lambda e,l:journal(e)['policy_observations'][0]['snapshot']['candidates'][0]['target'].update(id=7)),
        ('wrong policy actor job',lambda e,l:journal(e)['policy_observations'][0]['snapshot']['actor'].update(job_id=2)),
        ('wrong policy actor side',lambda e,l:journal(e)['policy_observations'][0]['snapshot']['actor'].update(side='enemy')),
        ('stale policy actor tile',lambda e,l:journal(e)['policy_observations'][0]['snapshot']['actor'].update(tile=[5,10])),
        ('MP spent on refusal',lambda e,l:journal(e)['recovery']['after'].update(mp=79)),
        ('target healed despite refusal',lambda e,l:journal(e)['continuations'][0]['party_after'][0].update(hp=150)),
        ('fabricated cure action',lambda e,l:e[i]['selected_action'].update(kind='identified-ally-cure',ability_id=1)),
        ('empty ledger',lambda e,l:l.clear()),
        ('missing modal cancel input',lambda e,l:l.pop(45)),
        ('missing Wait final policy',lambda e,l:journal(e).update(wait_events=[r for r in journal(e)['wait_events'] if r['event']!='final_policy'])),
        ('no next enemy',lambda e,l:journal(e).update(continuations=[])),
        ('input after terminal',escaped),
        ('cleanup count changed',lambda e,l:journal(e)['transport'][-1].update(write_count=0)),
    ]
    rejected=[]
    with tempfile.TemporaryDirectory(prefix='ffta-party-decline-') as folder:
        path=Path(folder);(path/'run.json').write_text(json.dumps(run))
        for label,mutate in controls:
            es,log=copy.deepcopy(events),copy.deepcopy(ledger);mutate(es,log)
            (path/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in es))
            (path/'input-log.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in log))
            errors=validate(str(path));assert errors,label+' survived'
            rejected.append({'case':label,'errors':errors})
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'status':'pass','run':args.run,'scope':__doc__,'rejections':rejected},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS party decline: {len(rejected)} rejected mutations')


if __name__=='__main__':main()
