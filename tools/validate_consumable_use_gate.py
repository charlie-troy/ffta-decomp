"""Host single-use protocol controls; no native consumption acceptance."""
import argparse,json,hashlib
from dataclasses import replace
from pathlib import Path
from consumable_final import PotionFinalToken
from consumable_use_gate import PotionUseGate


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    token=PotionFinalToken(0x02000188,0x02000188,362,251,2,100,(5,10),((1,0),(82,0),(42,0)),(20,1),(), 'raw')
    cases=['success','STOP','late STOP','stale','late stale','foreign','last item','zero','reserve','partial','ambiguous']
    results=[]
    for case in cases:
        class Reader:
            calls=0
            def revalidate(self,t):
                self.calls+=1
                if case=='stale' or case=='late stale' and self.calls==2:raise ValueError('stale')
                return t
        class Transport:
            writes=0
            def press(self,mask,**kw):
                assert mask==1 and kw['stop_check']() is False
                self.writes+=1
                if case=='ambiguous':raise OSError('ambiguous delivery')
                return 2 if case=='partial' else 5
        r,p=Reader(),Transport();stop_calls=[0]
        def stopped():
            stop_calls[0]+=1
            return case=='STOP' or case=='late STOP' and stop_calls[0]>=3
        gate=PotionUseGate(r,p,stop_check=stopped,reserve=2 if case=='reserve' else 1)
        t=object() if case=='foreign' else replace(token,count=1 if case=='last item' else 0 if case=='zero' else 2)
        try:out=gate.execute(t)
        except (ValueError,OSError):assert case!='success'
        else:assert case=='success' and out['outcome']=='final-input-delivered-only'
        expected=int(case in ('success','partial','ambiguous'));assert p.writes==expected
        try:gate.execute(token)
        except ValueError:pass
        else:raise AssertionError('retry accepted: '+case)
        assert p.writes==expected;results.append({'case':case,'press_attempts':p.writes,'retry_refused':True})
    result={'status':'pass','scope':__doc__,'checks':results,'source_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in ['tools/consumable_use_gate.py','tools/validate_consumable_use_gate.py']}}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS Potion single-use gate:',len(results),'controls')


if __name__=='__main__':main()
