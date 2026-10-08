"""Exercise read-only status decoding under the actual small-packet constraint."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from fixture_guard import ROSTER, STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, require
from recovery_boundary_diagnostic import capture_boundary_diagnostic


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True)
    args=ap.parse_args();memory=bytearray(0x40000);reads=[]
    for base,slot,unit_id in [(ROSTER,5,5),(ROSTER,7,7),(MEMBERS,1,5),(MEMBERS,0,7)]:
        start=base-0x02000000+slot*STRIDE
        memory[start:start+4]=(0x08001234+unit_id).to_bytes(4,'little')
        memory[start+0x104]=unit_id
    def read(address,size):
        require(size<=0x200,'diagnostic exceeds mGBA packet bound')
        reads.append((address,size));offset=address-0x02000000
        return memory[offset:offset+size]
    # Deliberately no write/press/continue methods: this reader has no authority.
    g=SimpleNamespace(read_mem=read)
    probe=SimpleNamespace(read_target_cursor=lambda:(5,10),read_cmd_cursor=lambda:0)
    negative=capture_boundary_diagnostic(g,probe)
    require(len(reads)==8+MEMBER_COUNT,'diagnostic did not read each complete unit')
    require(all(not r['sleep'] for rows in negative['party'].values() for r in rows),
            'negative Sleep decoder differs')
    for rows in negative['party'].values():
        require({r['id'] for r in rows}=={5,7},'diagnostic identity inclusion differs')
        for row in rows:
            offset=row['address']-0x02000000;memory[offset+0xEB]=4;memory[offset+0xDF]=3
    positive=capture_boundary_diagnostic(g,probe)
    require(all(r['sleep'] and r['sleep_duration']==3 and r['status_EB']==4
                for rows in positive['party'].values() for r in rows),'positive Sleep decode differs')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-read-only-boundary-diagnostic','scope':__doc__,
        'checks':['all22 units read below512 byte packet bound','unique fixture identities',
                  'Sleep absent','Sleep flag and duration present','no input or write API'],
        'source_sha256':{p:sha(p) for p in ['tools/recovery_boundary_diagnostic.py',
            'tools/validate_recovery_boundary_diagnostic.py']},
        'limitations':['Host decoder controls only; native Sleep requires a live diagnostic capture.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS read-only diagnostic: packet-bound, identity, Sleep positive/negative controls')


if __name__=='__main__':main()
