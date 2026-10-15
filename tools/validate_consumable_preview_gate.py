"""Exercise one-attempt preview input, STOP precedence and stale-token refusal."""
import json
import argparse
from consumable_preview_gate import PotionPreviewGate
from consumable_overlay import PotionOverlayToken


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);args=ap.parse_args()
    token=PotionOverlayToken(0x02000188,0x02000188,0x0202270C,251,362,2,100,241,(5,10),'inventory','raw')
    checks=[]
    class Reader:
        def __init__(self):self.stale=False
        def revalidate(self,t):
            if self.stale:raise ValueError('stale native token')
            assert t==token;return t
    class Transport:
        def __init__(self):self.writes=0;self.error=False;self.partial=False
        def press(self,mask,**kwargs):
            assert mask==1 and kwargs['tag']=='a66-Potion-target-accept-only'
            assert kwargs['stop_check']() is False
            self.writes+=1
            if self.error:raise OSError('ambiguous transport delivery')
            return 1 if self.partial else 5
    for case in ['success','STOP','stale','foreign','partial','ambiguous']:
        r,p=Reader(),Transport();r.stale=case=='stale';p.partial=case=='partial';p.error=case=='ambiguous'
        gate=PotionPreviewGate(r,p,stop_check=lambda:case=='STOP')
        try:gate.advance(object() if case=='foreign' else token)
        except (ValueError,OSError):assert case!='success'
        else:assert case=='success'
        assert p.writes==(1 if case in ('success','partial','ambiguous') else 0)
        prior=p.writes
        try:gate.advance(token)
        except ValueError:pass
        else:raise AssertionError('gate reused after '+case)
        assert p.writes==prior;checks.append(case+' single-attempt/no-final-input')
    from pathlib import Path
    Path(args.out).write_text(json.dumps({'status':'pass','scope':__doc__,'checks':checks,
        'limitations':['Host protocol controls only; no native preview, law or consumption claim.']},indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS Potion preview gate:',len(checks),'controls')


if __name__=='__main__':main()
