"""Read an unaccepted self-Potion overlay, with no final-input authority.

The preceding owned Item token pins the source, quantity and list capability.
This bounded reader only accepts the one-target native self overlay. General
target legality, law compliance and item consumption are separate gates.
"""
from dataclasses import dataclass, asdict
import hashlib

from consumable_inventory import ConsumableInventory
from fixture_guard import BATTLE_STRUCT, STRIDE
from probe_control_handoff import TARGET_X
from recovery_menu import MENU_ROOT, MEMBERS, MEMBER_COUNT, PLAYER_DRIVER, LIST, exact, integer, require


@dataclass(frozen=True)
class PotionOverlayToken:
    source: int
    target: int
    wrapper: int
    ability_id: int
    item_id: int
    count: int
    hp: int
    max_hp: int
    tile: tuple
    inventory_sha256: str
    raw_sha256: str

    def receipt(self):return asdict(self)


class PotionOverlayReader:
    def __init__(self, menu, origin):
        menu.revalidate(origin)
        require(origin.rows[origin.scroll+origin.cursor]==1 and origin.items[0][0:2]==(1,362)
                and origin.items[0][-1], 'Potion overlay origin is not enabled selected Potion')
        self.menu,self.origin,self.g=menu,origin,menu.g

    def snapshot(self):
        g,b,origin=self.g,self.menu.bound,self.origin
        require(integer(exact(g,MENU_ROOT,4),0)==b.context,'Potion overlay context moved')
        root=exact(g,b.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0)
        require(root[4]==7 and integer(root,0,2)==1 and integer(root,0x14)==251
                and integer(root,0x18)==integer(root,0x1C)==b.member
                and integer(root,0x20)==b.manager and integer(root,0x28)==b.callback,
                'Potion overlay selection/source/peer differs')
        require(integer(driver,4)==integer(driver,8)==b.wrapper and integer(driver,0x60)==BATTLE_STRUCT
                and integer(driver,0xDC,2)==0x31 and integer(driver,0xD0)==0x248,
                'Potion overlay driver/source differs')
        require(integer(exact(g,b.manager+4,4),0)==0,'Potion overlay still has active cached UI')
        callback=exact(g,b.callback,0x18)
        require(integer(callback,0)==LIST and integer(callback,0x14,2)==3,
                'Potion list has not yielded to target processor')
        header=exact(g,BATTLE_STRUCT,0xA4)
        ability=exact(g,BATTLE_STRUCT+0xEC,2)
        state=exact(g,BATTLE_STRUCT+0x1118,2);flags=exact(g,BATTLE_STRUCT+0x1112,2)
        require(integer(header,0)==integer(header,0x50)==b.wrapper
                and integer(header,12)==integer(header,16)==0
                and header[0xA1]==0 and header[0xA2]==1,
                'Potion overlay target list/source/copies differ')
        require(integer(ability,0,2)==251 and integer(state,0,2)==10 and integer(flags,0,2)==0,
                'Potion overlay is not unaccepted targeting')
        wrapper=exact(g,b.wrapper,0x40);unit=exact(g,b.member,STRIDE)
        require(integer(wrapper,0)==b.member and hashlib.sha256(unit).hexdigest()==origin.unit_sha256
                and b.name_hash()==b.name_digest,'Potion canonical actor/target changed')
        for i in range(MEMBER_COUNT):
            member=MEMBERS+i*STRIDE
            if member!=b.member:
                other=exact(g,member,STRIDE)
                require(integer(other,0)!=b.owner['name'] and other[0x104]!=b.owner['id'],
                        'Potion source/target canonical alias appeared')
        require(not unit[0xEA]&128 and not unit[0xEB]&4,'Potion source has Stop/Sleep')
        inventory=ConsumableInventory(g).snapshot()
        require(inventory.raw.hex()==origin.inventory_raw and inventory.sha256==origin.inventory_sha256,
                'Potion inventory changed before acceptance')
        law=exact(g,0x0200203D,1)
        require(law[0]==origin.availability_flag13,'Potion native availability flag changed')
        x=exact(g,0x0200F3B8,2);y=exact(g,0x0200F3BC,2);display=exact(g,TARGET_X,2)
        tile=(integer(x,0,2),integer(y,0,2))
        require(tile==tuple(display)==tuple(unit[0xF6:0xF8]),'Potion cursor/canonical target tile differs')
        reads=[(b.context,root),(PLAYER_DRIVER,driver),(b.callback,callback),(BATTLE_STRUCT,header),
               (BATTLE_STRUCT+0xEC,ability),(BATTLE_STRUCT+0x1118,state),(BATTLE_STRUCT+0x1112,flags),
               (b.wrapper,wrapper),(b.member,unit),(0x0200203D,law),(0x0200F3B8,x),(0x0200F3BC,y),
               (TARGET_X,display),(b.manager+4,bytes(4))]
        require(all(exact(g,a,len(raw))==raw for a,raw in reads),'Potion overlay changed during read')
        ConsumableInventory(g).revalidate(inventory)
        return PotionOverlayToken(b.member,b.member,b.wrapper,251,362,inventory.items()[362]['available'],
                integer(unit,0x18,2),integer(unit,0x1A,2),tile,inventory.sha256,
                hashlib.sha256(b''.join(raw for _,raw in reads)).hexdigest())

    def revalidate(self, token):
        require(isinstance(token,PotionOverlayToken) and self.snapshot()==token,'stale/foreign Potion overlay token')
        return token
