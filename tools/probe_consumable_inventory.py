"""Capture owned Item rows and inventory without selecting or consuming an item.

Command and Action navigation uses existing ownership/acceptance tokens. Once
Item opens this research probe captures raw RAM, then stops; a raw list is not
published as an executable item candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter, IdentityError
from consumable_inventory import ConsumableInventory, INVENTORY, ITEM_IDS
from consumable_menu import OwnedItemList
from consumable_overlay import PotionOverlayReader
from consumable_preview_gate import PotionPreviewGate
from consumable_description import PotionDescriptionReader,PotionPromptInspectionGate
from consumable_final import PotionFinalPromptReader
from consumable_use_gate import PotionUseGate
from consumable_effect_trace import PotionExecutionProbe
from emulate import Gba
from ffta_names import Names, UI_STRINGS
from fixture_guard import FixtureSession, STRIDE,read_roster
from recovery_life_wait import LifeWaitBoundary
from recovery_party_continuation import observe_party_continuation
from probe_control_handoff import Probe
from probe_recovery_ko_lifecycle import source_dependencies
from probe_recovery_party import block
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, exact, integer, require, RecoveryTransient
from recovery_menu_list import ResearchMenuList
from consumable_transport import ConsumableResearchTransport
from consumable_transaction import drive_potion_transaction


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',default='outputs/autobattle/a64-life-fixture-01/life-recovery.ss0')
    ap.add_argument('--rom',default='baserom.gba')
    ap.add_argument('--scenario',default='configs/battle-scenarios/a4-two-player.json')
    ap.add_argument('--out',required=True)
    ap.add_argument('--inspect-potion-target',action='store_true',
                    help='Select enabled Potion once, capture the overlay, then stop without target acceptance')
    ap.add_argument('--accept-potion-target',action='store_true',
                    help='One guarded self target-acceptance input; capture preview, never confirm item use')
    ap.add_argument('--inspect-potion-final-prompt',action='store_true',
                    help='Open the final prompt from a pinned description; never select Do it')
    ap.add_argument('--execute-potion-once',action='store_true',help='Research only: one guarded final use and passive native HP-store observation')
    ap.add_argument('--complete-potion-turn',action='store_true',help='After witnessed use, guarded Wait and independent next-actor observation')
    ap.add_argument('--inject-stop-at',choices=('final-use','post-effect','Wait-final'),help='Research cancellation control: create an actual STOP file at this boundary')
    args=ap.parse_args()
    require(not args.accept_potion_target or args.inspect_potion_target,'preview requires explicit Potion overlay inspection')
    require(not args.inspect_potion_final_prompt or args.accept_potion_target,'final-prompt inspection requires target acceptance')
    require(not args.execute_potion_once or args.inspect_potion_final_prompt,'single use requires final-context inspection')
    require(not args.complete_potion_turn or args.execute_potion_once,'turn completion requires single-use witness')
    require(not args.inject_stop_at or args.execute_potion_once,'STOP injection requires bounded use experiment')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    paths=[args.state,args.rom,args.scenario]+source_dependencies('probe_consumable_inventory')
    result={'schema':'ffta-consumable-inventory-research/1','status':'unknown','scope':__doc__,
            'source_sha256':{p:sha(p) for p in paths},'observations':[],'inputs':[]}
    expect=json.loads(Path(args.scenario).read_text())['guard_expectations']
    expect['slot0_name']=int(expect['slot0_name'],0)
    probe=None;session=None
    try:
        with FixtureSession(args.state,rom=args.rom,expect=expect,quiet=True,work_dir=str(out/'session')) as session:
            session.g.sock.settimeout(2)
            result['pid']=session.pid
            probe=(PotionExecutionProbe if args.execute_potion_once else Probe)(session,verbose=False)
            if args.execute_potion_once:probe.item_log_path=out/'native-Potion-hits.jsonl'
            adapter=ActorAdapter(session);owner=None
            deadline=time.monotonic()+100
            while owner is None and time.monotonic()<deadline:
                require(not (out/'STOP').exists(),'STOP during passive owner acquisition')
                probe.pump(2,'Item-owner',sample_every=60)
                try:owner=adapter.observe(probe,adapter.snapshot())
                except IdentityError as exc:
                    adapter.prior=None
                    result.setdefault('passive_rejections',[]).append(str(exc))
            require(owner is not None,'no independently verified fresh Item-menu owner')
            probe.active_player_slot=owner['slot'];adapter.revalidate(owner,probe);result['owner']=owner
            with ConsumableResearchTransport(probe) as transport:
                drive_potion_transaction(session,probe,owner,transport,args,out,result)
            session.screenshot(str(out/'Item-list.png'))
            # Terminal research exit already disarmed while halted. No trace
            # restoration or second disarm can race a newly queued trace stop.
            result['strict_trace_disarmed']=True
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:
        if probe is not None:
            result.update(gameplay_writes=getattr(probe,'key_write_log',[]),fixture_writes=probe.s.writes)
        result['owned_process_closed']=session is not None and session.pid is None
        result['inputs_unchanged']=all(sha(p)==h for p,h in result['source_sha256'].items())
        (out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['status'],result['raw_list']['rows'])


if __name__=='__main__':main()
