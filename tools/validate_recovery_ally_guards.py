"""Explicit A6.2 target guard controls on retained RAM, plus disabled-row host control."""
import argparse
import hashlib
import json
from pathlib import Path
from dataclasses import replace

from fixture_guard import STRIDE, BATTLE_STRUCT
from recovery_menu import RecoveryMenu, RecoveryStateError, exact
from recovery_ally_confirmation import AllyConfirmationReader
from recovery_ally_target import ACCEPTANCE_CURSOR
from validate_recovery_menu import Memory
from validate_recovery_ally_executor import setup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',default='outputs/autobattle/a62-ally-turn-02')
    parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.capture)
    doc=json.loads((folder/'probe.json').read_text());rom=Path('baserom.gba').read_bytes()
    initial_raw=(folder/'initial-ewram.bin').read_bytes()
    raw=(folder/'confirmation-ewram.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==doc['capture_sha256']['confirmation-ewram.bin']
    rejected=[]
    for label,address,value,size in [
        ('KO-target',0x02000188+0x18,0,2),
        ('cross-side-target',0x02000188+0x28,0x8081,2),
        ('unaffiliated-target',0x02000188+0x28,0x1081,2),
        ('same-job-ID-alias',0x02000188+0x104,7,1),
        ('same-job-name-alias',0x02000188,doc['owner']['name'],4),
        ('stale-target-tile',0x02000188+0xF6,0x0A04,2),
        ('stale-acceptance-tile',ACCEPTANCE_CURSOR,4,2),
        ('changed-caster-MP',0x02000080+0x1C,84,2),
        ('insufficient-caster-MP',0x02000080+0x1C,5,2),
        ('changed-target-MP',0x02000188+0x1C,220,2),
        ('foreign-ability',BATTLE_STRUCT+0xEC,29,2),
        ('stale-controller',BATTLE_STRUCT+0x1118,10,2),
    ]:
        initial=Memory(initial_raw);memory=Memory(raw)
        menu=RecoveryMenu(initial,rom,doc['owner'])
        units={p['canonical']:exact(initial,p['canonical'],STRIDE) for p in doc['party_before']}
        menu.g=memory;reader=AllyConfirmationReader(memory,menu,doc['party_before'],units)
        token=reader.confirmation_snapshot();memory.put(address,value,size)
        try:reader.policy_snapshot(token)
        except RecoveryStateError:rejected.append(label)
        else:raise AssertionError('accepted '+label)
    menu,probe,executor=setup()
    ability=menu.states['ability-list']
    menu.states['ability-list']=replace(ability,enabled=(0,)+ability.enabled[1:])
    try:executor.run()
    except RecoveryStateError:
        assert not menu.final and len(probe.keys)==5
        rejected.append('engine-disabled-ability-row-host-only')
    else:raise AssertionError('disabled Cure navigated to final')
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'capture':args.capture,
        'mutations_rejected':rejected,'live_scope':'Negative RAM mutations are offline reader controls, not live fixture mutations'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS {len(rejected)} explicit ally target/disabled-row controls')


if __name__=='__main__':main()
