"""Exercise real ordinary press logging without duplicating recovery transport ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from autobattle_runtime import BattleRuntime
from probe_control_handoff import BP_KEY
from recovery_menu import require


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    cases=[]
    for recovery in (False,True):
        with tempfile.TemporaryDirectory(prefix='ffta-ordinary-input-') as directory:
            out=Path(directory);sent=[];regs=[0]*16;regs[15]=BP_KEY
            def send(packet):
                if packet.startswith('P1='):sent.append(int.from_bytes(bytes.fromhex(packet[3:]),'little'))
                return 'OK'
            g=SimpleNamespace(send=send,cont=lambda:None,_read_packet=lambda:'S05',read_registers=lambda:regs)
            session=SimpleNamespace(g=g)
            runtime=BattleRuntime(session,{'scenario_id':'host-raw-input'},'host',str(out),
                                  verbose=False,bounded_self_cure=recovery)
            try:
                require(runtime.p.press(1,frames=2,pause=0)==2 and sent==[1,1],'actual inherited press not exercised')
                runtime._input_log.flush()
                rows=[json.loads(s) for s in (out/'input-log.jsonl').read_text().splitlines()]
                if recovery:
                    require(not rows,'ordinary logger duplicated recovery-owned writes')
                else:
                    require(len(rows)==2 and all(r['event']=='key_write' and r['val']==1
                        and r['manual'] is False for r in rows),'actual ordinary key writes not serialized')
                    require([{k:v for k,v in r.items() if k!='event'} for r in rows]==runtime.p.key_write_log,
                            'serialized writes differ from actual probe history')
                cases.append({'recovery':recovery,'actual_writes':len(sent),'serialized':len(rows)})
            finally:runtime._input_log.close()
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'pass-ordinary-raw-input-logging','scope':__doc__,'cases':cases,
        'source_sha256':{p:sha(p) for p in ['tools/validate_ordinary_input_logging.py','tools/autobattle_runtime.py',
                                        'tools/probe_control_handoff.py']},
        'limitations':['Real transport/log path with fake hardware; no native gameplay.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS ordinary raw logging and recovery ownership separation')


if __name__=='__main__':main()
