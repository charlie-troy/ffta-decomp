"""Join retained native final Potion context to actual schema2 policy decisions."""
import argparse,json,hashlib
from pathlib import Path
from validate_consumable_menu import Memory
from consumable_menu import OwnedItemList
from consumable_final import PotionFinalPromptReader
from consumable_policy import potion_snapshot,POTION_CANDIDATE
from tactics_policy import load_policy_file,evaluate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.capture);d=json.loads((root/'inventory.json').read_text());rom=Path('baserom.gba').read_bytes();checks=[]
    explicit=load_policy_file('configs/tactics/potion-self.json');default=load_policy_file('configs/tactics/healer.json')
    for label,count,hp,policy,selected in [('enabled',2,100,explicit,True),('default disabled',2,100,default,False),
        ('last item policy',1,100,explicit,False),('above threshold',2,125,explicit,False)]:
        initial=Memory((root/'Item-list-ewram.bin').read_bytes());final=Memory((root/'Potion-final-prompt-ewram.bin').read_bytes())
        for m in [initial,final]:m.put(0x02001EE6,count,1);m.put(0x02000188+0x18,hp,2)
        menu=OwnedItemList(initial,rom,d['owner'],0x02000188);origin=menu.snapshot();reader=PotionFinalPromptReader(menu,origin)
        initial.raw=final.raw;token=reader.snapshot();snapshot=potion_snapshot(reader,token,d['owner']);decision=evaluate(snapshot,policy)
        assert ((decision.get('decision') or {}).get('candidate_id')==POTION_CANDIDATE)==selected
        checks.append({'case':label,'selected':selected})
    result={'status':'pass','scope':__doc__,'checks':checks,'source_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
        for f in ['tools/consumable_policy.py','tools/validate_potion_policy.py','configs/tactics/potion-self.json']},
        'limitations':['Native final reader replay plus policy evaluation; modified count/HP cases are host memory controls.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS Potion native-policy join:',len(checks),'controls')


if __name__=='__main__':main()
