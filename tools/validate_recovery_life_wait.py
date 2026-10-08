"""Replay a native Wait facing capture; host STOP and single-attempt controls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_menu import FACING, PLAYER_DRIVER, require
from recovery_menu_list import ResearchMenuList
from recovery_life_wait import LifeWaitBoundary
from tactics_policy import load_policy_file
from validate_recovery_life_menu import Memory
from validate_recovery_life_final import Transport


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True);ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--out',required=True);args=ap.parse_args()
    directory=Path(args.capture);doc=json.loads((directory/'Life-overlay.json').read_text())
    path=directory/'Wait-facing-ewram.bin';data=path.read_bytes();rom=Path(args.rom).read_bytes()
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    require(sha(path)==doc['capture_sha256'][path.name],'Wait facing capture hash differs')
    policy=load_policy_file('configs/tactics/healer.json')
    c=next(p['canonical'] for p in doc['party'] if p['id']==5)
    def fixture(clock=lambda:1):
        g=Memory(data);m=ResearchMenuList(g,rom,doc['owner'],c)
        units={p['canonical']:g.read_mem(p['canonical'],STRIDE) for p in doc['party']}
        r=LifeWaitBoundary(g,m,units,clock=clock);return g,m,r,r.snapshot()
    g,m,r,t=fixture();r.revalidate(t);valid=Transport();r.commit(t,valid,policy,lambda:False)
    require(len(valid.calls)==1 and r.final_attempted,'valid Wait did not request exactly once')
    valid_events=deepcopy(r.events)
    rejected=[]
    changes=[('mode',m.context+4,b'\x07'),('selection',m.context,b'\x00\x00'),
        ('member',m.context+0x18,b'\x00'*4),('callback',m.callback,b'\x00'*4),
        ('state',m.callback+0x14,b'\x02\x01'),('driver',PLAYER_DRIVER+0xDC,b'\x25\x00'),
        ('control',PLAYER_DRIVER+0xD0,b'\x00'*4),('processor',PLAYER_DRIVER+0x60,b'\x01\x00\x00\x02'),
        ('wrapper',PLAYER_DRIVER+4,b'\x00'*4),('facing-owner',FACING,b'\x00'*4),
        ('facing-active',FACING+0x10,b'\x00'),('direction',FACING+4,b'\xff'),
        ('active-callback',m.manager+4,m.callback.to_bytes(4,'little'))]
    changes.extend((role+'-'+hex(o),p['canonical']+o,b'\xff')
        for role,p in [('caster',next(p for p in doc['party'] if p['id']==5)),
                       ('target',next(p for p in doc['party'] if p['id']==7))]
        for o in (0,9,0x18,0x1A,0x1C,0x28,0xF2,0xF6,0x104))
    for label,address,value in changes:
        g,m,r,t=fixture();g.write(address,value);transport=Transport()
        try:r.commit(t,transport,policy,lambda:False)
        except ValueError:require(not transport.calls,'mutant sent Wait');rejected.append(label)
        else:raise AssertionError('accepted Wait mutation: '+label)
    for point in range(1,5):
        g,m,r,t=fixture();transport=Transport();count=[0]
        def stopped():
            count[0]+=1;require(count[0]!=point,'injected STOP');return False
        try:r.commit(t,transport,policy,stopped)
        except ValueError:require(not transport.calls,'STOP sent Wait');rejected.append('STOP-'+str(point))
        else:raise AssertionError('STOP accepted')
    for label,transport in [('delivered',Transport()),('partial',Transport(reply=2)),('disconnect',Transport(error=True))]:
        g,m,r,t=fixture()
        try:r.commit(t,transport,policy,lambda:False)
        except (ValueError,ConnectionError):pass
        require(r.final_attempted and len(transport.calls)==1,'missing Wait attempt latch')
        try:r.commit(t,transport,policy,lambda:False)
        except ValueError:require(len(transport.calls)==1,'duplicate Wait');rejected.append('duplicate-'+label)
        else:raise AssertionError('Wait retried')
    g,m,r,t=fixture();r.clock=lambda:4
    try:r.revalidate(t)
    except ValueError:rejected.append('expired')
    else:raise AssertionError('expired Wait accepted')
    output={'status':'pass-retained-Life-Wait-facing','scope':__doc__,'controls':rejected,
            'valid_events':valid_events,'source_sha256':{p:sha(p) for p in
            ('tools/recovery_life_wait.py','tools/validate_recovery_life_wait.py')},
            'evidence_sha256':{str(path):sha(path),str(directory/'Life-overlay.json'):sha(directory/'Life-overlay.json')},
            'limitations':['Retained reader/host transport proof only; no live STOP or continuation claim.',
                           'Capture source unchanged flag: '+str(doc['inputs_unchanged'])]}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life Wait:',len(rejected),'controls')


if __name__=='__main__':main()
