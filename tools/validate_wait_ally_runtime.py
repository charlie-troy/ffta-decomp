"""Mutate a real zero-seed next-ally Wait through the complete public receipt validator."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

from recovery_menu import require
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--allow-seeded',action='store_true',help='Audit current ordinary Wait input on the existing seeded path')
    args=ap.parse_args();root=Path(args.run);require(not validate(str(root)),'public next-ally baseline invalid')
    run=json.loads((root/'run.json').read_text());events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    index=next(i for i,e in enumerate(events) if (e.get('engine_result') or {}).get('progress')
               or args.allow_seeded and (e.get('selected_action') or {}).get('kind')=='identified-wait')
    turn=events[index];boundary=next(e for e in reversed(events[:index]) if e['kind']=='boundary')
    has_progress=bool(turn['engine_result'].get('progress'))
    require(turn['selected_action']['kind']=='identified-wait' and run['inputs_unchanged']
            and (has_progress and turn['seeds']==boundary['seeds'] and
                 turn['next_actor']['source']=='owned-next-ally-command-menu'
                 or args.allow_seeded and run.get('ordinary_raw_input') is True),
            'baseline not a stable next-ally/current raw-input Wait')
    progress=lambda e:e[index]['engine_result']['progress']
    mutations=([
        ('missing completion proof',lambda r,e,l:e[index]['engine_result'].pop('progress')),
        ('empty post raw reads',lambda r,e,l:progress(e).__setitem__('reads',{})),
        ('empty origin reads',lambda r,e,l:progress(e)['origin'].__setitem__('reads',{})),
        ('missing original command',lambda r,e,l:progress(e)['origin'].pop('command')),
        ('foreign original wrapper',lambda r,e,l:progress(e)['origin']['facing'].__setitem__('actor_wrapper',0)),
        ('same completed actor',lambda r,e,l:progress(e)['next']['actor'].__setitem__('id',5)),
        ('foreign next canonical',lambda r,e,l:progress(e)['next'].__setitem__('canonical',0)),
        ('wrong next source',lambda r,e,l:e[index]['next_actor'].__setitem__('source','sequencer actor context')),
        ('changed selected actor MP',lambda r,e,l:e[index]['engine_result']['players_before'][0].__setitem__('mp',0)),
    ] if has_progress else [])+[
        ('empty input log',lambda r,e,l:l.clear()),
        ('no resumed input',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x['t']<boundary['t']])),
        ('missing input log resume',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('event')!='resume'])),
    ]
    def remove_all_labels(r,e,l):
        e[index]['engine_result'].pop('progress');e[index]['next_actor']['source']='sequencer actor context'
    if has_progress:mutations.append(('zero-seed proof/source both deleted',remove_all_labels))
    mutations.extend([
        ('duplicate final confirm',lambda r,e,l:l.append(deepcopy(next(x for x in l if x.get('tag')=='c3:confirm-wait')))),
        ('missing final confirm',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('tag')!='c3:confirm-wait'])),
        ('wrong confirm mask',lambda r,e,l:next(x for x in l if x.get('tag')=='c3:confirm-wait').__setitem__('mask',128)),
    ])
    if run.get('ordinary_raw_input') is True:
        mutations.append(('missing current raw writes',lambda r,e,l:l.__setitem__(slice(None),
            [x for x in l if not (x.get('event')=='key_write' and x['t']>=boundary['t']-0.051)])))
        confirm=next(x for x in ledger if x.get('tag')=='c3:confirm-wait')
        def drop_confirm_raw(r,e,l):
            i=next(i for i,x in enumerate(l) if x.get('event')=='key_write' and confirm['t']<=x['t']<=confirm['t']+confirm['duration'])
            l.pop(i)
        mutations.append(('missing one final register write',drop_confirm_raw))
    def leak(r,e,l):
        row=deepcopy(next(x for x in l if x.get('event') in ('key_write','press')))
        row['t']=events[-1]['t']+2;l.append(row)
    mutations.append(('input after terminal',leak));rejected=[]
    with tempfile.TemporaryDirectory(prefix='ffta-Wait-ally-public-') as directory:
        out=Path(directory)
        for label,edit in mutations:
            r,e,l=deepcopy(run),deepcopy(events),deepcopy(ledger);edit(r,e,l)
            (out/'run.json').write_text(json.dumps(r),encoding='utf-8')
            for name,rows in [('events',e),('input-log',l)]:
                (out/(name+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
            errors=validate(str(out));require(bool(errors),'public next-ally mutation survived: '+label)
            rejected.append({'case':label,'errors':errors})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-public-Wait-next-ally-mutations','scope':__doc__,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/validate_wait_ally_runtime.py','tools/wait_ally_continuation.py',
                                         'tools/validate_autobattle_runtime.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','events.jsonl','input-log.jsonl']},
        'limitations':['Retained full receipt mutations; no new gameplay or whole-battle claim.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS public identified Wait inputs/completion:',len(rejected),'mutations')


if __name__=='__main__':main()
