"""Read-only owned-menu boundary for manual B cancellation, never item use."""
import hashlib
from consumable_inventory import ConsumableInventory
from recovery_menu import MENU_ROOT,PLAYER_DRIVER,MEMBERS,MEMBER_COUNT,STRIDE,LIST,DESCRIPTION,CONFIRM,exact,integer,require
from recovery_menu_list import ResearchMenuList
from fixture_guard import BATTLE_STRUCT


class PotionManualCancel:
    def __init__(self,g,rom,owner,unit,inventory):
        self.g,self.unit,self.inventory=g,unit,inventory
        self.menu=ResearchMenuList(g,rom,owner,0x02000188)

    def snapshot(self):
        g,m=self.g,self.menu
        root=exact(g,m.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0);cb=exact(g,m.callback,0x18)
        unit=exact(g,m.member,STRIDE)
        require(integer(exact(g,MENU_ROOT,4),0)==m.context and integer(root,0x18)==m.member
            and integer(root,0x20)==m.manager and integer(root,0x28)==m.callback,'manual cancel menu allocation/owner changed')
        require(integer(driver,4)==integer(driver,8)==m.wrapper
            and integer(exact(g,m.wrapper,4),0)==m.member,'manual cancel driver owner differs')
        require(unit==self.unit and m.name_hash()==m.name_digest,'manual cancel canonical unit changed')
        require(ConsumableInventory(g).snapshot().raw.hex()==self.inventory,'manual cancellation spent inventory')
        for i in range(MEMBER_COUNT):
            a=MEMBERS+i*STRIDE
            if a==m.member:continue
            other=exact(g,a,STRIDE)
            require(integer(other,0)!=integer(unit,0) and other[0x104]!=5,'manual cancel actor alias')
        mode,state,handler=root[4],integer(cb,0x14,2),integer(cb,0)
        require(mode in (4,5,7,11,12) and handler in (LIST,DESCRIPTION,CONFIRM)
            and state in (3,0x102,0x106),'manual cancel does not own an accepting supported menu')
        if mode in (11,12):
            require(integer(root,0x14)==251 and handler==(CONFIRM if mode==11 else DESCRIPTION)
                and (state==0x102 or mode==12 and state==3) and integer(driver,0xDC,2)==0x31 and integer(driver,0x60)==BATTLE_STRUCT
                and integer(driver,0xD0)==0x248,'manual cancel final/description signature differs')
            if state==3:
                header=exact(g,BATTLE_STRUCT,0x54)
                require(integer(header,0)==integer(header,0x50)==integer(header,12)==m.wrapper and integer(header,16)==0
                    and integer(exact(g,BATTLE_STRUCT+0xEC,2),0,2)==251
                    and integer(exact(g,BATTLE_STRUCT+0x1118,2),0,2)==10
                    and integer(exact(g,BATTLE_STRUCT+0x1112,2),0,2)==0,'manual cancel cached description is not unaccepted self-target')
        if mode==7:
            require(handler==LIST and ((state==3 and integer(driver,0xDC,2)==0x31 and integer(driver,0x60)==BATTLE_STRUCT)
                or (state==0x102 and integer(driver,0xDC,2)==0x4B and integer(driver,0x60)==0)),
                'manual cancel Item/overlay driver differs')
        command=None
        if mode in (4,5):
            token=m.snapshot()
            if mode==4:
                require(token.state=='command' and token.rows.count(9)==token.rows.count(10)==1
                    and token.enabled[token.rows.index(9)] and token.enabled[token.rows.index(10)],'cancel did not restore unspent command')
                command=token.receipt()
        require(all(exact(g,a,len(b))==b for a,b in [(m.context,root),(PLAYER_DRIVER,driver),(m.callback,cb),(m.member,unit)]),
            'manual cancel changed during read')
        return {'mode':mode,'state':state,'handler':handler,'canonical':m.member,'command':command,
                'unit_sha256':hashlib.sha256(unit).hexdigest()}
