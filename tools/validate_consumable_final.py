"""Reject wrong actor/item/law/count or non-final Potion prompt tokens."""
import argparse,json,hashlib
from pathlib import Path
from consumable_final import PotionFinalPromptReader
from consumable_menu import OwnedItemList
from recovery_menu import RecoveryStateError,PLAYER_DRIVER,MEMBERS,STRIDE
from fixture_guard import BATTLE_STRUCT
from validate_consumable_menu import Memory


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.capture);doc=json.loads((root/'inventory.json').read_text());rom=Path(args.rom).read_bytes()
    initial=(root/'Item-list-ewram.bin').read_bytes();raw=(root/'Potion-final-prompt-ewram.bin').read_bytes()
    def reader():
        g=Memory(initial);menu=OwnedItemList(g,rom,doc['owner'],doc['groups']['member']);item=menu.snapshot()
        r=PotionFinalPromptReader(menu,item,rom_path=args.rom);g.raw=bytearray(raw);return g,r
    g,r=reader();token=r.snapshot();r.revalidate(token);b=r.menu.bound;rejected=[]
    for label,address,value,size in [
        ('wrong ability',b.context+0x14,29,4),('wrong peer',b.context+0x1C,0,4),
        ('wrong mode',b.context+4,12,1),('wrong source',b.context+0x18,MEMBERS,4),
        ('wrong callback',b.callback,0,4),('wrong callback state',b.callback+0x14,3,2),
        ('Cancel selected',b.callback+0x18+0x69,1,1),('wrong driver',PLAYER_DRIVER+0xDC,0x4B,2),
        ('wrong processor ability',BATTLE_STRUCT+0xEC,29,2),('wrong processor state',BATTLE_STRUCT+0x1118,10,2),
        ('wrong final flags',BATTLE_STRUCT+0x1112,0x6C,2),('wrong target wrapper',BATTLE_STRUCT+8,0,4),
        ('foreign accepted source',BATTLE_STRUCT+12,0,4),('already committed target',BATTLE_STRUCT+16,1,4),
        ('changed HP',b.member+0x18,1,2),('changed count',0x02001EE6,1,1),
        ('unknown law',0x02003C34,83,2),('duplicate law',0x02003C36,1,2),
        ('extra law',0x02003C33,4,1),('Items law forbids Potion',0x02003C34,20,2),
        ('target tile changed',BATTLE_STRUCT+0x109,0,2),('aliased source id',MEMBERS+2*STRIDE+0x104,5,1)]:
        g,r=reader();old=r.snapshot();g.put(address,value,size)
        try:r.revalidate(old)
        except RecoveryStateError as exc:rejected.append({'case':label,'reason':str(exc)})
        else:raise AssertionError('accepted '+label)
    assert token.law_matches==((1,0),(82,0),(42,0)) and token.law_control==(20,1)
    result={'status':'pass','scope':__doc__,'final_prompt':token.receipt(),'rejected':rejected,
        'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ['tools/consumable_final.py','tools/validate_consumable_final.py']},
        'evidence_sha256':{str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ['inventory.json','Item-list-ewram.bin','Potion-final-prompt-ewram.bin']},
        'limitations':['Read-only final context and isolated native law predicates; no actual item use or effect queue claim.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Potion final context:',len(rejected),'mutations and native Items-law control')


if __name__=='__main__':main()
