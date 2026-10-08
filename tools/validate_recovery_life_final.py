"""Exercise the single-attempt Life final gate against retained native prompt RAM.

Only transport is replaced; actual reader, policy evaluator and final gate run.
No emulated battle effect is generated or asserted by these host controls.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE, BATTLE_STRUCT
from recovery_menu import require
from recovery_menu_list import ResearchMenuList
from recovery_life_target import LifeOverlayReader
from recovery_life_final import LifeFinalGate
from tactics_policy import load_policy_file
from validate_recovery_life_menu import Memory


class Transport:
    def __init__(self, *, reply=5, error=False):
        self.calls, self.reply, self.error = [], reply, error

    def press(self, mask, **kwargs):
        kwargs['stop_check']()
        self.calls.append({'mask': mask,'tag': kwargs['tag']})
        if self.error:
            raise ConnectionError('injected ambiguous final transport delivery')
        return self.reply


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    directory = Path(args.capture)
    doc = json.loads((directory/'Life-overlay.json').read_text())
    path = directory/'final-prompt-second-ewram.bin'
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    require(doc['status'] == 'captured-Life-final-prompt-only' and doc['inputs_unchanged']
            and not doc['final_confirmation'] and sha(path) == doc['capture_sha256'][path.name],
            'native final capture differs')
    data,rom = path.read_bytes(),Path(args.rom).read_bytes()
    require(sha(args.rom) == doc['source_sha256'][args.rom], 'ROM differs')
    default = load_policy_file('configs/tactics/healer.json')
    def fixture():
        g = Memory(data)
        caster = next(p['canonical'] for p in doc['party'] if p['id'] == 5)
        menu = ResearchMenuList(g,rom,doc['owner'],caster)
        units = {p['canonical']:g.read_mem(p['canonical'],STRIDE) for p in doc['party']}
        reader = LifeOverlayReader(g,menu,doc['party'],units,clock=lambda:1)
        return g,reader,reader.confirmation_snapshot()
    g,reader,token = fixture()
    transport = Transport()
    gate = LifeFinalGate(reader,transport,deepcopy(default))
    result = gate.commit(token)
    require(len(transport.calls) == 1 and gate.final_attempted and result['effect'] == 'unknown',
            'valid gate did not send exactly one final request')
    valid_events = deepcopy(gate.events)
    controls = []
    def rejected(label, *, policy=None, mutation=None, stop=None, foreign=None, latched=False):
        g,r,t = fixture()
        transport = Transport()
        gate = LifeFinalGate(r,transport,deepcopy(policy or default),
                            stop_check=stop or (lambda:False),
                            before_final=(lambda:mutation(g,r,t)) if mutation else (lambda:None))
        try:
            gate.commit(t if foreign is None else foreign(t))
        except (ValueError,ConnectionError):
            require(not transport.calls and gate.final_attempted == latched,label+' input/latch state differs')
            controls.append(label)
        else:
            raise AssertionError(label+' was accepted')
    reserve = deepcopy(default)
    reserve['assignments']['party']['player']['rules'][0]['when']['remaining_mp_after_cost']={'gte':212}
    rejected('actual-offered-Life-reserve-refusal',policy=reserve)
    disabled = deepcopy(default)
    disabled['assignments']['party']['player']['rules'][0]['enabled']=False
    rejected('disabled-revive-rule',policy=disabled)
    rejected('STOP-before-final-policy',stop=lambda:True)
    for n in range(2,6):
        checks=[0]
        def stop_at(n=n,checks=checks):
            checks[0]+=1
            return checks[0] >= n
        rejected('STOP-check-'+str(n),stop=stop_at,latched=n==5)
    rejected('MP-drift-between-policies',mutation=lambda g,r,t:g.write(t.caster+0x1C,b'\0\0'))
    rejected('target-became-living',mutation=lambda g,r,t:g.write(t.target+0x18,b'\x01\0'))
    rejected('target-tile-drift',mutation=lambda g,r,t:g.write(t.target+0xF6,b'\x3f'))
    rejected('target-wrapper-drift',mutation=lambda g,r,t:g.write(t.target_wrapper,t.caster.to_bytes(4,'little')))
    rejected('actor-id-drift',mutation=lambda g,r,t:g.write(t.caster+0x104,b'\x07'))
    rejected('foreign-token',foreign=lambda t:object())
    rejected('overlay-token-is-not-final',foreign=lambda t:__import__('dataclasses').replace(t,stage='overlay'))
    rejected('missing-final-Life-id',mutation=lambda g,r,t:g.write(r.menu.context+0x14,b'\x01\0\0\0'))
    rejected('misleading-preview-only',mutation=lambda g,r,t:g.write(BATTLE_STRUCT+0x1112,b'\x6c\0'))
    # A policy changing after initial selection is re-evaluated, not cached.
    g,r,t = fixture()
    policy=deepcopy(default);transport=Transport()
    gate=LifeFinalGate(r,transport,policy,before_final=lambda:policy['assignments']['party']['player']['rules'][0].update(enabled=False))
    try:gate.commit(t)
    except ValueError:
        require(not transport.calls and not gate.final_attempted,'changed policy committed')
        controls.append('policy-changed-between-evaluations')
    else:raise AssertionError('changed policy accepted')
    # Any request, including an ambiguous delivery, irrevocably consumes the gate.
    for label,transport in [('delivered',Transport()),('partial',Transport(reply=2)),('disconnect',Transport(error=True))]:
        g,r,t=fixture();gate=LifeFinalGate(r,transport,deepcopy(default))
        try:gate.commit(t)
        except (ValueError,ConnectionError):pass
        require(gate.final_attempted and len(transport.calls)==1,'missing pre-transport latch')
        try:gate.commit(t)
        except ValueError:
            require(len(transport.calls)==1,'duplicate final attempt')
            controls.append('duplicate-after-'+label)
        else:raise AssertionError('reused gate accepted')
    output={'status':'pass-host-Life-final-gate','scope':__doc__,'controls':controls,
        'valid_final_requests':1,'full_policy':default,'valid_events':valid_events,
        'source_sha256':{p:sha(p) for p in ('tools/validate_recovery_life_final.py',
            'tools/recovery_life_final.py','tools/recovery_life_target.py','tools/tactics_policy.py',
            'configs/tactics/healer.json')},
        'evidence_sha256':{str(p):sha(p) for p in (directory/'Life-overlay.json',path)},
        'limitations':['Host transport controls only; no live STOP timing or revival execution.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Life final gate:',len(controls),'rejection/single-attempt controls')


if __name__ == '__main__':
    main()
