"""One guarded self-Potion target acceptance input; never final item use."""
from consumable_overlay import PotionOverlayToken
from recovery_menu import require


class PotionPreviewGate:
    def __init__(self,reader,transport,*,stop_check=lambda:False):
        self.reader,self.transport,self.stop_check=reader,transport,stop_check
        self.started=False;self.attempted=False;self.events=[]

    def check_stop(self):
        require(not self.stop_check(),'STOP observed; Potion preview input forbidden')
        return False

    def advance(self,token):
        require(not self.started,'Potion preview gate cannot be retried')
        self.started=True
        self.check_stop()
        require(isinstance(token,PotionOverlayToken) and token.source==token.target
                and token.item_id==362 and token.ability_id==251 and token.count>0
                and 0<token.hp<token.max_hp,'preview lacks wounded self-Potion overlay token')
        self.reader.revalidate(token)
        self.check_stop()
        self.reader.revalidate(token)
        self.check_stop()
        self.attempted=True
        self.events.append({'event':'target_input_requested','mask':1})
        hits=self.transport.press(1,tag='a66-Potion-target-accept-only',stop_check=self.check_stop)
        require(hits==5,'partial Potion preview input; never retry')
        self.events.append({'event':'target_input_delivered','hits':hits})
        return {'outcome':'target-input-delivered-only','final_input':False}
