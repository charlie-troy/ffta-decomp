"""Research process-end transport must stay halted with hooks removed."""
import argparse,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from validate_recovery_transport import Peer
from probe_control_handoff import Probe,ALL_BPS
from consumable_transport import ConsumableResearchTransport


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args();checks=[]
    with patch('probe_control_handoff.time.sleep',lambda _:None):
        for case in ('halted','running','STOP','partial'):
            peer=Peer();probe=Probe(SimpleNamespace(g=peer),verbose=False);probe.arm();ledger=[]
            t=ConsumableResearchTransport(probe,log_input=ledger.append)
            try:
                with t:
                    assert t.press(1,pause=0,stop_check=lambda:case=='STOP')==(-1 if case=='STOP' else 5)
                    if case=='running':t.cont()
                    if case=='partial':raise ValueError('experiment failed')
            except ValueError:assert case=='partial'
            assert not peer.armed and peer.halted and not t.active and t.closed
            assert not any(e['event']=='trace_restored' for e in t.events)
            count=peer.writes;t.close();assert peer.writes==count
            assert len(ledger)==(0 if case=='STOP' else 5);checks.append(case)
    Path(args.out).write_text(json.dumps({'status':'pass','scope':__doc__,'checks':checks},indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS research terminal transport:',len(checks),'controls')


if __name__=='__main__':main()
