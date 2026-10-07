"""Run owned research STOP or reserve-policy controls without touching original fixtures."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('confirmation','facing','reserve'),required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    out=Path(args.out)
    if out.exists():raise FileExistsError(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    stop=out.parent/(out.name+'.stop')
    if stop.exists():raise FileExistsError(stop)
    runner='tools/probe_recovery_ally_turn.py' if args.phase=='facing' else 'tools/probe_recovery_ally_cure.py'
    command=[sys.executable,runner,'--out',str(out),'--stop-file',str(stop)]
    if args.phase=='reserve':
        policy=json.loads(Path('configs/tactics/healer.json').read_text())
        for rule in policy['assignments']['party']['player']['rules']:
            if rule['id']=='heal-wounded-ally':rule['when']['remaining_mp_after_cost']['gte']=80
        policy_path=out.parent/(out.name+'-policy.json')
        if policy_path.exists():raise FileExistsError(policy_path)
        policy_path.write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8',newline='\n')
        command+=['--policy',str(policy_path)]
    marker=out/('confirmation-marker.json' if args.phase=='confirmation' else 'facing-ewram.bin')
    launched=time.monotonic();triggered=None
    with (out.parent/(out.name+'.log')).open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        while process.poll() is None:
            if args.phase!='reserve' and triggered is None and marker.exists():
                triggered=time.monotonic()
                stop.write_text('STOP\n',encoding='utf-8')
            if time.monotonic()-launched>180:
                raise TimeoutError('Owned research runner still active; inspect its PID before cleanup')
            time.sleep(0.05)
    document={'phase':args.phase,'runner':runner,'command':command,'runner_pid':process.pid,
              'exit_code':process.returncode,'triggered':triggered is not None,
              'trigger_marker':str(marker) if triggered is not None else None}
    (out/'control.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(document))
    if process.returncode==0 or (args.phase!='reserve' and triggered is None):
        raise AssertionError('negative control unexpectedly completed or never triggered')


if __name__=='__main__':main()
