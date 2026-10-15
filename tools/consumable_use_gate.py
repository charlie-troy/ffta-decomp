"""Bounded research final-A gate; delivery alone never proves item use."""
from consumable_final import PotionFinalToken
from recovery_menu import require


class PotionUseGate:
    def __init__(self,reader,transport,*,stop_check=lambda:False,reserve=1):
        require(type(reserve) is int and reserve>=1,'Potion reserve must preserve at least one item')
        self.reader,self.transport,self.stop_check=reader,transport,stop_check
        self.reserve=reserve;self.started=False;self.attempted=False;self.events=[]

    def check_stop(self):
        require(not self.stop_check(),'STOP observed; Potion final input forbidden')
        return False

    def execute(self,token):
        require(not self.started,'Potion use gate cannot be retried')
        self.started=True
        self.check_stop()
        require(type(token) is PotionFinalToken and token.source==token.target==0x02000188
                and token.item==362 and token.ability==251 and 0<token.hp<241
                and token.count>self.reserve,'final input lacks bounded Potion token or violates reserve')
        self.reader.revalidate(token);self.check_stop()
        self.reader.revalidate(token);self.check_stop()
        self.attempted=True
        self.events.append({'event':'Potion_final_input_requested','mask':1})
        hits=self.transport.press(1,pause=0,tag='a662-self-Potion-final-once',stop_check=self.check_stop)
        require(hits==5,'partial Potion final input; never retry')
        self.events.append({'event':'Potion_final_input_delivered','hits':hits})
        return {'outcome':'final-input-delivered-only','actual_consumption_proved':False}
