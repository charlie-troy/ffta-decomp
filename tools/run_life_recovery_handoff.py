"""Run public Life Wait STOP, owned manual Wait and same-PID public resume."""
import argparse
from pathlib import Path
import subprocess
import sys

from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-id',required=True)
    ap.add_argument('--state',default='outputs/autobattle/a64-life-fixture-02/life-recovery.ss0')
    ap.add_argument('--resume-paused',action='store_true')
    ap.add_argument('--wall-timeout',type=int,default=300);args=ap.parse_args()
    require(Path(args.run_id).name==args.run_id and not any(c in args.run_id for c in ':\\/'),
            'run-id must be a filename')
    root=Path('outputs/autobattle')/args.run_id
    def child(label,command,code=0):
        path=root.with_name(root.name+'-'+label+'.log');require(not path.exists(),'handoff child log must be new')
        with path.open('x',encoding='utf-8') as output:
            process=subprocess.run([sys.executable,*command],stdout=output,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        require(process.returncode==code,f'Life handoff {label} failed; inspect {path}')
    if not args.resume_paused:
        child('watch',['tools/run_life_cli_stop.py','--state',args.state,'--run-id',args.run_id,
                       '--phase','Life-Wait-final'])
    child('manual',['tools/manual_life_wait_handoff.py','--run',str(root)])
    child('resume',['tools/run_autobattle.py','--resume',args.run_id,
        '--scenario','configs/battle-scenarios/a4-two-player.json','--max-turns','1',
        '--wall-timeout',str(args.wall_timeout),'--on-stop','kill','--yes'],1)
    child('handoff-checks',['tools/validate_life_recovery_handoff.py','--run',str(root),
                          '--out',str(root/'handoff-checks.json')])
    print('PASS public Life manual/same-PID resume:',root)


if __name__=='__main__':main()
