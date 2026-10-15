"""Read-only bounded self-Potion final context and isolated native law check.

This is not an executor. It does not certify preview/effect-queue identity.
The native law matcher is evaluated with only the pinned source unit mapped;
any other EWRAM dependency or EWRAM write invalidates that evidence.
"""
from dataclasses import dataclass,asdict
import hashlib,struct
from emulate import Gba,STOP
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC
from consumable_description import PotionDescriptionReader
from consumable_inventory import ConsumableInventory
from fixture_guard import BATTLE_STRUCT,STRIDE
from probe_control_handoff import TARGET_X
from recovery_menu import MENU_ROOT,MEMBERS,MEMBER_COUNT,PLAYER_DRIVER,CONFIRM,exact,integer,require


@dataclass(frozen=True)
class PotionFinalToken:
    source:int
    target:int
    item:int
    ability:int
    count:int
    hp:int
    tile:tuple
    law_matches:tuple
    law_control:tuple
    native_unit_read_offsets:tuple
    raw_sha256:str

    def receipt(self):return asdict(self)


class PotionFinalPromptReader(PotionDescriptionReader):
    def __init__(self,menu,origin,*,rom_path='baserom.gba'):
        super().__init__(menu,origin)
        self.native=Gba(rom_path)
        require(self.native.rom==menu.rom and hashlib.sha256(menu.rom).hexdigest()==
            '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19','unverified native law ROM')

    def laws(self,unit,raw):
        require(len(raw)==10 and raw[0]==4 and 0<raw[1]<=4,'unsupported current-law bounds')
        ids=tuple(integer(raw,2+i*2,2) for i in range(raw[1]))
        require(len(set(ids))==len(ids) and all(i in (1,20,42,82) for i in ids)
                and not any(raw[2+raw[1]*2:]),'unknown/aliased current-law set')
        member=self.menu.bound.member;native=self.native;native.reset_ram();native.uc.mem_write(member,unit)
        reads=set();bad=[]
        def read(uc,access,address,size,value,user):
            if 0x02000000<=address<0x03000000:
                if not member<=address<=member+STRIDE-size:bad.append(('foreign-read',address,size))
                reads.add((address-member,size))
            elif 0x03000000<=address<0x04000000 and not 0x03007000<=address<=0x03007F10-size:
                bad.append(('non-stack-IWRAM-read',address,size))
        def write(uc,access,address,size,value,user):
            if 0x02000000<=address<0x03000000:bad.append(('EWRAM-write',address,size))
        hooks=[native.uc.hook_add(UC_HOOK_MEM_READ,read),native.uc.hook_add(UC_HOOK_MEM_WRITE,write)]
        try:
            require(native.call(0x08133D78,[member,251])==1,'Potion is not native Item action set1')
            results=[]
            for law in ids+(20,):
                native.uc.mem_write(0x03007F00,struct.pack('<IIII',0,0,0,0x08528F34+law*16))
                value=native.call(0x081343C8,[member,member,251,0])
                require(native.uc.reg_read(UC_ARM_REG_PC)==STOP,'native law matcher did not return')
                results.append((law,value))
            require(not bad and bytes(native.uc.mem_read(member,STRIDE))==unit,
                    'native law matcher depends on foreign RAM or mutates source')
            require(results[-1]==(20,1),'native Items-law control did not discriminate')
            require(all(value==0 for _,value in results[:-1]),'active law forbids self-Potion')
            return tuple(results[:-1]),results[-1],tuple(sorted(reads))
        finally:
            for hook in hooks:native.uc.hook_del(hook)

    def snapshot(self):
        g,b,origin=self.g,self.menu.bound,self.origin
        require(integer(exact(g,MENU_ROOT,4),0)==b.context,'Potion final context moved')
        root=exact(g,b.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0);cb=exact(g,b.callback,0x18)
        active=exact(g,b.manager+4,4);cursor=exact(g,b.callback+0x18+0x69,1)
        require(root[4]==11 and integer(root,0,2)==0 and integer(root,0x14)==251
                and integer(root,0x18)==integer(root,0x1C)==b.member
                and integer(root,0x20)==b.manager and integer(root,0x28)==b.callback,
                'Potion final source/peer/ability differs')
        require(integer(driver,4)==integer(driver,8)==b.wrapper and integer(driver,0x60)==BATTLE_STRUCT
                and integer(driver,0xDC,2)==0x31 and integer(driver,0xD0)==0x248,'Potion final driver differs')
        require(integer(cb,0)==CONFIRM and integer(cb,0x14,2)==0x102 and integer(active,0)==b.callback
                and cursor==b'\0','Potion final prompt is not owned Do it')
        header=exact(g,BATTLE_STRUCT,0xA4);ability=exact(g,BATTLE_STRUCT+0xEC,2)
        state=exact(g,BATTLE_STRUCT+0x1118,2);flags=exact(g,BATTLE_STRUCT+0x1112,2)
        require(all(integer(header,o)==b.wrapper for o in [0,4,8,12,0x50])
                and integer(header,16)==0 and header[0xA1]==0 and header[0xA2]==1,
                'Potion final self-target table/accepted source differs')
        require(integer(ability,0,2)==251 and integer(state,0,2)==2 and integer(flags,0,2)==0x20,
                'Potion final processor signature differs')
        unit=exact(g,b.member,STRIDE);wrapper=exact(g,b.wrapper,0x40)
        require(integer(wrapper,0)==b.member and hashlib.sha256(unit).hexdigest()==origin.unit_sha256
                and b.name_hash()==b.name_digest,'Potion final canonical source changed')
        for i in range(MEMBER_COUNT):
            address=MEMBERS+i*STRIDE
            if address!=b.member:
                other=exact(g,address,STRIDE)
                require(integer(other,0)!=b.owner['name'] and other[0x104]!=b.owner['id'],'Potion final source alias')
        inv=ConsumableInventory(g).snapshot();availability=exact(g,0x0200203D,1);laws=exact(g,0x02003C32,10)
        require(inv.raw.hex()==origin.inventory_raw and availability[0]==origin.availability_flag13,
                'Potion final inventory/availability changed')
        matches,control,offsets=self.laws(unit,laws)
        x=exact(g,0x0200F3B8,2);y=exact(g,0x0200F3BC,2);display=exact(g,TARGET_X,2)
        committed=exact(g,BATTLE_STRUCT+0x109,2);tile=(integer(x,0,2),integer(y,0,2))
        require(tile==tuple(display)==tuple(committed)==tuple(unit[0xF6:0xF8]),'Potion final target tile differs')
        reads=[(b.context,root),(PLAYER_DRIVER,driver),(b.callback,cb),(b.manager+4,active),
            (b.callback+0x18+0x69,cursor),(BATTLE_STRUCT,header),(BATTLE_STRUCT+0xEC,ability),
            (BATTLE_STRUCT+0x1118,state),(BATTLE_STRUCT+0x1112,flags),(b.member,unit),(b.wrapper,wrapper),
            (0x0200203D,availability),(0x02003C32,laws),(0x0200F3B8,x),(0x0200F3BC,y),
            (TARGET_X,display),(BATTLE_STRUCT+0x109,committed)]
        require(all(exact(g,a,len(raw))==raw for a,raw in reads),'Potion final context changed during read')
        ConsumableInventory(g).revalidate(inv)
        return PotionFinalToken(b.member,b.member,362,251,inv.items()[362]['available'],integer(unit,0x18,2),
            tile,matches,control,offsets,hashlib.sha256(b''.join(raw for _,raw in reads)).hexdigest())

    def revalidate(self,token):
        require(type(token) is PotionFinalToken and self.snapshot()==token,'stale/foreign Potion final token')
        return token
