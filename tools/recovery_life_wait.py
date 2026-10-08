"""Separate research Wait boundary for the verified post-Life caster."""
from dataclasses import asdict, dataclass
import time
from copy import deepcopy

from fixture_guard import STRIDE
from recovery_menu import FACING, LIST, MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, exact, integer, require
from tactics_policy import evaluate


@dataclass(frozen=True)
class LifeFacingToken:
    observed_at: float
    member: int
    actor_wrapper: int
    direction: int
    context: int
    callback: int
    hp: int
    mp: int

    def receipt(self):
        return asdict(self)


class LifeWaitBoundary:
    def __init__(self,g,menu,units,*,clock=time.monotonic):
        self.g,self.menu,self.units,self.clock=g,menu,dict(units),clock
        self.final_attempted=False
        self.events=[]

    def snapshot(self):
        g,m=self.g,self.menu
        require(integer(exact(g,MENU_ROOT,4),0)==m.context,'Wait context changed')
        root=exact(g,m.context,0x30);driver=exact(g,PLAYER_DRIVER,0xE0)
        callback=exact(g,m.callback,0x18);facing=exact(g,FACING,0x14)
        require(root[4]==4 and integer(root,0,2)==3 and integer(root,0x18)==m.member
                and integer(root,0x20)==m.manager and integer(root,0x28)==m.callback,
                'Wait root is not the bound caster')
        require(integer(callback,0)==LIST and integer(callback,0x14,2)==3
                and integer(exact(g,m.manager+4,4),0)==0,'Wait cached callback differs')
        require(integer(driver,4)==integer(driver,8)==m.wrapper
                and integer(exact(g,m.wrapper,4),0)==m.member
                and integer(driver,0x60)==0 and integer(driver,0xDC,2)==0x2F
                and integer(driver,0xD0)==0x48,'Wait driver is not accepting facing input')
        require(integer(facing,0)==m.wrapper and facing[0x10]==1
                and facing[4] in range(4) and facing[5] in range(4)
                and exact(g,m.wrapper+0x1F,1)[0]==facing[4],'Wait facing owner/direction differs')
        for a,u in self.units.items():
            require(exact(g,a,STRIDE)==u,'post-Life party changed before Wait')
        unit=self.units[m.member]
        require(m.name_hash()==m.name_digest,'Wait caster name content differs')
        for i in range(MEMBER_COUNT):
            address=MEMBERS+i*STRIDE
            if address!=m.member:
                other=exact(g,address,STRIDE)
                require(integer(other,0)!=integer(unit,0) and other[0x104]!=unit[0x104],
                        'Wait caster name/id alias')
        reads=[(m.context,root),(m.callback,callback[:0x16]),(FACING,facing[:6]),
               (FACING+0x10,facing[0x10:0x11]),(PLAYER_DRIVER+4,driver[4:12]),
               (PLAYER_DRIVER+0x60,driver[0x60:0x64]),(PLAYER_DRIVER+0xD0,driver[0xD0:0xD4]),
               (PLAYER_DRIVER+0xDC,driver[0xDC:0xDE])]
        require(all(exact(g,a,len(b))==b for a,b in reads),'Wait changed during observation')
        return LifeFacingToken(self.clock(),m.member,m.wrapper,facing[4],m.context,m.callback,
                               integer(unit,0x18,2),integer(unit,0x1C,2))

    def revalidate(self,token):
        require(isinstance(token,LifeFacingToken) and 0<=self.clock()-token.observed_at<=2,
                'stale/foreign Wait token')
        current=self.snapshot()
        require(current.receipt()|{'observed_at':0}==token.receipt()|{'observed_at':0},
                'Wait token changed')
        return current

    def policy_snapshot(self,token):
        self.revalidate(token);m=self.menu;u=self.units[m.member]
        return {'schema':'ffta-tactics-snapshot/2','identity':'verified','age_seconds':0,
                'actor':{'name':m.owner['name_text'],'id':u[0x104],'job_id':u[7],'side':'player',
                         'hp':token.hp,'max_hp':integer(u,0x1A,2),'mp':token.mp,
                         'max_mp':integer(u,0x1E,2),'tile':list(u[0xF6:0xF8])},
                'candidates':[{'id':'wait','kind':'wait','action_id':10,'legal':True,'cost':0}]}

    def commit(self,token,transport,policy,stopped):
        require(not self.final_attempted,'Wait final input already attempted')
        stopped();snapshot=self.policy_snapshot(token);decision=evaluate(snapshot,policy)
        require((decision.get('decision') or {}).get('candidate_id')=='wait','policy declined Wait')
        self.events.append({'event':'final_policy','policy':deepcopy(policy),
                            'snapshot':snapshot,'evaluation':decision,'facing':token.receipt()})
        stopped();snapshot=self.policy_snapshot(token);decision=evaluate(snapshot,policy)
        require((decision.get('decision') or {}).get('candidate_id')=='wait','policy declined final Wait')
        self.events.append({'event':'revalidated_final_policy','policy':deepcopy(policy),
                            'snapshot':snapshot,'evaluation':decision})
        self.revalidate(token);stopped()
        self.final_attempted=True
        self.events.append({'event':'final_input_requested','mask':1})
        hits=transport.press(1,tag='a64-Life-single-Wait-final-A',stop_check=stopped)
        require(hits==5,'Wait final delivery incomplete; never retry')
        self.events.append({'event':'final_input_delivered','hits':hits})
        return {'outcome':'delivered','continuation':'unknown','facing':token.receipt()}
