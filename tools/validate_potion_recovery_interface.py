"""Public Potion opt-in must reject invalid policy/family before emulator use."""
import argparse,json,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import run_autobattle
from potion_recovery_runtime import drive_potion_recovery
from tactics_policy import load_policy_file
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args();checks=[]
    with tempfile.TemporaryDirectory(prefix='Potion-interface-') as tmp:
        p=Path(tmp)/'schema1.json';p.write_text(json.dumps({'schema':'ffta-tactics-policy/1','assignments':{},'fallback':'wait'}))
        for label,argv in [('missing-policy',['--bounded-self-potion','--yes']),
            ('schema1',['--bounded-self-potion','--tactics-policy',str(p),'--yes']),
            ('default-disabled',['--bounded-self-potion','--tactics-policy','configs/tactics/healer.json','--yes']),
            ('mutual',['--bounded-self-potion','--bounded-ally-life','--yes'])]:
            with patch.object(run_autobattle,'FixtureSession',side_effect=AssertionError('emulator touched')):
                try:code=run_autobattle.main(argv)
                except SystemExit as exc:code=exc.code
            require(code==2,'invalid Potion CLI accepted');checks.append(label)
    policy=load_policy_file('configs/tactics/potion-self.json');good={'id':5,'job':5,'race':1,'x':5,'y':10}
    with patch.object(run_autobattle,'FixtureSession',side_effect=AssertionError('valid-cli-reached-session')) as session:
        try:run_autobattle.main(['--bounded-self-potion','--tactics-policy','configs/tactics/potion-self.json','--yes','--run-id','host-Potion-interface-control'])
        except AssertionError as exc:require(str(exc)=='valid-cli-reached-session','unexpected valid CLI failure')
        except SystemExit as exc:raise AssertionError('valid bounded Potion flag was not recognized') from exc
        else:raise AssertionError('valid Potion CLI did not reach session seam')
        require(session.call_count==1,'valid Potion CLI never dispatched');checks.append('recognized-valid-cli')
    for label,field,value in [('id','id',7),('job','job',2),('race','race',2),('tile-x','x',4),('tile-y','y',11),('party',None,None)]:
        runtime=SimpleNamespace(owner=good|({field:value} if field else {}),p=SimpleNamespace(key_write_log=[]),
            tactics=SimpleNamespace(policy=policy),_pre_players=[{}]*(2 if field else 1),t0=time.time())
        journal={}
        try:drive_potion_recovery(runtime,journal)
        except ValueError:require(not runtime.p.key_write_log and not journal['raw_writes'] and not journal['transport'],'family rejection touched input')
        else:raise AssertionError('wrong Potion family accepted')
        checks.append(label)
    Path(args.out).write_text(json.dumps({'status':'pass','scope':__doc__,'checks':checks,'limitations':['Host pre-transport checks only.']},indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS Potion public interface:',len(checks),'controls')


if __name__=='__main__':main()
