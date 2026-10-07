"""Opt-in public transaction for the exact eight-unit living ally-Cure family.

The target reader owns engine facts; the public tactics adapter sees each
fresh candidate. Wait and one independently joined next enemy close this
bounded transaction. Public lifecycle and terminal cleanup remain the caller's.
"""
import json
import time

from fixture_guard import read_roster, ROSTER, STRIDE
from recovery_menu import RecoveryMenu, RecoveryStateError, require, exact, MEMBERS, MEMBER_COUNT
from recovery_party import pin_party
from recovery_ally_confirmation import AllyConfirmationReader
from recovery_ally_executor import AllyCureExecutor
from recovery_executor import WaitFacingExecutor, RecoveryStopped
from recovery_transport import RecoveryTransport
from recovery_party_continuation import observe_party_continuation
from probe_recovery_party import block


class PartyPolicyDeclined(RecoveryStateError):
    pass


class PublicAllyReader(AllyConfirmationReader):
    def __init__(self,*args,adapter,journal,**kwargs):
        super().__init__(*args,**kwargs)
        self.adapter,self.journal=adapter,journal

    def policy_snapshot(self,token,clock=time.monotonic):
        snapshot=super().policy_snapshot(token,clock=clock)
        decision=self.adapter.choose_recovery(snapshot)
        self.journal.setdefault('policy_observations',[]).append({'snapshot':snapshot,'evaluation':decision})
        if (decision.get('decision') or {}).get('candidate_id')!='cure-ally':
            raise PartyPolicyDeclined('public policy declined ally Cure')
        return snapshot


def drive_party_recovery(runtime,journal,*,before_confirmation=lambda observation:None):
    owner,probe=runtime.owner,runtime.p
    start=len(getattr(probe,'key_write_log',[]))
    journal.update(schema='ffta-party-recovery-turn/1',scope='eight-unit pinned living ally Cure',
                   owner=dict(owner),write_start=start,continuations=[],
                   started_t=round(time.time()-runtime.t0,3),
                   policy_document=runtime.tactics.policy if runtime.tactics else None)
    def checkpoint():
        if runtime._stop_check():raise RecoveryStopped('STOP requested during party recovery')
        if time.time()-runtime.t0>=runtime.wall_timeout:raise TimeoutError('party recovery wall budget')
        return False
    def log_input(record):
        runtime._input_log.write(json.dumps(record)+'\n');runtime._input_log.flush()
    transport=RecoveryTransport(probe,log_input=log_input);journal['transport']=transport.events
    try:
        require(runtime.tactics is not None,'party recovery requires schema2 tactics')
        require((owner['id'],owner['job'],owner['race'],owner['x'],owner['y'])==(7,5,1,4,10)
                and len(runtime._pre_players)==2,'party recovery caster/party outside bounded family')
        rom=runtime.s.read_rom_bytes()
        with transport:
            checkpoint()
            roster=read_roster(transport.g,rom=rom)
            baseline=[r for r in roster['slots'] if r['live']]
            require(roster['struct_count']==roster['live_count']==8 and roster['ids_distinct']
                    and roster['live_contiguous'] and {r['id'] for r in baseline}==set(range(8)),
                    'party recovery requires restored eight-unit roster')
            g=transport.g
            def name(address):
                return rom[address-0x08000000:address-0x08000000+32] if address>=0x08000000 else exact(g,address,32)
            pins=pin_party(block(g,ROSTER,8*STRIDE),block(g,MEMBERS,MEMBER_COUNT*STRIDE),
                           runtime.adapter.expected,name)
            require({p['id'] for p in pins}=={5,7},'party recovery identities differ')
            units={p['canonical']:exact(g,p['canonical'],STRIDE) for p in pins}
            journal.update(party_before=pins,baseline_roster=baseline)
            menu=RecoveryMenu(g,rom,owner)
            reader=PublicAllyReader(g,menu,pins,units,adapter=runtime.tactics,journal=journal)
            require(menu.snapshot().cure_cost==6,'unsupported party Cure cost')
            def after_key(key):checkpoint();transport.cont();time.sleep(0.25)
            def observed(observation):
                checkpoint()
                log_input({'event':'recovery_confirmation','state':observation.state,
                           't':round(time.time()-runtime.t0,3),'actor_id':owner['id']})
                before_confirmation(observation);checkpoint()
            options=dict(stop_check=checkpoint,after_key=after_key,before_policy_final=observed,
                         choose=runtime.tactics.choose_recovery)
            cure=AllyCureExecutor(menu,transport,runtime.tactics.policy,reader,**options)
            journal['cure_events']=cure.events
            before=menu.snapshot()
            try:
                journal['recovery']=cure.run()
            except PartyPolicyDeclined:
                require(not cure.committed,'policy declined after final input')
                require(len(journal['policy_observations'])==1,'party policy changed after observation; no retry')
                journal['recovery']=cure.cancel(before)
                require(all(exact(g,a,STRIDE)[0x18:0x20]==u[0x18:0x20] for a,u in units.items()),
                        'party resources changed while cancelling declined Cure')
            wait=WaitFacingExecutor(menu,transport,runtime.tactics.policy,**options)
            journal['wait_events']=wait.events;journal['finish']=wait.run()
            if journal['finish']['outcome']!='confirmed':
                journal['status']='unexecuted-wait';return False
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                checkpoint();transport.cont();time.sleep(0.25);checkpoint();transport.interrupt()
                try:
                    observation=observe_party_continuation(g,rom,owner,journal['finish']['facing'],pins,units,baseline)
                except RecoveryStateError as exc:
                    journal.setdefault('continuation_rejections',[]).append(str(exc));continue
                require(observation['relation']=='enemy','bounded party continuation requires next enemy')
                journal['continuations'].append(observation);break
            require(len(journal['continuations'])==1,'party continuation not established')
            journal['status']='confirmed';return True
    finally:
        journal['raw_writes']=list(getattr(probe,'key_write_log',[])[start:])
        journal['ended_t']=round(time.time()-runtime.t0,3)
