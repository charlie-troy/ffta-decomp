"""Read-only research hooks for damage results and attributed KO turn picks.

All extra hooks participate in disarm, so inherited key presses still run with
only the key-poll hook. No unit field or register is changed by these readers.
"""
import json
from pathlib import Path

from fixture_guard import STRIDE, u8, u16, u32
from probe_control_handoff import Probe
from recovery_menu import require


class KOLifecycleProbe(Probe):
    sites = {0x0809E7FE: 'tail-zero-check', 0x0809E246: 'tail-loop-skip',
             0x080A487A: 'damage-before', 0x080A487E: 'damage-after',
             0x080A2298: 'HP-adjust-before', 0x080A229A: 'HP-adjust-after',
             0x08093018: 'battle-driver-picked'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lifecycle_hits = []
        self.lifecycle_log_path = None

    def arm(self, strict=False):
        super().arm(strict=strict)
        for address in self.sites:
            reply = self.set_bp(address)
            require(not strict or reply == 'OK', 'KO observer breakpoint insertion failed')

    def disarm(self, strict=False):
        super().disarm(strict=strict)
        for address in self.sites:
            self.clear_bp(address, strict=strict)

    def unit_facts(self, address):
        require(type(address) is int and 0x02000000 <= address <= 0x02040000-STRIDE,
                'invalid lifecycle unit pointer')
        return {'unit': f'{address:08x}', 'name': u32(self.g, address),
                'id': u8(self.g, address+0x104), 'hp': u16(self.g, address+0x18),
                'mp': u16(self.g, address+0x1C), 'ko_suffered': u8(self.g, address+0xF2)}

    def handle_stop(self, during=''):
        pc = self.g.read_pc()
        if pc not in self.sites:
            return super().handle_stop(during)
        regs = self.g.read_registers()
        require(regs is not None, 'missing lifecycle registers')
        hit = {'t': self.now(), 'pc': f'{pc:08x}', 'phase': self.sites[pc], 'during': during}
        if pc in (0x0809E7FE, 0x0809E246):
            facts = self.unit_facts(regs[4])
            if facts['id'] not in (5, 7) or facts['hp'] != 0:
                return regs
            hit.update(facts, slot_register=regs[7], root=f'{regs[8]:08x}',
                       flags=u32(self.g, regs[10]+regs[7]*4), caller_lr=self.caller_lr(regs))
        elif pc in (0x080A2298, 0x080A229A):
            facts = self.unit_facts(regs[6])
            if facts['id'] not in (5, 7):
                return regs
            hit.update(facts, store_value=regs[5] & 0xFFFF,
                       old_class=regs[7], registers=[f'{r:08x}' for r in regs])
        elif pc in (0x080A487A, 0x080A487E):
            context = regs[10]
            require(0x02000000 <= context <= 0x0203FFC0, 'invalid damage result context')
            wrapper = u32(self.g, context)
            require(type(wrapper) is int and 0x02000000 <= wrapper <= 0x0203FF70, 'invalid damage wrapper')
            facts = self.unit_facts(u32(self.g, wrapper))
            if facts['id'] not in (5, 7):
                return regs
            hit.update(facts, context=f'{context:08x}', wrapper=f'{wrapper:08x}',
                       damage=u16(self.g, context+6), result_flags=u16(self.g, context+4))
        else:
            wrapper = regs[0]
            require(0x02000000 <= wrapper <= 0x0203FF70, 'invalid picked wrapper')
            hit.update(self.unit_facts(u32(self.g, wrapper)), wrapper=f'{wrapper:08x}',
                       driver=f'{regs[6]:08x}', caller='08093014 -> 0809f850 -> 08093018')
        self.lifecycle_hits.append(hit)
        if self.lifecycle_log_path:
            with Path(self.lifecycle_log_path).open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(json.dumps(hit)+'\n')
        return regs
