"""Reject wrong-source, stale-count and already-accepted Potion overlays."""
import argparse
import hashlib
import json
from pathlib import Path

from consumable_menu import OwnedItemList
from consumable_overlay import PotionOverlayReader
from consumable_inventory import INVENTORY
from fixture_guard import BATTLE_STRUCT
from recovery_menu import RecoveryStateError, PLAYER_DRIVER, MEMBERS, STRIDE
from validate_consumable_menu import Memory


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True);ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.capture);doc=json.loads((root/'inventory.json').read_text());rom=Path(args.rom).read_bytes()
    initial=(root/'Item-list-ewram.bin').read_bytes();overlay=(root/'Potion-overlay-ewram.bin').read_bytes()
    for name,raw in [('Item-list-ewram.bin',initial),('Potion-overlay-ewram.bin',overlay)]:
        assert hashlib.sha256(raw).hexdigest()==doc['capture_sha256'][name]
    member=doc['groups']['member']
    def reader():
        g=Memory(initial);menu=OwnedItemList(g,rom,doc['owner'],member);origin=menu.snapshot()
        r=PotionOverlayReader(menu,origin);g.raw=bytearray(overlay);return g,r
    memory,r=reader();token=r.snapshot();r.revalidate(token);rejected=[]
    b=r.menu.bound
    edits=[('wrong selected ability',b.context+0x14,5,4),('wrong selection',b.context,2,2),
        ('foreign overlay peer',b.context+0x1C,0,4),('wrong overlay mode',b.context+4,12,1),
        ('foreign source wrapper',BATTLE_STRUCT,0,4),('foreign target wrapper',BATTLE_STRUCT+0x50,0,4),
        ('extra target',BATTLE_STRUCT+0xA2,2,1),('invalid target index',BATTLE_STRUCT+0xA1,1,1),
        ('accepted source copy',BATTLE_STRUCT+12,1,4),('accepted target copy',BATTLE_STRUCT+16,1,4),
        ('wrong processor ability',BATTLE_STRUCT+0xEC,1,2),('final state already active',BATTLE_STRUCT+0x1118,2,2),
        ('confirmation flag',BATTLE_STRUCT+0x1112,32,2),('foreign target processor',PLAYER_DRIVER+0x60,0,4),
        ('wrong driver state',PLAYER_DRIVER+0xDC,0x4B,2),('cached UI still owns input',b.manager+4,b.callback,4),
        ('non-target callback',b.callback+0x14,0x102,2),('HP changed',member+0x18,1,2),
        ('inventory consumed',INVENTORY+2,max(0,token.count-1),1),('cursor x differs',0x0200F3B8,30,2),
        ('cursor y differs',0x0200F3BC,30,2),('law flag changed',0x0200203D,1,1),
        ('canonical source alias',MEMBERS+2*STRIDE+0x104,doc['owner']['id'],1),
        ('foreign driver peer',PLAYER_DRIVER+8,0,4),('foreign wrapped target',b.wrapper,0,4)]
    for label,address,value,size in edits:
        g,reader1=reader();t=reader1.snapshot();g.put(address,value,size)
        try:reader1.revalidate(t)
        except RecoveryStateError as exc:rejected.append({'case':label,'reason':str(exc)})
        else:raise AssertionError('accepted '+label)
    result={'status':'pass','scope':__doc__,'overlay':token.receipt(),'rejected':rejected,
            'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                ['tools/validate_consumable_overlay.py','tools/consumable_overlay.py']},
            'evidence_sha256':{str(root/name):hashlib.sha256((root/name).read_bytes()).hexdigest()
                for name in ['inventory.json','Item-list-ewram.bin','Potion-overlay-ewram.bin']},
            'limitations':['Target overlay identity only; no legal final item confirmation or consumption.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Potion overlay:',len(rejected),'mutations')


if __name__=='__main__':main()
