"""Run final-source Life/Cure/default/refusal controls sequentially through the real public CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fixture_guard import port_listener_pid
from recovery_menu import require
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--prefix',required=True)
    ap.add_argument('--after-run',help='Wait for this owned preceding run to terminate and release its port')
    ap.add_argument('--cases',nargs='+',choices=('Life','ally-Cure','self-Cure','default','unsupported','reserve',
                    'STOP-navigation','STOP-final'),help='Run only named remaining controls; defaults to all')
    args=ap.parse_args();require(Path(args.prefix).name==args.prefix and not any(c in args.prefix for c in ':\\/'),
        'matrix prefix must be a filename')
    root=Path('outputs/autobattle');output=root/(args.prefix+'-matrix.json')
    require(not output.exists(),'matrix evidence must be new')
    life='outputs/autobattle/a64-life-fixture-02/life-recovery.ss0'
    self_state='outputs/autobattle/a61-public-fixture-mp85-02/recovery.ss0'
    ally_state='outputs/autobattle/a62-party-fixture-01/party-recovery.ss0'
    cases=[('Life',life,'--bounded-ally-life','life'),('ally-Cure',ally_state,'--bounded-ally-cure','ally'),
        ('self-Cure',self_state,'--bounded-self-cure','self'),('default',life,None,'default'),
        ('unsupported',self_state,'--bounded-ally-life','unsupported'),
        ('reserve',life,'--bounded-ally-life','reserve')]
    if args.cases:cases=[c for c in cases if c[0] in args.cases]
    for name,state,flag,kind in cases:
        require(Path(state).is_file(),'missing verified fixture: '+state)
        require(not (root/(args.prefix+'-'+name)).exists(),'run evidence must be new')
    if args.after_run:
        previous=root/args.after_run;deadline=time.monotonic()+420
        while time.monotonic()<deadline:
            if (previous/'run.json').exists():
                run=json.loads((previous/'run.json').read_text())
                if run.get('resumed') and run.get('emulator_handoff')=='terminated' and port_listener_pid(2345) is None:break
            time.sleep(0.5)
        else:raise RuntimeError('preceding owned run did not terminate/release port')
    result={'status':'partial','scope':__doc__,'cases':[],'limitations':['Exact retained local fixtures; no whole-battle claim.']}
    pinned=None
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def child(run_id,label,command,expected=0):
        path=root/(run_id+'-'+label+'.log');require(not path.exists(),'child log must be new')
        with path.open('x',encoding='utf-8') as log:
            proc=subprocess.run([sys.executable,*command],stdout=log,stderr=subprocess.STDOUT,
                timeout=300,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        require(proc.returncode==expected,f'{label} failed; inspect {path}')
    try:
        for name,state,flag,kind in cases:
            require(port_listener_pid(2345) is None,'another emulator holds the matrix port')
            run_id=args.prefix+'-'+name;directory=root/run_id
            policy='outputs/autobattle/a64-life-reserve-policy.json' if kind=='reserve' else 'configs/tactics/healer.json'
            command=['tools/run_autobattle.py','--state',state,'--tactics-policy',policy,'--run-id',run_id,
                '--max-turns','1','--wall-timeout','180','--on-stop','kill','--yes']
            if state!=self_state:command.extend(['--scenario','configs/battle-scenarios/a4-two-player.json'])
            if flag:command.append(flag)
            child(run_id,'cli',command,1)
            require(not validate(str(directory)),'matrix public receipt invalid')
            run=json.loads((directory/'run.json').read_text());require(run['inputs_unchanged'],'matrix source changed')
            sources={p:h for p,h in run['input_sha256'].items() if p.startswith('tools/')}
            common={p:sources[p] for p in ('tools/run_autobattle.py','tools/autobattle_runtime.py','tools/wait_ally_continuation.py')}
            if pinned is None:pinned=common
            require(common==pinned,'matrix core changed between cases')
            validator={'life':'validate_life_recovery_runtime','ally':'validate_party_recovery_runtime',
                       'self':'validate_recovery_runtime','default':'validate_life_recovery_default'}.get(kind)
            checks=directory/'checks.json'
            if validator:child(run_id,'checks',[f'tools/{validator}.py','--run',str(directory),'--out',str(checks)])
            elif kind=='reserve':child(run_id,'checks',['tools/validate_life_recovery_decline.py','--run',str(directory),
                '--mode','reserve','--out',str(checks)])
            else:
                ledger=[json.loads(s) for s in (directory/'input-log.jsonl').read_text().splitlines()]
                require(run['turns']==0 and not any(r.get('event') in ('key_write','press','drive') for r in ledger)
                        and 'outside bounded family' in run['terminal_reason'],'unsupported family got input')
            result['cases'].append({'case':name,'run_id':run_id,'status':'pass','pid':run['emulator_pid'],
                'turns':run['turns'],'input_sha256':run['input_sha256'],
                'evidence_sha256':{str(directory/n):sha(directory/n) for n in ('run.json','events.jsonl','input-log.jsonl')}})
            print('PASS final-source matrix case:',name,flush=True)
        for name,phase in [('STOP-navigation','navigation'),('STOP-final','Life-final')]:
            if args.cases and name not in args.cases:continue
            require(port_listener_pid(2345) is None,'matrix STOP port held')
            run_id=args.prefix+'-'+name;directory=root/run_id
            child(run_id,'watch',['tools/run_life_cli_stop.py','--state',life,'--run-id',run_id,
                '--phase',phase,'--kill-on-stop'])
            child(run_id,'checks',['tools/validate_life_recovery_decline.py','--run',str(directory),
                '--mode',phase,'--out',str(directory/'checks.json')])
            run=json.loads((directory/'run.json').read_text());require(run['inputs_unchanged'],'STOP source changed')
            result['cases'].append({'case':name,'run_id':run_id,'status':'pass','pid':run['emulator_pid'],
                'evidence_sha256':{str(directory/n):sha(directory/n) for n in ('run.json','events.jsonl','input-log.jsonl','checks.json')}})
            print('PASS final-source matrix case:',name,flush=True)
        result['status']='pass-final-source-Life-regressions';result['common_source_sha256']=pinned
    finally:output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS final-source public matrix:',len(result['cases']),'cases')


if __name__=='__main__':main()
