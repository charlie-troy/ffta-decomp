"""Pinned self-Potion description; only permits opening the final prompt.

No item-use or law-compliance authority. In particular a description token
cannot be reused as an overlay token or authorize a final confirmation.
"""
from dataclasses import dataclass,asdict
import hashlib
from consumable_inventory import ConsumableInventory
from fixture_guard import BATTLE_STRUCT,STRIDE
from probe_control_handoff import TARGET_X
from recovery_menu import MENU_ROOT,MEMBERS,MEMBER_COUNT,PLAYER_DRIVER,DESCRIPTION,exact,integer,require


@dataclass(frozen=True)
class PotionDescriptionToken:
    source:int
    target:int
    ability:int
    item:int
    count:int
    hp:int
    tile:tuple
    raw_sha256:str

    def receipt(self):return asdict(self)


class PotionDescriptionReader:
    def __init__(self,menu,origin):
        menu.revalidate(origin)
        require(origin.rows[origin.scroll+origin.cursor]==1 and origin.items[0][0:2]==(1,362)
                and origin.items[0][-1],'description origin is not selected enabled Potion')
        self.menu,self.origin,self.g=menu,origin,menu.g

    def snapshot(self):
        g,b,origin=self.g,self.menu.bound,self.origin
        require(integer(exact(g,MENU_ROOT,4),0)==b.context,'Potion description context moved')
        root=exact(g,b.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0);cb=exact(g,b.callback,0x18)
        active=exact(g,b.manager+4,4)
        require(root[4]==12 and integer(root,0,2)==0 and integer(root,0x14)==251
                and integer(root,0x18)==integer(root,0x1C)==b.member
                and integer(root,0x20)==b.manager and integer(root,0x28)==b.callback,
                'Potion description source/peer/ability differs')
        require(integer(driver,4)==integer(driver,8)==b.wrapper and integer(driver,0x60)==BATTLE_STRUCT
                and integer(driver,0xDC,2)==0x31 and integer(driver,0xD0)==0x248,
                'Potion description driver differs')
        require(integer(cb,0)==DESCRIPTION and integer(cb,0x14,2)==0x102 and integer(active,0)==b.callback,
                'Potion description does not own input')
        header=exact(g,BATTLE_STRUCT,0xA4);ability=exact(g,BATTLE_STRUCT+0xEC,2)
        state=exact(g,BATTLE_STRUCT+0x1118,2);flags=exact(g,BATTLE_STRUCT+0x1112,2)
        require(all(integer(header,o)==b.wrapper for o in [0,4,8,0x50])
                and integer(header,12)==integer(header,16)==0 and header[0xA1]==0 and header[0xA2]==1,
                'Potion description self-target table/copies differ')
        require(integer(ability,0,2)==251 and integer(state,0,2)==10 and integer(flags,0,2)==0x6C,
                'Potion description processor signature differs')
        wrapper=exact(g,b.wrapper,0x40);unit=exact(g,b.member,STRIDE)
        require(integer(wrapper,0)==b.member and hashlib.sha256(unit).hexdigest()==origin.unit_sha256
                and b.name_hash()==b.name_digest,'Potion description canonical source changed')
        for i in range(MEMBER_COUNT):
            address=MEMBERS+i*STRIDE
            if address!=b.member:
                other=exact(g,address,STRIDE)
                require(integer(other,0)!=b.owner['name'] and other[0x104]!=b.owner['id'],
                        'Potion description canonical alias')
        inv=ConsumableInventory(g).snapshot();law=exact(g,0x0200203D,1)
        require(inv.raw.hex()==origin.inventory_raw and law[0]==origin.availability_flag13,
                'Potion description inventory/availability changed')
        x=exact(g,0x0200F3B8,2);y=exact(g,0x0200F3BC,2);display=exact(g,TARGET_X,2)
        committed=exact(g,BATTLE_STRUCT+0x109,2);tile=(integer(x,0,2),integer(y,0,2))
        require(tile==tuple(display)==tuple(committed)==tuple(unit[0xF6:0xF8]),'Potion description tile differs')
        reads=[(b.context,root),(PLAYER_DRIVER,driver),(b.callback,cb),(b.manager+4,active),
               (BATTLE_STRUCT,header),(BATTLE_STRUCT+0xEC,ability),(BATTLE_STRUCT+0x1118,state),
               (BATTLE_STRUCT+0x1112,flags),(b.wrapper,wrapper),(b.member,unit),(0x0200203D,law),
               (0x0200F3B8,x),(0x0200F3BC,y),(TARGET_X,display),(BATTLE_STRUCT+0x109,committed)]
        require(all(exact(g,a,len(raw))==raw for a,raw in reads),'Potion description changed during read')
        ConsumableInventory(g).revalidate(inv)
        return PotionDescriptionToken(b.member,b.member,251,362,inv.items()[362]['available'],
            integer(unit,0x18,2),tile,hashlib.sha256(b''.join(raw for _,raw in reads)).hexdigest())

    def revalidate(self,token):
        require(type(token) is PotionDescriptionToken and self.snapshot()==token,'stale/foreign Potion description')
        return token


class PotionPromptInspectionGate:
    def __init__(self,reader,transport,*,stop_check=lambda:False):
        self.reader,self.transport,self.stop_check=reader,transport,stop_check
        self.started=False;self.events=[]

    def check_stop(self):
        require(not self.stop_check(),'STOP observed; Potion prompt inspection forbidden')
        return False

    def advance(self,token):
        require(not self.started,'Potion prompt inspection cannot be retried');self.started=True
        self.check_stop();require(type(token) is PotionDescriptionToken,'prompt lacks description token')
        self.reader.revalidate(token);self.check_stop()
        self.events.append({'event':'prompt_inspection_input_requested','mask':1})
        hits=self.transport.press(1,tag='a66-Potion-final-prompt-inspection-only',stop_check=self.check_stop)
        require(hits==5,'partial prompt inspection input; never retry')
        self.events.append({'event':'prompt_inspection_input_delivered','hits':hits})
        return {'outcome':'prompt-inspection-input-only','final_input':False}
