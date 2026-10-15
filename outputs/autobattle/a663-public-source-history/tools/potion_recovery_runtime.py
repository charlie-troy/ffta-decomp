"""Public explicit opt-in to the bounded A6.6.2 self-Potion transaction."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json,time
from consumable_transaction import drive_potion_transaction
from recovery_transport import RecoveryTransport
from recovery_executor import RecoveryStopped
from recovery_menu import require


def drive_potion_recovery(runtime,journal,*,before_confirmation=lambda observation:None):
    owner,probe=runtime.owner,runtime.p
    journal.update(status='unknown',raw_writes=[],transport=[],inputs=[],observations=[],policy_observations=[])
    require(runtime.tactics is not None and runtime.tactics.policy['schema']=='ffta-tactics-policy/2'
            and runtime.tactics.policy.get('consumables') is True,'public Potion requires explicit schema2 consumables opt-in')
    require((owner['id'],owner['job'],owner['race'],owner['x'],owner['y'])==(5,5,1,5,10)
            and len(runtime._pre_players)==2,'public Potion actor/party outside bounded family')
    root=Path(runtime.events_path).parent;index=1
    while (root/f'Potion-transaction-{index}').exists():index+=1
    out=root/f'Potion-transaction-{index}';out.mkdir()
    start=len(getattr(probe,'key_write_log',[]))
    journal.update(schema='ffta-potion-recovery-turn/1',scope=__doc__,owner=dict(owner),capture_dir=str(out),
        started_t=round(time.time()-runtime.t0,3),write_start=start,policy_document=deepcopy(runtime.tactics.policy))
    def checkpoint():
        if runtime._stop_check():raise RecoveryStopped('STOP requested during public Potion')
        if time.time()-runtime.t0>=runtime.wall_timeout:raise TimeoutError('public Potion wall budget')
        return False
    def log_input(record):
        journal['raw_writes'].append(record);runtime._input_log.write(json.dumps(record)+'\n');runtime._input_log.flush()
    def observed(stage):
        checkpoint();before_confirmation(SimpleNamespace(state=stage));checkpoint()
    options=SimpleNamespace(rom=runtime.s.rom,inspect_potion_target=True,accept_potion_target=True,
        inspect_potion_final_prompt=True,execute_potion_once=True,complete_potion_turn=True,inject_stop_at=None)
    transport=RecoveryTransport(probe,log_input=log_input);probe.item_hits=[];probe.item_errors=[];probe.item_log_path=out/'Potion-engine.jsonl'
    try:
        with transport:
            drive_potion_transaction(runtime.s,probe,owner,transport,options,out,journal,
                external_stop_check=checkpoint,choose=runtime.tactics.choose_recovery,policy=runtime.tactics.policy,
                before_Potion_final=lambda token:observed('Potion-final'),
                before_Wait_final=lambda token:observed('Potion-Wait-final'))
        require(journal['Potion_continuation']['relation']=='enemy','public Potion continuation differs')
        journal['status']='confirmed';return True
    finally:
        journal.update(gameplay_writes=list(getattr(probe,'key_write_log',[])[start:]),fixture_writes=list(runtime.s.writes),
            potion_engine_hits=deepcopy(probe.item_hits),potion_engine_errors=list(probe.item_errors),
            ended_t=round(time.time()-runtime.t0,3))


def drive_public_potion_boundary(runtime,before):
    from autobattle_runtime import PAUSED,STALLED,RUNNING
    journal={}
    def capture(observation):
        runtime.s.screenshot(str(Path(runtime.events_path).parent/f'recovery-{observation.state}-turn{runtime.turn+1}.png'))
    try:confirmed=drive_potion_recovery(runtime,journal,before_confirmation=capture)
    except RecoveryStopped as exc:
        runtime.event('note',**runtime._actor_fields(),recovery=journal,note=str(exc))
        runtime._finish(PAUSED,'STOP during bounded Potion: manual handoff');return
    except (ValueError,TimeoutError) as exc:
        runtime.event('note',**runtime._actor_fields(),recovery=journal,note=str(exc))
        runtime._finish(STALLED,'bounded Potion rejected: '+str(exc));return
    except (OSError,ConnectionError) as exc:
        runtime.event('note',**runtime._actor_fields(),recovery=journal,note=str(exc));raise
    if runtime._stop_check():
        runtime.event('note',**runtime._actor_fields(),recovery=journal,note='STOP after Potion cleanup')
        runtime._finish(PAUSED,'STOP after bounded Potion');return
    require(confirmed,'Potion left unexecuted')
    after=journal['Potion_party_after']
    require({r['id'] for r in after}=={r['id'] for r in runtime._pre_players},'Potion post-turn party differs')
    for row in after:
        original=next(r for r in runtime._pre_players if r['id']==row['id'])
        require(all(row[k]==original[k] for k in ('name','job','race','level','max_hp','max_mp','side_raw')),
                'Potion party identity/maxima changed')
    runtime._engine_result={'verified':True,'players_before':runtime._pre_players,'players_after':after,
                            'source':'Potion native decrement/HP store and independent next actor'}
    runtime.turn+=1
    runtime.event('turn',turn=runtime.turn,**runtime._actor_fields(),control_mode='external',
        selected_action={'kind':'identified-self-potion','ability_id':251,'item_id':362},
        selected_target={'kind':'unit','id':5},position_before=before,
        position_after={'x':runtime.owner['x'],'y':runtime.owner['y']},engine_result=runtime._engine_result,
        recovery=journal,note='bounded self-Potion, guarded Wait and independent next enemy')
    runtime.state=RUNNING
