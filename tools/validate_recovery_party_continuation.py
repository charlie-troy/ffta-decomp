"""Replay actual eight-unit next-actor capture and reject misleading joins."""
import argparse
import hashlib
import json
from pathlib import Path

from fixture_guard import ROSTER, STRIDE, BATTLE_STRUCT, COUNT_OFF
from recovery_menu import PLAYER_DRIVER, RecoveryStateError, exact
from recovery_party_continuation import observe_party_continuation
from validate_recovery_menu import Memory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    folder=Path(args.capture);doc=json.loads((folder/'probe.json').read_text())
    rom=Path('baserom.gba').read_bytes()
    initial=Memory((folder/'initial-ewram.bin').read_bytes())
    units={p['canonical']:exact(initial,p['canonical'],STRIDE) for p in doc['party_before']}
    raw=(folder/'continuation-ewram.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == doc['capture_sha256']['continuation-ewram.bin']
    def observe(memory):
        return observe_party_continuation(memory,rom,doc['owner'],doc['wait']['facing'],
                                          doc['party_before'],units,doc['baseline_roster'])
    observed=observe(Memory(raw))
    assert observed == doc['continuations'][0]
    actor=observed['actor'];canonical=observed['canonical'];mirror=ROSTER+STRIDE*actor['slot']
    def coherent(memory,offset,value,size=1):
        memory.put(canonical+offset,value,size);memory.put(mirror+offset,value,size)
    rejected=[]
    for label,mutate in [
        ('borrowed-roster',lambda m:m.put(BATTLE_STRUCT+COUNT_OFF,2)),
        ('wrapper-disagreement',lambda m:m.put(PLAYER_DRIVER+8,0)),
        ('stale-caster-wrapper',lambda m:(m.put(PLAYER_DRIVER+4,doc['wait']['facing']['actor_wrapper']),
                                         m.put(PLAYER_DRIVER+8,doc['wait']['facing']['actor_wrapper']))),
        ('invalid-canonical',lambda m:m.put(observed['wrapper'],0)),
        ('stale-cursor',lambda m:m.put(0x0200FFC9,0,2)),
        ('coherent-foreign-job',lambda m:coherent(m,7,200)),
        ('coherent-wrong-name',lambda m:coherent(m,0,doc['owner']['name'],4)),
        ('coherent-KO-actor',lambda m:coherent(m,0x18,0,2)),
        ('coherent-impossible-tile',lambda m:(coherent(m,0xF6,0xFFFF,2),m.put(0x0200FFC9,0xFFFF,2))),
        ('party-alias',lambda m:m.put(0x02000188+0x104,7,1)),
        ('party-MP-disagreement',lambda m:m.put(0x02000080+0x1C,0,2)),
        ('party-tile-drift',lambda m:m.put(0x02000188+0xF6,0,2)),
    ]:
        memory=Memory(raw);mutate(memory)
        try:observe(memory)
        except (RecoveryStateError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'observed':observed,
                              'mutations_rejected':rejected},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS next actor id{actor["id"]}; {len(rejected)} rejected misleading joins')


if __name__=='__main__':main()
