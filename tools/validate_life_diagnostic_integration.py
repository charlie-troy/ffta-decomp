"""Exercise the real terminal serializer, validator and session cleanup with fake hardware."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from autobattle_runtime import BattleRuntime, STALLED
from fixture_guard import FixtureSession, ROSTER, STRIDE
from recovery_menu import require
from validate_autobattle_runtime import validate
from validate_life_boundary_diagnostic import check


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='outputs/autobattle/a65-public-STOP-Wait-02')
    ap.add_argument('--runtime-ref',help='Load historical runtime code to demonstrate the pre-fix failure')
    ap.add_argument('--out',required=True);args=ap.parse_args();root=Path(args.baseline)
    require(not validate(str(root)),'retained baseline invalid')
    run=json.loads((root/'run.json').read_text())
    events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    journal=next(e['recovery'] for e in events if e.get('recovery'))
    pins={p['id']:p for p in journal['party']}
    runtime_class=BattleRuntime
    if args.runtime_ref:
        code=subprocess.check_output(['git','show',args.runtime_ref+':tools/autobattle_runtime.py'])
        namespace={'__name__':'historical_runtime'};exec(compile(code,'historical_runtime','exec'),namespace)
        runtime_class=namespace['BattleRuntime']
    cases=[]
    for fault in ('none','missing','truncated','timeout','cursor-error','screenshot-error'):
        with tempfile.TemporaryDirectory(prefix='ffta-diagnostic-integration-') as directory:
            out=Path(directory);calls=[];memory=bytearray(0x40000)
            for pin in pins.values():
                unit=bytes.fromhex(journal['effect_units_after'][str(pin['canonical'])])
                for address in (pin['canonical'],ROSTER+pin['slot']*STRIDE):
                    offset=address-0x02000000;memory[offset:offset+STRIDE]=unit
            def read(address,size):
                require(size<=512,'diagnostic exceeded packet limit');calls.append(('read',address,size))
                if fault=='missing':return None
                if fault=='truncated':return bytes(size-1)
                if fault=='timeout':raise TimeoutError('host transport timeout')
                offset=address-0x02000000;return memory[offset:offset+size]
            def cursor():
                if fault=='cursor-error':raise ValueError('host cursor unavailable')
                return (11,8)
            g=SimpleNamespace(read_mem=read,send=lambda *a,**k:calls.append(('resume',)),
                              close=lambda:calls.append(('closed',)))
            s=object.__new__(FixtureSession)
            s.g=g;s.pid=987654;s.proc=None;s.port=12345;s.keep_process=False;s.log=lambda _:None
            def screenshot(path):
                if fault=='screenshot-error':raise OSError('host screenshot unavailable')
                Path(path).write_bytes(b'host frame only')
            s.screenshot=screenshot
            runtime=object.__new__(runtime_class)
            runtime.s=s;runtime.g=g;runtime.resume=True;runtime.scenario_id=run['scenario']
            runtime.t0=time.time()-(events[-1]['t']+1);runtime.events_path=str(out/'events.jsonl')
            runtime._stop_requested_t=None
            runtime.p=SimpleNamespace(seeds=[None]*run['seeds'],router_hits=run['router_hits'],verbose=False,
                read_target_cursor=cursor,read_cmd_cursor=lambda:0,disarm=lambda:calls.append(('disarmed',)))
            (out/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events[:-1]),encoding='utf-8')
            (out/'input-log.jsonl').write_bytes((root/'input-log.jsonl').read_bytes())
            runtime._input_log=(out/'input-log.jsonl').open('a',encoding='utf-8')
            try:runtime._finish(STALLED,'host diagnostic bound')
            except BaseException:
                # Preserve the actual pre-fix exception on Windows rather
                # than masking it with TemporaryDirectory's open-file error.
                runtime._input_log.close()
                raise
            with patch('fixture_guard.port_listener_pid',return_value=None), \
                 patch('fixture_guard.subprocess.run',side_effect=lambda command,**kw:calls.append(('kill',command))):
                s.__exit__(None,None,None)
            receipt=deepcopy(run);receipt['terminal_reason']=runtime._terminal_reason
            (out/'run.json').write_text(json.dumps(receipt),encoding='utf-8')
            require(not validate(str(out)),'integrated terminal receipt rejected: '+str(validate(str(out))))
            actual=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
            require(actual[-1]['kind']=='stop' and actual[-1]['state']=='stalled','terminal receipt missing')
            require(runtime._input_log.closed and s.pid is None and s.g is None,'cleanup incomplete')
            require(calls.count(('disarmed',))==calls.count(('closed',))==1,'cleanup duplicated/absent')
            require([c[1] for c in calls if c[0]=='kill']==[['taskkill','/F','/PID','987654']],
                    'cleanup targeted another process')
            diagnostic=actual[-2].get('boundary_diagnostic')
            if fault in ('none','screenshot-error'):
                require(diagnostic is not None,'serialized diagnostic missing');check(diagnostic,pins)
            else:
                require(diagnostic is None and 'diagnostic unavailable' in actual[-2]['note'],
                        'transport error not preserved truthfully')
            cases.append(fault)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-Life-diagnostic-integration','scope':__doc__,'cases':cases,
        'source_sha256':{p:sha(p) for p in ['tools/validate_life_diagnostic_integration.py',
            'tools/autobattle_runtime.py','tools/recovery_boundary_diagnostic.py',
            'tools/validate_autobattle_runtime.py','tools/fixture_guard.py']},
        'limitations':['Host terminal/cleanup integration with fake hardware; no fresh gameplay or CLI adoption proof.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS real terminal serialization/validation/session cleanup:',len(cases),'cases')


if __name__=='__main__':main()
