"""Cancel an unspent Potion through the owned window and leave native command for resume."""
import argparse,json,hashlib,subprocess,time
from pathlib import Path
from fixture_guard import port_listener_pid,STRIDE
from manual_input_probe import capture
from recovery_menu import exact,require
from trace_mgba import Gdb
from potion_manual_cancel import PotionManualCancel
from probe_recovery_ko_lifecycle import source_dependencies


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);args=ap.parse_args();root=Path(args.run)
    output=root/'manual-Potion-cancel.json';require(not output.exists(),'manual evidence must be new')
    run=json.loads((root/'run.json').read_text());require(run['bounded_self_potion'] and run['final_state']=='paused'
        and run['emulator_handoff']=='left-running-for-player','public Potion pause required')
    pid,port=run['manual_handoff']['pid'],run['manual_handoff']['port'];require(port_listener_pid(port)==pid,'manual PID differs')
    events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()];j=next(e['recovery'] for e in reversed(events) if e.get('recovery'))
    require(j.get('Potion_final_token') and not j.get('Potion_use_events'),'manual cancel requires unspent final prompt')
    expected=bytes.fromhex(j['Potion_final_prompt_raw']['canonical']);rom=Path('baserom.gba').read_bytes();g=Gdb('127.0.0.1',port,timeout=6)
    record={'schema':'ffta-Potion-manual-cancel/1','status':'unknown','pid':pid,'stub_gameplay_writes':0,
        'input_channel':'verified owned window; GDB reads/control only','keys':[],'states':[]}
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record['source_sha256']={p:sha(p) for p in source_dependencies('manual_potion_cancel_handoff')+['tools/send_owned_mgba_key.ps1']}
    base=max(e['t'] for e in events)+1;start=time.time()
    try:
        reply=g.interrupt();require(reply and reply[0] in 'ST' and reply[:3]!='S04','manual cancel halt failed')
        reader=PotionManualCancel(g,rom,j['owner'],expected,j['inventory_before']['raw'])
        initial=reader.snapshot();require(initial['mode']==11,'manual cancel is not at final prompt')
        capture(pid,str((root/'manual-Potion-cancel-before.png').resolve()))
        for _ in range(8):
            state=reader.snapshot();record['states'].append(state)
            if state['command']:
                record['status']='verified-manual-Potion-cancel';break
            require(port_listener_pid(port)==pid,'manual cancel PID changed')
            g.cont()
            sent=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','tools/send_owned_mgba_key.ps1',
                '-ProcId',str(pid),'-Key','B'],capture_output=True,text=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
            require(sent.returncode==0,'owned manual B failed: '+sent.stdout+sent.stderr)
            record['keys'].append({'key':'B','before':state,'window':json.loads(sent.stdout)})
            with (root/'input-log.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'event':'manual_key_write','val':2,'t':round(base+time.time()-start,3)})+'\n')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                g.interrupt()
                try:reader.snapshot();break
                except ValueError as exc:record.setdefault('rejections',[]).append(str(exc));g.cont();time.sleep(.25)
            else:raise TimeoutError('manual B did not return to owned accepting menu')
        else:raise TimeoutError('manual cancel budget exceeded')
        require(record['status']=='verified-manual-Potion-cancel','native command not restored')
        record['final_unit']=exact(g,0x02000188,STRIDE).hex()
        capture(pid,str((root/'manual-Potion-cancel-after.png').resolve()))
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        try:g.cont()
        finally:
            g.close();record['inputs_unchanged']=all(sha(p)==h for p,h in record['source_sha256'].items())
            output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS manual Potion cancellation to unspent command:',len(record['keys']),'owned window B inputs; PID',pid)


if __name__=='__main__':main()
