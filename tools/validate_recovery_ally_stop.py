"""Validate owned research STOP suppression; no manual handoff or resume claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import STRIDE
from recovery_menu import RecoveryMenu, RecoveryStateError, exact, integer, require
from recovery_ally_confirmation import AllyConfirmationReader
from validate_recovery_menu import Memory


def audit(doc,control,captures,rom):
    phase=control['phase'];count=45 if phase=='confirmation' else 65
    require(phase in ('confirmation','facing') and control['triggered'] and control['exit_code'] != 0,
            'control not triggered')
    require(doc['status']=='unknown' and 'RecoveryStopped' in doc['error'] and doc['inputs_unchanged']
            and doc['verified_turns']==0 and isinstance(doc['stop_requested_at'],(int,float)), 'wrong STOP outcome')
    require(doc['stop_raw_write_count']==len(doc['raw_writes'])==count, 'post-STOP or missing input')
    require(doc['transport'][-1]=={'event':'trace_restored','write_count':count}, 'STOP trace cleanup missing')
    raw=doc['raw_writes']
    masks=[128,1,128,128,1,1,16,1,1]+([1,128,128,1] if phase=='facing' else [])
    require([w['val'] for w in raw[::5]]==masks
            and all([w['hits'] for w in raw[i:i+5]]==[1,2,3,4,5]
                    and all(w['val']==masks[i//5] and w['event']=='key_write' and not w['manual']
                            for w in raw[i:i+5]) for i in range(0,count,5))
            and all(a['t']<=b['t'] for a,b in zip(raw,raw[1:])), 'STOP raw sequence differs')
    initial=Memory(captures['initial-ewram.bin']);confirmation=Memory(captures['confirmation-ewram.bin'])
    menu=RecoveryMenu(initial,rom,doc['owner']);menu.g=confirmation
    units={p['canonical']:exact(initial,p['canonical'],STRIDE) for p in doc['party_before']}
    reader=AllyConfirmationReader(confirmation,menu,doc['party_before'],units)
    reader.confirmation_snapshot()
    cure_finals=[e for e in doc['events'] if e['event']=='input_requested' and e.get('final')]
    if phase=='confirmation':
        require(not cure_finals and 'recovery' not in doc and 'after-cure-ewram.bin' not in captures,
                'Cure executed after confirmation STOP')
    else:
        require(len(cure_finals)==1 and cure_finals[0]['facts']['state']=='confirmation'
                and not any(e['event']=='input_requested' and e.get('final') for e in doc['wait_events']),
                'Wait final executed after facing STOP')
        memory=Memory(captures['facing-ewram.bin']);menu.g=memory;facing=menu.snapshot()
        require(facing.state=='facing' and facing.mp==79 and facing.hp==442
                and doc['recovery']['outcome']=='accepted-effect-only'
                and integer(exact(memory,reader.target,STRIDE),0x18,2)==doc['recovery']['target_after']['hp']>100
                and integer(exact(memory,reader.target,STRIDE),0x1C,2)==221, 'pre-STOP effect differs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();folder=Path(args.capture)
    doc=json.loads((folder/'probe.json').read_text());control=json.loads((folder/'control.json').read_text())
    captures={p.name:p.read_bytes() for p in folder.glob('*.bin')}
    for name,digest in doc['capture_sha256'].items():assert hashlib.sha256(captures[name]).hexdigest()==digest,name
    for path,digest in doc['source_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    rom=Path('baserom.gba').read_bytes();audit(doc,control,captures,rom)
    rejected=[]
    for label,mutate in [
        ('post-STOP-input',lambda d:d['raw_writes'].append(d['raw_writes'][-1])),
        ('missing-ledger',lambda d:d.update(raw_writes=[])),
        ('wrong-STOP-count',lambda d:d.update(stop_raw_write_count=0)),
        ('missing-STOP-time',lambda d:d.pop('stop_requested_at')),
        ('false-turn',lambda d:d.update(verified_turns=1)),
        ('missing-cleanup',lambda d:d['transport'].pop()),
    ]:
        changed=copy.deepcopy(doc);mutate(changed)
        try:audit(changed,control,captures,rom)
        except (RecoveryStateError,KeyError,IndexError):rejected.append(label)
        else:raise AssertionError('accepted '+label)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'pass','scope':__doc__,'phase':control['phase'],
        'raw_writes':len(doc['raw_writes']),'mutations_rejected':rejected,
        'cleanup':'owned FixtureSession exited; no manual takeover or resume exercised'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS {control["phase"]} STOP; {len(rejected)} rejected receipts')


if __name__=='__main__':main()
