"""Execute the retail law matcher on pinned self-Potion facts, with a violating control.

081343C8(source,target,ability,action_flag,phase,amount,effect_bits,law_entry)
is called by 08134B88 (e.g.0813504E..08135072). Stack arguments are ABI words.
This isolates the matcher; it does not claim an observed live invocation,
validated action-result queue, final-prompt legality or item execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from emulate import Gba,STOP
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.capture);doc=json.loads((root/'inventory.json').read_text())
    raw=(root/'Potion-preview-ewram.bin').read_bytes()
    require(doc['inputs_unchanged'] and hashlib.sha256(raw).hexdigest()==doc['capture_sha256']['Potion-preview-ewram.bin'],
            'invalid preview capture bytes/source')
    member=doc['groups']['member'];require(member==0x02000188 and doc['Potion_overlay']['item_id']==362,
                                         'not the bounded self-Potion fixture')
    require(raw[member-0x02000000+0x18:member-0x02000000+0x1A]==b'\x64\x00','source is not wounded100')
    active=[int.from_bytes(raw[0x3C34+i*2:0x3C36+i*2],'little') for i in range(raw[0x3C33])]
    require(active==[1,82,42],'active-law fixture changed')
    cases=[]
    for law in active+[20]:
        for amount in [-30,0,30]:
            gba=Gba(args.rom);gba.uc.mem_write(0x02000000,raw)
            pcs=[];writes=[]
            def code(uc,address,size,user):
                if 0x081343C8<=address<=0x08134A00:pcs.append(address)
            def write(uc,access,address,size,value,user):
                if 0x02000000<=address<0x02040000:writes.append([address,size,value])
            gba.uc.hook_add(UC_HOOK_CODE,code);gba.uc.hook_add(UC_HOOK_MEM_WRITE,write)
            require(gba.call(0x08133D78,[member,251])==1,'native Potion action-set lookup differs')
            # Gba.call sets SP=03007F00. These four words remain above the
            # callee frame, exactly as the observed ARM caller prepares them.
            gba.uc.mem_write(0x03007F00,struct.pack('<IIII',0,amount&0xFFFFFFFF,0,0x08528F34+law*16))
            outcome=gba.call(0x081343C8,[member,member,251,0])
            require(gba.uc.reg_read(UC_ARM_REG_PC)==STOP,'law matcher did not return normally')
            require(outcome==(1 if law==20 else 0),'law matcher fails active/Items discrimination')
            require(not writes and bytes(gba.uc.mem_read(0x02000000,0x40000))==raw,'matcher changed EWRAM')
            cases.append({'law':law,'amount_probe':amount,'match':outcome,'branch_sha256':
                hashlib.sha256(b''.join(a.to_bytes(4,'little') for a in pcs)).hexdigest(),
                'instruction_count':len(pcs),'native_action_set':1,'EWRAM_writes':writes})
    result={'status':'pass-isolated-Potion-law-matcher','scope':__doc__,'active_laws':active,'cases':cases,
        'native_law_table':'08528F34/stride10','matcher':'081343C8','action_set_lookup':'08133D78',
        'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ['tools/validate_consumable_law_predicate.py','tools/emulate.py',args.rom]},
        'evidence_sha256':{str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ['inventory.json','Potion-preview-ewram.bin']},
        'limitations':['Isolated native matcher, not an observed live call or law-compliant action queue.',
                       'Preview screenshot has Blizzard/damage fields despite Potion selection; unresolved.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS isolated native law matcher:',len(cases),'cases, active laws clear / Items20 matches')


if __name__=='__main__':main()
