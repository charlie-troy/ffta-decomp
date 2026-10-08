"""Observe real public Life boundaries and drop STOP; CLI owns its process."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--state',required=True)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--phase',choices=('navigation','Life-final','Life-Wait-final'),required=True)
    ap.add_argument('--kill-on-stop',action='store_true');args=ap.parse_args()
    require(Path(args.run_id).name==args.run_id and not any(c in args.run_id for c in ':\\/'),
            'run-id must be a filename')
    root=Path('outputs/autobattle')/args.run_id;log_path=root.with_suffix('.log')
    require(not root.exists() and not log_path.exists(),'STOP run/log must be new')
    command=[sys.executable,'tools/run_autobattle.py','--state',args.state,
        '--scenario','configs/battle-scenarios/a4-two-player.json','--tactics-policy','configs/tactics/healer.json',
        '--bounded-ally-life','--run-id',args.run_id,'--wall-timeout','180','--yes',
        '--on-stop','kill' if args.kill_on_stop else 'leave-running']
    fired=False;trigger=None;deadline=time.monotonic()+210
    with log_path.open('x',encoding='utf-8') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        while process.poll() is None:
            if args.phase=='navigation':
                ledger=root/'input-log.jsonl'
                if ledger.exists():
                    rows=[]
                    for line in ledger.read_text().splitlines():
                        try:rows.append(json.loads(line))
                        except json.JSONDecodeError:pass
                    keys=[r for r in rows if r.get('event')=='key_write']
                    if keys:trigger={'raw_writes_seen':len(keys),'last_input':keys[-1]}
            elif (root/f'recovery-{args.phase}.png').exists():
                trigger={'screenshot':f'recovery-{args.phase}.png'}
            if trigger:
                (root/'STOP').write_text('STOP at public '+args.phase+'\n',encoding='utf-8')
                fired=True;break
            if time.monotonic()>deadline:
                (root/'STOP').write_text('STOP watcher timeout\n',encoding='utf-8');break
            time.sleep(0.01)
        code=process.wait(timeout=90)
    receipt=json.loads((root/'run.json').read_text())
    require(fired and code==0 and receipt['final_state']=='paused' and receipt['bounded_ally_life']
            and receipt['inputs_unchanged'],'public Life STOP did not establish a source-stable pause')
    require(receipt['emulator_handoff']==('terminated' if args.kill_on_stop else 'left-running-for-player'),
            'public Life STOP cleanup differs')
    (root/'paused-run.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    (root/'STOP-trigger.json').write_text(json.dumps({'phase':args.phase,'trigger':trigger,
        'pid':receipt['emulator_pid'],'cli_exit':code,'source_stable':True},indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS public Life STOP',args.phase,'owned PID',receipt['emulator_pid'])


if __name__=='__main__':main()
