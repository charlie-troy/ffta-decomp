"""Execute actual ROM panel branches on retained preview RAM; no live input or cast claim.

Identifies the cached-name rendering path. It does not decode bitmap pixels or
prove which earlier draw produced the displayed Blizzard label.
"""
import argparse
import hashlib
import json
from pathlib import Path

from emulate import Gba, REGS
from ffta_text import decode1
from recovery_menu import integer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',default='outputs/autobattle/a62-ally-panel-02')
    parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.capture)
    doc=json.loads((folder/'probe.json').read_text())
    assert doc['status']=='captured-preview-panel-only' and doc['inputs_unchanged'] and not doc['fixture_writes']
    assert len(doc['raw_writes'])==40
    for path,digest in doc['source_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    for name,digest in doc['capture_sha256'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
    raw=(folder/'preview-ewram.bin').read_bytes();assert len(raw)==0x40000
    get=lambda a,s=4:integer(raw,a-0x02000000,s)
    root=get(0x0200F440);callback=get(root+12);payload=callback+0x18
    canonical=get(payload+12);flags=get(payload+0x10,2)
    assert get(callback)==0x0802D551 and canonical==0x02000188
    name=get(canonical);rom=Path('baserom.gba').read_bytes()
    assert decode1(rom,name-0x08000000)[0]=='Montblanc'
    assert get(canonical+0x18,2)==100 and get(canonical+0x1C,2)==221
    assert flags & 2
    gba=Gba('baserom.gba');gba.uc.mem_write(0x02000000,raw)
    # Execute the observed branch up to its initial buffer-clear helper.
    # Execute the following copy-argument fragment separately, omitting that
    # BIOS-backed clear; this is not whole-function or graphics emulation.
    gba.run_range(0x0802C8C4,0x0802C8E8,{'r0':payload})
    assert gba.uc.reg_read(REGS['r4'])==payload+0x28
    gba.run_range(0x0802C8EC,0x0802C8FE,{'r6':payload,'r4':payload+0x28})
    copied={r:gba.uc.reg_read(REGS[r]) for r in ('r0','r1','r2')}
    assert copied=={'r0':payload+0x28,'r1':root+0x8FC,'r2':0x100},copied
    # Negative control clears only the cache flag and must reach the name
    # accessor branch rather than the preceding bitmap-copy destination.
    gba.uc.mem_write(payload+0x10,(flags & ~2).to_bytes(2,'little'))
    gba.run_range(0x0802C8C4,0x0802C988,{'r0':payload})
    assert gba.uc.reg_read(REGS['r6'])==payload
    # Execute the actual getter call with that payload. The captured unit
    # reference supplies Montblanc, never Blizzard's UI-table pointer.
    pointer=gba.run_range(0x0802C9A0,0x0802C9A8,{'r6':payload})
    assert pointer==name
    assert pointer!=int.from_bytes(rom[0x5567F0+419*4:0x5567F0+419*4+4],'little')
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'capture':args.capture,
        'rom_sha256':hashlib.sha256(rom).hexdigest(),'preview_panel':{'root':root,'callback':callback,
        'payload':payload,'flags':flags,'canonical':canonical,'name':name,'name_text':'Montblanc'},
        'observed_cache_branch':copied,'cleared_cache_flag_name_pointer':pointer,
        'verdict':'Captured preview selects cached bitmap branch; canonical/name-accessor join remains Montblanc',
        'unknown':'Provenance and pixel interpretation of the cached Blizzard label'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS actual cache/name ROM branches; cached bitmap provenance remains unknown')


if __name__=='__main__':main()
