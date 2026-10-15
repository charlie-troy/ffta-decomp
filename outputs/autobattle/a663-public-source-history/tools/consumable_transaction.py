"""Shared bounded self-Potion transaction; owns no process or terminal cleanup.

Research callers pin exact evidence; public callers additionally supply STOP,
schema2 policy evaluation and before-final lifecycle callbacks.
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
from fixture_guard import FixtureSession, STRIDE,read_roster,ROSTER
from recovery_life_wait import LifeWaitBoundary
from recovery_party_continuation import observe_party_continuation
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, exact, integer, require, RecoveryTransient
from recovery_menu_list import ResearchMenuList
from consumable_transport import ConsumableResearchTransport


def drive_potion_transaction(session,probe,owner,transport,args,out,result,*,external_stop_check=lambda:False,
                             choose=None,policy=None,before_Potion_final=lambda token:None,
                             before_Wait_final=lambda token:None):
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result['transport_events']=transport.events
    rom=session.read_rom_bytes();names=Names(rom)
    matches=[MEMBERS+i*STRIDE for i in range(MEMBER_COUNT)
             if integer(exact(transport.g,MEMBERS+i*STRIDE,STRIDE),0)==owner['name']
             and exact(transport.g,MEMBERS+i*STRIDE+0x104,1)[0]==owner['id']]
    require(len(matches)==1,'canonical item actor missing/ambiguous');member=matches[0]
    menu=ResearchMenuList(transport.g,rom,owner,member)
    inventory=ConsumableInventory(transport.g);before=inventory.snapshot()
    result['inventory_before']={'raw':before.raw.hex(),'sha256':before.sha256,'items':before.items()}
    def stopped():
        require(not external_stop_check(),'external STOP during Potion transaction')
        if (out/'STOP').exists():
            result.setdefault('stop_requested',{'t':time.monotonic(),'write_count':len(probe.key_write_log)})
        require(not (out/'STOP').exists(),'STOP observed; research input forbidden')
        return False
    def inject_stop(phase):
        if args.inject_stop_at==phase:
            (out/'STOP').write_text(phase,encoding='utf-8')
            result['stop_injection']={'phase':phase,'t':time.monotonic(),'write_count':len(probe.key_write_log)}
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
                    before_Potion_final(final_token)
                    stopped()
                    if choose is not None:
                        from consumable_policy import potion_snapshot,POTION_CANDIDATE
                        for _ in range(2):
                            snapshot=potion_snapshot(final_reader,final_token,owner)
                            decision=choose(snapshot)
                            result.setdefault('policy_observations',[]).append({'snapshot':snapshot,'evaluation':decision})
                            require((decision.get('decision') or {}).get('candidate_id')==POTION_CANDIDATE,'policy declined bounded Potion; no final input')
                            stopped()
                    inject_stop('final-use')
                    try:result['Potion_use_input']=use_gate.execute(final_token)
                    except ValueError:
                        result['Potion_final_refusal']={'started':use_gate.started,'attempted':use_gate.attempted,
                            'hp':integer(exact(transport.g,member+0x18,2),0,2),
                            'inventory':inventory.snapshot().raw.hex()}
                        raise
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
                    inject_stop('post-effect');stopped()
                    if args.complete_potion_turn:
                        # Rebind only after the native HP store/count pair has passed.
                        menu=ResearchMenuList(transport.g,rom,owner,member)
                        deadline=time.monotonic()+12
                        while time.monotonic()<deadline:
                            stopped()
                            try:post=menu.snapshot()
                            except ValueError as exc:
                                result.setdefault('Potion_command_rejections',[]).append(str(exc))
                                now=exact(transport.g,member,STRIDE)
                                changes=[i for i,(a,b) in enumerate(zip(after_unit,now)) if a!=b]
                                if changes==[0x0A] and now[0x0A]==10:
                                    result['Potion_EXP_reward']={'before':after_unit[0x0A],'after':10,'offset':10}
                                    menu=ResearchMenuList(transport.g,rom,owner,member)
                                transport.cont();time.sleep(.25);continue
                            if post.state=='command':break
                            transport.cont();time.sleep(.25)
                        else:raise TimeoutError('Potion did not restore owned command; never retry')
                        require(post.rows.count(9)==1 and not post.enabled[post.rows.index(9)]
                            and post.rows.count(10)==1 and post.enabled[post.rows.index(10)],'Potion did not consume Action and leave Wait')
                        result['Potion_post_roster']=[r for r in read_roster(transport.g,rom=rom)['slots'] if r['live']]
                        result['Potion_post_command']=post.receipt()
                        current=exact(transport.g,member,STRIDE)
                        baseline=[r for r in read_roster(transport.g,rom=rom)['slots'] if r['live']]
                        name=rom[owner['name']-0x08000000:owner['name']-0x08000000+32] if owner['name']>=0x08000000 else exact(transport.g,owner['name'],32)
                        pins=[{'canonical':member,'id':5,'tile':list(current[0xF6:0xF8]),'max_hp':241,'max_mp':221,
                               'name_sha256':hashlib.sha256(name).hexdigest()}]
                        # Selection now pins the independently witnessed post-use pool.
                        before=inventory.snapshot()
                        require(before==after_inv,'inventory changed after witnessed consumption')
                        units={member:current};select('command',10)
                        boundary=LifeWaitBoundary(transport.g,menu,units)
                        facing=boundary.snapshot();boundary.revalidate(facing)
                        result['Potion_Wait_events']=boundary.events
                        # Pure policy selects only the native legal Wait candidate.
                        wait_policy=policy or {'schema':'ffta-tactics-policy/2','assignments':{},'fallback':'wait','observation':{'max_age_seconds':3}}
                        before_Wait_final(facing)
                        stopped()
                        inject_stop('Wait-final')
                        result['Potion_Wait']=boundary.commit(facing,transport,wait_policy,stopped,choose=choose)
                        deadline=time.monotonic()+30
                        while time.monotonic()<deadline:
                            stopped()
                            try:continuation=observe_party_continuation(transport.g,rom,owner,facing.receipt(),pins,units,baseline)
                            except ValueError as exc:
                                result.setdefault('Potion_continuation_rejections',[]).append(str(exc))
                                transport.cont();time.sleep(.25);continue
                            break
                        else:raise TimeoutError('Potion Wait lacks independently attributed next actor')
                        result['Potion_continuation']=continuation
                        rows=[r for r in read_roster(transport.g,rom=rom)['slots'] if r['live']]
                        party_after=[]
                        for row in rows:
                            if row['id'] not in (5,7):continue
                            units_now=[exact(transport.g,MEMBERS+i*STRIDE,STRIDE) for i in range(MEMBER_COUNT)]
                            matches=[u for u in units_now if integer(u,0)==row['name'] and u[0x104]==row['id']]
                            require(len(matches)==1,'Potion continuation party alias/missing')
                            u=matches[0]
                            require(all(row[k]==integer(u,o,2) for k,o in [('hp',0x18),('max_hp',0x1A),('mp',0x1C),('max_mp',0x1E)])
                                    and u[0xF6:0xF8]==exact(transport.g,ROSTER+row['slot']*STRIDE+0xF6,2),
                                    'Potion continuation canonical/mirror mismatch')
                            party_after.append(row|{'x':u[0xF6],'y':u[0xF7]})
                        require({r['id'] for r in party_after}=={5,7},'Potion continuation party differs')
                        result['Potion_party_after']=party_after
                        path=out/'Potion-next-actor-ewram.bin';path.write_bytes(block(transport.g,0x02000000,0x40000))
                        result['capture_sha256'][path.name]=sha(path)
                        result['status']='observed-Potion-use-Wait-and-next-actor'
    require(not session.writes,'research probe edited RAM')
