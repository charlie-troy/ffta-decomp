"""Capture owned Item rows and inventory without selecting or consuming an item.

Command and Action navigation uses existing ownership/acceptance tokens. Once
Item opens this research probe captures raw RAM, then stops; a raw list is not
published as an executable item candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter, IdentityError
from consumable_inventory import ConsumableInventory, INVENTORY, ITEM_IDS
from consumable_menu import OwnedItemList
from consumable_overlay import PotionOverlayReader
from emulate import Gba
from ffta_names import Names, UI_STRINGS
from fixture_guard import FixtureSession, STRIDE
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, exact, integer, require, RecoveryTransient
from recovery_menu_list import ResearchMenuList
from recovery_transport import RecoveryTransport


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',default='outputs/autobattle/a64-life-fixture-01/life-recovery.ss0')
    ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--scenario',default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out',required=True)
    ap.add_argument('--inspect-potion-target',action='store_true',
                    help='Select enabled Potion once, capture the overlay, then stop without target acceptance')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths=[args.state,args.rom,args.scenario]+source_dependencies('probe_consumable_inventory')
    result={'schema':'ffta-consumable-inventory-research/1','status':'unknown','scope':__doc__,
            'source_sha256':{p:sha(p) for p in paths},'observations':[],'inputs':[]}
    expect=json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name']=int(expect['slot0_name'],0)
    probe=None
    try:
        with FixtureSession(args.state,rom=args.rom,expect=expect,quiet=True,work_dir=str(out/'session')) as session:
            session.g.sock.settimeout(2)
            result['pid']=session.pid
            probe=Probe(session,verbose=False);adapter=ActorAdapter(session);owner=None
            deadline=time.monotonic()+100
            while owner is None and time.monotonic()<deadline:
                require(not (out/'STOP').exists(),'STOP during passive owner acquisition')
                probe.pump(2,'Item-owner',sample_every=60)
                try:owner=adapter.observe(probe,adapter.snapshot())
                except IdentityError as exc:
                    adapter.prior=None
                    result.setdefault('passive_rejections',[]).append(str(exc))
            require(owner is not None,'no independently verified fresh Item-menu owner')
            probe.active_player_slot=owner['slot'];adapter.revalidate(owner,probe);result['owner']=owner
            with RecoveryTransport(probe) as transport:
                rom=session.read_rom_bytes();names=Names(rom)
                matches=[MEMBERS+i*STRIDE for i in range(MEMBER_COUNT)
                         if integer(exact(transport.g,MEMBERS+i*STRIDE,STRIDE),0)==owner['name']
                         and exact(transport.g,MEMBERS+i*STRIDE+0x104,1)[0]==owner['id']]
                require(len(matches)==1,'canonical item actor missing/ambiguous');member=matches[0]
                menu=ResearchMenuList(transport.g,rom,owner,member)
                inventory=ConsumableInventory(transport.g);before=inventory.snapshot()
                result['inventory_before']={'raw':before.raw.hex(),'sha256':before.sha256,'items':before.items()}
                def stopped():
                    require(not (out/'STOP').exists(),'STOP observed; research input forbidden')
                    return False
                def observe(kind):
                    for _ in range(20):
                        stopped()
                        try:
                            token=menu.snapshot();require(token.state==kind,'unexpected menu kind')
                            result['observations'].append(token.receipt());return token
                        except RecoveryTransient:
                            transport.cont();time.sleep(.25)
                    raise TimeoutError('research menu did not settle')
                def select(kind,row):
                    for _ in range(34):
                        token=observe(kind)
                        require(token.rows.count(row)==1,'item navigation row missing/ambiguous')
                        index=token.rows.index(row);require(token.enabled[index],'item navigation row disabled')
                        mask=1 if token.scroll+token.cursor==index else (128 if token.scroll+token.cursor<index else 64)
                        stopped();menu.revalidate(token);inventory.revalidate(before);stopped()
                        hits=transport.press(mask,tag='a66-open-Item-list-only',stop_check=stopped)
                        result['inputs'].append({'mask':mask,'hits':hits,'before':token.receipt()})
                        require(hits==5,'partial item navigation press')
                        if mask==1:return
                    raise TimeoutError('item navigation budget exceeded')
                select('command',9)
                groups=observe('action-group');result['groups']=groups.receipt()
                # Group 1 is independently identified by the native title table
                # and canonical secondary action set, not by cursor position.
                title_id=integer(rom,0x00527244+4,2)
                title=names._string(UI_STRINGS,title_id)
                result['item_group_title']={'row':1,'string_id':title_id,'title':title}
                require(title=='Item' and exact(transport.g,member+0x36,1)[0]==1,
                        'native secondary Item set/title differs')
                select('action-group',1)
                transport.cont();time.sleep(.75);transport.interrupt();stopped()
                raw=block(transport.g,0x02000000,0x40000)
                (out/'Item-list-ewram.bin').write_bytes(raw)
                result['capture_sha256']={'Item-list-ewram.bin':sha(out/'Item-list-ewram.bin')}
                context=integer(exact(transport.g,MENU_ROOT,4),0)
                root=exact(transport.g,context,0x30);callback=integer(root,0x28)
                obj=exact(transport.g,callback+0x18,0x9C)
                count=integer(obj,0x50,2);require(0<count<=15,'Item row count bounds')
                rows=exact(transport.g,integer(obj,0x94),count*4)
                enabled=exact(transport.g,integer(obj,0x98),count)
                result['raw_list']={'context':context,'root':root.hex(),'callback':callback,
                    'object':obj.hex(),'rows':[integer(rows,i*4) for i in range(count)],'enabled':list(enabled)}
                after=inventory.snapshot();require(after==before,'opening Item list changed inventory')
                gba=Gba(args.rom);gba.uc.mem_write(0x02000000,raw)
                result['native_counts']={str(i):gba.call(0x080CB2B4,[i]) for i in ITEM_IDS}
                require(all(before.items()[i]['available']==result['native_counts'][str(i)] for i in ITEM_IDS),
                        'live pool disagrees with actual ROM count accessor')
                item_reader=OwnedItemList(transport.g,rom,owner,member)
                item_token=item_reader.snapshot();item_reader.revalidate(item_token)
                result['joined_item_list']=item_token.receipt()
                result['status']='pass-live-owned-Item-list-and-inventory-reader'
                if args.inspect_potion_target:
                    require(item_token.rows[item_token.scroll+item_token.cursor]==1
                            and item_token.items[0][0]==1 and item_token.items[0][-1],
                            'Potion must already be the enabled current native row')
                    overlay_reader=PotionOverlayReader(item_reader,item_token)
                    stopped();item_reader.revalidate(item_token);stopped()
                    hits=transport.press(1,tag='a66-inspect-Potion-target-only',stop_check=stopped)
                    result['inputs'].append({'mask':1,'hits':hits,'before_Item':item_token.receipt()})
                    require(hits==5,'partial Potion overlay input')
                    transport.cont();time.sleep(.75);transport.interrupt();stopped()
                    overlay=block(transport.g,0x02000000,0x40000)
                    path=out/'Potion-overlay-ewram.bin';path.write_bytes(overlay)
                    result['capture_sha256'][path.name]=sha(path)
                    context=integer(exact(transport.g,MENU_ROOT,4),0)
                    result['Potion_overlay_raw']={'context':context,'root':exact(transport.g,context,0x30).hex(),
                        'driver':exact(transport.g,0x0200F4E8,0xE0).hex(),
                        'inventory_unchanged':inventory.snapshot()==before}
                    require(result['Potion_overlay_raw']['inventory_unchanged'],'opening Potion overlay spent inventory')
                    overlay_token=overlay_reader.snapshot();overlay_reader.revalidate(overlay_token)
                    result['Potion_overlay']=overlay_token.receipt()
                    result['status']='pass-owned-Item-reader-with-unaccepted-Potion-overlay'
                require(not session.writes,'research probe edited RAM')
            session.screenshot(str(out/'Item-list.png'));probe.disarm(strict=True)
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe,'key_write_log',[]),fixture_writes=probe.s.writes)
        result['inputs_unchanged']=all(sha(p)==h for p,h in result['source_sha256'].items())
        (out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['status'],result['raw_list']['rows'])


if __name__=='__main__':main()
