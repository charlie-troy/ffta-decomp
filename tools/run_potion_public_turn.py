"""One current-source public Potion turn after an optional owned regression matrix."""
import argparse,json,time,hashlib
from pathlib import Path
from run_consumable_refusal_matrix import run
from recovery_menu import require
from fixture_guard import port_listener_pid


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--after-matrix');ap.add_argument('--run-id',required=True)
    ap.add_argument('--state',default='outputs/autobattle/a662-use-fixture-01/consumable-recovery.ss0');args=ap.parse_args()
    require(Path(args.run_id).name==args.run_id,'run-id must be a filename');root=Path('outputs/autobattle')/args.run_id
    require(not root.exists(),'public evidence must be new')
    if args.after_matrix:
        matrix=Path(args.after_matrix);deadline=time.monotonic()+1800
        while time.monotonic()<deadline:
            try:d=json.loads(matrix.read_text())
            except (FileNotFoundError,json.JSONDecodeError):d={}
            if d.get('status')=='pass-final-source-Life-regressions':break
            if d.get('error'):raise RuntimeError('preceding regression matrix failed: '+d['error'])
            time.sleep(1)
        else:raise TimeoutError('preceding owned matrix did not complete')
        for p,h in d['common_source_sha256'].items():require(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,'matrix core source changed')
    require(port_listener_pid(2345) is None,'another owned native leg still holds port')
    run(['tools/run_autobattle.py','--state',args.state,'--scenario','configs/battle-scenarios/a4-two-player.json',
        '--bounded-self-potion','--tactics-policy','configs/tactics/potion-self.json','--max-turns','1','--wall-timeout','180',
        '--on-stop','kill','--yes','--run-id',args.run_id],root.with_suffix('.log'),expected=1)
    run(['tools/audit_potion_public_run.py','--run',str(root),'--out',str(root/'checks.json')],root.with_name(root.name+'-audit.log'))
    print('PASS current-source public Potion turn and receipt audit:',root,flush=True)


if __name__=='__main__':main()
