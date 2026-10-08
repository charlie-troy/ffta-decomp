"""Retained actual Life/level-up replay and adversarial attribution checks."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_life_effect import verify_life_effect
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();directory=Path(args.capture)
    doc=json.loads((directory/'Life-overlay.json').read_text())
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths=[directory/n for n in ('final-prompt-second-ewram.bin','after-Life-ewram.bin')]
    require(doc['inputs_unchanged'] and not doc['fixture_writes'] and doc['final_confirmation']
            and doc.get('effect_attribution'),'missing accepted Life effect')
    for p in paths:require(sha(p)==doc['capture_sha256'][p.name],'Life effect capture hash differs')
    caster=next(p for p in doc['party'] if p['id']==5);target=next(p for p in doc['party'] if p['id']==7)
    units=lambda path:{p['canonical']:path.read_bytes()[p['canonical']-0x02000000:
                          p['canonical']-0x02000000+STRIDE] for p in doc['party']}
    before,after=map(units,paths);hits=doc['life_engine_hits']
    valid=verify_life_effect(before,after,hits,caster,target)
    rejected=[]
    def reject(label,edit):
        b,a,h=deepcopy(before),deepcopy(after),deepcopy(hits);edit(b,a,h)
        try:verify_life_effect(b,a,h,caster,target)
        except (ValueError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted Life effect mutation: '+label)
    for phase in ('EXP-award','level-up-before','level-up-after','HP-store-before','HP-store-after',
                  'Life-effect-entry','Life-effect-flags-written'):
        reject('missing-'+phase,lambda b,a,h,p=phase:h.__setitem__(slice(None),[r for r in h if r['phase']!=p]))
        reject('duplicate-'+phase,lambda b,a,h,p=phase:h.append(deepcopy(next(r for r in h if r['phase']==p))))
    def change_hit(phase,key,value):
        return lambda b,a,h:next(r for r in h if r['phase']==phase).__setitem__(key,value)
    for phase,key,value in [('EXP-award','old_exp',0),('EXP-award','awarded_exp',0),
        ('EXP-award','t',-1),('level-up-before','caller_lr','00000000'),
        ('level-up-after','level_up_result',0),('level-up-after','unit_hex','00'),
        ('Life-effect-flags-written','flags',0),('Life-effect-entry','context_words',[0,0,0]),
        ('HP-store-after','stored_hp',1),('HP-store-after','t',-1)]:
        reject(phase+'-'+key,change_hit(phase,key,value))
    for role,address in [('caster',caster['canonical']),('target',target['canonical'])]:
        for offset in (0,9,0x18,0x1A,0x1C,0x28,0xF2,0xF6,0x104):
            def edit(b,a,h,address=address,offset=offset):
                raw=bytearray(a[address]);raw[offset]^=1;a[address]=bytes(raw)
            reject(role+'-post-'+hex(offset),edit)
    output={'status':'pass-retained-Life-effect','scope':__doc__,'valid':valid,
            'rejected':rejected,'source_sha256':{p:sha(p) for p in
                ('tools/recovery_life_effect.py','tools/validate_recovery_life_effect.py')},
            'evidence_sha256':{str(p):sha(p) for p in [directory/'Life-overlay.json',*paths]},
            'limitations':['Retained replay, not a fresh cast or Wait continuation.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life effect:',len(rejected),'adversarial controls')


if __name__=='__main__':main()
