"""Validate raw terminal Sleep observations without claiming resumed control."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE
from recovery_menu import integer, require
from validate_autobattle_runtime import validate


def check(diagnostic, pins):
    cursor=diagnostic['target_cursor']
    require(isinstance(cursor,(list,tuple)) and len(cursor)==2 and all(type(v)==int and 0<=v<64 for v in cursor)
            and type(diagnostic['command_cursor'])==int and 0<=diagnostic['command_cursor']<=255,
            'terminal raw cursor missing/outside bounds')
    require(diagnostic['sleep_reader']=={'getter':0x080CDB24,'offset':0xEB,'mask':4,'duration_offset':0xDF},
            'terminal status decoder provenance differs')
    structure=diagnostic['structure'];struct_raw=bytes.fromhex(structure['raw'])
    require(structure['address']==BATTLE_STRUCT and len(struct_raw)==4
            and structure['count']==integer(struct_raw,0),'terminal raw structure differs')
    snapshots=diagnostic['mirror_snapshots']
    require(len(snapshots)==8 and [r['address'] for r in snapshots]==[ROSTER+i*STRIDE for i in range(8)]
            and all(len(bytes.fromhex(r['raw']))==STRIDE for r in snapshots),'terminal raw mirror incomplete')
    raw_mirror={r['address']:bytes.fromhex(r['raw']) for r in snapshots}
    candidates=[address for address,raw in raw_mirror.items() if raw[0x104] in (5,7) and integer(raw,0)!=0]
    require([r['address'] for r in diagnostic['party']['mirror']]==candidates,
            'terminal mirror candidate filter differs from raw snapshot')
    decoded={}
    for label in ('canonical','mirror'):
        rows=diagnostic['party'][label]
        if label=='canonical':
            require(len(rows)==2 and {r['id'] for r in rows}=={5,7},'terminal canonical identity set differs')
        decoded[label]={}
        for row in rows:
            raw=bytes.fromhex(row['raw'])
            require(len(raw)==STRIDE and raw[0x104]==row['id'] and integer(raw,0)==row['name'],
                    'terminal raw diagnostic identity differs')
            if label=='canonical':
                pin=pins[row['id']]
                require(row['address']==pin['canonical'] and row['name']==pin['name'],
                        'terminal canonical address/name differs')
            else:require(raw==raw_mirror[row['address']],'terminal mirror row differs from raw capture')
            require(row['status_EB']==raw[0xEB] and row['sleep']==bool(raw[0xEB]&4)
                    and row['sleep_duration']==raw[0xDF] and row['hp']==integer(raw,0x18,2)
                    and row['mp']==integer(raw,0x1C,2),'terminal diagnostic raw decoding differs')
            decoded[label][row['id']]={'sleep':row['sleep'],'duration':row['sleep_duration'],
                                      'hp':row['hp'],'mp':row['mp']}
    joined=(structure['count']==8 and len(diagnostic['party']['mirror'])==2
            and {r[0x104] for r in raw_mirror.values()}==set(range(8))
            and all(row['name']==pins[row['id']]['name'] and row['address']==ROSTER+pins[row['id']]['slot']*STRIDE
                    for row in diagnostic['party']['mirror']))
    if joined:require(decoded['canonical']==decoded['mirror'],'canonical/mirror terminal statuses disagree')
    return {'canonical':decoded['canonical'],'mirror_state':'party-mirror-joined' if joined else 'unidentified',
            'structure_count':structure['count']}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.run)
    require(not validate(str(root)),'diagnostic public baseline fails')
    run=json.loads((root/'run.json').read_text());events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    require(run['resumed'] and run['turns']==0 and run['inputs_unchanged'], 'diagnostic not stable bounded resume')
    captures=[e['boundary_diagnostic'] for e in events if e.get('boundary_diagnostic')]
    require(len(captures)==1,'native diagnostic missing/repeated')
    journal=next(e['recovery'] for e in events if e.get('recovery'));pins={p['id']:p for p in journal['party']}
    decoded=check(captures[0],pins);rejected=[]
    for field,value in [('sleep',not captures[0]['party']['canonical'][0]['sleep']),
                        ('sleep_duration',255),('hp',999),('name',0),('address',0)]:
        d=deepcopy(captures[0]);d['party']['canonical'][0][field]=value
        try:check(d,pins)
        except ValueError:rejected.append(field)
        else:raise AssertionError('terminal diagnostic mutation survived: '+field)
    controls=[('missing raw structure',lambda d:d.pop('structure')),
              ('wrong structure count',lambda d:d['structure'].__setitem__('count',0)),
              ('truncated raw structure',lambda d:d['structure'].__setitem__('raw','00')),
              ('missing mirror unit',lambda d:d['mirror_snapshots'].pop()),
              ('truncated mirror unit',lambda d:d['mirror_snapshots'][0].__setitem__('raw','00')),
              ('foreign mirror address',lambda d:d['mirror_snapshots'][0].__setitem__('address',0)),
              ('missing cursor',lambda d:d.pop('target_cursor')),
              ('invalid cursor',lambda d:d.__setitem__('target_cursor',[255,0])),
              ('unknown status decoder',lambda d:d['sleep_reader'].__setitem__('mask',8))]
    for label,edit in controls:
        d=deepcopy(captures[0]);edit(d)
        try:check(d,pins)
        except (ValueError,KeyError,TypeError):rejected.append(label)
        else:raise AssertionError('terminal diagnostic mutation survived: '+label)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    output={'status':'pass-native-terminal-status-diagnostic','scope':__doc__,'observed':decoded,
        'rejected':rejected,'acceptance':'same-PID-player-control-UNKNOWN',
        'source_sha256':{p:sha(p) for p in ['tools/validate_life_boundary_diagnostic.py','tools/recovery_boundary_diagnostic.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','events.jsonl','input-log.jsonl']},
        'limitations':['Native status at the bounded terminal only; not complete causal history or a resumed player turn.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS raw terminal status:',decoded,';',len(rejected),'mutations; resumed control UNKNOWN')


if __name__=='__main__':main()
