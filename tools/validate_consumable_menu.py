"""Replay a native Item capture and reject unavailable, foreign and stale joins."""
import argparse
import hashlib
import json
from pathlib import Path

from consumable_inventory import INVENTORY
from consumable_menu import OwnedItemList
from recovery_menu import RecoveryStateError, PLAYER_DRIVER, MEMBERS, STRIDE


class Memory:
    def __init__(self, raw): self.raw=bytearray(raw)
    def read_mem(self,a,n):
        offset=a-0x02000000
        return bytes(self.raw[offset:offset+n]) if 0<=offset<=len(self.raw)-n else None
    def put(self,a,value,n=4):
        offset=a-0x02000000;self.raw[offset:offset+n]=value.to_bytes(n,'little')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.capture)
    doc=json.loads((root/'inventory.json').read_text());rom=Path(args.rom).read_bytes()
    assert doc['inputs_unchanged'] and not doc['fixture_writes']
    raw=(root/'Item-list-ewram.bin').read_bytes()
    assert len(raw)==0x40000 and hashlib.sha256(raw).hexdigest()==doc['capture_sha256']['Item-list-ewram.bin']
    memory=Memory(raw);member=doc['groups']['member'];owner=doc['owner']
    reader=OwnedItemList(memory,rom,owner,member);token=reader.snapshot();reader.revalidate(token)
    potion_count=doc['inventory_before']['items']['362']['available']
    assert token.items[0][1:5]==(362,'Potion',251,potion_count)
    assert len(token.items)==13 and token.excluded_rows==((15,265,'Draw Weapon: no consumable count'),)
    assert all(row[1]!=366 for row in token.items)
    rejected=[]
    def reject(label,address,value,size=4):
        g=Memory(raw);r=OwnedItemList(g,rom,owner,member);t=r.snapshot();g.put(address,value,size)
        try:r.revalidate(t)
        except RecoveryStateError as exc:rejected.append({'case':label,'reason':str(exc)})
        else:raise AssertionError('accepted '+label)
    for label,offset,value,size in [('KO actor',0x18,0,2),('actor MP changed',0x1C,0,2),
            ('foreign id',0x104,20,1),('foreign name',0,0,4),('race changed',6,0,1),
            ('job changed',7,7,1),('secondary Item removed',0x36,9,1),('enemy side',0x29,128,1)]:
        reject(label,member+offset,value,size)
    b=reader.bound
    for label,address,value,size in [
        ('foreign menu owner',b.context+0x18,MEMBERS if member!=MEMBERS else MEMBERS+STRIDE,4),
        ('wrong mode',b.context+4,6,1),('wrong action group',b.context+0x10,1,2),
        ('callback moved',b.context+0x28,0,4),('manager moved',b.context+0x20,0,4),
        ('foreign driver owner',PLAYER_DRIVER+4,0,4),('foreign driver peer',PLAYER_DRIVER+8,0,4),
        ('active target processor',PLAYER_DRIVER+0x60,0x02020000,4),
        ('wrong driver state',PLAYER_DRIVER+0xDC,0x25,2),
        ('nonaccepting callback',b.callback+0x14,0x106,2),
        ('wrong handler',b.callback,0,4),('invalid menu race',b.callback+0x18+0xA,1,1),
        ('invalid cursor',b.callback+0x18+0x69,99,1),('zero row count',b.callback+0x18+0x50,0,2),
        ('short inventory pointer',b.callback+0x18+0x94,0x03000000,4),
        ('zero Potion count',INVENTORY+2,0,1),('last Potion invalidates old token',INVENTORY+2,1,1),
        ('reserved Potion invalidates old token',INVENTORY+3,1,1),
        ('aliased item id',INVENTORY+4,362,2),('foreign inventory id',INVENTORY,361,2),
        ('aliased canonical id',MEMBERS+2*STRIDE+0x104,owner['id'],1),
        ('changed native availability flag13',0x0200203D,1,1),
        ('unknown native availability flag13',0x0200203D,2,1),
    ]:reject(label,address,value,size)
    obj=bytes.fromhex(doc['raw_list']['object']);pointer=int.from_bytes(obj[0x94:0x98],'little')
    reject('row alias',pointer+4,1)
    reject('invalid row',pointer,99)
    flagptr=int.from_bytes(obj[0x98:0x9C],'little')
    reject('invalid enabled byte',flagptr,2,1)
    reject('stale engine disabled flag',flagptr,0,1)
    g=Memory(raw);g.put(flagptr,0,1)
    t=OwnedItemList(g,rom,owner,member).snapshot()
    assert t.items[0][-1] is False
    g=Memory(raw)
    g.put(member+0xE9,g.read_mem(member+0xE9,1)[0]|1,1)
    try:OwnedItemList(g,rom,owner,member).snapshot()
    except RecoveryStateError as exc:rejected.append({'case':'fresh Frog with stale enabled Potion','reason':str(exc)})
    else:raise AssertionError('fresh stale status/enable combination accepted')
    result={'status':'pass','scope':__doc__,'joined':token.receipt(),'rejected':rejected,
            'checks':[f'native Potion {potion_count} and Ether 6 joined','absent Elixir zero excluded',
                      'Draw Weapon row15 has no count and is excluded','disabled native row stays disabled'],
            'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                ['tools/consumable_menu.py','tools/consumable_inventory.py','tools/validate_consumable_menu.py']},
            'evidence_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                [root/'inventory.json',root/'Item-list-ewram.bin']},
            'limitations':['Retained live RAM replay; target/law legality and consumption remain UNKNOWN.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS owned Item inventory join:',len(rejected),'mutations')


if __name__=='__main__':main()
