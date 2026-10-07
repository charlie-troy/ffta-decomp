"""Live unsupported-family controls followed by the accepted self-Cure matrix."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from recovery_menu import require
from validate_autobattle_runtime import validate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--prefix',required=True)
    ap.add_argument('--skip-self',action='store_true')
    args=ap.parse_args();require(Path(args.prefix).name==args.prefix and not any(c in args.prefix for c in ':\\/'),'prefix must be a filename')
    root=Path('outputs/autobattle');summary=root/(args.prefix+'-regressions.json');require(not summary.exists(),'new summary required')
    result={'status':'partial','scope':__doc__,'unsupported':[]}
    def child(command,log,code):
        with log.open('x',encoding='utf-8') as output:
            p=subprocess.run([sys.executable,*command],stdout=output,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        require(p.returncode==code,f'child failed ({p.returncode}); inspect {log}')
    try:
        for label,state,scenario in [
            ('self-family','outputs/autobattle/a61-public-fixture-mp85-02/recovery.ss0',None),
            ('no-secondary','outputs/lua-nav/a4-multi-ally-battle-start.ss0','configs/battle-scenarios/a4-two-player.json')]:
            name=args.prefix+'-'+label;directory=root/name;require(not directory.exists(),'new run required')
            command=['tools/run_autobattle.py','--state',state,'--bounded-ally-cure','--tactics-policy','configs/tactics/healer.json',
                     '--run-id',name,'--wall-timeout','120','--on-stop','kill','--yes']
            if scenario:command.extend(['--scenario',scenario])
            child(command,root/(name+'.log'),1)
            require(not validate(str(directory)),'unsupported receipt invalid')
            run=json.loads((directory/'run.json').read_text())
            events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
            ledger=[json.loads(l) for l in (directory/'input-log.jsonl').read_text().splitlines()]
            require(run['turns']==0 and run['inputs_unchanged'] and not any(e.get('event')=='key_write' for e in ledger),
                    'unsupported family received input')
            result['unsupported'].append({'run':name,'status':'pass','raw_writes':0,'turns':0,
                'reason':run.get('terminal_reason'),'metadata_sha256':{f:hashlib.sha256((directory/f).read_bytes()).hexdigest()
                for f in ('run.json','events.jsonl','input-log.jsonl')}})
            print(f'PASS unsupported {label}: zero input',flush=True)
        if not args.skip_self:
            prefix=args.prefix+'-self'
            child(['tools/run_recovery_cli_matrix.py','--prefix',prefix,
                   '--cure-state','outputs/autobattle/a61-public-fixture-mp85-02/recovery.ss0',
                   '--reserve-state','outputs/autobattle/a61-public-fixture-mp6-01/recovery.ss0',
                   '--disabled-state','outputs/autobattle/a61-public-fixture-mp5-01/recovery.ss0'],root/(prefix+'.log'),0)
            result['self_matrix']=str(root/(prefix+'-matrix.json'))
        result['status']='pass-bounded-regressions'
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:summary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
