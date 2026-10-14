"""Host controls for read-only native/adapter observation and hook suspension."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE
from probe_control_handoff import ALL_BPS, BP_KEY, Probe
from recovery_menu import MEMBERS, MENU_ROOT, PLAYER_DRIVER, require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True)
    args=ap.parse_args()
    from player_boundary_observer import PlayerBoundaryProbe, PICK_SITE
    memory=bytearray(0x40000);operations=[];armed=set()
    def store(address,data):
        offset=address-0x02000000;memory[offset:offset+len(data)]=data
    store(BATTLE_STRUCT,(8).to_bytes(4,'little'))
    member=MEMBERS+STRIDE;wrapper=0x0201F000;context=0x0201F100;callback=0x0201F200
    unit=bytearray(STRIDE);unit[:4]=(0x08551234).to_bytes(4,'little');unit[0x104]=5
    unit[0x18:0x20]=b'\xf1\x00\xf7\x00\xd3\x00\xde\x00';unit[5:8]=bytes((5,1,5));unit[9]=41
    unit[0xF6:0xF8]=bytes((5,10));store(member,unit);store(ROSTER+5*STRIDE,unit)
    store(wrapper,member.to_bytes(4,'little'));driver=bytearray(0xE0)
    driver[4:8]=driver[8:12]=wrapper.to_bytes(4,'little');driver[0xDC:0xDE]=(0x25).to_bytes(2,'little')
    store(PLAYER_DRIVER,driver)
    root=bytearray(0x30);root[4]=4;root[0x18:0x1C]=member.to_bytes(4,'little')
    root[0x28:0x2C]=callback.to_bytes(4,'little');store(context,root)
    cb=bytearray(0x18);cb[:4]=(0x08028DE1).to_bytes(4,'little');cb[0x14:0x16]=(0x100).to_bytes(2,'little');store(callback,cb)
    store(MENU_ROOT,context.to_bytes(4,'little'))
    regs=[0]*16;regs[0]=wrapper;regs[6]=PLAYER_DRIVER;regs[15]=PICK_SITE
    def read(address,size):
        require(size<=512,'observer exceeded RSP packet limit');operations.append(('read',address,size))
        offset=address-0x02000000;return bytes(memory[offset:offset+size])
    # No register/memory write or input API is available to these readers.
    g=SimpleNamespace(read_mem=read,read_pc=lambda:PICK_SITE,read_registers=lambda:regs)
    p=object.__new__(PlayerBoundaryProbe);p.g=g;p.s=SimpleNamespace(g=g);p.t0=time.time()
    p.verbose=False;p.observer_context=lambda:{'expected_levels':[41,50]}
    p.observer_errors=[];p.observer_hits=0;p._log=[]
    p.read_target_cursor=lambda:(5,10);p.read_cmd_cursor=lambda:0
    p.set_bp=lambda address:(armed.add(address),'OK')[1]
    p.clear_bp=lambda address,strict=False:armed.discard(address)
    with tempfile.TemporaryDirectory(prefix='ffta-player-observer-') as directory:
        p.observer_path=str(Path(directory)/'observations.jsonl')
        p.arm(strict=True);require(armed==set(ALL_BPS)|{PICK_SITE},'observer hook absent')
        p.handle_stop('host-native-pick')
        p.observe_adapter_attempt([],None,'host identity refusal')
        records=[json.loads(s) for s in Path(p.observer_path).read_text().splitlines()]
        require(records[0]['phase']=='native-pick' and records[0]['pick']['member']==member
                and records[0]['pick']['unit']['id']==5,'native pick attribution absent')
        require(records[1]['phase']=='adapter-attempt' and records[1]['adapter']['error']=='host identity refusal',
                'adapter refusal not preserved')
        require(records[0]['context']['expected_levels']==[41,50],'observer context absent')
        p.disarm(strict=True);require(not armed,'native hooks leaked into input/cleanup')
        regs[0]=0
        p.handle_stop('invalid-native-pick')
        require(p.observer_errors,'invalid native pointer accepted as known actor')
        with patch.object(Probe,'handle_stop',return_value='existing-hook'):
            g.read_pc=lambda:0x0809E3AE
            require(p.handle_stop('legacy')=='existing-hook','observer replaced inherited hook')
        def send(packet):
            if packet.startswith('Z0,'):
                armed.add(int(packet.split(',')[1],16));return 'OK'
            require(packet.startswith('P1='),'unexpected hardware write')
            require(armed=={BP_KEY},'native observer remained armed during actual inherited key injection')
            operations.append(('host-key-injection',packet));return 'OK'
        key_regs=[0]*16;key_regs[15]=BP_KEY
        g.send=send;g.cont=lambda:None;g._read_packet=lambda:'S05';g.read_registers=lambda:key_regs
        p.rearm_key_enable=False;p.key_write_log=[]
        p.arm(strict=True)
        require(p.press(1,frames=1,pause=0)==1 and len(p.key_write_log)==1,'inherited input path not exercised')
        require(armed==set(ALL_BPS)|{PICK_SITE},'trace not restored after actual inherited input')
        p.disarm(strict=True);require(not armed,'post-input observer cleanup failed')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-player-boundary-observer-host','checks':['read-only native pick','exact adapter refusal',
        'context metadata','all hooks disarmed','invalid native pointer','existing hook delegation',
        'actual inherited press suspends and restores native hook'],
        'source_sha256':{p:sha(p) for p in ['tools/validate_player_boundary_observer.py','tools/player_boundary_observer.py']},
        'limitations':['Host observation/hook controls only; native ownership and timing require live evidence.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS read-only player observer and hook lifecycle:7 controls')


if __name__=='__main__':main()
