"""Execute the bounded retail HP/Petrify classifier fragment; not KO lifecycle proof."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from emulate import Gba
from status_flags import STATUS_FLAGS


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--rom',default='baserom.gba');ap.add_argument('--out',required=True)
    args=ap.parse_args();unit=0x02002000
    petrify=next(x for x in STATUS_FLAGS if x['name']=='petrify')
    snapshot=next(x for x in STATUS_FLAGS if x['name']=='petrify_critical_snapshot')
    cases=[]
    for hp,pet,snap,expected in ((0,0,0,1),(1,0,0,2),(25,0,0,2),(26,0,0,3),
                                  (0,1,0,1),(0,1,1,1),(100,1,0,3),(100,1,1,2)):
        gba=Gba(args.rom);gba.uc.mem_write(unit,bytes(0x200))
        gba.write8(unit+petrify['offset'],petrify['mask'] if pet else 0)
        gba.call(snapshot['setter'],[unit,snap]);gba.uc.mem_write(unit+0x18,struct.pack('<HH',hp,100))
        observed=gba.run_range(0x080A2218,0x080A225E,{'r0':unit,'r6':unit})
        assert observed==expected,(hp,pet,snap,observed,expected)
        cases.append({'hp':hp,'max_hp':100,'petrify':pet,'critical_snapshot':snap,'class':observed})
    sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
        'tools/validate_recovery_ko_classifier.py','tools/emulate.py','tools/status_flags.py')}
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'status':'pass-bounded-ROM-fragment','scope':__doc__,
        'rom_sha256':hashlib.sha256(Path(args.rom).read_bytes()).hexdigest(),
        'start':'080A2218','stop':'080A225E','source_sha256':sources,'cases':cases,
        'limitations':['Synthetic unit inputs; no live KO, fixture reload, target acceptance or revival.',
                       'Numeric classes distinguish HP0 from living HP; the surrounding lifecycle is not executed.']},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS bounded KO classifier: {len(cases)} actual-ROM cases; lifecycle unknown')


if __name__=='__main__':main()
