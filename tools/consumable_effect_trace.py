"""Read-only native HP stores tied to the selected Item action processor."""
import json
from pathlib import Path
from probe_control_handoff import Probe
from fixture_guard import STRIDE,u8,u16,u32,BATTLE_STRUCT
from recovery_menu import MEMBERS,MEMBER_COUNT,require


class PotionExecutionProbe(Probe):
    sites={0x080A2298:'HP-store-before',0x080A229A:'HP-store-after',
           0x080CAA68:'inventory-decrement-before',0x080CAA6A:'inventory-decrement-after'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.item_hits=[];self.item_errors=[];self.item_log_path=None

    def arm(self,strict=False):
        super().arm(strict=strict)
        for address in self.sites:
            reply=self.set_bp(address);require(not strict or reply=='OK','Potion trace insertion failed')

    def disarm(self,strict=False):
        super().disarm(strict=strict)
        for address in self.sites:self.clear_bp(address,strict=strict)

    def handle_stop(self,during=''):
        pc=self.g.read_pc()
        if pc not in self.sites:return super().handle_stop(during)
        try:
            regs=self.g.read_registers();require(regs is not None,'Potion trace registers missing')
            hp_site=pc in (0x080A2298,0x080A229A)
            address=regs[6] if hp_site else 0x02000188
            require(address in [MEMBERS+i*STRIDE for i in range(MEMBER_COUNT)],'HP store target not canonical')
            hit={'t':self.now(),'pc':f'{pc:08x}','phase':self.sites[pc],'during':during,
                'registers':[f'{r:08x}' for r in regs],'canonical':address,'id':u8(self.g,address+0x104),
                'hp':u16(self.g,address+0x18),'mp':u16(self.g,address+0x1C),'stored_hp':regs[5]&0xFFFF,
                'processor_ability':u16(self.g,BATTLE_STRUCT+0xEC),
                'processor_source_wrapper':u32(self.g,BATTLE_STRUCT),
                'processor_target_wrapper':u32(self.g,BATTLE_STRUCT+8),
                'Potion_owned':u8(self.g,0x02001EE6),'Potion_reserved':u8(self.g,0x02001EE7)}
            if not hp_site:hit.update(item=regs[4],quantity=regs[5],record=regs[2],stored_count=regs[0]&255)
            self.item_hits.append(hit)
            if self.item_log_path:
                with Path(self.item_log_path).open('a',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(hit)+'\n')
            return regs
        except Exception as exc:self.item_errors.append(repr(exc));raise
