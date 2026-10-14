"""Build isolated count fixtures and capture native Item lists sequentially."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import psutil


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True)
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    result={'scope':__doc__,'status':'running','cases':[]}
    try:
        for count in [0,1]:
            fixture=out/f'count{count}-fixture';capture=out/f'count{count}-Item-list'
            commands=[['tools/build_consumable_fixture.py','--potion-count',str(count),'--out',str(fixture)],
                      ['tools/probe_consumable_inventory.py','--state',str(fixture/'consumable-recovery.ss0'),'--out',str(capture)],
                      ['tools/validate_consumable_count_capture.py','--capture',str(capture),'--expected',str(count),
                       '--out',str(out/f'count{count}-checks.json')],
                      ['tools/audit_consumable_capture.py','--capture',str(capture),'--out',str(out/f'count{count}-sources.json')]]
            for index,command in enumerate(commands):
                print('Potion',count,'step',index,command[0],flush=True)
                proc=subprocess.Popen([sys.executable,*command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                try:
                    output,_=proc.communicate(timeout=240)
                except BaseException:
                    # Only descendants of this exact owned Python process.
                    # Preserve evidence; never kill an unrelated occupied port.
                    try:
                        children=psutil.Process(proc.pid).children(recursive=True)
                        for child in reversed(children):
                            try:child.kill()
                            except psutil.NoSuchProcess:pass
                    except psutil.NoSuchProcess:pass
                    if proc.poll() is None:proc.kill()
                    output,_=proc.communicate()
                    (out/f'count{count}-step{index}.log').write_text(output,encoding='utf-8')
                    raise
                (out/f'count{count}-step{index}.log').write_text(output,encoding='utf-8')
                if proc.returncode:raise RuntimeError(f'Potion {count} step{index}: '+output)
            result['cases'].append({'count':count,'fixture':str(fixture),'capture':str(capture),'status':'pass'})
            (out/'matrix.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
        result['status']='pass-live-zero-one-Item-reader-controls'
    except BaseException as exc:result['error']=repr(exc);result['status']='partial-or-failed';raise
    finally:
        files=[p for p in out.rglob('*.json') if p.name!='matrix.json']
        result['evidence_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        (out/'matrix.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['status'])


if __name__=='__main__':main()
