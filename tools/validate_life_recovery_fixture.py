"""Reject unaccepted Life fixture variants before transaction navigation."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_life_effect import validate_life_fixture
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture',required=True)
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.capture)
    doc=json.loads((root/'Life-overlay.json').read_text());path=root/'final-prompt-second-ewram.bin';raw=path.read_bytes()
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    require(sha(path)==doc['capture_sha256'][path.name],'fixture replay capture differs')
    units={p['canonical']:raw[p['canonical']-0x02000000:p['canonical']-0x02000000+STRIDE] for p in doc['party']}
    valid=validate_life_fixture(doc['party'],units);rejected=[]
    for role,address in [('caster',0x02000188),('target',0x02000080)]:
        for offset in (0,4,5,6,7,9,0x18,0x1A,0x1C,0x1E,0xF2,0xF6,0x104):
            changed=deepcopy(units);unit=bytearray(changed[address]);unit[offset]^=1;changed[address]=bytes(unit)
            try:validate_life_fixture(doc['party'],changed)
            except ValueError:rejected.append(role+'-'+hex(offset))
            else:raise AssertionError('unaccepted fixture authorized before input')
    for offset in (8,10,0x35,0x36,0x3B):
        changed=deepcopy(units);unit=bytearray(changed[0x02000188]);unit[offset]^=1;changed[0x02000188]=bytes(unit)
        try:validate_life_fixture(doc['party'],changed)
        except ValueError:rejected.append('caster-'+hex(offset))
        else:raise AssertionError('unaccepted caster EXP/ability-state authorized')
    output={'status':'pass-Life-pre-navigation-fixture','scope':__doc__,'valid':valid,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/recovery_life_effect.py','tools/validate_life_recovery_fixture.py']},
        'evidence_sha256':{str(path):sha(path)},'limitations':['Retained pre-navigation gate; no new live execution.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life pre-navigation fixture:',len(rejected),'mutations')


if __name__=='__main__':main()
