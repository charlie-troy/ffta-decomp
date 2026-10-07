"""Assemble bounded A6.3 acceptance from validated public runs and regressions."""
import argparse
import hashlib
import json
from pathlib import Path
from recovery_menu import require
from validate_autobattle_runtime import validate


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--regressions',required=True);ap.add_argument('--ordinary-run',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args();root=Path('outputs/autobattle')
    regressions=read(args.regressions);require(regressions['status']=='pass-bounded-regressions','regressions incomplete')
    matrix=read(regressions['self_matrix']);require(matrix['status']=='pass-bounded-cli-matrix' and len(matrix['cases'])==6,'self matrix incomplete')
    sources={};evidence={};runs=[]
    def evidence_file(path):
        path=Path(path);evidence[path.as_posix()]=digest(path)
    def public(name):
        directory=root/name;require(not validate(str(directory)),f'invalid public run {name}')
        run=read(directory/'run.json');require(run['inputs_unchanged'],f'inputs changed {name}')
        for path,value in run['input_sha256'].items():
            require(digest(path)==value,f'current source/input drift {path}')
            if path.startswith('tools/'):sources[path]=value
            else:evidence[path]=value
        for pattern in ('*.json','*.jsonl','*.png'):
            for path in directory.glob(pattern):evidence_file(path)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        runs.append({'run':name,'turns':run['turns'],'resumed':run.get('resumed',False),
                     'final_state':run['final_state'],'pid':run['emulator_pid']})
        return run,events
    heals=[]
    for name in ('a63-public-cure-01','a63-public-cure-02'):
        run,events=public(name);j=next(e['recovery'] for e in events if e['kind']=='turn')
        require(run['turns']==1 and j['recovery']['outcome']=='accepted-effect-only','ally cast missing')
        checks=read(root/name/'mutation-checks.json');require(checks['status']=='pass' and len(checks['rejections'])>=38,'cast controls incomplete')
        heals.append({'run':name,'target_hp':[j['party_before'][0]['hp'],j['recovery']['target_after']['hp']],
                      'caster_mp':[j['recovery']['before']['mp'],j['recovery']['after']['mp']],
                      'raw_writes':len(j['raw_writes']),'next_enemy':j['continuations'][0]['actor']['id']})
    _,events=public('a63-public-damage-01');decline=next(e['recovery'] for e in events if e['kind']=='turn')
    require(decline['recovery']['outcome']=='declined','damage preset cast Cure')
    damage=read('configs/tactics/damage-focused.json');adapted=read(root/'a63-damage-policy.json')
    require(all(damage[k]==adapted[k] for k in ('assignments','fallback','observation')),'damage rules changed')
    evidence_file('configs/tactics/damage-focused.json')
    for name in ('a63-public-stop-cure-02','a63-public-stop-facing-01'):
        public(name);check=read(root/name/'handoff-checks.json')
        require(check['status']=='pass' and len(check['rejections'])==8 and len(check['partial_stop_rejections'])==7,'handoff controls incomplete')
    for case in regressions['unsupported']:
        public(case['run']);require(case['raw_writes']==case['turns']==0,'unsupported input')
    require(len(regressions['unsupported'])==2,'unsupported controls incomplete')
    for case in matrix['cases']:public(case['run'])
    ordinary,events=public(Path(args.ordinary_run).name)
    actions={e['selected_action']['kind'] for e in events if e['kind']=='turn'}
    require(ordinary['turns']>=2 and {'identified-move','identified-wait'}<=actions,'ordinary live Move/Wait missing')
    for name in ('a63-interface-checks.json','a63-resume-clock.json','a63-transport-checks.json',
                 'a63-self-executor-checks.json','a63-policy-checks.json','a63-host-checks.json'):
        evidence_file(root/name)
    evidence_file(root/'a63-raw-controls/checks.json')
    evidence_file(args.regressions);evidence_file(regressions['self_matrix'])
    for path in Path('tools').glob('*party_recovery*.py'):sources[path.as_posix()]=digest(path)
    for name in ('tools/validate_autobattle_runtime.py','tools/run_recovery_cli_stop.py','tools/validate_recovery_handoff.py'):
        sources[name]=digest(name)
    doc={'milestone':'A6.3','date':'2026-10-07','base_revision':'0e6bf65',
         'status':'pass-bounded-public-ally-cure','scope':'Eight-unit living ally Cure opt-in only',
         'criteria':[{'id':name,'status':'pass'} for name in (
             'bounded-interface-and-adapter','two-fresh-public-casts','healer-versus-damage-policy',
             'STOP-manual-handoff-and-same-PID-resume','unsupported-family-zero-input',
             'adversarial-public-receipts','self-Cure-and-ordinary-regressions')],
         'heals':heals,'runs':runs,'source_sha256':dict(sorted(sources.items())),
         'evidence_sha256':dict(sorted(evidence.items())),
         'source_hash_semantics':'Current production input hashes match each public launch; manual helper pins captured source before input. Exact Windows JSON/JSONL bytes are retained.',
         'limitations':['Exact pinned two-player/eight-unit fixture; no general target search.',
             'Damage-focused comparison proves declined Cure plus Wait, not an attack.',
             'Manual Wait and ordinary Move/Wait resume; no resumed Cure claim.',
             'No KO/revive, inventory/items, law/status coverage or complete-battle claim.',
             'Trial a63-public-stop-cure-01 needed a separate manual retry and is not final lifecycle acceptance.',
             'Cached UI target label provenance remains bounded/unknown as documented in A6.2.']}
    output=Path(args.out);output.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS assembled A6.3: {len(runs)} public runs, {len(evidence)} evidence hashes')


if __name__=='__main__':main()
