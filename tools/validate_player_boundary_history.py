"""Audit native/adapter observation history; a valid history alone is not resumed control."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE
from recovery_menu import MEMBERS, PLAYER_DRIVER, integer, require
from validate_autobattle_runtime import validate


def unit(row):
    raw=bytes.fromhex(row['raw']);require(len(raw)==STRIDE,'short observer unit')
    checks={'name':integer(raw,0),'id':raw[0x104],'type':raw[4],'race':raw[6],'job':raw[7],'level':raw[9],
        'hp':integer(raw,0x18,2),'max_hp':integer(raw,0x1A,2),'mp':integer(raw,0x1C,2),
        'max_mp':integer(raw,0x1E,2),'ct':integer(raw,0xD0,2),'tile':list(raw[0xF6:0xF8]),
        'side_raw':integer(raw,0x28,2),'status_flags':list(raw[0xE8:0xEE]),
        'sleep':bool(raw[0xEB]&4),'sleep_duration':raw[0xDF]}
    require(all(row[k]==v for k,v in checks.items()),'observer unit raw decoding differs')
    return row


def check(records):
    require(records,'observer history empty')
    native=[];opportunities=[];attempts=[];errors=[];previous=-1
    for rec in records:
        require(type(rec['t']) in (float,int) and rec['t']>=previous,'observer clock not monotonic')
        previous=rec['t'];require(rec['phase'] in ('native-pick','adapter-attempt'),'unknown observer phase')
        if rec.get('error'):
            errors.append({'t':rec['t'],'error':rec['error']});continue
        raw=bytes.fromhex(rec['structure']['raw'])
        require(len(raw)==4 and integer(raw,0)==rec['structure']['count'],'observer structure raw differs')
        canonical=rec['party']['canonical'];mirror=rec['party']['mirror']
        require([r['address'] for r in canonical]==[MEMBERS,MEMBERS+STRIDE]
                and [r['address'] for r in mirror]==[ROSTER+5*STRIDE,ROSTER+7*STRIDE],
                'observer party source addresses differ')
        for row in canonical+mirror:unit(row)
        require({r['id'] for r in canonical}=={5,7},'canonical observer party missing/reused')
        expected={r['id']:r for r in rec['context']['expected']}
        require(set(expected)=={5,7},'observer baseline identities missing')
        for row in canonical:
            require(all(row[k]==expected[row['id']][k] for k in ('id','name','race','job','level')),
                    'canonical observer identity differs from adopted baseline')
        driver=rec['driver'];d=bytes.fromhex(driver['raw'])
        require(driver['address']==PLAYER_DRIVER and len(d) in (0x64,0xE0)
                and integer(d,4)==driver['wrapper'] and integer(d,8)==driver['peer_wrapper'],
                'observer raw driver differs')
        if len(d)==0xE0:
            require(integer(d,0xDC,2)==driver['state'] and integer(d,0xD0)==driver['control'],
                    'observer native driver state/control differs')
        if driver.get('unit'):
            unit(driver['unit']);require(driver['unit']['address']==driver['member'],'driver member unit differs')
        menu=rec['menu']
        if menu.get('raw'):
            root=bytes.fromhex(menu['raw']);require(len(root)==0x30 and root[4]==menu['mode']
                and integer(root,0x18)==menu['member'] and integer(root,0x28)==menu['callback'],
                'observer raw menu differs')
        if menu.get('callback_raw'):
            cb=bytes.fromhex(menu['callback_raw']);require(len(cb)==0x18 and integer(cb,0)==menu['handler']
                and integer(cb,0x14,2)==menu['state'],'observer callback differs')
        if rec['phase']=='native-pick':
            pick=rec['pick'];unit(pick['unit']);require(pick['member']==pick['unit']['address'],
                'picked member raw address differs');native.append({'t':rec['t'],'id':pick['unit']['id'],
                    'name':pick['unit']['name'],'member':pick['member'],'side_raw':pick['unit']['side_raw']})
        else:
            adapter=rec['adapter'];attempts.append({'t':rec['t'],'accepted':adapter['owner'] is not None,
                'error':adapter['error'],'prior':rec['context']['adapter_prior']})
        actor=driver.get('unit')
        if (actor and actor['id'] in expected and actor['name']==expected[actor['id']]['name']
            and actor['side_raw']&0x9000==0 and actor['hp']>0 and not actor['sleep']
            and driver['wrapper']==driver['peer_wrapper'] and menu.get('member')==driver['member']
            and menu.get('handler')==0x08028DE1 and menu.get('mode')==4 and menu.get('state')==0x102
            and rec['cursor']['target']==actor['tile'] and rec['cursor']['command'] in (0,1,2)
            and rec['structure']['count']==8):
            candidates=[r for r in mirror if r['id']==actor['id'] and r['name']==actor['name']]
            if len(candidates)==1 and all(candidates[0][k]==actor[k] for k in ('job','race','level','hp','mp','tile')):
                opportunities.append({'t':rec['t'],'phase':rec['phase'],'id':actor['id'],
                    'canonical_ct':actor['ct'],'mirror_ct':candidates[0]['ct'],
                    'adapter':rec.get('adapter')})
    return {'native_picks':native,'native_player_picks':[r for r in native if r['id'] in (5,7) and r['side_raw']&0x9000==0],
        'command_menu_opportunities':opportunities,'adapter_attempts':attempts,'observer_errors':errors}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path(args.run);require(not validate(str(root)),'observed public run invalid')
    run=json.loads((root/'run.json').read_text());require(run['observe_player_boundaries'] and run['inputs_unchanged'],
        'observer source stability/explicit opt-in missing')
    records=[json.loads(s) for s in (root/'player-boundary-observer.jsonl').read_text().splitlines()]
    summary=check(records)
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    stop=events[-1]['t'];require(all(r['t']<=stop for r in records),'observer activity after terminal')
    mutations=[('empty history',lambda r:r.clear()),('unknown phase',lambda r:r[0].__setitem__('phase','invented')),
        ('wrong native member',lambda r:next(x for x in r if x.get('pick'))['pick'].__setitem__('member',0)),
        ('invented status',lambda r:r[0]['party']['canonical'][0].__setitem__('sleep',True)),
        ('foreign canonical address',lambda r:r[0]['party']['canonical'][0].__setitem__('address',0)),
        ('wrong structure',lambda r:r[0]['structure'].__setitem__('count',0)),
        ('missing native pick',lambda r:next(x for x in r if x.get('pick')).pop('pick'))]
    rejected=[]
    for label,edit in mutations:
        changed=deepcopy(records);edit(changed)
        try:check(changed)
        except (ValueError,KeyError,TypeError):rejected.append(label)
        else:raise AssertionError('observer history mutation survived: '+label)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-player-boundary-history-audit','scope':__doc__,'summary':summary,'rejected':rejected,
        'source_sha256':{p:sha(p) for p in ['tools/validate_player_boundary_history.py','tools/player_boundary_observer.py']},
        'evidence_sha256':{str(root/n):sha(root/n) for n in ['run.json','events.jsonl','input-log.jsonl','player-boundary-observer.jsonl']},
        'limitations':['Recorded observation history only; opportunity is not action commit, complete causal history or resumed control.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS observer history:',len(summary['native_picks']),'native picks;',len(summary['command_menu_opportunities']),
          'joined command opportunities;',len(summary['observer_errors']),'observer errors;',len(rejected),'mutations')


if __name__=='__main__':main()
