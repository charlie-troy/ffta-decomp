"""Verify consumable research capture bytes, input scope and source closure."""
import argparse
import hashlib
import json
from pathlib import Path

from recovery_source_versions import verify_source_versions
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True)
    ap.add_argument('--source-ref',action='append',default=[])
    ap.add_argument('--source-dir',action='append',default=[])
    ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.capture);path=root/'inventory.json'
    doc=json.loads(path.read_text())
    require(doc['inputs_unchanged'] and not doc['fixture_writes'],'source-tainted or edited capture')
    require(doc['status'] in ('pass-live-owned-Item-list-and-inventory-reader',
                             'pass-owned-Item-reader-with-unaccepted-Potion-overlay'),'incomplete research capture')
    require(doc['owner']['id']==5 and doc['groups']['rows'].count(1)==1
            and doc['item_group_title']['title']=='Item','unexpected Item actor/group')
    for name,digest in doc['capture_sha256'].items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,'capture bytes changed: '+name)
    sources={p:h for p,h in doc['source_sha256'].items() if p.startswith('tools/') and p.endswith('.py')}
    closure=verify_source_versions(sources,'probe_consumable_inventory',args.source_ref,args.source_dir)
    for p,digest in doc['source_sha256'].items():
        if p not in sources:require(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest,'source asset changed: '+p)
    for key in doc['inputs']:
        require(key['hits']==5 and key['mask'] in (1,64,128),'unexpected research key')
        if 'before_Item' in key:
            require(key['mask']==1 and key['before_Item']['rows'][key['before_Item']['scroll']+
                key['before_Item']['cursor']]==1,'overlay input did not select Potion')
        else:
            token=key['before'];require(token['state'] in ('command','action-group'),'input beyond open-list route')
            if key['mask']==1:
                row=token['rows'][token['scroll']+token['cursor']]
                require(row==(9 if token['state']=='command' else 1),'foreign navigation selection')
    require(len(doc['gameplay_writes'])==5*len(doc['inputs']),'partial/unaccounted raw input writes')
    for index,key in enumerate(doc['inputs']):
        writes=doc['gameplay_writes'][index*5:index*5+5]
        require(all(w['hits']==i+1 and w['val']&key['mask']==key['mask'] and not w['manual']
                    for i,w in enumerate(writes)),'raw input mask/hit attribution differs')
    require(sum('before_Item' in key for key in doc['inputs'])<=1,'repeated Potion selection')
    joined=doc['joined_item_list']
    require(joined['inventory_sha256']==doc['inventory_before']['sha256'],'inventory changed before Item join')
    if 'Potion_overlay_raw' in doc:
        require(doc['Potion_overlay_raw']['inventory_unchanged'] is True,'overlay consumed inventory')
    result={'status':'pass','scope':__doc__,'closure':closure,'input_count':len(doc['inputs']),
            'raw_writes':len(doc['gameplay_writes']),
            'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                ['tools/audit_consumable_capture.py','tools/recovery_source_versions.py']},
            'evidence_sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest()},
            'limitations':['Research provenance and open-list/overlay input scope only; no legal use or HP effect.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS consumable capture:',len(closure),'source modules;',len(doc['inputs']),'guarded navigation presses')


if __name__=='__main__':main()
