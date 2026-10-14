"""Audit the bounded Law Cards observation; do not authorize item use.

The active IDs match the inspected panel labels at MAIN_STRINGS[625+ID].
That name join is an inference for these three observed IDs, not a decoded
general law accessor or evidence that Potion complies with the Skills law.
"""
import argparse
import hashlib
import json
from pathlib import Path

from emulate import Gba, STOP
from unicorn.arm_const import UC_ARM_REG_PC
from ffta_names import Names, MAIN_STRINGS
from recovery_source_versions import verify_source_versions


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True)
    ap.add_argument('--source-ref',action='append',default=[])
    args=ap.parse_args();root=Path(args.capture);path=root/'law-menu.json';doc=json.loads(path.read_text())
    assert doc['status']=='observed-Law-Cards-open-only' and doc['inputs_unchanged']
    assert not doc['fixture_writes'] and doc['inventory_unchanged']
    pins={p:h for p,h in doc['source_sha256'].items() if p.startswith('tools/')}
    closure=verify_source_versions(pins,'probe_consumable_law_menu',args.source_ref)
    for file,digest in doc['source_sha256'].items():
        if file not in pins:assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==digest
    for name,digest in doc['capture_sha256'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
    assert doc['press']=={'mask':2,'hits':5} and doc['field_START']['mask']==8
    assert [p['mask'] for p in doc['System_inputs']]==[128,128,1]
    assert [p['before']['cursor'] for p in doc['System_inputs']]==[0,1,2]
    masks=[2,8,128,128,1];writes=doc['gameplay_writes'];assert len(writes)==25
    for index,mask in enumerate(masks):
        assert all(w['val']&mask==mask and w['hits']==i+1 and not w['manual']
                   for i,w in enumerate(writes[index*5:index*5+5]))
    raw=(root/'after-ewram.bin').read_bytes();before=(root/'before-ewram.bin').read_bytes()
    assert len(raw)==len(before)==0x40000
    law=raw[0x3C32:0x3C3C];assert law==before[0x3C32:0x3C3C]
    assert law[0]==4
    ids=[int.from_bytes(law[2+i*2:4+i*2],'little') for i in range(4)]
    assert ids==[1,82,42,0]
    gba=Gba(args.rom);gba.uc.mem_write(0x02000000,raw)
    actual=gba.call(0x0802D764,[]);assert actual==3 and gba.uc.reg_read(UC_ARM_REG_PC)==STOP
    names=Names(gba.rom);labels=[names._string(MAIN_STRINGS,625+i) for i in ids if i]
    assert labels==['Skills','Dmg2: Animal','Broadswords']
    controls=[]
    for values in [[0,0,0,0],[1,0,0,0],[1,82,42,0]]:
        gba.uc.mem_write(0x02003C34,b''.join(i.to_bytes(2,'little') for i in values))
        count=gba.call(0x0802D764,[])
        assert count==sum(bool(i) for i in values) and gba.uc.reg_read(UC_ARM_REG_PC)==STOP
        controls.append({'isolated_ids':values,'native_nonzero_count':count})
    result={'status':'pass-source-and-active-law-observation','scope':__doc__,'closure':closure,
        'capacity_address':'02003C32','active_ids_address':'02003C34','native_count_accessor':'0802D764',
        'active_ids':ids,'native_count':actual,'inferred_names_matching_inspected_panel':labels,
        'observed_recommended_labels':['Techniques','Status','Spears'],'isolated_count_controls':controls,
        'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in ['tools/validate_consumable_law_capture.py','tools/recovery_source_versions.py']},
        'evidence_sha256':{str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ['law-menu.json','before-ewram.bin','after-ewram.bin','battle-menu.png']},
        'limitations':['Recommended-ID mapping not decoded.','Current Skills-law classification of Potion is UNKNOWN.',
                       'No card application, item selection, target acceptance or consumption.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS source closure, guarded Law Cards route and native active-law count; Potion law compliance UNKNOWN')


if __name__=='__main__':main()
