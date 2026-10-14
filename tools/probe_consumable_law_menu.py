"""Inspect battle-menu access from a pinned command; never confirm a choice.

One B or START press, or guarded B then START; no target input or item use. Raw captures
and screenshot identify what the engine actually opens before decoding laws.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from build_recovery_fixture import verified_owner
from consumable_inventory import ConsumableInventory
from fixture_guard import FixtureSession
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import source_dependencies
from probe_recovery_party import block
from recovery_menu import MENU_ROOT, exact, integer, require
from recovery_menu_list import ResearchMenuList
from recovery_transport import RecoveryTransport
from ffta_names import Names, UI_STRINGS


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',default='outputs/autobattle/a66-wounded-Item-fixture-01/consumable-recovery.ss0')
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True)
    ap.add_argument('--cancel-command',action='store_true',help='Inspect one B instead of START; no subsequent key')
    ap.add_argument('--open-after-cancel',action='store_true',help='After verified field cancellation, inspect START once')
    ap.add_argument('--inspect-law-cards',action='store_true',help='Open observed System row3 Law Cards, then stop')
    ap.add_argument('--scenario',default='configs/battle-scenarios/a4-two-player.json')
    args=ap.parse_args()
    require(not args.open_after_cancel or args.cancel_command,'field START requires explicit command cancel')
    require(not args.inspect_law_cards or args.open_after_cancel,'Law Cards inspection requires field System menu')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    files=[args.state,args.rom,args.scenario]+source_dependencies('probe_consumable_law_menu')
    result={'scope':__doc__,'status':'unknown','source_sha256':{p:sha(p) for p in files}}
    expect=json.loads(Path(args.scenario).read_text())['guard_expectations'];expect['slot0_name']=int(expect['slot0_name'],0)
    probe=None
    try:
        with FixtureSession(args.state,rom=args.rom,expect=expect,quiet=True,work_dir=str(out/'session')) as session:
            probe=Probe(session,verbose=False);owner=verified_owner(session,probe);result['owner']=owner
            with RecoveryTransport(probe) as transport:
                member=0x02000188;menu=ResearchMenuList(transport.g,session.read_rom_bytes(),owner,member)
                token=menu.snapshot();require(token.state=='command','not a pinned command menu')
                before=ConsumableInventory(transport.g).snapshot()
                (out/'before-ewram.bin').write_bytes(block(transport.g,0x02000000,0x40000))
                require(not (out/'STOP').exists(),'STOP before START');menu.revalidate(token)
                mask=2 if args.cancel_command else 8
                hits=transport.press(mask,tag='a66-inspect-battle-menu-only',
                    stop_check=lambda:(out/'STOP').exists())
                require(hits==5,'partial START inspection press')
                transport.cont();time.sleep(1);transport.interrupt()
                if args.open_after_cancel:
                    context=integer(exact(transport.g,MENU_ROOT,4),0)
                    field=exact(transport.g,context,0x30);driver=exact(transport.g,0x0200F4E8,0xE0)
                    require(context==menu.context and field[4]==0 and integer(field,0,2)==0xFFFF
                            and integer(field,0x18)==member and integer(driver,4)==integer(driver,8)==menu.wrapper
                            and integer(driver,0x60)==0 and integer(driver,0xDC,2)==0x54
                            and integer(driver,0xD0)==0x258,'unrecognized field state after command cancel')
                    require(hashlib.sha256(exact(transport.g,member,0x108)).hexdigest()==token.unit_sha256
                            and ConsumableInventory(transport.g).snapshot()==before,'actor/inventory changed after cancel')
                    (out/'cancel-ewram.bin').write_bytes(block(transport.g,0x02000000,0x40000))
                    require(not (out/'STOP').exists(),'STOP before field START')
                    hits2=transport.press(8,tag='a66-inspect-field-START-only',stop_check=lambda:(out/'STOP').exists())
                    require(hits2==5,'partial field START inspection')
                    result['field_START']={'mask':8,'hits':hits2,'field':field.hex(),'driver':driver.hex()}
                    transport.cont();time.sleep(1);transport.interrupt()
                if args.inspect_law_cards:
                    require(Names(session.read_rom_bytes())._string(UI_STRINGS,3)=='Law Cards','System name differs')
                    result['System_inputs']=[]
                    def system_token():
                        context=integer(exact(transport.g,MENU_ROOT,4),0)
                        root=exact(transport.g,context,0x30);callback=integer(root,0x28)
                        cb=exact(transport.g,callback,0x18);obj=exact(transport.g,callback+0x18,0x9C)
                        driver=exact(transport.g,0x0200F4E8,0xE0)
                        require(context==menu.context and root[4]==1 and integer(root,0x18)==0
                                and integer(root,0x20)==menu.manager and callback==menu.callback
                                and integer(cb,0)==0x08028DE1 and integer(cb,0x14,2)==0x102
                                and integer(driver,4)==integer(driver,8)==menu.wrapper
                                and integer(driver,0xDC,2)==0x67 and integer(driver,0x60)==0,
                                'System list allocation/driver differs')
                        require(integer(obj,0x50,2)==6 and integer(obj,0x52,2)==0 and obj[0x69]<6,'System list bounds')
                        data=exact(transport.g,integer(obj,0x94),24);flags=exact(transport.g,integer(obj,0x98),6)
                        require(tuple(integer(data,i*4) for i in range(6))==(1,2,3,4,5,6)
                                and flags==bytes([1])*6,'System rows/flags differ')
                        require(hashlib.sha256(exact(transport.g,member,0x108)).hexdigest()==token.unit_sha256
                                and ConsumableInventory(transport.g).snapshot()==before,'System actor/count changed')
                        return {'root':root.hex(),'object':obj.hex(),'cursor':obj[0x69],
                                'rows':[1,2,3,4,5,6],'enabled':list(flags)}
                    (out/'System-ewram.bin').write_bytes(block(transport.g,0x02000000,0x40000))
                    for _ in range(7):
                        first=system_token();require(first==system_token(),'System token changed')
                        mask3=1 if first['cursor']==2 else 128
                        require(first['cursor']<=2,'System navigation overshot Law Cards')
                        require(not (out/'STOP').exists(),'STOP before Law Cards navigation')
                        hits3=transport.press(mask3,tag='a66-open-Law-Cards-only',stop_check=lambda:(out/'STOP').exists())
                        result['System_inputs'].append({'mask':mask3,'hits':hits3,'before':first})
                        require(hits3==5,'partial System navigation')
                        transport.cont();time.sleep(.5);transport.interrupt()
                        if mask3==1:break
                    else:raise TimeoutError('Law Cards navigation budget exceeded')
                (out/'after-ewram.bin').write_bytes(block(transport.g,0x02000000,0x40000))
                context=integer(exact(transport.g,MENU_ROOT,4),0)
                result.update(pid=session.pid,command=token.receipt(),press={'mask':8,'hits':hits},
                    root=exact(transport.g,context,0x30).hex(),context=context,
                    driver=exact(transport.g,0x0200F4E8,0xE0).hex(),
                    inventory_unchanged=ConsumableInventory(transport.g).snapshot()==before)
                require(result['inventory_unchanged'] and not session.writes,'law inspection changed inventory/RAM')
            session.screenshot(str(out/'battle-menu.png'));probe.disarm(strict=True)
        result['press']['mask']=mask
        result['status']='observed-field-START-research' if args.open_after_cancel else (
            'observed-command-cancel-research' if args.cancel_command else 'observed-START-inspection')
        if args.inspect_law_cards:result['status']='observed-Law-Cards-open-only'
    except BaseException as exc:result['error']=repr(exc);raise
    finally:
        if probe is not None:result.update(gameplay_writes=probe.key_write_log,fixture_writes=probe.s.writes)
        result['capture_sha256']={p.name:sha(p) for p in out.glob('*ewram.bin')}
        result['inputs_unchanged']=all(sha(p)==h for p,h in result['source_sha256'].items())
        (out/'law-menu.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['status'])


if __name__=='__main__':main()
