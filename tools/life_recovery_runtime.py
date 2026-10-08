"""Explicit public opt-in for the exact accepted A6.4 Life transaction."""
from copy import deepcopy
import json
from pathlib import Path
import time
from types import SimpleNamespace

from fixture_guard import STRIDE
from life_recovery_transaction import drive_life_transaction
from recovery_executor import RecoveryStopped
from recovery_menu import require
from recovery_transport import RecoveryTransport


def drive_life_recovery(runtime,journal,*,before_confirmation=lambda observation:None):
    owner,probe=runtime.owner,runtime.p
    require(runtime.tactics is not None and runtime.tactics.policy['schema']=='ffta-tactics-policy/2',
            'public Life requires schema2 tactics')
    early_t=round(time.time()-runtime.t0,3)
    journal.update(schema='ffta-life-recovery-turn/1',owner=dict(owner),status='unknown',
        write_start=len(getattr(probe,'key_write_log',[])),started_t=early_t,ended_t=early_t,
        raw_writes=[],gameplay_writes=[],fixture_writes=[],life_engine_errors=[],transport=[],
        policy_document=deepcopy(runtime.tactics.policy),policy_observations=[],navigation=[],
        final_confirmation=False)
    require((owner['id'],owner['job'],owner['race'],owner['x'],owner['y'])==(5,5,1,5,10)
            and len(runtime._pre_players)==2,'public Life caster/party outside bounded family')
    root=Path(runtime.events_path).parent
    index=1
    while (root/f'Life-transaction-{index}').exists():index+=1
    out=root/f'Life-transaction-{index}';out.mkdir()
    start=len(getattr(probe,'key_write_log',[]))
    journal.update(schema='ffta-life-recovery-turn/1',scope=__doc__,owner=dict(owner),
        status='unknown',write_start=start,started_t=round(time.time()-runtime.t0,3),
        capture_dir=str(out),raw_writes=[],navigation=[],phases=[],target_acceptance=False,
        final_confirmation=False,policy_document=deepcopy(runtime.tactics.policy),policy_observations=[])
    def checkpoint():
        if runtime._stop_check():raise RecoveryStopped('STOP requested during public Life')
        if time.time()-runtime.t0>=runtime.wall_timeout:raise TimeoutError('public Life wall budget')
        return False
    def log_input(record):
        journal['raw_writes'].append(record)
        runtime._input_log.write(json.dumps(record)+'\n');runtime._input_log.flush()
    def choose(snapshot):
        decision=runtime.tactics.choose_recovery(snapshot)
        journal['policy_observations'].append({'snapshot':deepcopy(snapshot),'evaluation':deepcopy(decision)})
        return decision
    def observed(stage):
        checkpoint();before_confirmation(SimpleNamespace(state=stage));checkpoint()
    options=SimpleNamespace(execute_Life=True,execute_Wait=True,inspect_Wait=False,
        move_to_KO=True,accept_target=True,inspect_final_prompt=True,stop_at_stage=None)
    transport=RecoveryTransport(probe,log_input=log_input);journal['transport']=transport.events
    probe.life_hits=[];probe.life_errors=[];probe.life_log_path=str(out/'Life-engine.jsonl')
    try:
        with transport:
            checkpoint()
            drive_life_transaction(runtime.s,probe,owner,transport,runtime.tactics.policy,options,out,journal,
                external_stop_check=checkpoint,choose=choose,
                before_Life_final=lambda token:observed('Life-final'),
                before_Wait_final=lambda token:observed('Life-Wait-final'))
        require(journal['Life_effect']['wait']=='delivered'
                and journal['Life_effect']['continuation']['relation']=='enemy','public Life continuation differs')
        # Only independently verified native growth may update future fresh-menu identity.
        row=next(r for r in journal['post_Life_roster'] if r['id']==owner['id'])
        require(row['level']==41 and journal['effect_attribution']['level']==[40,41],
                'public Life growth rebind lacks its native witness')
        for expected in runtime.adapter.expected:
            if expected['id']==owner['id']:
                expected.update(level=row['level'],max_hp=row['max_hp'],max_mp=row['max_mp'])
        journal['status']='confirmed';return True
    finally:
        journal.update(gameplay_writes=list(getattr(probe,'key_write_log',[])[start:]),
            fixture_writes=list(runtime.s.writes),life_engine_hits=deepcopy(probe.life_hits),
            life_engine_errors=list(probe.life_errors),ended_t=round(time.time()-runtime.t0,3))
        for key,name in [('effect_units_before','final-prompt-second-ewram.bin'),('effect_units_after','after-Life-ewram.bin')]:
            path=out/name
            if path.exists() and journal.get('party'):
                raw=path.read_bytes()
                journal[key]={str(p['canonical']):raw[p['canonical']-0x02000000:
                    p['canonical']-0x02000000+STRIDE].hex() for p in journal['party']}
