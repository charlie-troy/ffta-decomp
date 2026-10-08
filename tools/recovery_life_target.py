"""Read-only Life overlay research token; never authorizes final confirmation.

The exact fixture has living Montblanc5 and genuine engine-KO Marche7. Its
native target table contains only Marche, unlike the two-entry Cure overlay.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import time

from fixture_guard import BATTLE_STRUCT, STRIDE
from probe_control_handoff import TARGET_X
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, LIST, DESCRIPTION, exact, integer, require
from ability_resources import effective_mp_cost

ACCEPTANCE_CURSOR = 0x0200F3B8


@dataclass(frozen=True)
class LifeOverlayToken:
    observed_at: float
    caster: int
    target: int
    target_wrapper: int
    cursor: tuple
    target_tile: tuple
    decision_sha256: str
    stage: str = 'overlay'

    def receipt(self):
        return asdict(self)


class LifeOverlayReader:
    def __init__(self, g, menu, pins, units, clock=time.monotonic):
        self.g, self.menu, self.clock = g, menu, clock
        self.pins = {p['canonical']: dict(p) for p in pins}
        self.units = {a: bytes(u) for a,u in units.items()}
        require({p['id'] for p in pins} == {5, 7} and menu.owner['id'] == 5
                and set(self.pins) == set(self.units), 'Life overlay fixture differs')
        self.caster = next(a for a,p in self.pins.items() if p['id'] == 5)
        self.target = next(a for a,p in self.pins.items() if p['id'] == 7)
        require(menu.member == self.caster and self.pins[self.target]['hp'] == 0
                and self.pins[self.target]['ko_suffered'] > 0
                and not any(self.pins[self.target]['statuses'].values()), 'Life lacks genuine KO baseline')
        for address,pin in self.pins.items():
            unit = self.units[address]
            require(hashlib.sha256(unit).hexdigest() == pin['canonical_sha256']
                    and integer(unit,0) == pin['name'] and unit[0x104] == pin['id'], 'Life baseline pin differs')
        self.name_hashes = {a: self.name_hash(p['name']) for a,p in self.pins.items()}

    def name_hash(self, address):
        rom = self.menu.rom
        if 0x08000000 <= address <= 0x08000000+len(rom)-32:
            value = rom[address-0x08000000:address-0x08000000+32]
        else:
            value = exact(self.g, address, 32)
        return hashlib.sha256(value).hexdigest()

    def snapshot(self):
        return self._snapshot('overlay')

    def preview_snapshot(self):
        return self._snapshot('preview')

    def _snapshot(self, stage):
        g, menu = self.g, self.menu
        require(stage in ('overlay','preview'), 'Life target stage is unknown')
        mode, selection, handler, controller_state, target_flags = (
            (7,5,LIST,3,0) if stage == 'overlay' else (12,0,DESCRIPTION,0x102,0x6C))
        require(integer(exact(g,MENU_ROOT,4),0) == menu.context, 'Life root moved')
        root = exact(g,menu.context,0x30)
        callback = exact(g,menu.callback,0x18)
        require(root[4] == mode and integer(root,0,2) == selection and integer(root,0x14) == 5
                and integer(root,0x18) == integer(root,0x1C) == self.caster
                and integer(root,0x20) == menu.manager and integer(root,0x28) == menu.callback
                and integer(callback,0) == handler and integer(callback,0x14,2) == controller_state,
                'not the captured Life '+stage)
        driver = exact(g,PLAYER_DRIVER,0xE0)
        active = exact(g,menu.manager+4,4)
        require(integer(driver,4) == integer(driver,8) == menu.wrapper
                and integer(driver,0xDC,2) == 0x31 and integer(driver,0x60) == BATTLE_STRUCT
                and integer(active,0) == (0 if stage == 'overlay' else menu.callback),
                'Life target driver/callback differs')
        header = exact(g,BATTLE_STRUCT,0xA4)
        actor_wrapper = exact(g,menu.wrapper,0x10)
        require(integer(actor_wrapper,0) == self.caster and integer(header,0) == menu.wrapper
                and integer(header,12) == integer(header,16) == 0
                and header[0xA2] == 1 and header[0xA1] == 0, 'Life target table or accepted copies differ')
        ability = exact(g,BATTLE_STRUCT+0xEC,2)
        flags = exact(g,BATTLE_STRUCT+0x1112,2)
        state = exact(g,BATTLE_STRUCT+0x1118,2)
        require(integer(ability,0,2) == 5 and integer(flags,0,2) == target_flags and integer(state,0,2) == 10,
                'Life target processor differs')
        target_wrapper = integer(header,0x50)
        wrapper = exact(g,target_wrapper,0x10)
        require(target_wrapper != menu.wrapper and integer(wrapper,0) == self.target,
                'Life target wrapper does not join canonical KO')
        if stage == 'preview':
            require(integer(header,4) == menu.wrapper and integer(header,8) == target_wrapper,
                    'Life preview did not accept the canonical KO wrapper')
        reads = [(MENU_ROOT,menu.context.to_bytes(4,'little')), (menu.context,root),
                 (menu.callback,callback), (menu.manager+4,active), (PLAYER_DRIVER+4,driver[4:12]),
                 (PLAYER_DRIVER+0x60,driver[0x60:0x64]), (PLAYER_DRIVER+0xDC,driver[0xDC:0xDE]),
                 (menu.wrapper,actor_wrapper), (target_wrapper,wrapper),
                 (BATTLE_STRUCT+0xEC,ability), (BATTLE_STRUCT+0x1112,flags), (BATTLE_STRUCT+0x1118,state)]
        # Live preview captures differ at +93/+94/+9C while the accepted
        # wrapper, table, resources and coordinates agree. These animation
        # bytes are not a targeting decision and cannot invalidate its token.
        reads.extend((BATTLE_STRUCT+o,header[o:o+n]) for o,n in ((0,0x18),(0x50,4),(0xA1,2)))
        for address,baseline in self.units.items():
            unit = exact(g,address,STRIDE)
            require(unit == baseline and self.name_hash(self.pins[address]['name']) == self.name_hashes[address],
                    'Life canonical resources/identity/status/tile changed')
            require(integer(unit,0x28,2) & 0x9000 == 0, 'Life party side changed')
            reads.append((address,unit))
        require(integer(self.units[self.caster],0x18,2) > 0
                and integer(self.units[self.target],0x18,2) == 0
                and effective_mp_cost(menu.rom,5,self.units[self.caster]) == 10
                and integer(self.units[self.caster],0x1C,2) >= 10, 'Life resources/cost unsupported')
        for i in range(MEMBER_COUNT):
            address = MEMBERS+i*STRIDE
            if address not in self.pins:
                other = exact(g,address,STRIDE)
                require(all(integer(other,0) != p['name'] and other[0x104] != p['id']
                            for p in self.pins.values()), 'Life canonical name/id alias')
        display = exact(g,TARGET_X,2)
        x,y = exact(g,ACCEPTANCE_CURSOR,2),exact(g,ACCEPTANCE_CURSOR+4,2)
        cursor = (integer(x,0,2),integer(y,0,2))
        target_tile = tuple(self.pins[self.target]['tile'])
        require(cursor == tuple(display) and cursor in (tuple(self.pins[self.caster]['tile']),target_tile),
                'Life cursor is outside the captured two tiles')
        reads.extend([(TARGET_X,display),(ACCEPTANCE_CURSOR,x),(ACCEPTANCE_CURSOR+4,y)])
        if stage == 'preview':
            committed = exact(g,BATTLE_STRUCT+0x109,2)
            require(cursor == tuple(committed) == target_tile, 'Life preview committed tile differs')
            reads.append((BATTLE_STRUCT+0x109,committed))
        require(all(exact(g,a,len(b)) == b for a,b in reads), 'Life overlay changed during read')
        digest = hashlib.sha256(repr([(a,b.hex()) for a,b in reads]).encode()).hexdigest()
        return LifeOverlayToken(self.clock(),self.caster,self.target,target_wrapper,cursor,target_tile,digest,stage)

    def revalidate(self, token, *, at_target=False):
        require(isinstance(token,LifeOverlayToken) and 0 <= self.clock()-token.observed_at <= 2,
                'stale or foreign Life overlay token')
        current = self._snapshot(token.stage)
        require(replace(current,observed_at=token.observed_at) == token, 'Life overlay token changed')
        require(not at_target or current.cursor == current.target_tile, 'Life KO cursor is not selected')
        return current
