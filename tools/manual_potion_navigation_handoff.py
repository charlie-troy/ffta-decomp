"""Actual owned-window menu toggle before Item scratch; preserve native adoption guard."""
import argparse,json,hashlib,subprocess,time
from pathlib import Path
from fixture_guard import port_listener_pid,read_roster,STRIDE
from recovery_menu import MENU_ROOT,PLAYER_DRIVER,exact,integer,require
from recovery_menu_list import ResearchMenuList
from consumable_inventory import ConsumableInventory
from manual_input_probe import capture
from trace_mgba import Gdb
from probe_recovery_ko_lifecycle import source_dependencies


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);args=ap.parse_args();root=Path(args.run)
    out=root/'manual-Potion-navigation.json';require(not out.exists(),'manual evidence must be new')
    run=json.loads((root/'run.json').read_text());pid=run['manual_handoff']['pid'];port=run['manual_handoff']['port']
    require(run['bounded_self_potion'] and run['final_state']=='paused' and run['emulator_handoff']=='left-running-for-player'
        and port_listener_pid(port)==pid,'owned public navigation pause missing')
    events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()];j=next(e['recovery'] for e in reversed(events) if e.get('recovery'))
    require('Potion_use_events' not in j,'navigation handoff already attempted final use')
    rom=Path('baserom.gba').read_bytes();g=Gdb('127.0.0.1',port,timeout=2)
    record={'schema':'ffta-Potion-manual-navigation/1','status':'unknown','pid':pid,'stub_gameplay_writes':0,
        'input_channel':'verified owned window; GDB reads/control only','keys':[],'states':[]}
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record['source_sha256']={p:sha(p) for p in source_dependencies('manual_potion_navigation_handoff')+['tools/send_owned_mgba_key.ps1']}
    base=max(e['t'] for e in events)+1;start=time.time()
    try:
        g.interrupt();unit=exact(g,0x02000188,STRIDE);pool=ConsumableInventory(g).snapshot()
        menu=ResearchMenuList(g,rom,j['owner'],0x02000188)
        def observe():
            roster=read_roster(g,rom=rom)
            require(roster['struct_count']==roster['live_count']==8 and roster['ids_distinct'] and roster['live_contiguous'],
                'manual navigation native eight-unit roster unavailable')
            require(exact(g,0x02000188,STRIDE)==unit and ConsumableInventory(g).snapshot()==pool,'manual toggle changed resources')
            root_raw=exact(g,menu.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0);mode=root_raw[4]
            require(integer(exact(g,MENU_ROOT,4),0)==menu.context and integer(root_raw,0x18)==menu.member
                and integer(driver,4)==integer(driver,8)==menu.wrapper,'manual navigation owner changed')
            if mode==0:
                require(integer(driver,0xDC,2)==0x54 and exact(g,0x0200FFC9,2)==bytes([5,10]),'manual field not owned actor/cursor')
                token=None
            else:
                token=menu.snapshot();require(token.state in ('command','action-group'),'manual toggle outside native command/group')
            return {'mode':mode,'command':token.receipt() if token else None,'roster':roster}
        def press(key,expected):
            state=observe();record['states'].append(state);require(state['mode']==expected,'manual phase differs')
            capture(pid,str((root/f'manual-Potion-navigation-{len(record["keys"])}.png').resolve()))
            require(port_listener_pid(port)==pid,'manual PID changed');g.cont()
            sent=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','tools/send_owned_mgba_key.ps1',
                '-ProcId',str(pid),'-Key',key],capture_output=True,text=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
            require(sent.returncode==0,'manual window key failed: '+sent.stdout+sent.stderr)
            record['keys'].append({'key':key,'before_mode':expected,'window':json.loads(sent.stdout)})
            with (root/'input-log.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps({'event':'manual_key_write','val':2 if key=='B' else 1,'t':round(base+time.time()-start,3)})+'\n')
            g.interrupt()
        initial=observe();require(initial['mode'] in (4,5),'navigation pause is not owned menu')
        if initial['mode']==5:press('B',5)
        press('B',4);press('A',0)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                final=observe()
                require(final['mode']==4 and final['command']['state']=='command','manual menu did not reopen')
                break
            except ValueError as exc:
                record.setdefault('settle_rejections',[]).append(str(exc));g.cont();time.sleep(.25);g.interrupt()
        else:raise TimeoutError('manual command did not settle after window input')
        record['states'].append(final);record['final_unit']=unit.hex();record['inventory']=pool.raw.hex()
        capture(pid,str((root/'manual-Potion-navigation-restored.png').resolve()))
        record['status']='verified-manual-Potion-navigation'
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        try:g.cont()
        finally:
            g.close();record['inputs_unchanged']=all(sha(p)==h for p,h in record['source_sha256'].items())
            out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS owned navigation menu toggle, native roster8 retained; PID',pid)


if __name__=='__main__':main()
