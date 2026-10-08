"""Replay captured Life overlays and reject stale/foreign KO-target tokens."""
import argparse
import hashlib
import json
from pathlib import Path

from fixture_guard import BATTLE_STRUCT, STRIDE
from probe_control_handoff import TARGET_X
from recovery_menu import MEMBERS, PLAYER_DRIVER, require
from recovery_menu_list import ResearchMenuList
from recovery_life_target import LifeOverlayReader, ACCEPTANCE_CURSOR
from validate_recovery_life_menu import Memory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--out', required=True)
    ap.add_argument('--stage', choices=('overlay','preview'), default='overlay')
    args = ap.parse_args()
    directory = Path(args.capture)
    doc = json.loads((directory/'Life-overlay.json').read_text())
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    preview = args.stage == 'preview'
    require(doc['status'] == ('captured-Life-target-selection-only' if preview else 'captured-Life-overlay-only')
            and doc['inputs_unchanged'] and doc['target_acceptance'] == preview and not doc['final_confirmation']
            and not doc['fixture_writes'], 'capture authority differs')
    rom = Path(args.rom).read_bytes()
    require(sha(args.rom) == doc['source_sha256'][args.rom], 'ROM differs')
    paths = [directory/(p['tag']+'-ewram.bin') for p in doc['phases']
             if p['tag'].startswith('selected-' if preview else 'overlay-')]
    require(len(paths) >= 2, 'missing second Life overlay join')
    for path in paths:
        require(sha(path) == doc['capture_sha256'][path.name], 'capture hash differs')
    def reader(data, clock=lambda: 1):
        g = Memory(data)
        caster = next(p['canonical'] for p in doc['party'] if p['id'] == 5)
        menu = ResearchMenuList(g,rom,doc['owner'],caster)
        units = {p['canonical']: g.read_mem(p['canonical'],STRIDE) for p in doc['party']}
        return g,menu,LifeOverlayReader(g,menu,doc['party'],units,clock=clock)
    tokens = []
    snapshot = lambda r: r.preview_snapshot() if preview else r.snapshot()
    for path in paths:
        g,menu,r = reader(path.read_bytes())
        token = snapshot(r)
        r.revalidate(token)
        tokens.append(token)
    require(tokens[0] == tokens[1], 'two captured Life joins differ')
    data = paths[0].read_bytes()
    g,menu,r = reader(data)
    token = snapshot(r)
    rejected = []
    def reject(label, changes):
        g,m,r = reader(data)
        original = snapshot(r)
        for address,value in changes:
            g.write(address,value)
        try:
            r.revalidate(original)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError('accepted Life overlay mutation: '+label)
    for role,address in [('caster',token.caster),('KO-target',token.target)]:
        for label,offset,value in [('name',0,b'\0'*4),('id',0x104,b'\x2a'),
                ('race',6,b'\x02'),('job',7,b'\xff'),('secondary',8,b'\xff'),
                ('HP',0x18,(1 if role == 'KO-target' else 0).to_bytes(2,'little')),
                ('MP',0x1C,b'\0\0'),('side',0x29,b'\x80'),('unaffiliated',0x29,b'\x10'),
                ('tile',0xF6,b'\x3f'),('status',0xE9,b'\xff'),('KO-counter',0xF2,b'\xff')]:
            reject(role+'-'+label,[(address+offset,value)])
    for label,address,value in [('root',0x0200F438,b'\0'*4),
            ('ability',menu.context+0x14,(1).to_bytes(4,'little')),
            ('peer',menu.context+0x1C,token.target.to_bytes(4,'little')),
            ('member',menu.context+0x18,token.target.to_bytes(4,'little')),
            ('mode',menu.context+4,b'\x07' if preview else b'\x0c'),('selection',menu.context,b'\x01\x00'),
            ('callback',menu.context+0x28,b'\0'*4),('manager',menu.context+0x20,b'\0'*4),
            ('handler',menu.callback,b'\0'*4),('controller',menu.callback+0x14,b'\x03\0' if preview else b'\x02\x01'),
            ('active-callback',menu.manager+4,b'\0'*4 if preview else menu.callback.to_bytes(4,'little')),
            ('driver-owner',PLAYER_DRIVER+4,b'\0'*4),('driver-peer',PLAYER_DRIVER+8,b'\0'*4),
            ('processor',PLAYER_DRIVER+0x60,b'\0'*4),('driver-state',PLAYER_DRIVER+0xDC,b'\x25\0'),
            ('wrapper',menu.wrapper,token.target.to_bytes(4,'little')),
            ('target-wrapper',token.target_wrapper,token.caster.to_bytes(4,'little')),
            ('target-table',BATTLE_STRUCT+0x50,menu.wrapper.to_bytes(4,'little')),
            ('count-zero',BATTLE_STRUCT+0xA2,b'\0'),('Cure-count-two',BATTLE_STRUCT+0xA2,b'\x02'),
            ('index',BATTLE_STRUCT+0xA1,b'\x01'),('accepted-copy',BATTLE_STRUCT+12,b'\x01\0\0\0'),
            ('processor-ability',BATTLE_STRUCT+0xEC,b'\x01\0'),
            ('target-flags',BATTLE_STRUCT+0x1112,b'\0\0' if preview else b'\x6c\0'),('target-state',BATTLE_STRUCT+0x1118,b'\x02\0'),
            ('display-cursor',TARGET_X,b'\x3f\x3f'),('acceptance-x',ACCEPTANCE_CURSOR,b'\x3f\0')]:
        reject(label,[(address,value)])
    alias = MEMBERS+13*STRIDE
    for p in doc['party']:
        reject('alias-name-'+str(p['id']),[(alias,p['name'].to_bytes(4,'little'))])
        reject('alias-id-'+str(p['id']),[(alias+0x104,bytes([p['id']]))])
    # The initial cursor is on the caster despite the one-entry KO table.
    if not preview:
        try:
            r.revalidate(token,at_target=True)
        except ValueError:
            rejected.append('caster-cursor-is-not-KO-selection')
        else:
            raise AssertionError('initial Life cursor accepted as selected KO')
    else:
        r.revalidate(token,at_target=True)
        reject('accepted-preview-wrapper',[(BATTLE_STRUCT+8,menu.wrapper.to_bytes(4,'little'))])
        reject('committed-preview-tile',[(BATTLE_STRUCT+0x109,b'\x3f\x3f')])
    now = [1]
    g,m,r = reader(data,clock=lambda: now[0])
    old = snapshot(r)
    now[0] = 4
    try:
        r.revalidate(old)
    except ValueError:
        rejected.append('expired-token')
    else:
        raise AssertionError('expired overlay token accepted')
    # Synthetic coherence control, not observed navigation or acceptance.
    g,m,r = reader(data)
    x,y = token.target_tile
    g.write(TARGET_X,bytes((x,y)))
    g.write(ACCEPTANCE_CURSOR,x.to_bytes(2,'little'))
    g.write(ACCEPTANCE_CURSOR+4,y.to_bytes(2,'little'))
    r.revalidate(snapshot(r),at_target=True)
    result = {'status': 'pass-retained-Life-overlay-guards', 'scope': __doc__,
        'stage': args.stage, 'captured_joins': len(paths), 'rejected': rejected, 'synthetic_KO_cursor_control': not preview,
        'token': token.receipt(),
        'source_sha256': {p: sha(p) for p in ('tools/validate_recovery_life_overlay.py',
            'tools/recovery_life_target.py','tools/recovery_menu_list.py','tools/validate_recovery_life_menu.py')},
        'evidence_sha256': {str(p): sha(p) for p in [directory/'Life-overlay.json',*paths]},
        'limitations': ['Retained overlay guards and synthetic cursor coherence only; no accepted target or final authority.']}
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS retained Life overlay:',len(rejected),'rejected mutations/controls')


if __name__ == '__main__':
    main()
