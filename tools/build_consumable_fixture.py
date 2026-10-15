"""Construct and independently reload a disposable wounded Item-owner fixture.

Only copied-session RAM is edited; no source ROM/save/state is overwritten.
Fixture HP/count changes are construction, never an item action or HP effect.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_recovery_fixture import verified_owner
from consumable_inventory import ConsumableInventory, INVENTORY
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import export_owned_state, source_dependencies
from recovery_menu import MEMBERS, MEMBER_COUNT, exact, integer, require
from recovery_menu_list import ResearchMenuList
from recovery_transport import RecoveryTransport
from emulate import Gba


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',default='outputs/autobattle/a64-life-fixture-01/life-recovery.ss0')
    ap.add_argument('--scenario',default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--hp',type=int,default=100)
    ap.add_argument('--potion-count',type=int,default=2)
    ap.add_argument('--clear-reaction',action='store_true',help='Explicitly construct a reaction-free actor; no original asset changes')
    ap.add_argument('--experience',type=int,help='Explicitly set copied actor EXP to avoid unrelated level-up prompts')
    ap.add_argument('--out',required=True)
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    files=[args.state,args.scenario,args.rom]+source_dependencies('build_consumable_fixture')
    result={'scope':__doc__,'status':'unknown','source_sha256':{p:sha(p) for p in files}}
    expect=json.loads(Path(args.scenario).read_text())['guard_expectations'];expect['slot0_name']=int(expect['slot0_name'],0)
    state=out/'consumable-recovery.ss0'
    require(0<=args.potion_count<=99,'Potion fixture count bounds')
    require(args.experience is None or 0<=args.experience<=99,'fixture EXP bounds')
    try:
        with FixtureSession(args.state,rom=args.rom,expect=expect,quiet=True,work_dir=str(out/'build-session')) as session:
            probe=Probe(session,verbose=False);owner=verified_owner(session,probe)
            require(owner['id']==5 and 0<args.hp<owner['max_hp'],'bounded wounded Item owner differs')
            with RecoveryTransport(probe) as transport:
                matches=[MEMBERS+i*STRIDE for i in range(MEMBER_COUNT)
                    if integer(exact(transport.g,MEMBERS+i*STRIDE,STRIDE),0)==owner['name']
                    and exact(transport.g,MEMBERS+i*STRIDE+0x104,1)[0]==owner['id']]
                require(len(matches)==1,'canonical fixture actor missing/ambiguous');member=matches[0]
                require(exact(transport.g,member+0x36,1)[0]==1,'fixture actor lacks Item action set')
                menu=ResearchMenuList(transport.g,session.read_rom_bytes(),owner,member)
                require(menu.snapshot().state=='command','fixture must start at fresh command')
                inventory=ConsumableInventory(transport.g).snapshot();record=inventory.items()[362]['record']
                require(record is not None,'fixture Potion record absent')
                for address in [member,ROSTER+owner['slot']*STRIDE]:
                    session.write_bytes(address+0x18,args.hp.to_bytes(2,'little'),'disposable Item fixture: wounded actor')
                    if args.clear_reaction:
                        session.write_u8(address+0x3A,0,'disposable Item fixture: clear reaction slot')
                    if args.experience is not None:
                        session.write_u8(address+0x0A,args.experience,'disposable Item fixture: explicit EXP')
                session.write_bytes(record+2,bytes([args.potion_count,0]),'disposable Item fixture: Potion owned/reserved')
                result.update(owner=owner,canonical=member,fixture_writes=session.writes,
                              gameplay_writes=getattr(probe,'key_write_log',[]))
            result['export']=export_owned_state(session,probe,state)
        with FixtureSession(str(state),rom=args.rom,expect=expect,quiet=True,work_dir=str(out/'reload-session')) as session:
            probe=Probe(session,verbose=False);owner=verified_owner(session,probe)
            with RecoveryTransport(probe) as transport:
                menu=ResearchMenuList(transport.g,session.read_rom_bytes(),owner,member);token=menu.snapshot()
                count=ConsumableInventory(transport.g).snapshot().items()[362]['available']
                require(owner['id']==5 and token.state=='command' and token.hp==args.hp
                        and count==args.potion_count,'fresh Item fixture reload differs')
                require(not session.writes,'reload unexpectedly edited fixture')
                if args.experience is not None:
                    require(all(exact(transport.g,a+0x0A,1)[0]==args.experience for a in
                        [member,ROSTER+owner['slot']*STRIDE]),'fresh fixture EXP reload differs')
                    result['reloaded_experience']=args.experience
                if args.clear_reaction:
                    unit=exact(transport.g,member,STRIDE);native=Gba(args.rom);native.uc.mem_write(member,unit)
                    require(unit[0x3A]==0 and native.call(0x080CD4D4,[member])==0,'native reaction getter differs after reload')
                    result['native_reaction']={'slot_offset':'3A','getter':'080CD4D4','reloaded_effect':0}
                result['reload']={'pid':session.pid,'owner':owner,'command':token.receipt(),'Potion_count':count,
                                  'fixture_writes':session.writes,'gameplay_writes':getattr(probe,'key_write_log',[])}
            session.screenshot(str(out/'wounded-reload.png'));probe.disarm(strict=True)
        result.update(status='verified-constructed-consumable-fixture',fixture=str(state),fixture_sha256=sha(state))
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:
        result['inputs_unchanged']=all(sha(p)==h for p,h in result['source_sha256'].items())
        (out/'fixture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['status'],state)


if __name__=='__main__':main()
