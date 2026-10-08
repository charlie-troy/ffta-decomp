"""Research command/group/ability lists for a pinned living caster.

ROM and RAM names are checked explicitly. Target overlays, descriptions and
final prompts are deliberately outside this reader's accepted states.
"""
from dataclasses import asdict, dataclass
import hashlib

from ability_resources import RACE_TABLE
from fixture_guard import STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, MENU_ROOT, PLAYER_DRIVER, LIST, exact, integer, require, RecoveryTransient


@dataclass(frozen=True)
class ListToken:
    state: str
    cursor: int
    scroll: int
    rows: tuple
    enabled: tuple
    ability_ids: tuple
    hp: int
    mp: int
    member: int
    mode: int
    context: int
    callback: int
    active: int
    unit_sha256: str
    decision_sha256: str

    def receipt(self):
        return asdict(self)


class ResearchMenuList:
    def __init__(self, g, rom, owner, canonical):
        self.g, self.rom, self.owner, self.member = g, rom, dict(owner), canonical
        unit = exact(g, canonical, STRIDE)
        require(integer(unit, 0) == owner['name'] and unit[0x104] == owner['id']
                and unit[6:8] == bytes((owner['race'], owner['job']))
                and integer(unit, 0x28, 2) & 0x9000 == 0 and integer(unit, 0x18, 2) > 0,
                'research list caster identity differs')
        self.identity = (unit[:0x18], unit[0x1A:0x1C], unit[0x1E:0x20], unit[0x28:0x2A],
                         unit[0x3B], unit[0xF6:0xF8], unit[0x104])
        self.name_digest = self.name_hash()
        self.context = integer(exact(g, MENU_ROOT, 4), 0)
        root = exact(g, self.context, 0x30)
        require(integer(root, 0x18) == canonical, 'research list menu owner differs')
        self.callback, self.manager = integer(root, 0x28), integer(root, 0x20)
        self.wrapper = integer(exact(g, PLAYER_DRIVER+4, 4), 0)

    def name_hash(self):
        address = self.owner['name']
        if 0x08000000 <= address <= 0x08000000+len(self.rom)-32:
            name = self.rom[address-0x08000000:address-0x08000000+32]
        else:
            name = exact(self.g, address, 32)
        return hashlib.sha256(name).hexdigest()

    def snapshot(self):
        g = self.g
        require(integer(exact(g, MENU_ROOT, 4), 0) == self.context, 'research list context moved')
        root = exact(g, self.context, 0x30)
        unit = exact(g, self.member, STRIDE)
        identity = (unit[:0x18], unit[0x1A:0x1C], unit[0x1E:0x20], unit[0x28:0x2A],
                    unit[0x3B], unit[0xF6:0xF8], unit[0x104])
        require(identity == self.identity and self.name_hash() == self.name_digest,
                'research list canonical identity changed')
        hp, maximum, mp, max_mp = [integer(unit, o, 2) for o in (0x18, 0x1A, 0x1C, 0x1E)]
        require(0 < hp <= maximum <= 999 and 0 <= mp <= max_mp <= 999, 'research list resource bounds')
        for i in range(MEMBER_COUNT):
            address = MEMBERS+i*STRIDE
            if address != self.member:
                other = exact(g, address, STRIDE)
                require(integer(other, 0) != self.owner['name'] and other[0x104] != self.owner['id'],
                        'research list canonical name/id alias')
        require(integer(root, 0x18) == self.member and integer(root, 0x28) == self.callback
                and integer(root, 0x20) == self.manager, 'research list allocation changed')
        driver = exact(g, PLAYER_DRIVER, 0xE0)
        require(integer(driver, 4) == integer(driver, 8) == self.wrapper
                and integer(exact(g, self.wrapper, 4), 0) == self.member
                and integer(driver, 0x60) == 0
                and integer(exact(g, self.manager+4, 4), 0) == self.callback,
                'research list driver/callback differs')
        callback = exact(g, self.callback, 0x18)
        mode, state = root[4], integer(callback, 0x14, 2)
        require(integer(callback, 0) == LIST, 'research list handler is unsupported')
        active = self.callback
        if mode == 5 and state == 0x106:
            active = integer(callback, 0x10)
            child = exact(g, active, 0x18)
            require(integer(child, 0) == LIST and integer(child, 0xC) == self.callback,
                    'research list Action child is unowned')
            state = integer(child, 0x14, 2)
            kind = 'action-group'
        elif mode == 4:
            require(integer(driver, 0xDC, 2) == 0x25, 'research command driver is unowned')
            kind = 'command'
        elif mode in (6, 7):
            kind = 'ability-list'
        else:
            raise ValueError(f'research list rejects mode={mode} state={state:04x} handler={integer(callback,0):08x}')
        if state in (0x100, 0x101):
            raise RecoveryTransient('owned research list is opening')
        require(state == 0x102, 'research list is not accepting input')
        obj = exact(g, active+0x18, 0x9C)
        count, scroll, cursor = integer(obj, 0x50, 2), integer(obj, 0x52, 2), obj[0x69]
        require(0 < count <= 32 and cursor < count and scroll+cursor < count, 'research list bounds')
        data = exact(g, integer(obj, 0x94), count*4)
        enabled = exact(g, integer(obj, 0x98), count)
        rows = tuple(integer(data, i*4) for i in range(count))
        require(all(v in (0, 1) for v in enabled), 'research list enable flags invalid')
        ids = ()
        if kind == 'ability-list':
            require(obj[0xA] == unit[6], 'research ability race differs')
            start = integer(self.rom, RACE_TABLE+unit[6]*4)-0x08000000
            stop = integer(self.rom, RACE_TABLE+unit[6]*4+4)-0x08000000
            require(0 <= start < stop <= len(self.rom) and all(start+i*8+8 <= stop for i in rows),
                    'research ability row outside race table')
            ids = tuple(integer(self.rom, start+i*8+4, 2) for i in rows)
            require(all(0 < i < 347 for i in ids), 'research ability ID bounds')
        reads = [(self.context, root), (self.member, unit), (self.callback, callback),
                 (PLAYER_DRIVER+4, driver[4:12]), (PLAYER_DRIVER+0x60, driver[0x60:0x64]),
                 (active+0x18+0x50, obj[0x50:0x54]), (active+0x18+0x69, obj[0x69:0x6A]),
                 (integer(obj, 0x94), data), (integer(obj, 0x98), enabled)]
        require(all(exact(g, a, len(b)) == b for a, b in reads), 'research list changed during read')
        decision = hashlib.sha256(repr((kind, rows, tuple(enabled), ids, cursor, scroll, root.hex())).encode()).hexdigest()
        return ListToken(kind, cursor, scroll, rows, tuple(enabled), ids, hp, mp, self.member,
                         mode, self.context, self.callback, active, hashlib.sha256(unit).hexdigest(), decision)

    def revalidate(self, token):
        require(isinstance(token, ListToken) and self.snapshot() == token, 'stale/foreign research list token')
        return token
