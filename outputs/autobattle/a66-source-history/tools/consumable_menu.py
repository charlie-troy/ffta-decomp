"""Pinned read-only join of a native secondary Item list to inventory counts.

No executor consumes these facts. Native enabled flags describe this list;
target/law legality and item-use completion remain separate gates.
"""
from dataclasses import dataclass, asdict
import hashlib

from ability_resources import RACE_TABLE
from consumable_inventory import ConsumableInventory, ITEM_IDS
from ffta_names import Names
from fixture_guard import STRIDE
from recovery_menu import (MENU_ROOT, MEMBERS, MEMBER_COUNT, PLAYER_DRIVER,
                           LIST, exact, integer, require)
from recovery_menu_list import ResearchMenuList


@dataclass(frozen=True)
class ItemListToken:
    member: int
    context: int
    callback: int
    cursor: int
    scroll: int
    rows: tuple
    enabled: tuple
    items: tuple
    excluded_rows: tuple
    inventory_raw: str
    inventory_sha256: str
    unit_sha256: str
    list_sha256: str

    def receipt(self):
        return asdict(self)


class OwnedItemList:
    def __init__(self, g, rom, owner, canonical):
        # Reuse the existing canonical-name/actor/menu allocation pins.
        self.bound = ResearchMenuList(g, rom, owner, canonical)
        self.g, self.rom = g, rom
        self.inventory = ConsumableInventory(g)

    def snapshot(self):
        g, b = self.g, self.bound
        require(integer(exact(g, MENU_ROOT, 4),0)==b.context, 'Item context moved')
        root=exact(g,b.context,0x30);unit=exact(g,b.member,STRIDE)
        identity=(unit[:0x18],unit[0x1A:0x1C],unit[0x1E:0x20],unit[0x28:0x2A],
                  unit[0x3B],unit[0xF6:0xF8],unit[0x104])
        require(identity==b.identity and b.name_hash()==b.name_digest, 'Item canonical identity changed')
        require(integer(unit,0x28,2)&0x9000==0 and 0<integer(unit,0x18,2)<=integer(unit,0x1A,2)<=999
                and 0<=integer(unit,0x1C,2)<=integer(unit,0x1E,2)<=999, 'Item actor resources/side invalid')
        for i in range(MEMBER_COUNT):
            address=MEMBERS+i*STRIDE
            if address!=b.member:
                other=exact(g,address,STRIDE)
                require(integer(other,0)!=b.owner['name'] and other[0x104]!=b.owner['id'],
                        'Item canonical actor alias')
        require(root[4]==7 and integer(root,0x10,2)==2 and unit[0x36]==1,
                'Item secondary group/mode differs')
        require(integer(root,0x18)==b.member and integer(root,0x28)==b.callback
                and integer(root,0x20)==b.manager, 'Item allocation/owner changed')
        driver=exact(g,PLAYER_DRIVER,0xE0)
        require(integer(driver,4)==integer(driver,8)==b.wrapper
                and integer(exact(g,b.wrapper,4),0)==b.member
                and integer(driver,0x60)==0 and integer(driver,0xDC,2)==0x4B
                and integer(exact(g,b.manager+4,4),0)==b.callback, 'Item driver/callback is unowned')
        callback=exact(g,b.callback,0x18)
        require(integer(callback,0)==LIST and integer(callback,0x14,2)==0x102,
                'Item list is not accepting input')
        obj=exact(g,b.callback+0x18,0x9C)
        count,scroll,cursor=integer(obj,0x50,2),integer(obj,0x52,2),obj[0x69]
        require(obj[0xA]==0 and 0<count<=15 and cursor<count and scroll+cursor<count,
                'Item list race/count/cursor invalid')
        data=exact(g,integer(obj,0x94),count*4);enabled=exact(g,integer(obj,0x98),count)
        rows=tuple(integer(data,i*4) for i in range(count))
        require(len(set(rows))==count and all(1<=r<=15 for r in rows)
                and all(v in (0,1) for v in enabled), 'Item rows/flags invalid or aliased')
        inventory=self.inventory.snapshot();pool=inventory.items();names=Names(self.rom)
        start=integer(self.rom,RACE_TABLE)-0x08000000
        require(0<=start and start+16*8<=len(self.rom), 'Item ROM row table outside ROM')
        facts=[];excluded=[]
        for row,flag in zip(rows,enabled):
            ability=integer(self.rom,start+row*8+4,2)
            if row==15:
                require(ability==265 and names.ability(ability)=='Draw Weapon', 'special Item row changed')
                excluded.append((row,ability,'Draw Weapon: no consumable count'))
                continue
            item=ITEM_IDS[row-1];available=pool[item]['available']
            require(available>0, 'Item list contains an exhausted/missing inventory item')
            require(names.item(item)==names.ability(ability), 'Item/global ability name join differs')
            facts.append((row,item,names.item(item),ability,available,bool(flag)))
        require({r for r in rows if r<=14}=={i+1 for i,item in enumerate(ITEM_IDS) if pool[item]['available']>0},
                'Item list omits an available consumable')
        reads=[(b.context,root),(b.member,unit),(PLAYER_DRIVER,driver),(b.callback,callback),
               (b.callback+0x18,obj),(integer(obj,0x94),data),(integer(obj,0x98),enabled)]
        require(all(exact(g,a,len(raw))==raw for a,raw in reads), 'Item list changed during read')
        self.inventory.revalidate(inventory)
        return ItemListToken(b.member,b.context,b.callback,cursor,scroll,rows,tuple(enabled),tuple(facts),
                             tuple(excluded),inventory.raw.hex(),inventory.sha256,
                             hashlib.sha256(unit).hexdigest(),
                             hashlib.sha256(root+driver+callback+obj+data+enabled).hexdigest())

    def revalidate(self, token):
        require(isinstance(token,ItemListToken) and self.snapshot()==token, 'stale/foreign Item list token')
        return token
