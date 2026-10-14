"""Host regression for an identified Wait ending directly at another ally's menu."""
import argparse
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from autobattle_runtime import BattleRuntime, TAKEOVER
from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE, read_roster
from recovery_menu import MEMBERS, MENU_ROOT, PLAYER_DRIVER, require
from probe_control_handoff import TARGET_X, TARGET_Y, CMD_CURSOR


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True)
    ap.add_argument('--runtime-ref');args=ap.parse_args()
    from wait_ally_continuation import capture_wait_origin, inspect_next_ally, validate_next_ally_progress
    cls=BattleRuntime
    if args.runtime_ref:
        namespace={'__name__':'historical_wait_runtime'}
        code=subprocess.check_output(['git','show',args.runtime_ref+':tools/autobattle_runtime.py'])
        exec(compile(code,'historical_wait_runtime','exec'),namespace);cls=namespace['BattleRuntime']
    root=Path('outputs/autobattle/a652-resume-observer-01')
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    native=next(e['boundary_diagnostic'] for e in events if e.get('boundary_diagnostic'))
    template=bytearray(Path('outputs/autobattle/a65-public-Life-04/Life-transaction-1/after-Life-ewram.bin').read_bytes())
    rom=Path('baserom.gba').read_bytes();results=[]
    for stop in (False,True):
        with tempfile.TemporaryDirectory(prefix='ffta-Wait-ally-') as directory, ExitStack() as cleanup:
            memory=bytearray(template);clock=[1000.0];out=Path(directory)
            def store(address,data):
                offset=address-0x02000000;memory[offset:offset+len(data)]=data
            for row in native['mirror_snapshots']:store(row['address'],bytes.fromhex(row['raw']))
            for row in native['party']['canonical']:store(row['address'],bytes.fromhex(row['raw']))
            store(BATTLE_STRUCT,(8).to_bytes(4,'little'))
            context,callback,manager,data=0x02030000,0x02030100,0x02030200,0x02030300
            wrappers={5:0x02030400,7:0x02030404}
            for identifier,member in ((5,MEMBERS+STRIDE),(7,MEMBERS)):
                store(wrappers[identifier],member.to_bytes(4,'little'))
            def menu(identifier):
                member=MEMBERS+STRIDE if identifier==5 else MEMBERS
                driver=bytearray(0xE0);driver[4:8]=driver[8:12]=wrappers[identifier].to_bytes(4,'little')
                driver[0xDC:0xDE]=(0x25).to_bytes(2,'little');store(PLAYER_DRIVER,driver)
                block=bytearray(0x30);block[4]=4;block[0x18:0x1C]=member.to_bytes(4,'little')
                block[0x20:0x24]=manager.to_bytes(4,'little');block[0x28:0x2C]=callback.to_bytes(4,'little')
                store(context,block);store(MENU_ROOT,context.to_bytes(4,'little'))
                cb=bytearray(0x18);cb[:4]=(0x08028DE1).to_bytes(4,'little');cb[0x14:0x16]=(0x102).to_bytes(2,'little')
                store(callback,cb);store(manager+4,callback.to_bytes(4,'little'))
                obj=bytearray(0x9C);obj[0x50:0x52]=(4).to_bytes(2,'little')
                obj[0x94:0x98]=data.to_bytes(4,'little');obj[0x98:0x9C]=(data+16).to_bytes(4,'little')
                store(callback+0x18,obj);store(data,b''.join(i.to_bytes(4,'little') for i in range(4)))
                store(data+16,b'\x01'*4)
                store(TARGET_X,bytes((5 if identifier==5 else 4,)));store(TARGET_Y,b'\x0a');store(CMD_CURSOR,b'\x00')
            def packet():clock[0]+=3;raise socket.timeout('host no new sequencer seed')
            def read(address,size):
                require(size<=512,'host reply too large');offset=address-0x02000000
                return bytes(memory[offset:offset+size])
            g=SimpleNamespace(read_mem=read,cont=lambda:None,_read_packet=packet,interrupt=lambda:'S02',
                read_pc=lambda:0x08000494,send=lambda *a,**k:'OK')
            menu(5);roster=read_roster(g,rom=rom)
            session=SimpleNamespace(g=g,receipt={'ok':True,'roster':roster},writes=[],
                read_rom_bytes=lambda:rom,screenshot=lambda path:Path(path).write_bytes(b'host frame'))
            with patch('time.time',side_effect=lambda:clock[0]):
                runtime=cls(session,{'scenario_id':'host-Wait-next-ally','actor_actions':[]},'host',str(out),
                    verbose=False,wall_timeout=60)
                cleanup.callback(runtime._input_log.close)
                require(runtime.live_guard(),'host live identity guard failed')
                runtime.owner=next(r for r in runtime.adapter.snapshot() if r['id']==5)
                runtime._pre_players=runtime.adapter.snapshot();runtime.state=TAKEOVER
                origin=capture_wait_origin(session,runtime.owner,runtime._pre_players,clock=lambda:clock[0]-runtime.t0)
                require(origin is not None,'supported living-party origin missing')
                runtime._wait_origin=origin
                menu(7)
                proof=inspect_next_ally(session,runtime.owner,origin,clock=lambda:clock[0]-runtime.t0)
                post=runtime.adapter.snapshot();validate_next_ally_progress(proof,runtime.owner,post)
                raw_controls=[]
                for label,edit in [
                    ('missing origin command',lambda p:p['origin'].pop('command')),
                    ('foreign origin wrapper',lambda p:p['origin']['facing'].__setitem__('actor_wrapper',0)),
                    ('missing origin raw reads',lambda p:p['origin'].pop('reads')),
                    ('wrong next actor',lambda p:p['next']['actor'].__setitem__('id',5)),
                    ('empty post-action raw',lambda p:p.__setitem__('reads',{}))]:
                    changed=deepcopy(proof);edit(changed)
                    try:validate_next_ally_progress(changed,runtime.owner,post)
                    except (ValueError,KeyError,TypeError):raw_controls.append(label)
                    else:raise AssertionError('invalid continuation receipt accepted: '+label)
                controls=[]
                for label,edit in [
                    ('same actor wrapper',lambda m:store(PLAYER_DRIVER+4,wrappers[5].to_bytes(4,'little'))),
                    ('foreign member',lambda m:store(wrappers[7],(0x02031000).to_bytes(4,'little'))),
                    ('wrong cursor',lambda m:store(TARGET_X,b'\x06')),
                    ('opening command',lambda m:store(callback+0x14,(0x100).to_bytes(2,'little'))),
                    ('unrestored mirror',lambda m:store(BATTLE_STRUCT,(0x0202243C).to_bytes(4,'little'))),
                    ('sleeping next actor',lambda m:store(MEMBERS+0xEB,b'\x04'))]:
                    saved=bytes(memory);edit(memory)
                    try:inspect_next_ally(session,runtime.owner,origin,clock=lambda:clock[0]-runtime.t0)
                    except ValueError:controls.append(label)
                    else:raise AssertionError('unowned continuation accepted: '+label)
                    memory[:]=saved
                if stop:(out/'STOP').write_text('host STOP')
                runtime._record_identified_turn(plan_kind='identified-wait',plan={'command_id':0,'from':[5,10]},
                    dest_used=None,drove=True,before={'x':5,'y':10})
                emitted=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
                if stop:require(runtime.turn==0 and runtime.state=='paused','STOP lost to next-ally completion')
                else:
                    require(runtime.turn==1,'valid next ally command menu rejected solely for zero new seeds')
                    turn=next(e for e in emitted if e['kind']=='turn')
                    require(turn['engine_result']['progress']['kind']=='next-ally-command-menu'
                            and turn['next_actor']['id']==7,'next ally attribution absent')
                    require(not runtime.p.seeds,'host accidentally supplied a sequencer seed')
                runtime._input_log.close();results.append({'stop':stop,'turns':runtime.turn,'controls':controls,
                    'raw_controls':raw_controls})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-Wait-next-ally-regression','scope':__doc__,'results':results,
        'source_sha256':{p:sha(p) for p in ['tools/validate_wait_ally_continuation.py',
            'tools/wait_ally_continuation.py','tools/autobattle_runtime.py']},
        'limitations':['Actual readers/runtime with fake RAM/transport; not fresh gameplay or action acceptance.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS zero-seed next-ally Wait, STOP precedence and6 native-shape controls')


if __name__=='__main__':main()
