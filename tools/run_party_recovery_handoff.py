"""Run public ally STOP, owned-window manual Wait and same-PID Move/Wait resume.

Each child owns its emulator lifecycle. On failure, preserve the receipt and
owned PID for inspection instead of terminating unrelated processes.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from recovery_menu import require


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--phase',choices=('confirmation','facing'),required=True)
    parser.add_argument('--resume-paused',action='store_true',help='continue an already completed STOP watcher')
    args=parser.parse_args()
    require(Path(args.run_id).name==args.run_id and not any(c in args.run_id for c in ':\\/'),'run-id must be a filename')
    root=Path('outputs/autobattle')/args.run_id
    def child(label,command,expected=0):
        with root.with_name(root.name+'-'+label+'.log').open('x',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,*command],stdout=log,stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        require(result.returncode==expected,f'{label} failed; inspect owned run {root}')
    if not args.resume_paused:
        child('watcher',['tools/run_recovery_cli_stop.py','--state',args.state,'--run-id',args.run_id,'--phase',args.phase,'--ally'])
    paused=json.loads((root/'paused-run.json').read_text())
    require(paused['bounded_ally_cure'] and paused['final_state']=='paused','party paused handoff required')
    child('manual',['tools/manual_party_recovery_handoff.py','--run',str(root)])
    child('resume',['tools/run_autobattle.py','--resume',args.run_id,
                    '--scenario','configs/battle-scenarios/a4-two-player.json',
                    '--max-turns','1','--wall-timeout','150','--on-stop','kill','--yes'],expected=1)
    child('checks',['tools/validate_party_recovery_handoff.py','--run',str(root),'--phase',args.phase,
                    '--out',str(root/'handoff-checks.json')])
    print(f'PASS public party {args.phase}: {root}')


if __name__=='__main__':main()
