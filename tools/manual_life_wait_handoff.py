"""Finish an owned post-Life Wait through the window; monitor via read-only GDB."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from fixture_guard import port_listener_pid, STRIDE
from manual_input_probe import capture
from recovery_life_effect import verify_life_effect
from recovery_life_wait import LifeWaitBoundary
from recovery_menu import exact, require
from recovery_menu_list import ResearchMenuList
from recovery_party_continuation import observe_party_continuation
from trace_mgba import Gdb


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--rom',default='baserom.gba');args=ap.parse_args();root=Path(args.run)
    output=root/'manual-Life-Wait.json';require(not output.exists(),'manual evidence must be new')
    run=json.loads((root/'run.json').read_text())
    require(run['bounded_ally_life'] and run['final_state']=='paused'
            and run['emulator_handoff']=='left-running-for-player','public Life pause required')
    pid,port=run['manual_handoff']['pid'],run['manual_handoff']['port']
    require(port_listener_pid(port)==pid,'manual listener PID differs')
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    journal=next(e['recovery'] for e in reversed(events) if e.get('recovery'))
    require(journal['schema']=='ffta-life-recovery-turn/1' and journal['final_confirmation']
            and journal['Wait_facing'] and not journal.get('Wait_final_attempted',False),
            'manual Life handoff requires unconfirmed post-Life Wait')
    before={int(a):bytes.fromhex(u) for a,u in journal['effect_units_before'].items()}
    units={int(a):bytes.fromhex(u) for a,u in journal['effect_units_after'].items()}
    roles={p['id']:p for p in journal['party']}
    require(verify_life_effect(before,units,journal['life_engine_hits'],roles[5],roles[7])
            ==journal['effect_attribution'],'manual Life effect attribution differs')
    rom=Path(args.rom).read_bytes();owner=journal['owner'];g=Gdb('127.0.0.1',port,timeout=6)
    record={'schema':'ffta-Life-manual-Wait/1','status':'unknown','pid':pid,
            'input_channel':'verified owned window; GDB reads/control only','stub_gameplay_writes':0,
            'keys':[],'continuations':[]}
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    from probe_recovery_ko_lifecycle import source_dependencies
    record['source_sha256']={p:sha(p) for p in
        source_dependencies('manual_life_wait_handoff') + ['tools/send_owned_mgba_key.ps1']}
    base=max(e.get('t',0) for e in events)+1;started=time.time()
    try:
        reply=g.interrupt();require(reply and reply[:1] in ('S','T') and reply[:3]!='S04','manual halt failed')
        require(all(exact(g,a,STRIDE)==u for a,u in units.items()),'manual post-Life party changed')
        menu=ResearchMenuList(g,rom,owner,roles[5]['canonical']);boundary=LifeWaitBoundary(g,menu,units)
        token=boundary.snapshot();boundary.revalidate(token);record['facing']=token.receipt()
        capture(pid,str((root/'manual-Life-Wait-before.png').resolve()))
        require(port_listener_pid(port)==pid,'manual PID changed before input')
        boundary.revalidate(boundary.snapshot());g.cont()
        sent=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',
            'tools/send_owned_mgba_key.ps1','-ProcId',str(pid),'-Key','A'],capture_output=True,text=True,
            timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
        require(sent.returncode==0,'owned manual A failed: '+sent.stdout+sent.stderr)
        record['keys'].append({'key':'A','before':token.receipt(),'window':json.loads(sent.stdout)})
        with (root/'input-log.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'event':'manual_key_write','val':1,'t':round(base+time.time()-started,3)})+'\n')
        g.interrupt()
        pins=[]
        for pin in journal['Life_effect']['after']:
            address=pin['name'];name=rom[address-0x08000000:address-0x08000000+32] if address>=0x08000000 else exact(g,address,32)
            pins.append(pin|{'name_sha256':hashlib.sha256(name).hexdigest()})
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            g.cont();time.sleep(0.25);g.interrupt()
            try:later=observe_party_continuation(g,rom,owner,token.receipt(),pins,units,journal['post_Life_roster'])
            except ValueError as exc:record.setdefault('rejections',[]).append(str(exc));continue
            require(later['relation']=='enemy','manual Life next actor is not an enemy')
            record['continuations'].append(later);break
        require(len(record['continuations'])==1,'manual Life Wait next actor missing')
        expected=[{'id':p['id'],'canonical':p['canonical'],'hp':int.from_bytes(units[p['canonical']][0x18:0x1A],'little'),
                   'mp':int.from_bytes(units[p['canonical']][0x1C:0x1E],'little'),'tile':p['tile']} for p in pins]
        require(later['party_after']==expected,'manual Life Wait changed party resources')
        capture(pid,str((root/'manual-Life-Wait-after.png').resolve()))
        record['status']='verified-manual-Life-Wait'
    except BaseException as exc:record['error']=repr(exc);raise
    finally:
        try:g.cont()
        finally:
            g.close();record['inputs_unchanged']=all(sha(p)==h for p,h in record['source_sha256'].items())
            output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS owned window Life Wait and next actor; PID',pid,'left alive for public resume')


if __name__=='__main__':main()
