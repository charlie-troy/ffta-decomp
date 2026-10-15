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
from consumable_preview_gate import PotionPreviewGate
from consumable_description import PotionDescriptionReader,PotionPromptInspectionGate
from consumable_final import PotionFinalPromptReader
from consumable_use_gate import PotionUseGate
from consumable_effect_trace import PotionExecutionProbe
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
    ap.add_argument('--accept-potion-target',action='store_true',
                    help='One guarded self target-acceptance input; capture preview, never confirm item use')
    ap.add_argument('--inspect-potion-final-prompt',action='store_true',
                    help='Open the final prompt from a pinned description; never select Do it')
    ap.add_argument('--execute-potion-once',action='store_true',help='Research only: one guarded final use and passive native HP-store observation')
    args=ap.parse_args()
    require(not args.accept_potion_target or args.inspect_potion_target,'preview requires explicit Potion overlay inspection')
    require(not args.inspect_potion_final_prompt or args.accept_potion_target,'final-prompt inspection requires target acceptance')
    require(not args.execute_potion_once or args.inspect_potion_final_prompt,'single use requires final-context inspection')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
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
            probe=(PotionExecutionProbe if args.execute_potion_once else Probe)(session,verbose=False)
            if args.execute_potion_once:probe.item_log_path=out/'native-Potion-hits.jsonl'
            adapter=ActorAdapter(session);owner=None
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
                final_reader=PotionFinalPromptReader(item_reader,item_token,rom_path=args.rom) if args.inspect_potion_final_prompt else None
                result['joined_item_list']=item_token.receipt()
                result['status']='pass-live-owned-Item-list-and-inventory-reader'
                if args.inspect_potion_target:
                    require(item_token.rows[item_token.scroll+item_token.cursor]==1
                            and item_token.items[0][0]==1 and item_token.items[0][-1],
                            'Potion must already be the enabled current native row')
                    overlay_reader=PotionOverlayReader(item_reader,item_token)
                    description_reader=PotionDescriptionReader(item_reader,item_token)
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
                    if args.accept_potion_target:
                        gate=PotionPreviewGate(overlay_reader,transport,stop_check=stopped)
                        result['Potion_target_input_events']=gate.events
                        result['Potion_target_input']=gate.advance(overlay_token)
                        transport.cont();time.sleep(1);transport.interrupt();stopped()
                        preview=block(transport.g,0x02000000,0x40000)
                        path=out/'Potion-preview-ewram.bin';path.write_bytes(preview)
                        result['capture_sha256'][path.name]=sha(path)
                        root=exact(transport.g,context,0x30)
                        result['Potion_preview_raw']={'root':root.hex(),
                            'driver':exact(transport.g,0x0200F4E8,0xE0).hex(),
                            'inventory':inventory.snapshot().raw.hex(),
                            'canonical':exact(transport.g,member,STRIDE).hex()}
                        result['status']='captured-Potion-target-acceptance-only'
                        session.screenshot(str(out/'Potion-preview.png'));stopped()
                        if args.inspect_potion_final_prompt:
                            description=description_reader.snapshot();description_reader.revalidate(description)
                            result['Potion_description']=description.receipt()
                            prompt_gate=PotionPromptInspectionGate(description_reader,transport,stop_check=stopped)
                            result['Potion_prompt_events']=prompt_gate.events
                            result['Potion_prompt_input']=prompt_gate.advance(description)
                            transport.cont();time.sleep(1);transport.interrupt();stopped()
                            path=out/'Potion-final-prompt-ewram.bin'
                            path.write_bytes(block(transport.g,0x02000000,0x40000))
                            result['capture_sha256'][path.name]=sha(path)
                            result['Potion_final_prompt_raw']={'root':exact(transport.g,context,0x30).hex(),
                                'driver':exact(transport.g,0x0200F4E8,0xE0).hex(),
                                'inventory':inventory.snapshot().raw.hex(),
                                'canonical':exact(transport.g,member,STRIDE).hex()}
                            final_token=final_reader.snapshot();final_reader.revalidate(final_token)
                            result['Potion_final_token']=final_token.receipt()
                            result['status']='captured-Potion-final-prompt-only'
                            if args.execute_potion_once:
                                unit=exact(transport.g,member,STRIDE)
                                require(unit[0x0A]==0 and unit[0x3A]==0,'use witness requires explicit EXP0/reaction-free fixture')
                                mp=integer(unit,0x1C,2)
                                use_gate=PotionUseGate(final_reader,transport,stop_check=stopped)
                                result['Potion_use_events']=use_gate.events
                                result['Potion_use_input']=use_gate.execute(final_token)
                                transport.interrupt();probe.arm(strict=True)
                                deadline=time.monotonic()+35
                                while time.monotonic()<deadline:
                                    stopped();transport.halted=False
                                    probe.pump(.5,'Potion-effect',sample_every=60,
                                        stop_when=lambda p:any(h['phase']=='HP-store-after' and h['canonical']==member for h in p.item_hits))
                                    if any(h['phase']=='HP-store-after' and h['canonical']==member for h in probe.item_hits):break
                                transport.halted=False;transport.interrupt();probe.disarm(strict=True);stopped()
                                require(not probe.item_errors,'native Potion trace errors')
                                after_unit=exact(transport.g,member,STRIDE);after_inv=inventory.snapshot()
                                result['Potion_after']={'hp':integer(after_unit,0x18,2),'mp':integer(after_unit,0x1C,2),
                                    'count':after_inv.items()[362]['available'],'canonical':after_unit.hex(),
                                    'inventory':after_inv.raw.hex(),'native_hits':probe.item_hits}
                                path=out/'Potion-after-ewram.bin';path.write_bytes(block(transport.g,0x02000000,0x40000))
                                result['capture_sha256'][path.name]=sha(path)
                                require(result['Potion_after']['count']==final_token.count-1,'Potion did not decrement exactly once')
                                require(final_token.hp<result['Potion_after']['hp']<=241 and result['Potion_after']['mp']==mp,
                                        'Potion healing/unchanged MP not observed')
                                require(any(h['phase']=='HP-store-after' and h['canonical']==member and h['id']==5
                                    and h['hp']==result['Potion_after']['hp']
                                    for h in probe.item_hits),'no actor-associated native Potion HP store')
                                require(any(h['phase']=='inventory-decrement-before' and h['item']==362 and h['quantity']==1
                                    and h['record']==0x02001EE4 and h['Potion_owned']==2 and h['stored_count']==1
                                    for h in probe.item_hits) and any(h['phase']=='inventory-decrement-after'
                                    and h['item']==362 and h['Potion_owned']==1 for h in probe.item_hits),
                                    'no native single-Potion decrement pair')
                                result['status']='observed-single-Potion-consumption-and-HP-store-only'
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
