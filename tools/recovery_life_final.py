"""Single-attempt research Life final input behind current target and policy gates.

This gate does not verify an effect or finish a turn. Transport delivery may be
ambiguous; the final-input latch is set before transport and cannot be retried.
"""
from copy import deepcopy

from recovery_menu import require
from recovery_life_target import LifeOverlayToken
from tactics_policy import evaluate


class LifeFinalGate:
    def __init__(self, reader, transport, policy, *, stop_check=lambda: False,
                 before_final=lambda: None, choose=None):
        self.reader, self.transport, self.policy = reader, transport, policy
        self.stop_check, self.before_final = stop_check, before_final
        self.started, self.final_attempted = False, False
        self.events = []
        self.choose = choose or (lambda snapshot:evaluate(snapshot,self.policy))

    def check_stop(self):
        require(not self.stop_check(), 'STOP observed; Life final input forbidden')
        return False

    def commit(self, token):
        require(not self.started, 'Life final gate cannot be reused')
        self.started = True
        self.check_stop()
        require(isinstance(token,LifeOverlayToken) and token.stage == 'confirmation',
                'Life final input lacks the accepted final target token')
        snapshot = self.reader.policy_snapshot(token)
        decision = self.choose(snapshot)
        self.events.append({'event': 'policy', 'policy': deepcopy(self.policy),
                            'snapshot': snapshot, 'evaluation': decision, 'token': token.receipt()})
        require((decision.get('decision') or {}).get('candidate_id') == 'life-ally',
                'policy declined Life; no final input')
        self.before_final()
        self.check_stop()
        token = self.reader.revalidate(token,at_target=True)
        snapshot = self.reader.policy_snapshot(token)
        final_decision = self.choose(snapshot)
        require((final_decision.get('decision') or {}).get('candidate_id') == 'life-ally',
                'final policy declined Life; no final input')
        self.events.append({'event': 'final_policy', 'policy': deepcopy(self.policy),
            'snapshot': snapshot, 'evaluation': final_decision, 'token': token.receipt()})
        self.check_stop()
        self.reader.revalidate(token,at_target=True)
        self.check_stop()
        self.final_attempted = True
        self.events.append({'event': 'final_input_requested', 'mask': 1})
        hits = self.transport.press(1,tag='a64-Life-single-final-A',stop_check=self.check_stop)
        require(hits == 5, 'Life final input delivery incomplete; never retry')
        self.events.append({'event': 'final_input_delivered', 'hits': hits})
        return {'outcome': 'final-input-delivered-only', 'final_attempted': True,
                'effect': 'unknown', 'wait': 'unexecuted', 'continuation': 'unknown'}
