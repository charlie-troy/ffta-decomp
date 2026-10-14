"""Check live zero/one Potion lists without selecting a consumable."""
import argparse
import hashlib
import json
from pathlib import Path

from consumable_menu import OwnedItemList
from consumable_inventory import INVENTORY
from emulate import Gba, STOP
from unicorn.arm_const import UC_ARM_REG_PC
from recovery_menu import RecoveryStateError
from validate_consumable_menu import Memory


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True);ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--expected',type=int,choices=[0,1],required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.capture);doc=json.loads((root/'inventory.json').read_text())
    assert doc['status']=='pass-live-owned-Item-list-and-inventory-reader' and doc['inputs_unchanged']
    assert not doc['fixture_writes'] and not any('before_Item' in p for p in doc['inputs'])
    raw=(root/'Item-list-ewram.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==doc['capture_sha256']['Item-list-ewram.bin']
    rom=Path(args.rom).read_bytes();g=Memory(raw)
    reader=OwnedItemList(g,rom,doc['owner'],doc['groups']['member']);token=reader.snapshot()
    potion=[r for r in token.items if r[1]==362]
    assert bool(potion)==bool(args.expected)
    if potion:assert potion[0][4]==args.expected and potion[0][-1] is True
    gba=Gba(args.rom);gba.uc.mem_write(0x02000000,raw)
    assert gba.call(0x080CB2B4,[362])==args.expected and gba.uc.reg_read(UC_ARM_REG_PC)==STOP
    assert doc['native_counts']['362']==args.expected
    rejected=[]
    for label,offset,value in [('count becomes stale',2,1-args.expected),('invalid reservation',3,99)]:
        memory=Memory(raw);r=OwnedItemList(memory,rom,doc['owner'],doc['groups']['member']);old=r.snapshot()
        memory.put(INVENTORY+offset,value,1)
        try:r.revalidate(old)
        except RecoveryStateError as exc:rejected.append({'case':label,'reason':str(exc)})
        else:raise AssertionError('accepted '+label)
    result={'status':'pass','scope':__doc__,'Potion_count':args.expected,'Potion_rows':potion,
        'rejected':rejected,'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ['tools/validate_consumable_count_capture.py','tools/consumable_menu.py','tools/consumable_inventory.py']},
        'evidence_sha256':{str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ['inventory.json','Item-list-ewram.bin']},
        'limitations':['Counts were constructed in separate disposable fixtures; no consumption or final item input.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS live Potion count',args.expected,'and stale-count refusals')


if __name__=='__main__':main()
