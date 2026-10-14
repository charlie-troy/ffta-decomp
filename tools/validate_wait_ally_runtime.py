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
    args=ap.parse_args();root=Path(args.run);require(not validate(str(root)),'public next-ally baseline invalid')
    run=json.loads((root/'run.json').read_text());events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    ledger=[json.loads(s) for s in (root/'input-log.jsonl').read_text().splitlines()]
    index=next(i for i,e in enumerate(events) if (e.get('engine_result') or {}).get('progress'))
    turn=events[index];boundary=next(e for e in reversed(events[:index]) if e['kind']=='boundary')
    require(turn['selected_action']['kind']=='identified-wait' and turn['seeds']==boundary['seeds']
            and turn['next_actor']['source']=='owned-next-ally-command-menu' and run['inputs_unchanged'],
            'baseline not a stable zero-seed next-ally Wait')
    progress=lambda e:e[index]['engine_result']['progress']
    mutations=[
        ('missing completion proof',lambda r,e,l:e[index]['engine_result'].pop('progress')),
        ('empty post raw reads',lambda r,e,l:progress(e).__setitem__('reads',{})),
        ('empty origin reads',lambda r,e,l:progress(e)['origin'].__setitem__('reads',{})),
        ('missing original command',lambda r,e,l:progress(e)['origin'].pop('command')),
        ('foreign original wrapper',lambda r,e,l:progress(e)['origin']['facing'].__setitem__('actor_wrapper',0)),
        ('same completed actor',lambda r,e,l:progress(e)['next']['actor'].__setitem__('id',5)),
        ('foreign next canonical',lambda r,e,l:progress(e)['next'].__setitem__('canonical',0)),
        ('wrong next source',lambda r,e,l:e[index]['next_actor'].__setitem__('source','sequencer actor context')),
        ('changed selected actor MP',lambda r,e,l:e[index]['engine_result']['players_before'][0].__setitem__('mp',0)),
        ('empty input log',lambda r,e,l:l.clear()),
        ('no resumed input',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x['t']<boundary['t']])),
        ('missing input log resume',lambda r,e,l:l.__setitem__(slice(None),[x for x in l if x.get('event')!='resume'])),
    ]
    def remove_all_labels(r,e,l):
        e[index]['engine_result'].pop('progress');e[index]['next_actor']['source']='sequencer actor context'
    mutations.append(('zero-seed proof/source both deleted',remove_all_labels))
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
    print('PASS public zero-seed next-ally Wait:',len(rejected),'mutations')


if __name__=='__main__':main()
