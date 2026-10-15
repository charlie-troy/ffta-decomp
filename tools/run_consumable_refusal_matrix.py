"""Sequential actual-emulator STOP, last-item and zero-quantity research cases."""
import argparse,json,subprocess,sys,hashlib
from pathlib import Path
import psutil


def run(command,path,expected=0):
    p=subprocess.Popen([sys.executable,*command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:output,_=p.communicate(timeout=240)
    except BaseException:
        try:
            for child in reversed(psutil.Process(p.pid).children(recursive=True)):
                try:child.kill()
                except psutil.NoSuchProcess:pass
        except psutil.NoSuchProcess:pass
        if p.poll() is None:p.kill()
        output,_=p.communicate();path.write_text(output,encoding='utf-8');raise
    path.write_text(output,encoding='utf-8')
    if expected==0 and p.returncode!=0 or expected!=0 and p.returncode==0:raise RuntimeError('unexpected exit: '+output)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--state',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.out);root.mkdir(parents=True,exist_ok=False);result={'status':'running','scope':__doc__,'cases':[]}
    flags=['--inspect-potion-target','--accept-potion-target','--inspect-potion-final-prompt','--execute-potion-once','--complete-potion-turn']
    try:
        for case in ['STOP-final-use','STOP-post-effect','STOP-Wait-final','last-item','zero']:
            print('Begin',case,flush=True);state=args.state
            if case in ('last-item','zero'):
                fixture=root/(case+'-fixture')
                run(['tools/build_consumable_fixture.py','--clear-reaction','--experience','0','--potion-count','1' if case=='last-item' else '0','--out',str(fixture)],root/(case+'-build.log'))
                state=str(fixture/'consumable-recovery.ss0')
            capture=root/case;cmd=['tools/probe_consumable_inventory.py','--state',state,*flags,'--out',str(capture)]
            if case.startswith('STOP-'):cmd+=['--inject-stop-at',case[5:]]
            run(cmd,root/(case+'-capture.log'),expected=1)
            check=root/(case+'-checks.json')
            run(['tools/validate_consumable_refusal.py','--capture',str(capture),'--case',case,'--out',str(check)],root/(case+'-checks.log'))
            result['cases'].append({'case':case,'capture':str(capture),'checks':str(check),'status':'pass'})
            (root/'matrix.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',case,flush=True)
        result['status']='pass-live-Potion-research-refusals'
    except BaseException as exc:result.update(status='partial-or-failed',error=repr(exc));raise
    finally:
        files=[p for p in root.rglob('*.json') if p.name!='matrix.json']
        result['evidence_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        (root/'matrix.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
