"""Inspect the UI target callback and payload after guarded selection; never cast."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from autobattle_identity import ActorAdapter
from build_recovery_fixture import verified_owner
from fixture_guard import FixtureSession, ROSTER, STRIDE
from probe_control_handoff import Probe
from probe_recovery_party import block
from recovery_menu import RecoveryMenu, MEMBERS, MEMBER_COUNT, exact, integer
from recovery_party import pin_party
from recovery_transport import RecoveryTransport
from recovery_ally_preview import AllyPreviewReader
from recovery_executor import SelfCureExecutor
from tactics_policy import load_policy_file


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True)
    args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    state='outputs/autobattle/a62-party-fixture-01/party-recovery.ss0'
    files=[state,'baserom.gba','configs/battle-scenarios/a4-two-player.json']+[
        'tools/'+name for name in ('probe_recovery_ally_panel.py','recovery_ally_preview.py','recovery_ally_target.py',
        'recovery_menu.py','recovery_party.py','recovery_executor.py','recovery_transport.py','probe_control_handoff.py')]
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    hashes={p:sha(p) for p in files};result={'status':'unknown','source_sha256':hashes,'raw_writes':[]}
    expect=json.loads(Path(files[2]).read_text())['guard_expectations'];expect['slot0_name']=int(expect['slot0_name'],0)
    try:
        with FixtureSession(state,expect=expect,quiet=True,work_dir=str(out/'session')) as session:
            session.g.sock.settimeout(1)
            probe=Probe(session,verbose=False);owner=verified_owner(session,probe);rom=session.read_rom_bytes()
            result.update(pid=session.pid,owner=owner)
            with RecoveryTransport(probe,log_input=result['raw_writes'].append) as transport:
                g=transport.g
                def name(address):
                    return rom[address-0x08000000:address-0x08000000+32] if address>=0x08000000 else exact(g,address,32)
                pins=pin_party(block(g,ROSTER,8*STRIDE),block(g,MEMBERS,MEMBER_COUNT*STRIDE),ActorAdapter(session).expected,name)
                units={p['canonical']:exact(g,p['canonical'],STRIDE) for p in pins};result['party_pins']=pins
                menu=RecoveryMenu(g,rom,owner);reader=AllyPreviewReader(g,menu,pins,units)
                def settle(key):transport.cont();time.sleep(0.25)
                executor=SelfCureExecutor(menu,transport,load_policy_file('configs/tactics/healer.json'),after_key=settle)
                result['events']=executor.events;result['transport']=transport.events
                def capture(tag):
                    (out/(tag+'-ewram.bin')).write_bytes(block(g,0x02000000,0x40000))
                    root=integer(exact(g,0x0200F440,4),0)
                    callback=integer(exact(g,root+12,4),0)
                    payload=callback+0x18
                    canonical=integer(exact(g,payload+12,4),0)
                    unit=exact(g,canonical,STRIDE)
                    result.setdefault('panels',[]).append({'tag':tag,'root':root,'callback':callback,
                        'handler':integer(exact(g,callback,4),0),'payload':payload,
                        'flags':integer(exact(g,payload+0x10,2),0,2),'canonical':canonical,
                        'name':integer(unit,0),'id':unit[0x104],'hp':integer(unit,0x18,2),'mp':integer(unit,0x1C,2)})
                    session.screenshot(str(out/(tag+'.png')))
                capture('initial')
                assert executor.select('command',9) and executor.select('action-group',10)
                assert executor.select('ability-list',1,ability=True)
                menu.revalidate(executor.observe('target-overlay'))
                assert transport.press(0x10,tag='panel-research:RIGHT')>0;settle('RIGHT')
                token=reader.snapshot();reader.revalidate(token)
                executor.press('A',executor.observe('target-overlay'))
                preview=reader.preview_snapshot();reader.revalidate_preview(preview)
                capture('preview')
                result['fixture_writes']=list(session.writes)
            result['status']='captured-preview-panel-only'
    except Exception as exc:
        result['error']=repr(exc);raise
    finally:
        result['inputs_unchanged']=all(sha(p)==h for p,h in hashes.items())
        result['capture_sha256']={p.name:sha(p) for p in out.glob('*.bin')}
        (out/'probe.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['panels'])


if __name__=='__main__':main()
