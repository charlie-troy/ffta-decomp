"""Run the actual Item list builder on captured RAM with isolated controls.

Synthetic RAM changes are confined to Unicorn. They are not live game actions
or proof of target/law legality. All native routines must return normally.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from emulate import Gba, STOP
from unicorn.arm_const import UC_ARM_REG_PC
from consumable_inventory import INVENTORY, ITEM_IDS
from consumable_menu import OwnedItemList
from validate_consumable_menu import Memory


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--out',required=True)
    args=ap.parse_args();directory=Path(args.capture)
    doc=json.loads((directory/'inventory.json').read_text());raw=(directory/'Item-list-ewram.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==doc['capture_sha256']['Item-list-ewram.bin']
    obj=doc['raw_list']['callback']+0x18;member=doc['groups']['member'];checks=[]
    def case(label,quantity=60,reserved=0,frog=False,flag13=0):
        gba=Gba(args.rom);gba.uc.mem_write(0x02000000,raw)
        gba.write8(INVENTORY+2,quantity);gba.write8(INVENTORY+3,reserved)
        original=gba.uc.mem_read(member+0xE9,1)[0]
        gba.write8(member+0xE9,original|1 if frog else original&254)
        gba.write8(0x0200203D,flag13)
        pointer=gba.read32(obj+0x98);gba.uc.mem_write(pointer,bytes([1])*15)
        ctx=0x0203E000
        gba.uc.mem_write(ctx,struct.pack('<I',0x0851BAE4)+bytes([1,15,1,7,0,0,0,0]))
        gba.call(0x08026B90,[obj,ctx])
        assert gba.uc.reg_read(UC_ARM_REG_PC)==STOP, 'builder did not return: '+label
        count=gba.uc.mem_read(ctx+9,1)[0]
        gba.uc.mem_write(obj+0x50,count.to_bytes(2,'little'))
        # The caller publishes the returned count; no rendering/controller is
        # emulated here, and this adapted RAM is only a reader test fixture.
        adapted=bytes(gba.uc.mem_read(0x02000000,0x40000))
        token=OwnedItemList(Memory(adapted),gba.rom,doc['owner'],member).snapshot()
        rows={r[0]:r for r in token.items}
        assert (1 in rows)==(quantity>reserved)
        if quantity>reserved:assert rows[1][4]==quantity-reserved
        if frog:
            assert all(r[-1]==(r[1]==370) for r in token.items)
        checks.append({'case':label,'rows':token.rows,'enabled':token.enabled,
                       'Potion_available':quantity-reserved,'flag13':flag13,'frog':frog})
    for n in [0,1,2,60]:case('Potion count '+str(n),n)
    case('all copies reserved',2,2)
    case('one copy available after reservation',2,1)
    case('Frog permits only Maiden Kiss',frog=True)
    case('native availability flag13=1',flag13=1)
    result={'status':'pass','scope':__doc__,'checks':checks,
            'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                ['tools/validate_consumable_builder.py','tools/consumable_menu.py','tools/consumable_inventory.py',args.rom]},
            'evidence_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                [directory/'inventory.json',directory/'Item-list-ewram.bin']},
            'limitations':['Flag13 native behavior is bounded; its gameplay/law meaning is not established.',
                           'No final item input, target legality, count decrement or HP effect.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS actual native Item builder:',len(checks),'controls')


if __name__=='__main__':main()
