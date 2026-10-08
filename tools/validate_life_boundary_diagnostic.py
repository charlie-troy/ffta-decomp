"""Validate raw terminal Sleep observations without claiming resumed control."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_menu import integer, require
from validate_autobattle_runtime import validate


def check(diagnostic, pins):
    decoded={}
    for label in ('canonical','mirror'):
        rows=diagnostic['party'][label]
        require(len(rows)==2 and {r['id'] for r in rows}=={5,7},'terminal diagnostic identity set differs')
        decoded[label]={}
        for row in rows:
            raw=bytes.fromhex(row['raw']);pin=pins[row['id']]
            require(len(raw)==STRIDE and raw[0x104]==row['id'] and integer(raw,0)==row['name']==pin['name'],
                    'terminal raw diagnostic identity differs')
            if label=='canonical':require(row['address']==pin['canonical'],'terminal canonical address differs')
            require(row['status_EB']==raw[0xEB] and row['sleep']==bool(raw[0xEB]&4)
                    and row['sleep_duration']==raw[0xDF] and row['hp']==integer(raw,0x18,2)
                    and row['mp']==integer(raw,0x1C,2),'terminal diagnostic raw decoding differs')
            decoded[label][row['id']]={'sleep':row['sleep'],'duration':row['sleep_duration'],
                                      'hp':row['hp'],'mp':row['mp']}
    require(decoded['canonical']==decoded['mirror'],'canonical/mirror terminal statuses disagree')
    return decoded['canonical']


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
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    output={'status':'pass-native-terminal-status-diagnostic','scope':__doc__,'observed':decoded,
        'rejected':rejected,'acceptance':'same-PID-player-control-UNKNOWN',
        'source_sha256':{p:sha(p) for p in ['tools/validate_life_boundary_diagnostic.py','tools/recovery_boundary_diagnostic.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','events.jsonl','input-log.jsonl']},
        'limitations':['Native status at the bounded terminal only; not complete causal history or a resumed player turn.']}
    Path(args.out).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS raw terminal status:',decoded,';',len(rejected),'mutations; resumed control UNKNOWN')


if __name__=='__main__':main()
