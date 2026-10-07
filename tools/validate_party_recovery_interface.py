"""Public recovery flags reject invalid policies and families before input."""
import argparse
import io
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import run_autobattle
from party_recovery_runtime import drive_party_recovery
from recovery_menu import RecoveryStateError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory(prefix='ffta-party-interface-') as directory:
        old=Path(directory)/'schema1.json'
        old.write_text(json.dumps({'schema':'ffta-tactics-policy/1','assignments':{},'fallback':'wait'}))
        for name,argv in [
            ('missing schema2',['--bounded-ally-cure','--yes']),
            ('schema1 refused',['--bounded-ally-cure','--tactics-policy',str(old),'--yes']),
            ('exclusive fixture flags',['--bounded-ally-cure','--bounded-self-cure','--yes'])]:
            with patch.object(run_autobattle,'FixtureSession',side_effect=AssertionError('emulator touched')):
                try:result=run_autobattle.main(argv)
                except SystemExit as exc:result=exc.code
            assert result==2,(name,result)
            checks.append({'case':name,'status':'pass','emulator_touched':False})
    for name,owner,count in [
        ('self-only caster',{'id':6,'job':2,'race':1,'x':4,'y':10},1),
        ('wrong party count',{'id':7,'job':5,'race':1,'x':4,'y':10},1),
        ('wrong caster job',{'id':7,'job':2,'race':1,'x':4,'y':10},2),
        ('wrong caster tile',{'id':7,'job':5,'race':1,'x':5,'y':10},2)]:
        probe=SimpleNamespace(key_write_log=[])
        runtime=SimpleNamespace(owner=owner,p=probe,t0=time.time(),tactics=SimpleNamespace(policy={}),
                                _pre_players=[{}]*count,_input_log=io.StringIO())
        journal={}
        try:drive_party_recovery(runtime,journal)
        except RecoveryStateError:pass
        else:raise AssertionError(name+' accepted')
        assert not journal['raw_writes'] and not journal['transport']
        checks.append({'case':name,'status':'pass','raw_writes':0})
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'status':'pass','scope':__doc__,'checks':checks},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS party public interface: {len(checks)} controls')


if __name__=='__main__':main()
