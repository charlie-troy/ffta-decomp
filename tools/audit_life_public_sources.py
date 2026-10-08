"""Resolve captured public Life import closures against exact local/Git bytes."""
import argparse
import hashlib
import json
from pathlib import Path

from recovery_menu import require
from recovery_source_versions import verify_source_versions


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True)
    ap.add_argument('--source-ref',action='append',default=[]);ap.add_argument('--out',required=True)
    ap.add_argument('--source-dir',action='append',default=[])
    args=ap.parse_args();root=Path(args.run);run=json.loads((root/'run.json').read_text())
    legs=[run]+([run['previous_leg']] if run.get('previous_leg') else [])
    resolutions=[]
    for index,leg in enumerate(legs):
        if not leg.get('bounded_ally_life'):continue
        pins=leg['input_sha256']
        require(leg['inputs_unchanged'] is True and leg['input_sha256_after']==pins,
                'captured public Life source changed')
        sources={p:h for p,h in pins.items() if p.startswith('tools/') and p.endswith('.py')}
        closure=verify_source_versions(sources,'life_recovery_runtime',args.source_ref,args.source_dir)
        resolutions.append({'leg':index,'entry':'life_recovery_runtime','closure':closure})
    require(resolutions,'no captured Life leg')
    manual=root/'manual-Life-Wait.json'
    if manual.exists():
        m=json.loads(manual.read_text());require(m['inputs_unchanged'],'manual source changed')
        pins={p:h for p,h in m['source_sha256'].items() if p.endswith('.py')}
        # Older manual captures did not pin the full import closure and cannot
        # be promoted to the strengthened source gate.
        closure=verify_source_versions(pins,'manual_life_wait_handoff',args.source_ref,args.source_dir)
        resolutions.append({'entry':'manual_life_wait_handoff','closure':closure})
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-captured-Life-source-closures','scope':__doc__,'resolutions':resolutions,
        'source_sha256':{p:sha(p) for p in ['tools/audit_life_public_sources.py','tools/recovery_source_versions.py']},
        'evidence_sha256':{str(root/'run.json'):sha(root/'run.json')},
        'limitations':['Captured source provenance only; not new gameplay or successful resume.']}
    if manual.exists():result['evidence_sha256'][str(manual)]=sha(manual)
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS captured Life source closures:',len(resolutions))


if __name__=='__main__':main()
