"""Replay native Potion description ownership and reject stale prompt-inspection authority."""
import argparse
import hashlib
import json
from pathlib import Path
from consumable_description import PotionDescriptionReader,PotionPromptInspectionGate
from consumable_menu import OwnedItemList
from consumable_overlay import PotionOverlayReader
from recovery_menu import RecoveryStateError,PLAYER_DRIVER
from fixture_guard import BATTLE_STRUCT
from validate_consumable_menu import Memory


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.capture);doc=json.loads((root/'inventory.json').read_text());rom=Path(args.rom).read_bytes()
    initial=(root/'Item-list-ewram.bin').read_bytes();raw=(root/'Potion-preview-ewram.bin').read_bytes()
    def reader():
        g=Memory(initial);menu=OwnedItemList(g,rom,doc['owner'],doc['groups']['member']);item=menu.snapshot()
        r=PotionDescriptionReader(menu,item);g.raw=bytearray(raw);return g,r
    g,r=reader();token=r.snapshot();r.revalidate(token);b=r.menu.bound;rejected=[]
    for label,address,value,size in [('wrong ability',b.context+0x14,29,4),('wrong callback',b.callback,0,4),
            ('unaccepted overlay',b.callback+0x14,3,2),('wrong driver',PLAYER_DRIVER+0xDC,0x4B,2),
            ('wrong preview flags',BATTLE_STRUCT+0x1112,0,2),('wrong target',BATTLE_STRUCT+8,0,4),
            ('accepted final target',BATTLE_STRUCT+16,1,4),('HP changed',b.member+0x18,1,2),
            ('committed tile changed',BATTLE_STRUCT+0x109,0,2)]:
        g,r=reader();old=r.snapshot();g.put(address,value,size)
        try:r.revalidate(old)
        except RecoveryStateError:rejected.append(label)
        else:raise AssertionError('accepted '+label)
    class Transport:
        def __init__(self):self.writes=0
        def press(self,mask,**kwargs):
            assert mask==1 and kwargs['tag']=='a66-Potion-final-prompt-inspection-only'
            self.writes+=1;return 5
    g,r=reader();p=Transport();gate=PotionPromptInspectionGate(r,p);gate.advance(r.snapshot());assert p.writes==1
    try:gate.advance(token)
    except RecoveryStateError:pass
    else:raise AssertionError('prompt inspection retried')
    assert p.writes==1
    g,r=reader();p=Transport();gate=PotionPromptInspectionGate(r,p,stop_check=lambda:True)
    try:gate.advance(r.snapshot())
    except RecoveryStateError:pass
    else:raise AssertionError('STOP permitted prompt inspection')
    assert p.writes==0
    result={'status':'pass','scope':__doc__,'description':token.receipt(),'rejected':rejected,
        'checks':['exactly one prompt-inspection input','retry forbidden','STOP gives zero input'],
        'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ['tools/consumable_description.py','tools/validate_consumable_description.py']},
        'evidence_sha256':{str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ['inventory.json','Item-list-ewram.bin','Potion-preview-ewram.bin']},
        'limitations':['Description ownership only; no coherent effect queue, law compliance or final item input.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Potion description:',len(rejected),'mutations and prompt-only/STOP controls')


if __name__=='__main__':main()
