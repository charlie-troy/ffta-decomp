"""Reject public Life policy/fixture mismatches before transport or input."""
import argparse
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import run_autobattle
from life_recovery_runtime import drive_life_recovery
from recovery_menu import require
from tactics_policy import load_policy_file


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    controls=[]
    with tempfile.TemporaryDirectory(prefix='ffta-Life-interface-') as directory:
        path=Path(directory)/'schema1.json'
        path.write_text(json.dumps({'schema':'ffta-tactics-policy/1','assignments':{},'fallback':'wait'}))
        for label,argv in [('missing-policy',['--bounded-ally-life','--yes']),
            ('schema1',['--bounded-ally-life','--tactics-policy',str(path),'--yes']),
            ('self-mutual',['--bounded-ally-life','--bounded-self-cure','--yes']),
            ('ally-mutual',['--bounded-ally-life','--bounded-ally-cure','--yes'])]:
            with patch.object(run_autobattle,'FixtureSession',side_effect=AssertionError('emulator touched')):
                try:code=run_autobattle.main(argv)
                except SystemExit as exc:code=exc.code
            require(code==2,'invalid Life CLI accepted');controls.append(label)
    policy=load_policy_file('configs/tactics/healer.json')
    good={'id':5,'job':5,'race':1,'x':5,'y':10}
    for label,field,value in [('caster-id','id',7),('caster-job','job',2),('caster-race','race',2),
                              ('caster-x','x',4),('caster-y','y',11),('party-count',None,None)]:
        owner=good|({field:value} if field else {})
        runtime=SimpleNamespace(owner=owner,p=SimpleNamespace(key_write_log=[]),
            tactics=SimpleNamespace(policy=policy),_pre_players=[{}]*(1 if not field else 2),t0=time.time())
        journal={}
        try:drive_life_recovery(runtime,journal)
        except ValueError:require(not runtime.p.key_write_log and not journal['raw_writes']
                                  and not journal['transport'],'family rejection touched input')
        else:raise AssertionError('accepted wrong Life family')
        controls.append(label)
    output={'status':'pass-Life-public-interface','scope':__doc__,'controls':controls,
            'limitations':['Host pre-transport guards only; no live public Life acceptance.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS public Life interface:',len(controls),'controls')


if __name__=='__main__':main()
