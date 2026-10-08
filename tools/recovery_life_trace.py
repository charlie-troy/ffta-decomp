"""Read-only native Life/HP-store observations, with partial logs on failure."""
import json
from pathlib import Path

from fixture_guard import STRIDE, u8, u16, u32
from probe_control_handoff import Probe
from recovery_menu import MEMBERS, MEMBER_COUNT, require


class LifeExecutionProbe(Probe):
    sites = {0x08133388:'Life-effect-entry',0x08133390:'Life-effect-flags-written',
             0x080A2298:'HP-store-before',0x080A229A:'HP-store-after',
             0x080A7198:'EXP-award',0x080C9B8C:'level-up-before',
             0x080A71C4:'level-up-after'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.life_hits, self.life_errors = [], []
        self.life_log_path = None

    def arm(self,strict=False):
        super().arm(strict=strict)
        for address in self.sites:
            require(not strict or self.set_bp(address) == 'OK','Life trace insertion failed')
            if not strict:
                self.set_bp(address)

    def disarm(self,strict=False):
        super().disarm(strict=strict)
        for address in self.sites:
            self.clear_bp(address,strict=strict)

    def facts(self,address):
        if address not in [MEMBERS+i*STRIDE for i in range(MEMBER_COUNT)]:
            return None
        return {'canonical':address,'id':u8(self.g,address+0x104),
                'name':u32(self.g,address),'hp':u16(self.g,address+0x18),
                'mp':u16(self.g,address+0x1C),'ko_suffered':u8(self.g,address+0xF2)}

    def handle_stop(self,during=''):
        pc = self.g.read_pc()
        if pc not in self.sites:
            return super().handle_stop(during)
        try:
            regs = self.g.read_registers()
            require(regs is not None,'Life trace registers missing')
            hit = {'t':self.now(),'pc':f'{pc:08x}','phase':self.sites[pc],
                   'registers':[f'{r:08x}' for r in regs], 'during':during}
            if pc in (0x080A2298,0x080A229A):
                hit.update(unit=self.facts(regs[6]),stored_hp=regs[5]&0xFFFF)
            elif pc in (0x080A7198,0x080C9B8C,0x080A71C4):
                address = regs[0] if pc == 0x080C9B8C else u32(self.g,u32(self.g,regs[4]))
                unit = self.facts(address)
                require(unit is not None,'level-up unit is not canonical')
                raw = self.g.read_mem(address,STRIDE)
                require(raw is not None and len(raw)==STRIDE,'short level-up unit capture')
                hit.update(unit=unit,unit_hex=raw.hex(),caller_lr=f'{regs[14]:08x}')
                if pc == 0x080A7198:
                    hit.update(old_exp=regs[0],awarded_exp=u16(self.g,regs[4]+4))
                if pc == 0x080A71C4:
                    hit['level_up_result'] = regs[0]
            else:
                address = regs[0]
                require(0x02000000 <= address <= 0x02040000-0x28,'Life effect context outside RAM')
                data = self.g.read_mem(address,0x28)
                require(data is not None and len(data)==0x28,'short Life effect context')
                words = [int.from_bytes(data[o:o+4],'little') for o in (0,4,8)]
                hit.update(context=address,context_words=words,flags=int.from_bytes(data[0x26:0x28],'little'),
                           canonical_joins=[self.facts(a) for a in words])
            self.life_hits.append(hit)
            if self.life_log_path:
                with Path(self.life_log_path).open('a',encoding='utf-8',newline='\n') as stream:
                    stream.write(json.dumps(hit)+'\n')
            return regs
        except Exception as exc:
            self.life_errors.append(repr(exc))
            raise
