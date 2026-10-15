"""Real Probe.press must poll STOP before every gameplay register injection."""
import argparse,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from probe_control_handoff import Probe
from validate_recovery_transport import Peer
from recovery_transport import RecoveryTransport


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args();checks=[]
    with patch('probe_control_handoff.time.sleep',lambda _:None):
        for limit in range(5):
            peer=Peer();probe=Probe(SimpleNamespace(g=peer),verbose=False);ledger=[];stop_seen=[]
            def stopped():
                value=peer.writes>=limit
                if value:stop_seen.append(peer.writes)
                return value
            with RecoveryTransport(probe,log_input=ledger.append) as transport:
                hits=transport.press(1,pause=0,stop_check=stopped)
            assert peer.writes==limit and len(ledger)==limit,(limit,peer.writes)
            assert hits==(-1 if limit==0 else limit)
            assert stop_seen and all(v==limit for v in stop_seen)
            checks.append({'stop_after_writes':limit,'actual_writes':peer.writes})
    Path(args.out).write_text(json.dumps({'status':'pass','scope':__doc__,'checks':checks,
        'limitations':['Host RSP protocol discrimination; real CLI STOP/manual/resume remains a separate gate.']},indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS Probe per-injection STOP:',len(checks),'controls')


if __name__=='__main__':main()
