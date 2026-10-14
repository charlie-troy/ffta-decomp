"""Execute the native count/mapping helpers against bounded inventory controls."""
import argparse
import hashlib
import json
from pathlib import Path

from emulate import Gba
from consumable_inventory import ConsumableInventory, INVENTORY, decode_inventory, ITEM_IDS
from recovery_menu import RecoveryStateError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    g = Gba(args.rom)
    checks = []
    def check(label, condition):
        assert condition, label
        checks.append(label)
    for row, item in enumerate(ITEM_IDS, 1):
        check(f'ROM row {row} maps to {item}', g.call(0x080CB388, [row]) == item)
    for quantity, reserved in [(0, 0), (1, 0), (2, 0), (99, 0), (2, 1), (2, 2)]:
        raw = (362).to_bytes(2, 'little') + bytes([quantity, reserved]) + bytes(52)
        g.uc.mem_write(INVENTORY, raw)
        decoded = decode_inventory(raw)
        check(f'ROM count {quantity} minus reserved {reserved}',
              decoded[362]['available'] == g.call(0x080CB2B4, [362]) == quantity-reserved)
        check(f'ROM absent item at {quantity}/{reserved}',
              decoded[363]['available'] == g.call(0x080CB2B4, [363]) == 0)
    for label, raw in [
        ('short pool', bytes(55)),
        ('foreign item', (361).to_bytes(2,'little')+bytes(54)),
        ('reserved exceeds owned', (362).to_bytes(2,'little')+bytes([1,2])+bytes(52)),
        ('invalid quantity', (362).to_bytes(2,'little')+bytes([100,0])+bytes(52)),
        ('empty id with quantity', bytes([0,0,1,0])+bytes(52)),
        ('duplicate id', ((362).to_bytes(2,'little')+bytes([1,0]))*2+bytes(48)),
    ]:
        try:
            decode_inventory(raw)
        except RecoveryStateError:
            checks.append('reject '+label)
        else:
            raise AssertionError('accepted '+label)
    class Memory:
        def __init__(self): self.raw=bytes(56); self.calls=0
        def read_mem(self,a,n):
            assert a == INVENTORY and n == 56
            self.calls += 1
            return self.raw if self.calls == 1 else bytes([1])+self.raw[1:]
    try:
        ConsumableInventory(Memory()).snapshot()
    except RecoveryStateError:
        checks.append('reject pool changed during read')
    else:
        raise AssertionError('accepted moving inventory')
    result={'status':'pass', 'scope':__doc__, 'checks':checks,
            'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                ['tools/consumable_inventory.py','tools/validate_consumable_inventory.py','tools/emulate.py','baserom.gba']},
            'limitations':['Isolated ROM helper executions on synthetic RAM; no live Item list or use proof.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS native consumable inventory:',len(checks),'checks')


if __name__=='__main__': main()
