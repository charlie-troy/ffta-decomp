"""Retained final prompt ownership/resource corruptions must block manual B."""
import argparse,json
from pathlib import Path
from validate_consumable_menu import Memory
from potion_manual_cancel import PotionManualCancel
from recovery_menu import PLAYER_DRIVER,STRIDE


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    root=Path(args.capture);d=json.loads((root/'inventory.json').read_text());raw=(root/'Potion-final-prompt-ewram.bin').read_bytes();rom=Path('baserom.gba').read_bytes()
    def fixture():
        g=Memory(raw);r=PotionManualCancel(g,rom,d['owner'],g.read_mem(0x02000188,STRIDE),d['inventory_before']['raw']);return g,r
    g,r=fixture();assert r.snapshot()['mode']==11;rejected=[]
    changes=[('owner',r.menu.context+0x18,0,4),('ability',r.menu.context+0x14,29,4),('wrapper',PLAYER_DRIVER+4,0,4),
        ('unit HP',0x020001A0,101,2),('count',0x02001EE6,1,1),('handler',r.menu.callback,0,4),
        ('callback state',r.menu.callback+0x14,0,2),('driver state',PLAYER_DRIVER+0xDC,0,2),
        ('driver flags',PLAYER_DRIVER+0xD0,0,4),('mode',r.menu.context+4,0,1)]
    for label,a,v,n in changes:
        g,r=fixture();g.put(a,v,n)
        try:r.snapshot()
        except ValueError:rejected.append(label)
        else:raise AssertionError('manual B ownership accepted '+label)
    Path(args.out).write_text(json.dumps({'status':'pass','scope':__doc__,'rejected':rejected,
        'limitations':['Read-only retained final prompt controls; actual window cancellation tested separately.']},indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS manual cancel reader:',len(rejected),'corruptions')


if __name__=='__main__':main()
