"""Read-only, pinned identity and modal facts for bounded self-Cure research.

This does not relax ActorAdapter's battle-roster guard. Observations identify
UI states; they do not certify an action until a guarded executor verifies
the selection, final confirmation and causal effect.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import time

from ability_resources import effective_mp_cost, RACE_TABLE
from fixture_guard import STRIDE, SIDE_BIT, UNAFFILIATED_BIT, BATTLE_STRUCT
from probe_control_handoff import TARGET_X, TARGET_Y

MEMBERS = 0x02000080
MEMBER_COUNT = 14
MENU_ROOT = 0x0200F438
LIST = 0x08028DE1
DESCRIPTION = 0x08029189
CONFIRM = 0x080293DD
PLAYER_DRIVER = 0x0200F4E8
FACING = 0x0200F8A8


class RecoveryStateError(ValueError):
    pass


class RecoveryTransient(RecoveryStateError):
    """Known opening/settling rejection; permits a bounded passive retry only."""


def require(condition, message):
    if not condition:
        raise RecoveryStateError(message)


def integer(data, offset, size=4):
    return int.from_bytes(data[offset:offset + size], "little")


def exact(g, address, size):
    require(0x02000000 <= address and address + size <= 0x02040000, "RAM pointer outside EWRAM")
    data = g.read_mem(address, size)
    require(data is not None and len(data) == size, "short modal memory read")
    return bytes(data)


@dataclass(frozen=True)
class MenuObservation:
    observed_at: float
    context: int
    callback: int
    handler: int
    controller_state: int
    mode: int
    selection: int
    selected_ability: int
    member: int
    peer: int
    state: str
    cursor: int | None
    scroll: int | None
    rows: tuple[int, ...]
    enabled: tuple[int, ...]
    ability_ids: tuple[int, ...]
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    cure_cost: int
    target_tile: tuple[int, int]
    target_processor: int = 0
    target_state: int = 0
    target_flags: int = 0
    actor_wrapper: int = 0
    ui_active: int = 0
    driver_state: int = 0
    facing_direction: int | None = None

    def receipt(self):
        return asdict(self)


class RecoveryMenu:
    """Bind once to an independently verified owner, then reject identity drift."""

    def __init__(self, g, rom, owner, clock=time.monotonic):
        self.g, self.rom, self.owner, self.clock = g, rom, dict(owner), clock
        require(owner.get("side_bit") is False and not owner.get("unaffiliated"), "owner is not a verified player")
        matches = []
        for i in range(MEMBER_COUNT):
            addr = MEMBERS + STRIDE * i
            data = exact(g, addr, STRIDE)
            if integer(data, 0) == owner["name"] and data[0x104] == owner["id"]:
                matches.append((addr, data))
        require(len(matches) == 1, "canonical actor missing or ambiguous")
        self.member, unit = matches[0]
        self.identity = self._identity(unit)
        self.name_digest = hashlib.sha256(exact(g, owner["name"], 32)).digest()
        self._check_unit(unit)
        self.context = integer(exact(g, MENU_ROOT, 4), 0)
        root = exact(g, self.context, 0x30)
        require(integer(root, 0x18) == self.member, "menu actor does not match pinned owner")
        self.callback = integer(root, 0x28)
        self.manager = integer(root, 0x20)
        self.wrapper = integer(exact(g, PLAYER_DRIVER + 4, 4), 0)
        require(integer(exact(g, self.wrapper, 4), 0) == self.member,
                "player driver wrapper differs from canonical actor")
        self.last = None

    @staticmethod
    def _identity(unit):
        return (integer(unit, 0), unit[0x104], *unit[4:10], unit[0x3B],
                integer(unit, 0x1A, 2), integer(unit, 0x1E, 2),
                integer(unit, 0x28, 2) & (SIDE_BIT | UNAFFILIATED_BIT),
                unit[0xF6], unit[0xF7])

    def _check_unit(self, unit):
        owner = self.owner
        require(self._identity(unit) == self.identity, "pinned canonical actor changed")
        for field, offset in [("type", 4), ("base_job", 5), ("race", 6), ("job", 7), ("level", 9)]:
            require(unit[offset] == owner[field], "canonical actor differs from verified battle owner")
        require(integer(unit, 0x28, 2) & (SIDE_BIT | UNAFFILIATED_BIT) == 0, "canonical actor side changed")
        require((unit[0xF6], unit[0xF7]) == (owner["x"], owner["y"]), "canonical actor tile changed")
        require(integer(unit, 0x1A, 2) == owner["max_hp"] and integer(unit, 0x1E, 2) == owner["max_mp"],
                "canonical actor maxima differ")
        hp, maximum, mp, max_mp = [integer(unit, off, 2) for off in [0x18, 0x1A, 0x1C, 0x1E]]
        require(0 < hp <= maximum <= 999 and 0 <= mp <= max_mp <= 999, "invalid canonical actor resources")

    def snapshot(self):
        g = self.g
        context = integer(exact(g, MENU_ROOT, 4), 0)
        require(context == self.context, "menu root changed")
        root = exact(g, context, 0x30)
        require(integer(root, 0x18) == self.member, "modal actor pointer changed")
        peer = integer(root, 0x1C)
        require(peer in (0, self.member), "unsupported or changed modal peer")
        require(integer(root, 0x28) == self.callback, "modal callback allocation changed")
        require(integer(root, 0x20) == self.manager, "modal manager changed")
        driver = exact(g, PLAYER_DRIVER, 0x64)
        driver_control = exact(g, PLAYER_DRIVER + 0xD0, 0x10)
        driver_state = integer(driver_control, 0xC, 2)
        require(integer(driver, 4) == integer(driver, 8) == self.wrapper
                and integer(exact(g, self.wrapper, 4), 0) == self.member,
                "player driver actor wrapper changed")
        processor = integer(driver, 0x60)
        require(processor in (0, BATTLE_STRUCT), "unknown target processor allocation")
        active_callback = integer(exact(g, self.manager + 4, 4), 0)
        require(active_callback in (0, self.callback), "unowned active UI callback")
        target_state, target_flags = 0, 0
        processor_reads = []
        if processor:
            processor_reads = [(processor, exact(g, processor, 4)),
                               (processor + 0xEC, exact(g, processor + 0xEC, 2)),
                               (processor + 0x1112, exact(g, processor + 0x1112, 2)),
                               (processor + 0x1118, exact(g, processor + 0x1118, 2))]
            require(integer(processor_reads[0][1], 0) == self.wrapper
                    and integer(processor_reads[1][1], 0, 2) == 1,
                    "target processor actor or ability changed")
            target_flags = integer(processor_reads[2][1], 0, 2)
            target_state = integer(processor_reads[3][1], 0, 2)
            require(target_state < 32, "target processor state outside decoded switch")
        target_ready = processor and target_state == 10 and target_flags == 0 and active_callback == 0
        unit = exact(g, self.member, STRIDE)
        self._check_unit(unit)
        require(hashlib.sha256(exact(g, self.owner["name"], 32)).digest() == self.name_digest, "actor name changed")
        # Identity must remain unique while the battle mirror is borrowed.
        for i in range(MEMBER_COUNT):
            addr = MEMBERS + STRIDE * i
            if addr != self.member:
                other = exact(g, addr, STRIDE)
                require(not (integer(other, 0) == self.owner["name"] and other[0x104] == self.owner["id"]),
                        "canonical actor became ambiguous")
        callback = self.callback
        block = exact(g, callback, 0x18)
        stable_reads = [(callback, block[:4]), (callback + 0x10, block[0x10:0x16])]
        handler, state = integer(block, 0), integer(block, 0x14, 2)
        mode, selection, ability = root[4], integer(root, 0, 2), integer(root, 0x14)
        active = callback
        facing_reads = []
        facing_direction = None
        if handler == LIST and mode == 5 and state == 0x106:
            active = integer(block, 0x10)
            child = exact(g, active, 0x18)
            stable_reads.extend([(active, child[:4]), (active + 0xC, child[0xC:0x10]),
                                 (active + 0x14, child[0x14:0x16])])
            require(integer(child, 0) == LIST and integer(child, 0xC) == callback
                    and integer(child, 0x14, 2) == 0x102, "Action child is not a stable owned list")
            kind = "action-group"
        elif handler == LIST and mode == 4 and state == 0x102:
            require(driver_state == 0x25 and processor == 0,
                    "command callback is not owned by the command driver")
            kind = "command"
        elif handler == LIST and mode == 4 and state in (0x100, 0x101):
            # 08028DE0 dispatches 0x100 to initialization (08028E5E),
            # 0x101 to window opening (08028ECC), and only 0x102 to input.
            # Both reject the observation and allow passive bounded retry.
            raise RecoveryTransient("command controller is opening")
        elif handler == LIST and mode == 4 and state == 3 and selection == 3:
            # The completed command callback is cached. Main switch entry
            # 0x2F (080955E0) owns input through 080A82C0 -> 080A1BE8.
            require(driver_state == 0x2F and integer(driver_control, 0) == 0x48
                    and processor == 0 and active_callback == 0,
                    "facing controller is not the owned input state")
            facing = exact(g, FACING, 0x14)
            direction = exact(g, self.wrapper + 0x1F, 1)
            require(integer(facing, 0) == self.wrapper and facing[0x10] == 1
                    and facing[4] in range(4) and facing[5] in range(4)
                    and direction[0] == facing[4], "facing actor or direction changed")
            facing_direction = facing[4]
            # Exclude animation counters +6..8; they are not decisions.
            facing_reads = [(FACING, facing[:6]), (FACING + 0x10, facing[0x10:0x11]),
                            (self.wrapper + 0x1F, direction)]
            kind = "facing"
        elif handler == LIST and mode == 7 and state == 0x102:
            kind = "ability-list"
        elif handler == LIST and mode == 7 and state == 3 and selection > 0 and target_ready:
            kind = "target-overlay"
        elif handler == DESCRIPTION and mode == 12 and state == 3 and target_ready:
            kind = "target-overlay"
        elif handler == DESCRIPTION and mode == 12 and state == 0x102:
            # This callback is also reused immediately after confirmation.
            # The executor must track its lifecycle; never treat it as proof
            # of acceptance or as permission for another confirmation.
            kind = "description"
        elif handler == CONFIRM and mode == 11 and state == 0x102 and selection == 0:
            kind = "confirmation"
        elif (((handler == DESCRIPTION and mode == 12) or (handler == CONFIRM and mode == 11))
              and state in (3, 0x103)) or (handler == DESCRIPTION and mode == 12 and state == 0x104):
            kind = "settling"
        else:
            raise RecoveryStateError(f"unknown/transient modal signature: {handler:08x}/{mode}/{state:04x}")
        if kind in ("target-overlay", "description", "confirmation", "settling"):
            require(ability == 1 and peer == self.member, "unsupported selected ability or target")
        if kind in ("command", "action-group", "ability-list", "description", "confirmation"):
            require(active_callback == self.callback, "cached callback is no longer active")
        if kind == "confirmation":
            require(processor and target_state == 2 and target_flags == 0x20,
                    "final confirmation target processor is not ready")
        cursor, scroll, rows, enabled, ids = None, None, (), (), ()
        if kind in ("command", "action-group", "ability-list", "confirmation"):
            obj = exact(g, active + 0x18, 0x9C)
            # The list payload also contains animation counters. Only decoded
            # decision facts participate in coherence checks.
            stable_reads.extend((active + 0x18 + off, obj[off:off + width])
                                for off, width in [(0xA, 1), (0x50, 4), (0x69, 1), (0x94, 8)])
            cursor = obj[0x69]
            if kind == "confirmation":
                require(cursor in (0, 1), "confirmation cursor outside two choices")
            else:
                count, scroll = integer(obj, 0x50, 2), integer(obj, 0x52, 2)
                require(0 < count <= 32 and cursor < count and scroll + cursor < count, "invalid menu list bounds")
                rows_bytes = exact(g, integer(obj, 0x94), count * 4)
                stable_reads.append((integer(obj, 0x94), rows_bytes))
                rows = tuple(integer(rows_bytes, i * 4) for i in range(count))
                enabled = tuple(exact(g, integer(obj, 0x98), count))
                stable_reads.append((integer(obj, 0x98), bytes(enabled)))
                require(all(v in (0, 1) for v in enabled), "invalid enable flags")
                if kind == "ability-list":
                    require(obj[0xA] == unit[6], "ability-list race differs from actor")
                    race = unit[6]
                    start = integer(self.rom, RACE_TABLE + race * 4) - 0x08000000
                    stop = integer(self.rom, RACE_TABLE + race * 4 + 4) - 0x08000000
                    require(0 <= start < stop <= len(self.rom), "invalid race ability table")
                    require(all(start + i * 8 + 8 <= stop for i in rows), "ability-list row outside race table")
                    ids = tuple(integer(self.rom, start + i * 8 + 4, 2) for i in rows)
                    require(all(0 < i < 347 for i in ids), "ability identity outside decoded table")
        tile = tuple(exact(g, TARGET_X, 2))
        require(all(0 <= v < 64 for v in tile), "invalid target cursor")
        observed = MenuObservation(self.clock(), context, callback, handler, state, mode,
                                   selection, ability, self.member, peer, kind, cursor, scroll,
                                   rows, enabled, ids, integer(unit, 0x18, 2), integer(unit, 0x1A, 2),
                                   integer(unit, 0x1C, 2), integer(unit, 0x1E, 2),
                                   effective_mp_cost(self.rom, 1, unit), tile,
                                   processor, target_state, target_flags, self.wrapper, active_callback,
                                   driver_state, facing_direction)
        # Confirm the root did not move during this multi-read observation.
        require(integer(exact(g, MENU_ROOT, 4), 0) == context
                and exact(g, context, 0x30) == root, "modal root changed during snapshot")
        require(exact(g, self.member, STRIDE) == unit
                and tuple(exact(g, TARGET_X, 2)) == tile, "actor or target changed during snapshot")
        for address, data in stable_reads:
            require(exact(g, address, len(data)) == data,
                    f"modal controller changed during snapshot at {address:08x}")
        require(exact(g, PLAYER_DRIVER + 4, 8) == driver[4:12]
                and exact(g, PLAYER_DRIVER + 0x60, 4) == driver[0x60:0x64]
                and integer(exact(g, self.manager + 4, 4), 0) == active_callback
                and integer(exact(g, self.wrapper, 4), 0) == self.member,
                "player driver changed during snapshot")
        require(all(exact(g, address, len(data)) == data for address, data in processor_reads),
                "target processor changed during snapshot")
        coherent = (exact(g, PLAYER_DRIVER + 0xD0, 4) == driver_control[:4]
                    and exact(g, PLAYER_DRIVER + 0xDC, 2) == driver_control[0xC:0xE])
        if not coherent and kind == "settling":
            raise RecoveryTransient("main controller changed during read-only settling")
        require(coherent, "main player controller changed during snapshot")
        require(all(exact(g, address, len(data)) == data for address, data in facing_reads),
                "facing controller changed during snapshot")
        self.last = observed
        return observed

    def revalidate(self, previous, max_age=2.0):
        require(previous is self.last, "observation is not the latest owned snapshot")
        require(previous.state != "settling", "no input during modal settling")
        age = self.clock() - previous.observed_at
        require(0 <= age <= max_age, "modal observation is stale")
        current = self.snapshot()
        require(current.receipt() | {"observed_at": 0} == previous.receipt() | {"observed_at": 0},
                "modal state changed before input")
        return current
