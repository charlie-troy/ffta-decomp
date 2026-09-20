"""Offline transport-path validator for the A3 auto-battle runtime.

Roadmap A3 acceptance: "Validate disconnect, repeated start/stop,
unknown-dialog, and takeover paths using recorded transport responses; then
finish one normal battle with no tactical clicks."

The transport seam is `Probe`'s two handles:
  - ``session.g``  GDB stub drive: read_mem / read_pc / read_registers /
    cont / interrupt / send / _read_packet
  - ``session``    memory writes (ledgered), ROM bytes, screenshots, and the
    roster receipt the probe and guard read

``FakeSession``/``FakeGdb`` reproduce that surface and replay the recorded
engine shapes from A2.5 runs 14/18/19/20 and a3-full1..3. Every scenario
drives the REAL ``BattleRuntime`` state machine end-to-end (no monkeypatching
of runtime logic) and then gates the artifacts through
``validate_autobattle_runtime.validate``, so the receipts contract must hold
for faulted transports, not just happy paths.

Live guard is intentionally not exercised here: it is fixture data (decodable
unit names), not transport behavior, and is already validated on live
fixtures.

Scenarios:
  takeover   two full player boundaries; each commit re-opens the menu shape
             later; the battle ends on the recorded all-CTs-zero results
             shape -> ``completed``
  unknown    an unknown dialog swallows the proven route (presses land x>0
             but nothing commits and no seeds follow) -> bounded stop, and
             NO further presses after the bound (DE-020)
  disconnect transport dies mid-run (send raises) -> ``connection_lost``
             with the failure recorded, no further presses
  restart    two sequential BattleRuntime lifecycles over one transport:
             fresh probes, clean receipts, no cross-run state
  results    regression: a stable all-CTs-zero vector (the recorded results
             screen) must classify ``completed`` and never be driven
  pause      a STOP file lands mid-battle: input stops, breakpoints are
             disarmed, the engine keeps advancing for the player, and the
             run classifies ``paused`` (the real manual-handoff semantics)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from autobattle_runtime import BattleRuntime  # noqa: E402
from validate_autobattle_runtime import validate  # noqa: E402
from probe_control_handoff import (CMD_CURSOR as _CMD_CURSOR,  # noqa: E402
                                   TARGET_X as _TARGET_X,
                                   TARGET_Y as _TARGET_Y,
                                   MOVE_CMD as _MOVE_CMD,
                                   ACTION_CMD as _ACTION_CMD,
                                   WAIT_CMD as _WAIT_CMD)

BP_KEY = 0x08000494
BP_SEED = 0x080C03C2
BP_ROUTER = 0x0809E3AE
RUNNING_PC = BP_ROUTER
ROSTER = 0x020159E8
STRIDE = 0x108
OFF_CT = 0xD0
PLAYER_SLOT = 6
ABILITY_SCAN_MAX = 64        # mirrors probe_control_handoff's scan depth
                             # over the inline ability-state array at +0x34
SEED_INTERVAL = 3.0     # recorded inter-action seed gap is ~11-20 s; offline
                        # cadence only needs to be non-instant
# The fake engine runs on the WALL clock: frames advance in real time
# (60 fps) whether or not the probe polls, exactly as hardware does. The
# earlier per-read frame model let the engine clock race with the probe's
# read rate (~1,650 frames/wall-second): a committed CT saturated and
# re-opened a phantom menu mid-recovery, and key-poll stops flooded the
# stub queue so seed stops never surfaced. Wall-driven frames keep every
# recorded cadence (CT charge, menu settle, seed gaps) honest at any read
# rate.
FRAME_HZ = 60.0                  # GBA engine frame rate
FRAME_DT = 1.0 / FRAME_HZ
CT_PER_FRAME = 13.0 / FRAME_HZ   # ~12.9 CT/s recorded charge rate
CT_REOPEN_AT = 1000              # saturated CT -> the actor's menu opens
MENU_REOPEN_SECONDS = 5.0        # engine settle before a post-commit re-open
RESULTS_SETTLE_SECONDS = 2.0     # defeat/results settle before the end shape
MAX_PENDING_QUEUE = 16           # stub stop queue bound (engine-side buffer)


class FakeGdb:
    """Scripted GDB stub: the memory/registers/stop-reply surface Probe uses."""

    def __init__(self, world):
        self.world = world
        self.mem = {}
        self.armed = set()
        self.queue = []          # pending stop replies (pc, packet)
        self.stop_pc = None
        self.fail_sends = False
        self.send_log = []
        self.write_times = []  # (wall_t, cmd) for every send — C1 gap 2

    # -- transport failure injection --------------------------------------
    def _check(self):
        if self.fail_sends:
            raise OSError("transport reset: peer closed connection")

    # -- memory ------------------------------------------------------------
    def read_mem(self, addr, n, chunk=0x200):
        self._check()
        self.world.pump(self)
        return bytes(self.mem.get(addr + i, 0) for i in range(n))

    def read_pc(self):
        return self.stop_pc if self.stop_pc is not None else RUNNING_PC

    def read_registers(self):
        self.world.pump(self)
        regs = [0] * 16
        regs[15] = self.read_pc()
        return regs

    # -- run control ---------------------------------------------------------
    def cont(self):
        self._check()
        self.stop_pc = None

    def interrupt(self):
        self._check()

    # -- packet-level commands ------------------------------------------------
    def send(self, cmd):
        self._check()
        self.send_log.append(cmd)
        self.write_times.append((time.time(), cmd))
        if cmd.startswith("Z0,"):
            addr = int(cmd.split(",")[1], 16)
            self.armed.add(addr)
            return "OK"
        if cmd.startswith("z0,"):
            addr = int(cmd.split(",")[1], 16)
            self.armed.discard(addr)
            return "OK"
        if cmd.startswith("P1="):
            # the probe writes val.to_bytes(4, 'little').hex(); mGBA hands
            # the engine back the intended value (routes commit on hardware),
            # so the recorded hex parses little-endian
            val = int.from_bytes(bytes.fromhex(cmd.split("=")[1]), "little")
            self.world.on_key_write(val)
            return "OK"
        return ""

    def _read_packet(self, timeout=0.2):
        self._check()
        self.world.pump(self)
        if self.queue:
            pc, pkt = self.queue.pop(0)
            self.stop_pc = pc
            return pkt
        time.sleep(timeout)
        raise socket.timeout()

    # -- test observability ----------------------------------------------------
    def key_writes(self):
        # timestamped pairs: the C1 cancellation rule asserts against the
        # WRITE stream (STOP-observation ordering), not against run() return
        return [(ts, c) for (ts, c) in self.write_times
                if c.startswith("P1=")]

    def press_writes_after(self, mark):
        return [(ts, c) for (ts, c) in self.write_times[mark:]
                if c.startswith("P1=")]


class FakeSession:
    """Scripted FixtureSession surface: writes, ROM, screenshots, receipt."""

    def __init__(self, world):
        self.g = FakeGdb(world)
        world.session = self
        self.write_ledger = []
        rom = bytearray(0x100)
        rom[:4] = b"\x00\x00\x00\x00"
        self._rom = bytes(rom)
        # guard receipt in the shape Probe reads (player_slot / actor_info /
        # is_enemy): recorded roster from configs/battle-scenarios/
        # normal-battle.json — slots 0-4 enemy clan, 5 the neutral Judge,
        # 6 the player (EWRAM name pointer).
        slots = []
        for i in range(8):
            if i <= 4:
                side, name, name_text = 0x8000 | (0x1000 * 0), 0x085671ee + i, f"Enemy{i}"
            elif i == 5:
                side, name, name_text = 0x1000, 0x085671f6, "Judge"
            elif i == 6:
                side, name, name_text = 0x0000, 0x02001f1c, "Marche"
            else:
                side, name, name_text = 0, None, None
            slots.append({"live": name is not None, "side_raw": side,
                          "name": name, "name_text": name_text})
        self.receipt = {"roster": {"slots": slots, "ram_named_slots": [6]}}
        populate_roster(self.g)

    def read_rom_bytes(self):
        return self._rom

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # round-7: the CLI's guard-failure receipt reads keep_process (adopted
    # sessions keep their emulator); FakeSession never owns a real process.
    keep_process = False

    def adopt_existing(self):
        raise RuntimeError("FakeSession has no live emulator to adopt")

    def write_bytes(self, addr, data, note=""):
        self.write_ledger.append({"addr": addr, "data": bytes(data),
                                  "note": note})
        for i, b in enumerate(bytes(data)):
            self.g.mem[addr + i] = b

    def write_u8(self, addr, value, note=""):
        self.write_bytes(addr, bytes([value & 0xFF]), note)

    def screenshot(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"fake-frame")
        return path


def populate_roster(gdb):
    """Recorded roster shapes the probe reads directly: CT vector and HP.

    Slots 0-6 alive (hp/max nonzero, from normal-battle.json), slot 7 empty.
    Without this, the runtime's dead-unit and teardown checks see an all-zero
    roster — the run-6 mid-execution copy shape — and misclassify.
    """
    for i in range(7):
        base = ROSTER + STRIDE * i
        hp, max_hp = (388, 442) if i == 6 else (300, 300)
        gdb.mem[base + 0x18] = hp & 0xFF
        gdb.mem[base + 0x19] = hp >> 8
        gdb.mem[base + 0x1A] = max_hp & 0xFF
        gdb.mem[base + 0x1B] = max_hp >> 8
        ct = gdb.world.ct_vector()[i]
        gdb.mem[base + OFF_CT] = ct & 0xFF
        gdb.mem[base + OFF_CT + 1] = ct >> 8


def sync_memory(gdb):
    """Project the world's live state into probe-visible memory.

    The runtime classifies from memory reads (cts(), unit hp/tile, teardown),
    so the world state — charging CT, the results-screen all-zero vector —
    must be reflected on every poll, not just once at boot.
    """
    world = gdb.world
    for i in range(8):
        base = ROSTER + STRIDE * i
        ct = int(world.ct_vector()[i])
        gdb.mem[base + OFF_CT] = ct & 0xFF
        gdb.mem[base + OFF_CT + 1] = ct >> 8
        alive = world.march_hp_alive() or i != PLAYER_SLOT
        hp, max_hp = (388, 442) if i == 6 else (300, 300)
        if not alive:
            hp = max_hp = 0
        if i == 2:
            hp = world.slot2_hp  # scripted target-hp projection (slot 2)
        gdb.mem[base + 0x18] = hp & 0xFF
        gdb.mem[base + 0x19] = hp >> 8
        gdb.mem[base + 0x1A] = max_hp & 0xFF
        gdb.mem[base + 0x1B] = max_hp >> 8
        # max MP (+0x1E, unit-struct.md) must be projected too: the runtime's
        # plausibility guard bounds observed mp by max_mp, and an unwired 0
        # made every nonzero MP read look like roster garbage
        max_mp = 96 if i == PLAYER_SLOT else 50
        gdb.mem[base + 0x1E] = max_mp & 0xFF
        gdb.mem[base + 0x1F] = max_mp >> 8
        # chooser projections: a nonzero tile + the INLINE ability-state
        # array at unit+0x34 (include/ffta.h layout: 12-byte header + one
        # byte per race ability) with nonzero learned entries — zeroed only
        # on the results shape (choose_non_wait must decline there)
        # C2 cursor projection: the menu command copy and the move-target
        # copy ride their recorded addresses only while the fake's
        # identified-move law is on; (0, 0) clears them when closed so the
        # probe's plausibility guard reads "no cursor" (it must never infer
        # an open menu from stale bytes)
        if world.identified_move:
            if world.menu_up:
                if world._cmd_cursor is None:
                    world._cmd_cursor = _MOVE_CMD
                gdb.mem[_CMD_CURSOR] = world._cmd_cursor
                if world._target_cursor is not None:
                    gx, gy = world._target_cursor
                else:
                    # menu-open, target mode closed: the move-target copy
                    # reads the unit's own tile (probe3) — never (0, 0),
                    # which the probe's plausibility guard treats as "no
                    # cursor"
                    gx, gy = world._march_tile
                gdb.mem[_TARGET_X] = gx
                gdb.mem[_TARGET_Y] = gy
            else:
                # menu closed: the copies read cleared bytes (0) so the
                # probe's plausibility guard reads "no cursor" — a stale
                # nonzero copy must never reopen an identified state
                gdb.mem[_CMD_CURSOR] = 0
                gdb.mem[_TARGET_X] = 0
                gdb.mem[_TARGET_Y] = 0
        # the player roster tile follows the cursor law's executed move so
        # the runtime's engine-side verification (roster tile == the RAM-
        # read destination) is enforced against a real state change
        if world.identified_move:
            world.player_tile = (world._march_tile[0], world._march_tile[1])
        tx, ty = (world.player_tile if not world.results else (0, 0))
        gdb.mem[base + 0xF6] = tx
        gdb.mem[base + 0xF7] = ty
        # committed-action evidence fields (+0x1C MP, +0xE7 recent targets):
        # projected for the PLAYER slot so post-commit effect diffs can show
        # the actor-specific deltas a Wait can never produce
        if i == PLAYER_SLOT:
            mp = 0 if world.results else world.march_mp
            gdb.mem[base + 0x1C] = mp & 0xFF
            gdb.mem[base + 0x1D] = mp >> 8
            gdb.mem[base + 0xE7] = 0 if world.results else world.march_tg
        for k in range(ABILITY_SCAN_MAX):
            gdb.mem[base + 0x34 + k] = 0 if world.results else (
                0x03 if k < 12 else (0x01 if k < 16 else 0x00))


class FakeWorld:
    """Recorded engine shapes, advanced on the wall clock (see pump()).

    The GDB stop-reply stream is generated here: while the command menu is
    up the engine polls keys every frame; while charging it raises sequencer
    seeds periodically; the results shape parks every CT at 0.
    `on_key_write` mirrors the recorded commit shape: the second A onset of
    the proven route commits the turn (menu closes, CT re-bases, charging
    resumes).
    """

    def __init__(self):
        self.session = None
        self.vt = 0.0            # virtual engine clock (seconds)
        self.menu_up = True
        self.charging = False
        self.allow_seeds = False
        self.results = False
        self.teardown = False
        self.swallow_route = False   # unknown-dialog: presses land, nothing commits
        self.march_ct = 188
        self.other_cts = [45, 464, 850, 821, 515, 315]
        self.commits = 0
        self.presses = 0
        self.a_presses = 0
        # Each P1= write covers exactly ONE engine key-poll (the probe
        # intercepts a single poll; the next poll reads real KEYINPUT). A
        # FIFO keeps a write from outliving its poll: the earlier single-slot
        # model let an unconsumed edge from a drive survive an idle gap and
        # fire mid-recovery, ~150 s after the press.
        self._key_fifo = []      # pending injected vals, one per polled frame
        self._a_prev = False     # A held last frame (edge detection)
        self._b_prev = False     # B held last frame (edge detection)
        self.last_seed_t = None  # wall time of the last seed stop
        self.first_commit_t = None  # wall time of commit #1 (defeat anchor)
        self.last_commit_t = None   # wall time of the most recent commit
        self.reopen_park_ct = 600   # recorded re-open parked CT (run 19)
        self.expect_action_route = False  # DEPRECATED (chooser law removed):
        # scenarios must use the identified-move law; this flag is inert
        self.slot2_hp = 300        # scripted slot-2 target hp (sync_memory)
        self.march_mp = 60         # scripted player MP (sync_memory base)
        self.march_tg = 0          # scripted player +0xE7 recent-target byte
        self.ending_after = None      # begin the battle end N s after commit
                                      # #M: (M, seconds) — the recorded shape:
                                      # the end sequence follows the EXECUTED
                                      # final action, not the menu commit
        self.reopen_after_commits = None  # menu re-opens only while commits
                                          # < N (a battle-ending action is
                                          # followed by the end sequence,
                                          # not another command menu)
        self.march_mp = 60           # current MP (+0x1C); Wait costs none
        self.march_tg = 0            # engine-recorded recent targets (+0xE7)
        self.seeds = 0
        self.fail_at_commit = None   # transport dies after N commits
        self.after_commit = None     # scenario hook (callable, world)->None
        self.menu_reopen_seconds = None  # menu re-opens N s after a commit
        self.defeat_after_commit = None  # Marche falls N s after commit #1
        self.ending = False
        self.end_seeds_remaining = 0
        self.ending_t = 0.0
        self._last_wall = time.time()
        self.b_closes = 0            # B presses that backed out of a menu layer
        self.swallow_b = False       # unknown dialog: B does not back out
        self.swallow_first_route = False  # submenu shape eats the first route
        self.player_tile = (4, 10)   # cursor law: target copy init tile
        # C2 identified-move law: when set, the fake presents the DECODED
        # menu state — the command cursor rides the open menu (Move on
        # open), the move-target copy initializes at the unit's tile when
        # target mode opens, cursor keys move it, and a confirm executes
        # the READ cursor destination (probe6 engine-verified shape).
        self.identified_move = False
        self.wrong_move = False      # engine executes a DIFFERENT tile
        self.wrong_tile = (9, 9)     # the tile a wrong_move executes to
        self.occupied_dest = False   # c3 probe4 law: confirm onto an
                                     # OCCUPIED tile opens the unit info
                                     # panel (not a walk); the panel eats
                                     # D-pads and B dismisses one layer
        self.panel_first_reopen = False  # c3-live-a5 law: the FIRST
                                         # re-open is preceded by a
                                         # transition panel (menu not yet
                                         # open; echo lands, byte frozen)
        self._panel_layers = 0       # 0=menu, 1=target-under-panel,
                                     # 2=panel+target (byte frozen)
        self._march_tile = [4, 10]   # projected roster tile (sync_memory)
        self._cmd_cursor = None      # None = menu copy not initialized yet
        self._target_cursor = None   # None = target mode not open
        self._moved = False          # move executed; menu re-opened, turn open
        self._wait_confirm = False  # Wait selected; next A confirms (probe6:
                                    # the engine wants two As to close a turn)
        self._dir_prev = 0          # direction bits held last frame (edges)

    # -- time ---------------------------------------------------------------
    def now(self):
        return time.time()

    def pump(self, gdb):
        """Advance the engine on the wall clock; call on every probe event.

        Wall-driven frames project live state into probe memory, the open
        menu enqueues one key-poll stop per frame (bounded), and charging
        enqueues seed stops at the recorded cadence. This is the fake's only
        clock: the engine runs at real speed no matter how fast the probe
        reads, so idle gaps cannot masquerade as a parked menu and the stub
        queue cannot flood with stale stops.
        """
        now = time.time()
        while self._last_wall + FRAME_DT <= now:
            self._last_wall += FRAME_DT
            self._frame()
        # bounded queue: keep the newest pending stops (the probe drains at
        # human timescales; the engine-side stub only buffers so many)
        del self.session.g.queue[:-MAX_PENDING_QUEUE]

    def _frame(self):
        """One engine frame (1/60 s)."""
        self.vt += FRAME_DT
        if self.menu_up:
            self._frame_menu()
        elif self.charging:
            self._frame_charging()
        if self.session is not None:
            sync_memory(self.session.g)

    # -- probe-visible memory -------------------------------------------------
    def ct_vector(self):
        # slots 0-5: enemies + Judge (other_cts), slot 6: Marche, slot 7:
        # empty. The earlier `other_cts + [0, march_ct, 0]` layout was off
        # by one — it pinned Marche's projected CT at a permanent 0, which
        # player_menu_frozen read as an always-stable parked menu (phantom
        # boundaries mid-charge).
        v = list(self.other_cts) + [self.march_ct, 0]
        if self.results:
            v = [0] * 8
        return v

    def march_hp_alive(self):
        if self.teardown:
            return False
        if self.ending:
            # defeat path schedules 0 ending seeds: the hp block zeroes at
            # the fall and stays zero through the results shape. The natural
            # end (results scenario) keeps 1 ending seed, so the read only
            # zeroes after the last seed — mirroring a real victory where
            # the tracked player is alive on the results screen.
            return self.end_seeds_remaining > 0
        return True  # defeat scheduled but not yet held: alive until the fall

    def _frame_menu(self):
        # The engine polls keys every frame while a menu is up: the key
        # breakpoint hits and a stop reaches the probe. The probe answers
        # each stop with its injected val (or real KEYINPUT, no keys); the
        # write covers exactly that one poll, so edge detection is per
        # consumed frame — timing-free and faithful.
        val = self._key_fifo.pop(0) if self._key_fifo else 0
        a_seen = bool(val & 0x01)
        a_edge = a_seen and not self._a_prev
        if a_edge:
            self.a_presses += 1
            if self.identified_move:
                # C2 identified-move law: the commit shape follows the
                # DECODED cursor state (probe6), not a bare press count —
                # a bare count would commit at the move-confirm A, four
                # presses before the identified turn actually closes
                self._identified_a()
            else:
                self._maybe_commit()
        self._a_prev = a_seen
        # B is pure menu-back navigation on the key-DOWN edge, consumed one
        # poll per write exactly like A (one B press = one navigation
        # event, never one per held frame): in a submenu layer it backs out
        # to the parent command menu (which the plain route can then
        # drive); on the main menu it closes it (cursor returns to the
        # map); while charging/results it is inert. An unknown dialog
        # ignores B entirely.
        b_seen = bool(val & 0x02)
        if b_seen and not self._b_prev and self.menu_up:
            if self.identified_move:
                # B is menu-back navigation in the identified law too: the
                # runtime's identified flow never sends it, but a stop-gated
                # manual layer or a future B use must still navigate honestly
                self._identified_b()
            elif not self.swallow_b:
                if self.swallow_first_route and self.commits == 0:
                    # submenu layer: B returns to the parent command menu
                    self.swallow_first_route = False
                else:
                    # closing the menu parks the unit at CT 1000 — ready to
                    # be re-selected; the recorded parked-menu CT stays <= 999
                    self.menu_up = False
                    self.charging = True
                    self.march_ct = CT_REOPEN_AT
                self.a_presses = 0      # fresh menu episode
                self._a_prev = False
                self.b_closes += 1
        self._b_prev = b_seen
        # C2 cursor law: direction keys move the REAL cursors — the command
        # cursor in the command menu, the (x, y) target cursor in target
        # mode. Rising-edge per direction (one step per press), matching
        # the recorded menu feel and the driver's short presses.
        if self.identified_move and self.menu_up:
            d = val & 0xF0
            for bit, name in ((0x80, "down"), (0x10, "right"),
                              (0x40, "up"), (0x20, "left")):
                if (d & bit) and not (self._dir_prev & bit):
                    self._identified_dir(name)
            self._dir_prev = d
        # C3: a FRESH menu episode (engine-opened, not re-opened after a
        # move) presents the cursor where the engine last left it — the
        # recorded re-open shape parks on Action (probe5), but a menu the
        # engine opened from the map initializes on Move. The identified-
        # wait control needs the REAL fresh-menu law (cmd cursor 0) with
        # the unit's tile in the target copy — exactly what a live C3
        # resume leg reads after the manual handoff.
        if (self.identified_move and self._cmd_cursor is None
                and not self._panel_layers):
            self._cmd_cursor = _MOVE_CMD
            self._moved = False
            self._wait_confirm = False
        if self._panel_layers and self.identified_move:
            # c3-live-a5 offline law: the turn-transition info panel sits
            # over a NOT-YET-OPEN menu copy. The panel eats D-pads, and the
            # byte it covers holds the STICKY last value, so an echo probe
            # can't move it — but each B lands (the panel is dismissible)
            # and dismissing the last layer opens the menu for real, which
            # the next echo proves. (c3 probe4 live read: B landed, byte
            # unchanged, menu genuinely opened later — the panel, not a
            # dead UI.)
            self.session.g.queue.append((BP_KEY, "T05keypoll"))
            return
        # the engine polls keys every frame while a menu is up: the key
        # breakpoint hits and a stop reaches the probe
        self.session.g.queue.append((BP_KEY, "T05keypoll"))

    # -- C2 identified-move cursor law ---------------------------------------
    def _identified_dir(self, name):
        """One direction step on the DECODED cursor (command or target)."""
        if self.swallow_route:
            return  # unknown dialog: presses land, nothing changes
        if self._panel_layers:
            return  # occupied-tile info panel: eats D-pads (c3 probe4)
        if self._target_cursor is not None:
            if name == "down":
                self._target_cursor[1] += 1
            elif name == "up":
                self._target_cursor[1] -= 1
            elif name == "right":
                self._target_cursor[0] += 1
            elif name == "left":
                self._target_cursor[0] -= 1
        else:
            self._cmd_cursor = ((self._cmd_cursor or 0)
                                + {"down": 1, "up": -1}.get(name, 0)) % 3

    def _identified_a(self):
        """Consume one A edge per the DECODED cursor state (probe5/6 shape)."""
        if self.swallow_route:
            return  # unknown dialog: the press lands but no UI answers it
        if self._moved:
            # command menu re-opened after the move (probe5): the command
            # copy re-initialized at Action; A on Wait selects then confirms
            # (probe6's two-A shape closes the turn), A elsewhere re-opens
            # target mode at the unit's tile
            if self._target_cursor is None:
                if self._cmd_cursor == _WAIT_CMD:
                    if self._wait_confirm:
                        self._commit_turn()
                    else:
                        self._wait_confirm = True
                else:
                    self._target_cursor = [self._march_tile[0],
                                           self._march_tile[1]]
                    self._wait_confirm = False
            return
        if self._target_cursor is None:
            if self._cmd_cursor == _WAIT_CMD:
                # probe6's two-A Wait shape, generalized (C3): the engine's
                # Wait commit works from ANY identified menu whose cursor
                # reads Wait — fresh or re-opened. Select arms the confirm;
                # the second A closes the turn.
                if self._wait_confirm:
                    self._commit_turn()
                else:
                    self._wait_confirm = True
            elif self._moved or self._cmd_cursor == _MOVE_CMD:
                # A on Move opens target mode at the unit's tile (probe3);
                # on a re-opened post-move menu, choosing a command
                # re-opens target mode (probe5). A on Action of a menu no
                # move has reached is an unknown UI: nothing answers it.
                self._target_cursor = [self._march_tile[0], self._march_tile[1]]
                self._wait_confirm = False
            self._moved = False
            return
        # confirming the destination: execute at the READ cursor tile —
        # the engine never executes an inferred tile
        dest = tuple(self._target_cursor)
        if self.occupied_dest:
            # c3 probe4 law: the destination tile is OCCUPIED (an enemy
            # moved there during the enemy phase). No walk happens; A on
            # an occupied tile opens the unit info panel, which eats
            # D-pads. Two B presses dismiss back to the command menu
            # (panel -> move-target mode -> menu); the cmd byte stays
            # sticky-frozen at Move until the menu answers a D-pad again.
            self._panel_layers = 2
            self._target_cursor = None
            self._cmd_cursor = _MOVE_CMD
            self._wait_confirm = False
            return
        self._march_tile = list(self.wrong_tile if self.wrong_move else dest)
        self._moved = True
        self._target_cursor = None
        self._cmd_cursor = _ACTION_CMD  # the re-opened menu lands on Action
        self._wait_confirm = False
    def _identified_b(self):
        """B backs out of the identified UI one layer (menu-back navigation).

        With the occupied-tile panel up (c3 probe4 law), B dismisses one
        layer per press: panel -> move-target mode -> command menu (the
        cmd byte stays sticky-frozen at its last value until the menu
        layer is back and a D-pad lands).
        """
        if self._panel_layers:
            self._panel_layers -= 1
            if self._panel_layers == 0:
                self._moved = True   # the turn is still open: menu is back
            return
        if self._target_cursor is not None:
            self._target_cursor = None
            # the command menu is still on whatever command was selected
            return
        self.menu_up = False
        self.charging = True
        self.march_ct = CT_REOPEN_AT
        self.a_presses = 0
        self._a_prev = False
        self._moved = False
        self._wait_confirm = False
        self.b_closes += 1

    def _commit_turn(self):
        self.commits += 1
        self.menu_up = False
        self.charging = True
        self.march_ct = 0.0
        self.a_presses = 0
        self._moved = False
        self._wait_confirm = False
        self._cmd_cursor = None
        self._target_cursor = None
        self.last_commit_t = self.now()
        if self.first_commit_t is None:
            self.first_commit_t = self.last_commit_t
        if self.commits == self.fail_at_commit:
            self.session.g.fail_sends = True
        if self.after_commit:
            self.after_commit(self)

    def _frame_charging(self):
        self.march_ct = min(self.march_ct + CT_PER_FRAME, 1000)
        t = self.now()
        if (self.defeat_after_commit is not None
                and not self.ending
                and self.first_commit_t is not None
                and t - self.first_commit_t >= self.defeat_after_commit):
            # recorded a3-natural1 shape: Marche defeated ~18 s after the
            # route committed (hp block zeroes, seed traffic stops), the
            # engine animates the defeat, then the results shape holds
            self.mark_ending(0)
            return
        if (self.ending_after is not None
                and not self.ending
                and self.commits >= self.ending_after[0]
                and self.last_commit_t is not None
                and t - self.last_commit_t >= self.ending_after[1]):
            # the end sequence follows the executed final action (a finishing
            # blow), not the menu commit — the runtime's execution evidence
            # window gets its real chance to observe the action's effect
            self.mark_ending(1)
            return
        if self.ending:
            # battle end: the engine keeps acting (seeds flow) briefly,
            # then the results shape holds. Unit clocks KEEP CHARGING until
            # the results screen (a frozen mid-charge CT plus seed silence
            # reads exactly like a parked player menu — the runtime would
            # drive a phantom boundary into the end sequence).
            self.march_ct = min(self.march_ct + CT_PER_FRAME, 999.0)
            if self.end_seeds_remaining > 0:
                if self.last_seed_t is None or t - self.last_seed_t >= SEED_INTERVAL:
                    self.last_seed_t = t
                    self.seeds += 1
                    self.end_seeds_remaining -= 1
                    self.session.g.queue.append((BP_SEED, "T05seed-ending"))
            elif t - self.ending_t >= RESULTS_SETTLE_SECONDS:
                self.end_results()
            return
        if (self.menu_reopen_seconds is not None
                and (self.reopen_after_commits is None
                     or self.commits < self.reopen_after_commits)
                and self.last_commit_t is not None
                and t - self.last_commit_t >= self.menu_reopen_seconds):
            if ((self.occupied_dest and self.commits == 0)
                    or (self.panel_first_reopen and self.commits == 1)):
                # c3-live-a5 transition law: before the FIRST re-open the
                # engine parks the unit and holds the turn-transition info
                # panel for a few seconds; the menu copy is NOT open yet
                # (the byte stays sticky-frozen under the panel). Two Bs
                # dismiss the panel and the menu opens for real.
                self.menu_up = True
                self.charging = False
                self.march_ct = float(self.reopen_park_ct)
                self._panel_layers = 2
                # the byte under the panel is STICKY at the engine's last
                # menu state (c3-live-a5 read Action) — the fresh-episode
                # init below must not reset it to Move while the panel is
                # up, or the move planner would drive blind into the panel
                self._cmd_cursor = _ACTION_CMD
                self._moved = False
                self._wait_confirm = False
                self.a_presses = 0
                self._a_prev = False
                return
            # recorded re-open shape: the menu re-opens with the owner
            # parked at an arbitrary CT (600 observed in run 19)
            self.menu_up = True
            self.charging = False
            self.march_ct = float(self.reopen_park_ct)
            self.a_presses = 0  # fresh menu episode: edges count anew
            self._a_prev = False
            return
        if self.march_ct >= CT_REOPEN_AT:
            # engine behavior: a saturated CT means the actor's menu is
            # about to open — a frozen CT at 1000 without a menu is not a
            # stable shape (this is what produced phantom menus before)
            if (self.reopen_after_commits is not None
                    and self.commits >= self.reopen_after_commits):
                pass  # the final action executed: the end sequence follows,
                      # no further command menu (a phantom menu here wedges
                      # the runtime driving into a battle that is ending)
            else:
                self.menu_up = True
                self.charging = False
                self.march_ct = 999.0  # parked while the menu is open
                self.a_presses = 0  # fresh menu episode: edges count anew
                self._a_prev = False
            return
        if (self.allow_seeds
                and not (self.swallow_route and self.menu_up)
                and (self.last_seed_t is None
                     or t - self.last_seed_t >= SEED_INTERVAL)):
            self.last_seed_t = t
            self.seeds += 1
            self.session.g.queue.append((BP_SEED, "T05seed"))

    def _maybe_commit(self):
        # second A onset of the proven route commits the menu (A2.5 contract).
        # Retained ONLY for the old-law scenarios that still use a_presses;
        # identified-move turns commit through the cursor law (_identified_a).
        if self.a_presses < 2 or not self.menu_up:
            return
        if self.swallow_route:
            return  # unknown dialog eats the route; nothing changes
        if self.swallow_first_route and self.commits == 0:
            return  # submenu shape: the plain route cannot reach a commit
        self.commits += 1
        self.menu_up = False
        self.charging = True
        self.march_ct = 0.0
        self.march_tg = 0
        self.a_presses = 0  # fresh menu episode next time it opens
        self.last_seed_t = self.now()
        t = self.now()
        if self.first_commit_t is None:
            self.first_commit_t = t  # defeat counts from commit #1
        self.last_commit_t = t
        if self.commits == self.fail_at_commit:
            self.session.g.fail_sends = True
        if self.after_commit:
            self.after_commit(self)

    def mark_ending(self, n_seeds=1):
        """Begin the battle-end sequence: n seeds, then the results shape."""
        self.ending = True
        self.end_seeds_remaining = n_seeds
        self.ending_t = self.now()

    # -- input commit model ------------------------------------------------------
    def on_key_write(self, val):
        self.presses += 1
        # one P1= write covers exactly one upcoming engine key-poll (the
        # probe intercepts a single poll per stop); queued, not overwritten,
        # so a write can never outlive its frame and fire later.
        # BUT a HELD key never re-edges a menu: the probe's press() writes
        # the mask once and then answers subsequent key-poll breakpoints
        # with the SAME mask until the release. Coalescing consecutive
        # identical masks into one FIFO entry reproduces that physical law
        # (one held key = one navigation event). Without this, an answer
        # burst that straddles two engine polls re-arms the edge detector
        # and the same held key fires the menu twice — the turn-2
        # open-target press executed a move at the stale read (takeover
        # diag4 trace).
        if self._key_fifo and self._key_fifo[-1] == val:
            return
        self._key_fifo.append(val)

    def end_results(self):
        """Recorded run-20 end shape: every CT parked at 0, roster allocated."""
        self.charging = False
        self.results = True
        self.menu_up = False
        self.allow_seeds = False


def make_runtime(world, run_id, out_dir, **kw):
    os.makedirs(out_dir, exist_ok=True)
    session = world.session
    scenario = {"scenario_id": "normal-battle"}
    rt = BattleRuntime(session, scenario, run_id, out_dir,
                       wall_timeout=kw.pop("wall_timeout", 420.0), **kw)
    rt.p.verbose = False  # keep validator output readable
    # live runs assign rt.g inside live_guard(); the harness mirrors that
    # ordering (guards are fixture data, validated separately on hardware)
    rt.g = session.g
    return rt


def finish_run(rt, world, out_dir, final_note_override=None,
               resumed=False, leg1_turns=0, manual_handoff=None):
    receipt = {
        "schema": "a3-run/1",
        "run_id": rt.run_id,
        "scenario": rt.scenario_id,
        "mode": rt.mode,
        "final_state": rt.state,
        "turns": leg1_turns + rt.turn if resumed else rt.turn,
        "seeds": len(rt.p.seeds),
        "router_hits": rt.p.router_hits,
        "terminal_reason": rt._terminal_reason,
        "events": rt.events_path,
        # offline receipts document the CLI's non-pause default: every
        # scenario runs to a terminal state, so nothing is left running.
        # (The pause handoff semantics are asserted inside the pause scenario
        # and live-verified by tools/handoff_cli_probe.py on real hardware.)
        "emulator_handoff": "terminated",
    }
    if resumed:
        # mirror the live CLI receipt: the battle is one battle, leg 1
        # ended `paused` with the emulator left running, and this leg is
        # the recorded continuation (the validator's resume rule keys on
        # exactly these fields). rt.turn is the battle's RUNNING TOTAL
        # (the caller preset it to leg 1's count) — do not add leg1 again.
        receipt["resumed"] = True
        receipt["turns"] = rt.turn
        if manual_handoff:
            receipt["manual_handoff"] = manual_handoff
        if rt._terminal_reason:
            receipt["terminal_reason"] = (rt._terminal_reason
                                          + " [resumed after manual "
                                            "handoff; leg 1 ended paused]")
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    return receipt


def run_scenario(name, out_root):
    """Build + run one scripted scenario; return (receipt, errors)."""
    out_dir = os.path.join(out_root, name)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    world = FakeWorld()
    session = FakeSession(world)
    rt = make_runtime(world, f"transport-{name}", out_dir)
    errors = []

    if name == "takeover":
        # two full boundaries; then the recorded results shape. Retail AI
        # runs between player menus (seeds flow while charging) and the menu
        # re-opens after a few engine polls at an arbitrary parked CT.
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        # Astra 2026-09-17 + round 6: a deliberate claim must ride RAM-
        # identified selection. Under the identified-only contract every
        # boundary is driven from the DECODED cursor state: the destination
        # is read from RAM before the confirming input, and the turn event
        # carries the identified action+target with engine-side tile
        # verification. The battle ends only after turn 2's action — the
        # recorded end shape follows the executed action.
        world.identified_move = True
        world.reopen_after_commits = 2
        world.ending_after = (2, 12.0)
        state = rt.run()
        if state != "completed":
            errors.append(f"takeover: expected completed, got {state}")
        if rt.turn != 2:
            errors.append(f"takeover: expected 2 committed turns, got {rt.turn}")
        if world.commits != 2:
            errors.append(f"takeover: expected 2 engine commits, got {world.commits}")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        for t in turns:
            act = t.get("selected_action") or {}
            tgt = t.get("selected_target") or {}
            if act.get("kind") != "identified-move" or \
                    act.get("command_id") != _MOVE_CMD:
                errors.append(f"takeover: turn {t.get('turn')} action must be "
                              f"an identified Move (RAM cursor), got {act}")
            if tgt.get("kind") != "tile" or not tgt.get("dest"):
                errors.append(f"takeover: turn {t.get('turn')} must record the "
                              f"RAM-read destination, got {tgt}")
            if "verified" not in (t.get("note") or ""):
                errors.append(f"takeover: turn {t.get('turn')} note lacks the "
                              f"engine-side tile verification: {(t.get('note') or '')[:160]}")
            after = t.get("position_after") or {}
            if tgt.get("dest") and \
                    [after.get("x"), after.get("y")] != list(tgt["dest"]):
                errors.append(f"takeover: turn {t.get('turn')} position_after "
                              f"{after} != the identified destination "
                              f"{tgt['dest']} (the engine executed the move)")
    elif name == "unknown":
        # DE-020 recorded shape, migrated to the identified-only contract:
        # the first menu presents an unknown dialog that swallows the
        # identified flow's presses (they land, no UI answers them, nothing
        # commits, seeds stay silent). The contract has no recovery input,
        # so the run must bound with zero further writes and zero turns.
        world.identified_move = True
        world.swallow_route = True
        state = rt.run()
        if state != "stalled":
            errors.append(f"unknown: expected stalled, got {state}")
        # DE-020: after the bounded stop, no further key writes may occur
        mark = len(session.g.send_log)
        time.sleep(0.5)
        late = session.g.press_writes_after(mark)
        if late:
            errors.append(f"unknown: {len(late)} key writes after the bound")
        if rt.turn != 0:
            errors.append(f"unknown: expected 0 turns (the dialog swallowed "
                          f"the identified flow), got {rt.turn}")
    elif name == "disconnect":
        world.identified_move = True  # the commit needs the identified flow
        world.fail_at_commit = 1  # transport dies right after the first commit
        state = rt.run()
        if state != "connection_lost":
            errors.append(f"disconnect: expected connection_lost, got {state}")
        stop = [e for e in _events(rt.events_path) if e["kind"] == "stop"]
        if not stop or "transport lost" not in (stop[0].get("note") or ""):
            errors.append(f"disconnect: stop event must record the transport "
                          f"loss, got {stop}")
    elif name == "restart":
        # two sequential lifecycles over one transport
        states = []
        for i in (1, 2):
            sub = os.path.join(out_root, f"restart-{i}")
            if os.path.isdir(sub):
                shutil.rmtree(sub)  # fresh run dir: events must not append
            world2 = FakeWorld()
            session2 = FakeSession(world2)
            world2.allow_seeds = True
            world2.identified_move = True
            world2.after_commit = lambda w: w.mark_ending(1)
            rt2 = make_runtime(world2, f"transport-restart-{i}",
                               os.path.join(out_root, f"restart-{i}"))
            states.append(rt2.run())
            finish_run(rt2, world2, os.path.join(out_root, f"restart-{i}"))
        if states != ["completed", "completed"]:
            errors.append(f"restart: expected both runs completed, got {states}")
        # validate both receipts and fall through to the shared checks below
        for i in (1, 2):
            sub = os.path.join(out_root, f"restart-{i}")
            errs = validate(sub)
            if errs:
                errors.append(f"restart-{i}: {errs}")
        receipt = None
        print(f"  [{name}] two sequential lifecycles: {states}")
        return None, errors
    elif name == "defeat":
        # recorded a3-natural1 shape: mid-battle player defeat ends the battle
        # naturally (seed silence -> results shape). The runtime must not
        # drive the dead actor's ghost menu and must still classify completed.
        world.identified_move = True  # turn 1 commits via the identified flow
        world.allow_seeds = True
        world.defeat_after_commit = 18.0  # recorded: fell ~18 s after the
                                          # route committed (a3-natural1)
        state = rt.run()
        if state != "completed":
            errors.append(f"defeat: expected completed, got {state}")
        if rt.turn != 1:
            errors.append(f"defeat: expected 1 committed turn, got {rt.turn}")
        notes = [e for e in _events(rt.events_path) if e["kind"] == "note"]
        if not any("suppressing takeover" in (e.get("note") or "")
                   for e in notes):
            errors.append(f"defeat: takeover suppression was not recorded: "
                          f"{notes}")
        kinds = [e["kind"] for e in _events(rt.events_path)]
        if kinds.count("turn") != 1:
            errors.append(f"defeat: ghost menus were driven "
                          f"({kinds.count('turn')} turn events)")
    elif name == "results":
        # one committed turn, then the all-zero results shape held
        world.identified_move = True  # turn 1 commits via the identified flow
        world.allow_seeds = True
        world.after_commit = lambda w: w.mark_ending(1)
        state = rt.run()
        if state != "completed":
            errors.append(f"results: expected completed, got {state}")
        kinds = [e["kind"] for e in _events(rt.events_path)]
        if kinds.count("turn") != 1:
            errors.append(f"results: the results screen was driven "
                          f"({kinds.count('turn')} turn events)")
    elif name == "pause":
        # manual takeover request (STOP file) MID-battle: after turn 1 has
        # committed, the runtime must hand the battle over to the player —
        # no further input, breakpoints disarmed, engine still running
        # below — and classify `paused`. Astra's review: the old behavior
        # renamed the automation end `stalled (external takeover)` while
        # keeping the emulator owned; `takeover` in the runtime is the
        # automation-driven boundary, not a handoff.
        world.identified_move = True
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        import threading
        def _drop_stop():
            # turn 1 must be RECORDED (rt.turn >= 1: the turn event fired,
            # so the engine commit AND its tile verification finished) and
            # turn 2's menu already up before the STOP drops. The identified
            # flow paces its own drive (RAM re-reads between legs), so a
            # wall-clock guess lands before turn 1 — the old 25 s timer did
            # exactly that — and a world-side commit check races the
            # post-commit verification window.
            while not (rt.turn >= 1 and world.menu_up):
                time.sleep(0.1)
            open(rt.stop_file, "w").close()
        threading.Thread(target=_drop_stop, daemon=True).start()
        state = rt.run()
        if state != "paused":
            errors.append(f"pause: expected paused, got {state}")
        if rt.turn < 1:
            errors.append(f"pause: expected at least one committed turn "
                          f"before the pause, got {rt.turn}")
        # Astra 2026-09-17: the pause must take effect INSIDE long waits, not
        # only between them. The STOP lands ~25 s in, during turn 2's
        # post-route wait; under the old code the run only stopped after the
        # full 150 s wait expired. The stop event's timestamp is the proof.
        if rt.turn != 1:
            errors.append(f"pause: turn 2 committed after the STOP landed — "
                          f"a long wait ignored the pause request")
        stop_t = next((e["t"] for e in _events(rt.events_path)
                       if e["kind"] == "stop"), None)
        if stop_t is None or stop_t > 60.0:
            errors.append(f"pause: stop event landed at t={stop_t}; a pause "
                          f"inside the post-route wait must complete well "
                          f"before the 150 s wait would expire")
        mark = len(session.g.send_log)
        vt_at_pause = world.vt
        time.sleep(1.0)
        world.pump(session.g)  # the player's console keeps running: one
        # observer poll applies the frames the wall clock made due
        late = session.g.press_writes_after(mark)
        if late:
            errors.append(f"pause: {len(late)} key writes after the pause")
        if session.g.armed:
            errors.append(f"pause: breakpoints still armed after pause: "
                          f"{sorted(f'{a:08x}' for a in session.g.armed)}")
        if world.vt <= vt_at_pause:
            errors.append("pause: engine stopped advancing below the "
                          "paused run (the battle must stay live for the player)")
        kinds = [e["kind"] for e in _events(rt.events_path)]
        stops = [e for e in _events(rt.events_path) if e["kind"] == "stop"]
        if not stops or "manual play" not in (stops[0].get("note") or ""):
            errors.append(f"pause: stop event must record the handoff, got {stops}")
    elif name == "strict-press":
        # Astra round 3: after a STOP is OBSERVED, not one further key
        # write may reach the engine — the pre-round-3 shape pressed B and
        # re-drove the whole route before the post-recovery check ran. The
        # stop drops DURING turn 1's post-route drive window, so the
        # boundary handler's remaining route legs and any recovery presses
        # must all be gated per input.
        world.identified_move = True
        world.menu_reopen_seconds = 5.0
        import threading as _th
        armed = {"on": True}
        def _watch_writes():
            # drop the STOP as soon as the boundary drive's FIRST leg is
            # observed in the write stream — deterministic mid-route timing
            # (a wall-clock guess lands either before the drive or after it)
            while armed["on"]:
                if any(c.startswith("P1=") for c in session.g.send_log):
                    open(rt.stop_file, "w").close()
                    return
                time.sleep(0.05)
        _th.Thread(target=_watch_writes, daemon=True).start()
        state = rt.run()
        armed["on"] = False
        if state != "paused":
            errors.append(f"strict-press: expected paused, got {state}")
        stops = [e for e in _events(rt.events_path) if e["kind"] == "stop"]
        if not stops or stops[0].get("t", 1e9) > 60.0:
            errors.append(f"strict-press: stop landed at "
                          f"t={stops[0].get('t') if stops else None}; the "
                          f"observed STOP must end the input path promptly")
        # the core assertion: zero key writes after the STOP was observed.
        # The probe sees the stop file within one press cycle (~1.2 s); a
        # post-stop write would prove an input escaped the gate.
        mark = len(session.g.send_log)
        time.sleep(2.0)
        world.pump(session.g)
        late = session.g.press_writes_after(mark)
        if late:
            errors.append(f"strict-press: {len(late)} key writes reached the "
                          f"engine after the STOP was observed: {late[:3]}")
        # Astra round 4 gap 2: the timing rule must be measured from the
        # STOP OBSERVATION (stop_requested in the input log), not from
        # run() returning — a write that escaped between observation and
        # return would be invisible to a post-return mark
        ilog = _input_log(rt.input_log_path)
        stop_t = next((r["t"] for r in ilog
                       if r.get("event") == "stop_requested"), None)
        if stop_t is None:
            errors.append("strict-press: stop never latched in input log")
        else:
            _writes_after_stop(session, rt, stop_t, errors, "strict-press")
        # per-input evidence: the identified flow gates BETWEEN legs, so a
        # STOP that lands between presses suppresses the next attempt
        # entirely (no write, no abort record) — the raw-write ordering
        # check above is the proof. Require: after stop_requested, at most
        # the one in-flight press may complete and NO new press may START.
        # (The old assertion demanded a mid-press ABORTED record; the
        # identified law's coalesced held-key writes made that window
        # timing-dependent, and a between-legs stop is the honest shape.)
        ilog2 = _input_log(rt.input_log_path)
        presses_after = [r for r in ilog2
                         if r.get("event") == "press"
                         and stop_t is not None and r.get("t", 1e9) > stop_t
                         and not r.get("aborted")]
        if presses_after:
            errors.append(f"strict-press: {len(presses_after)} press(es) "
                          f"STARTED after stop_requested: {presses_after[:2]}")
    elif name == "stop-before-start":
        # C1 row: STOP before first input - no gameplay input at all, paused
        open(rt.stop_file, "w").close()  # dropped BEFORE run() is called
        state = rt.run()
        if state != "paused":
            errors.append(f"stop-before-start: expected paused, got {state}")
        if rt.turn != 0:
            errors.append(f"stop-before-start: {rt.turn} turns committed")
        writes = [c for _, c in session.g.key_writes()]
        if writes:
            errors.append(f"stop-before-start: {len(writes)} key writes "
                          f"reached the engine after a pre-run STOP: "
                          f"{writes[:3]}")
        stop = [e for e in _events(rt.events_path) if e["kind"] == "stop"]
        if not stop or "manual play" not in (stop[0].get("note") or ""):
            errors.append("stop-before-start: paused receipt required")
        ilog = _input_log(rt.input_log_path)
        if not any(r.get("event") == "stop_requested" for r in ilog):
            errors.append("stop-before-start: stop_requested not latched "
                          "in input log")
    elif name == "stop-during-drive":
        # C1 row (renamed from stop-during-recovery: the identified-only
        # contract has no B-recovery; the risk window is now the identified
        # drive's remaining legs). The menu presents the identified Move
        # state, but a second menu after commit 1 is an unknown dialog
        # (swallow_route) whose drive legs cannot commit; the STOP drops as
        # the FIRST key write after that point is observed, so the
        # drive's remaining presses must never fire.
        world.identified_move = True
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        world.after_commit = lambda w: setattr(w, "swallow_route", True)
        armed = {"on": True}
        def _watch_recovery():
            # drop the STOP on the first NEW key write AFTER commit 1 —
            # turn 2's dialog drive has begun, with legs still ahead of it.
            # Compare against the write count snapshotted at commit time:
            # turn 1's own presses are already in the log, and a press's
            # answer burst pushes the P1= write out of any small tail
            # window within milliseconds, so both a whole-log scan without
            # a mark and a tail slice get the timing wrong.
            p1_mark = None
            while armed["on"]:
                if world.commits >= 1:
                    if p1_mark is None:
                        p1_mark = sum(1 for c in session.g.send_log
                                      if c.startswith("P1="))
                    elif sum(1 for c in session.g.send_log
                             if c.startswith("P1=")) > p1_mark:
                        open(rt.stop_file, "w").close()
                        armed["on"] = False
                        return
                time.sleep(0.05)
        import threading as _th2
        _th2.Thread(target=_watch_recovery, daemon=True).start()
        state = rt.run()
        armed["on"] = False
        if state != "paused":
            errors.append(f"stop-during-drive: expected paused, got "
                          f"{state}, events={_events(rt.events_path)[-3:]}")
        # ordering proof from the raw log: no press may START after the
        # stop_requested record's timestamp
        ilog = _input_log(rt.input_log_path)
        stop_t = next((r["t"] for r in ilog
                       if r.get("event") == "stop_requested"), None)
        if stop_t is None:
            errors.append("stop-during-drive: stop never latched")
        else:
            _writes_after_stop(session, rt, stop_t, errors,
                               "stop-during-drive")
    elif name == "stop-coincides-with-progress":
        # C1 row: STOP coincides with progress - cancellation wins; no new
        # turn starts. Drop the STOP just as the post-commit seed arrives.
        world.identified_move = True
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        armed = {"on": True}
        def _watch_seed():
            while armed["on"]:
                if len(rt.p.seeds) > 0:
                    open(rt.stop_file, "w").close()
                    return
                time.sleep(0.02)
        import threading as _th3
        _th3.Thread(target=_watch_seed, daemon=True).start()
        state = rt.run()
        armed["on"] = False
        if state != "paused":
            errors.append(f"stop-coincides-with-progress: expected paused, "
                          f"got {state}")
        # no NEW turn may start after the latched stop: turn events must
        # all predate stop_requested (or none exist)
        ilog = _input_log(rt.input_log_path)
        stop_t = next((r["t"] for r in ilog
                       if r.get("event") == "stop_requested"), None)
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        if stop_t is not None and any(e.get("t", 1e9) > stop_t for e in turns):
            errors.append("stop-coincides-with-progress: a new turn started "
                          "after the stop was latched")
        # Astra round 4 gap 2: the same rule on the RAW WRITE stream —
        # any automation key write timestamped after stop_requested fails,
        # even if run() returned long before it was noticed
        if stop_t is not None:
            _writes_after_stop(session, rt, stop_t, errors,
                               "stop-coincides-with-progress")
        stops = [e for e in _events(rt.events_path) if e["kind"] == "stop"]
        if not stops:
            errors.append("stop-coincides-with-progress: stop event missing")
    elif name == "guard-failure":
        # Astra round 4 gap 3: the CLI's guard-failure path returned BEFORE
        # writing run.json and passed a `reason` kwarg the event schema
        # drops — the failure left only stdout text behind. Drive the REAL
        # run_autobattle.main() with the faked session (guard failure
        # induced by clearing the player's roster name pointer) and require
        # the same receipt the normal path writes.
        import run_autobattle as _ra
        from probe_control_handoff import ROSTER, STRIDE as _STRIDE
        from fixture_guard import OFF_NAME as _OFF_NAME
        cli_dir = os.path.join(out_root, f"transport-{name}")
        if os.path.isdir(cli_dir):
            shutil.rmtree(cli_dir)  # events append across runs: start clean
        orig_ctor = _ra.FixtureSession
        _ra.FixtureSession = lambda state, rom=None: session
        try:
            base = ROSTER + _STRIDE * 6 + _OFF_NAME
            for i in range(4):
                session.g.mem[base + i] = 0  # player name pointer gone
            rc = _ra.main(["--rom", "fake.gba", "--state", "fake.ss0",
                           "--scenario", "configs/battle-scenarios/normal-battle.json",
                           "--yes", "--out-root", out_root,
                           "--run-id", f"transport-{name}",
                           "--wall-timeout", "60"])
        finally:
            _ra.FixtureSession = orig_ctor
        if rc != 1:
            errors.append(f"guard-failure: CLI exit code {rc}, expected 1")
        # the CLI's run-id lands in its own dir (transport-guard-failure);
        # the harness's rt (built by run_scenario) points at out_dir, which
        # never receives a receipt on this path
        rpath = os.path.join(cli_dir, "run.json")
        if os.path.abspath(cli_dir) != os.path.abspath(out_dir):
            print(f"  [{name}] note: CLI receipt in {cli_dir}, harness rt "
                  f"dir {out_dir} stays empty (guard failed before run)")
        receipt = None
        if not os.path.exists(rpath):
            errors.append("guard-failure: no run.json written on the "
                          "guard-failure path (CLI exits before the receipt)")
        else:
            with open(rpath, encoding="utf-8") as fh:
                receipt = json.load(fh)
            if receipt.get("final_state") != "stalled":
                errors.append(f"guard-failure: run.json final_state "
                              f"{receipt.get('final_state')!r}")
            if receipt.get("turns") != 0:
                errors.append(f"guard-failure: turns={receipt.get('turns')}")
        ev_path = os.path.join(cli_dir, "events.jsonl")
        stops = [e for e in _events(ev_path) if e["kind"] == "stop"]
        if not stops:
            errors.append("guard-failure: no stop event")
        elif "guard" not in (stops[0].get("note") or ""):
            errors.append(f"guard-failure: the guard failure reason must ride "
                          f"the stop event note (not a dropped kwarg): {stops[0]}")
        ilog = _input_log(os.path.join(cli_dir, "input-log.jsonl"))
        if any(r.get("event") in ("press", "drive") for r in ilog):
            errors.append("guard-failure: input records exist although the "
                          "guard never passed (no input precedes the guard)")
        errs = validate(cli_dir)
        errors.extend(errs)
        print(f"  [{name}] state=stalled turns=0 (real CLI main path)")
        return receipt, errors
    elif name == "identified-move":
        # C2 positive control: the DECODED menu drives an identified move —
        # the destination is read from RAM before the confirming input, the
        # roster tile must reach exactly that destination, and the turn
        # event carries the identified action+target claim. One turn, then
        # the max_turns bound (the fake's law keeps the menu closed after
        # the commit, so the bound is the only classifier outcome).
        world.identified_move = True
        world.allow_seeds = True
        rt.max_turns = 1   # bound right after the committed turn (the fake's
                           # law keeps the menu closed; seeds would otherwise
                           # run to the wall timeout)
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-move: expected stalled (max_turns=1 "
                          f"bound after the committed turn), got {state}")
        if world.commits != 1:
            errors.append(f"identified-move: expected 1 engine commit, "
                          f"got {world.commits}")
        if tuple(world._march_tile) != (4, 11):
            errors.append(f"identified-move: the engine executed tile "
                          f"{tuple(world._march_tile)}, expected the "
                          f"identified destination (4, 11)")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        if len(turns) != 1:
            errors.append(f"identified-move: expected 1 turn event, "
                          f"got {len(turns)}")
        else:
            t = turns[0]
            act = t.get("selected_action") or {}
            if act.get("kind") != "identified-move" or act.get("command_id") != 0:
                errors.append(f"identified-move: the turn action is not "
                              f"claimed as an identified Move: {act}")
            tgt = t.get("selected_target") or {}
            if tgt.get("kind") != "tile" or list(tgt.get("dest") or []) != [4, 11]:
                errors.append(f"identified-move: the turn target is not the "
                              f"identified destination: {tgt}")
            if "verified" not in (t.get("note") or ""):
                errors.append(f"identified-move: the note must record the "
                              f"engine-side tile verification: {t.get('note')}")
    elif name == "identified-move-wrong":
        # C2 negative control: the engine executes a DIFFERENT tile than the
        # RAM cursor named (the dishonest-engine case). The runtime must
        # DEMOTE — no identified action/target claim may survive — while the
        # turn itself still commits (the input was fine; only the claim
        # rides engine-side verification).
        world.identified_move = True
        world.wrong_move = True
        world.allow_seeds = True
        rt.max_turns = 1
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-move-wrong: expected stalled, got {state}")
        if world.commits != 1:
            errors.append(f"identified-move-wrong: expected 1 commit, "
                          f"got {world.commits}")
        if tuple(world._march_tile) != tuple(world.wrong_tile):
            errors.append("identified-move-wrong: the fake did not execute "
                          "its wrong tile — the control does not exercise "
                          "the demotion path")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        if len(turns) != 1:
            errors.append(f"identified-move-wrong: expected 1 turn event, "
                          f"got {len(turns)}")
        else:
            t = turns[0]
            if t.get("selected_action") is not None or \
                    t.get("selected_target") is not None:
                errors.append(f"identified-move-wrong: the claim SURVIVED an "
                              f"engine that executed a different tile — "
                              f"action={t.get('selected_action')} "
                              f"target={t.get('selected_target')}")
            if "NOT claimed" not in (t.get("note") or ""):
                errors.append(f"identified-move-wrong: the demotion must be "
                              f"recorded in the turn note: {t.get('note')}")
    elif name == "identified-move-occupied":
        # C3 b-ladder control (c3-live-a attempts 2/3 + probe4 law): the
        # confirmed destination tile is OCCUPIED — no walk happens, the
        # unit info panel eats D-pads (cmd byte sticky-frozen, no echo),
        # and B dismisses one layer per press back to the command menu.
        # The driver's b-ladder must repair with echo-gated Bs (channel
        # liveness proven by echo hits>0) and close the turn with the
        # Wait tail; the CANCELLED move must NOT be claimed (only the
        # engine-observed Wait commit is the turn's outcome).
        world.identified_move = True
        world.occupied_dest = True
        world.allow_seeds = True
        rt.max_turns = 1
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-move-occupied: expected stalled "
                          f"(max_turns=1 bound after the repaired turn), "
                          f"got {state}")
        if world.commits != 1:
            errors.append(f"identified-move-occupied: expected 1 commit "
                          f"(the post-repair Wait), got {world.commits}")
        # no walk happened: the roster tile stays at the origin
        if tuple(world._march_tile) != (4, 10):
            errors.append(f"identified-move-occupied: the fake walked to "
                          f"{tuple(world._march_tile)} despite the occupied "
                          f"tile — the control does not exercise the panel")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        if len(turns) != 1:
            errors.append(f"identified-move-occupied: expected 1 turn "
                          f"event, got {len(turns)}")
        else:
            t = turns[0]
            act = t.get("selected_action") or {}
            if act.get("kind") != "identified-wait":
                errors.append(f"identified-move-occupied: the repaired turn "
                              f"must claim the WAIT it actually committed, "
                              f"not the cancelled move: {act}")
            if t.get("selected_target") is not None:
                errors.append(f"identified-move-occupied: a Wait commit "
                              f"carries no target claim: "
                              f"{t.get('selected_target')}")
        ilog = _input_log(rt.input_log_path)
        bs = [r for r in ilog if str(r.get("tag", "")).startswith("c3:backout-")
              and "echo" not in str(r.get("tag"))]
        if not bs:
            errors.append(f"identified-move-occupied: no b-ladder presses "
                          f"in the input log — the repair never ran")
        if len(bs) > 3:
            errors.append(f"identified-move-occupied: {len(bs)} b-ladder "
                          f"presses exceeds the bounded ladder (3)")
    elif name == "submenu":
        # REWRITTEN for the identified-only contract (round 6): the old
        # submenu shape exercised B-recovery, which is banned — recovery
        # drives un-identified routes. The recorded risk it covered (a
        # non-standard menu the committed shape cannot close) is now the
        # honest-bound path: the runtime may navigate BACK (B) — because
        # that is menu navigation, not a tactical selection — and must
        # otherwise stop pressing. The fake presents a menu the identified
        # shape cannot commit (swallow_route: A presses are swallowed), so
        # the run must bound with zero turns and no writes after the bound.
        world.identified_move = True
        world.swallow_route = True
        state = rt.run()
        if state != "stalled":
            errors.append(f"submenu: expected stalled (honest bound on an "
                          f"unidentifiable menu), got {state}")
        if rt.turn != 0:
            errors.append(f"submenu: {rt.turn} turns committed although the "
                          f"menu shape never committed — recovery input is "
                          f"banned (identified-only contract)")
        mark = len(session.g.send_log)
        time.sleep(0.5)
        late = session.g.press_writes_after(mark)
        if late:
            errors.append(f"submenu: {len(late)} key writes after the bound")
    elif name == "identified-move-invalid":
        # Astra round-6 gap 3 (negative control), recast for the C3 law:
        # the menu copy reads an UNKNOWN command byte (7) — garbage from a
        # redraw, a submenu, or a dialog. Neither the move planner nor the
        # C3 wait fallback may accept it: the rejection must prevent input
        # entirely — no chooser route, no fixed route, nothing. (The old
        # WAIT-cursor shape is no longer a rejection: identified-wait
        # closes exactly that menu, which identified-wait-control proves.)
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        world.identified_move = True
        world._cmd_cursor = 7           # unknown command byte: not 0/1/2
        world._target_cursor = [5, 9]   # stale target copy: a "readable" x/y
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-move-invalid: expected stalled "
                          f"(honest bound), got {state}")
        notes = [(e.get("note") or "") for e in _events(rt.events_path)]
        if not any("plan rejected" in n for n in notes):
            errors.append("identified-move-invalid: no planner-rejection "
                          f"note recorded: {notes}")
        # the input contract: the rejection must have prevented EVERY key
        # write (raw stream, not the intent log)
        writes = session.g.key_writes()
        if writes:
            errors.append(f"identified-move-invalid: {len(writes)} key "
                          "writes escaped after the planner rejected the "
                          "snapshot (rejection must prevent input, not "
                          f"fall back): {writes[:3]}")
    elif name == "identified-wait-control":
        # C3 offline control (offline counterpart of criterion 1): a menu
        # is open but NO move is plannable — the re-opened post-move shape
        # (probe5: the command copy re-initializes on ACTION) with no move
        # planned. The move planner rejects it (cursor != Move); the C3
        # identified-WAIT fallback must still close it: the command id is
        # read from RAM before any input, the driver navigates to Wait,
        # and the probe6 two-A shape commits the turn.
        world.identified_move = True
        world.allow_seeds = True
        world.menu_up = True
        world.charging = False
        world._cmd_cursor = _ACTION_CMD  # re-opened post-move shape (probe5)
        world._target_cursor = None
        rt.max_turns = 1
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-wait-control: expected stalled "
                          f"(max_turns bound after the committed turn), "
                          f"got {state}")
        if world.commits != 1:
            errors.append(f"identified-wait-control: expected 1 engine "
                          f"commit (the Wait closed the turn), got "
                          f"{world.commits}")
        if tuple(world._march_tile) != (4, 10):
            errors.append(f"identified-wait-control: the unit moved to "
                          f"{tuple(world._march_tile)} — a Wait commits no "
                          "move")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        if len(turns) != 1:
            errors.append(f"identified-wait-control: expected 1 turn event, "
                          f"got {len(turns)}")
        else:
            act = turns[0].get("selected_action") or {}
            if act.get("kind") != "identified-wait" or \
                    act.get("command_id") != _ACTION_CMD:
                errors.append(f"identified-wait-control: the turn is not "
                              f"claimed as identified-wait from the RAM-read "
                              f"command id: {act}")
    elif name == "identified-wait-noecho":
        # c3-live-a turn-3 failure, as an offline negative control: the
        # sticky cursor byte reads Action but NO menu is up (post-commit
        # animation freeze that the frozen-CT classifier misread as a
        # boundary). One DOWN must ECHO in the decoded cursor byte before
        # the Wait drive trusts the byte; here the UI cannot answer
        # (swallow_route: presses land, nothing changes), so after the
        # echo probe the driver must fire NOTHING further and the run must
        # bound honestly with zero commits.
        world.identified_move = True
        world.allow_seeds = True
        world.menu_up = False
        world.charging = False
        world.swallow_route = True
        world._cmd_cursor = _ACTION_CMD  # sticky byte from the last menu
        world._target_cursor = None
        state = rt.run()
        if state != "stalled":
            errors.append(f"identified-wait-noecho: expected stalled "
                          f"(honest bound after the silent UI), got {state}")
        if world.commits != 0:
            errors.append(f"identified-wait-noecho: expected 0 commits, "
                          f"got {world.commits}")
        # A hits=0 press is ATTEMPTED but never reaches the engine (the
        # channel is silent — that is the live failure being modeled). Under
        # the re-arm law the Wait driver probes echo + panel-B + echo2 per
        # boundary, bounded by the 3-strikes cap: 9 press attempts total,
        # ZERO delivered engine writes, and the honest 3-boundary bound.
        ilog = _input_log(rt.input_log_path)
        if len(ilog) > 9:
            errors.append(f"identified-wait-noecho: {len(ilog)} press "
                          f"attempts exceed the 3-boundary re-arm cap")
        if any(r.get("hits", 0) not in (0, None) for r in ilog):
            errors.append(f"identified-wait-noecho: a press landed (hits>0) "
                          f"but the control models a silent channel")
        notes = [(e.get("note") or "") for e in _events(rt.events_path)]
        if not any("never answered after 3" in n for n in notes):
            errors.append(f"identified-wait-noecho: the 3-boundary bound "
                          f"note was not recorded: {notes}")
        if world.commits != 0:
            errors.append(f"identified-wait-noecho: expected 0 commits, "
                          f"got {world.commits}")
    elif name == "boundary-panel":
        # c3-live-a5 positive control: the FIRST re-open sits behind a
        # turn-transition info panel — the frozen-CT classifier fires
        # while the menu is NOT yet open, the echo lands but the byte
        # cannot move (panel eats D-pads; the covered byte is sticky).
        # The Wait driver probes one panel-B; the re-arm law must then
        # WAIT for the real menu (no kill) and commit the turn when the
        # echo finally works. The run's only honest ending is the
        # max_turns bound AFTER the committed turn.
        world.identified_move = True
        world.panel_first_reopen = True
        world.allow_seeds = True
        world.menu_reopen_seconds = 25.0   # the panel must still be up when
                                           # the classifier re-polls: a 4 s
                                           # panel expires inside the
                                           # post-commit wait and the shape
                                           # never reaches the boundary
        rt.max_turns = 2   # the panel precedes re-open #2: one full drive
                           # must commit first, then the panel shape runs
        state = rt.run()
        if state != "stalled":
            errors.append(f"boundary-panel: expected stalled (max_turns=2 "
                          f"bound after the panel-repaired turn), "
                          f"got {state}")
        if world.commits != 2:
            errors.append(f"boundary-panel: expected 2 commits (the panel "
                          f"re-arm must end in a committed turn), "
                          f"got {world.commits}")
        ilog = _input_log(rt.input_log_path)
        pb = [r for r in ilog if r.get("tag") == "c3:panel-b"]
        if not pb:
            errors.append(f"boundary-panel: no panel-B probe in the input "
                          f"log — the transition-panel shape never ran")
        notes = [(e.get("note") or "") for e in _events(rt.events_path)]
        if not any("re-arming the menu boundary" in n for n in notes):
            errors.append(f"boundary-panel: the re-arm note was not "
                          f"recorded: {notes}")
    elif name == "boundary-dead":
        # c3-live-a5 negative control: a genuinely dead UI (swallow) at
        # every boundary. The re-arm law must bound honestly after 3
        # consecutive failed boundaries — zero commits, and the total
        # echo attempts bounded (no infinite echo ladder against a dead
        # channel).
        world.identified_move = True
        world.allow_seeds = True
        world.swallow_route = True
        world.menu_reopen_seconds = 4.0
        state = rt.run()
        if state != "stalled":
            errors.append(f"boundary-dead: expected stalled (honest "
                          f"bound), got {state}")
        if world.commits != 0:
            errors.append(f"boundary-dead: expected 0 commits, "
                          f"got {world.commits}")
        ilog = _input_log(rt.input_log_path)
        echoes = [r for r in ilog if str(r.get("tag", "")).startswith("c2:")]
        if not echoes:
            errors.append("boundary-dead: no drive presses recorded — the "
                          "negative control did not exercise the ladder")
        # each of the 3 failed boundaries drove exactly its bounded leg set
        # (open-target + 4 dest-search steps); a 4th boundary or extra
        # presses would mean the re-arm loop is unbounded against a dead UI
        if len(ilog) > 15:
            errors.append(f"boundary-dead: {len(ilog)} input records exceed "
                          f"the 3-boundary cap — the re-arm loop is "
                          f"unbounded against a dead UI")
        notes = [(e.get("note") or "") for e in _events(rt.events_path)]
        if not any("never answered after 3" in n for n in notes):
            errors.append(f"boundary-dead: the 3-boundary bound note was "
                          f"not recorded: {notes}")
    elif name == "resume-after-pause":
        # C3 offline control (offline counterpart of criteria 2+3): leg 1
        # drives one identified turn, a STOP pauses with the emulator
        # alive; leg 2 resumes on the SAME world/events/logs, the player
        # (manual write) closes the open menu, and the automated
        # continuation commits the NEXT turn of the SAME battle. The
        # validator's resume rule must accept exactly this shape.
        import threading as _th2
        world.identified_move = True
        world.allow_seeds = True
        world.menu_reopen_seconds = 4.0
        # leg 2 must reach a TERMINAL state for the validator's resumed
        # lifecycle check: menus stop re-opening after the battle's 3rd
        # commit and the end sequence follows the executed final action
        # (the takeover scenario's recorded complete-battle shape)
        world.reopen_after_commits = 3
        world.ending_after = (3, 12.0)
        def _drop_stop2():
            while not (rt.turn >= 1 and world.menu_up):
                time.sleep(0.05)
            open(rt.stop_file, "w").close()
        _th2.Thread(target=_drop_stop2, daemon=True).start()
        state1 = rt.run()
        if state1 != "paused":
            errors.append(f"resume-after-pause: leg 1 must pause, got "
                          f"{state1}")
        if rt.turn != 1:
            errors.append(f"resume-after-pause: leg 1 committed "
                          f"{rt.turn} turns, expected exactly 1 before "
                          "the pause")
        handoff_pid = 424242
        # -- leg 2: resume on the SAME world (the adopted battle) --------
        try:
            os.remove(rt.stop_file)   # leg 1's STOP must not latch leg 2
        except OSError:
            pass
        rt2 = make_runtime(world, f"transport-{name}", out_dir, resume=True)
        rt2.turn = 1                     # continuation of leg 1's count
        # the player acts during the handoff gap: one window write, the
        # manual record (never an automation press)
        rt2.log_manual_write(0x01)
        rt2.run()
        # the same battle must have advanced: one more turn committed by
        # the automated continuation
        if rt2.turn <= 1:
            errors.append(f"resume-after-pause: the resumed leg committed "
                          f"no turn of the same battle (rt2.turn={rt2.turn})")
        if world.commits < 2:
            errors.append(f"resume-after-pause: expected >=2 engine commits "
                          f"across both legs (same battle), got "
                          f"{world.commits}")
        evs = _events(rt2.events_path)
        stops = [e for e in evs if e["kind"] == "stop"]
        starts = [e for e in evs if e["kind"] == "start"]
        if len(stops) < 2 or stops[0].get("state") != "paused" or \
                stops[-1].get("state") not in ("completed", "stalled"):
            errors.append(f"resume-after-pause: event lifecycle is not "
                          f"paused-then-terminal: "
                          f"{[(e.get('kind'), e.get('state')) for e in evs]}")
        if len(starts) != 2 or not (starts[1].get("note") or "").startswith("resume:"):
            errors.append("resume-after-pause: leg 2 must emit a start event "
                          "whose note says it continues the paused handoff")
        turn_events = [e for e in evs if e["kind"] == "turn"]
        if len(turn_events) < 2 or any(
                (e.get("turn") or 0) < 2 for e in turn_events[1:]):
            errors.append(f"resume-after-pause: leg 2's turn must carry the "
                          f"continuation number (turn >= 2), got "
                          f"{[(e.get('turn')) for e in turn_events]}")
        # receipt: mirror the live CLI's resumed receipt, then the strict
        # validator must ACCEPT it (regression-first: the round-6 validator
        # rejected two starts; the resume rule must accept this shape)
        receipt = finish_run(rt2, world, out_dir, resumed=True,
                             leg1_turns=1,
                             manual_handoff={"pid": handoff_pid,
                                             "port": 2345})
        if receipt["turns"] != rt2.turn:
            errors.append(f"resume-after-pause: receipt turns "
                          f"{receipt['turns']} != the battle's running "
                          f"total {rt2.turn}")
        errs = validate(out_dir)
        if errs:
            errors.extend(f"resume-after-pause receipt: {e}" for e in errs)
        # adversarial check: a receipt claiming `resumed` WITHOUT leg 1's
        # paused stop must FAIL (the resume claim is auditable)
        ev_lines = [json.loads(l) for l in open(rt2.events_path,
                                                encoding="utf-8") if l.strip()]
        true_lines = list(ev_lines)
        fake = [e for e in ev_lines if e["kind"] != "stop"]
        with open(rt2.events_path, "w", encoding="utf-8") as fh:
            for e in fake:
                fh.write(json.dumps(e) + "\n")
        errs2 = validate(out_dir)
        if not errs2:
            errors.append("resume-after-pause: the validator ACCEPTED a "
                          "resumed receipt with no paused leg-1 stop — the "
                          "resume rule is not enforced")
        # restore the true stream: the common tail re-validates after the
        # scenario body, and the tampered file would fail it
        with open(rt2.events_path, "w", encoding="utf-8") as fh:
            for e in true_lines:
                fh.write(json.dumps(e) + "\n")
        # the receipt is final (resumed shape); the common tail must not
        # overwrite it with leg 1's stub receipt
        rt._final_receipt_done = True
    else:
        raise ValueError(f"unknown scenario {name}")

    if getattr(rt, "_final_receipt_done", False):
        # the scenario wrote its own final receipt (C3 resumed shape)
        with open(os.path.join(out_dir, "run.json"), encoding="utf-8") as fh:
            receipt = json.load(fh)
    else:
        receipt = finish_run(rt, world, out_dir)
    errs = validate(out_dir)
    # Astra round-6 gap 1: the receipt-vs-artifacts contract applies to
    # scenario outputs too — including an empty log for a run that recorded
    # no input (the file itself must exist from run start)
    errs = validate_run_receipt(receipt, out_dir, errs)
    if errs:
        errors.extend(errs)
    print(f"  [{name}] state={receipt['final_state']} turns={receipt['turns']} "
          f"seeds={receipt['seeds']} presses={len(session.g.key_writes())}")
    return receipt, errors



def _writes_after_stop(session, rt, stop_t, errors, label):
    """C1 gap 2: the cancellation rule measured from STOP OBSERVATION.

    Every automation key write whose packet timestamp is after the
    stop_requested record fails — regardless of when run() returned. The
    raw write stream (session.g.key_writes(), wall-clock tagged) is the
    ground truth, not the intent-level input log.
    """
    late = [(round(ts - rt.t0, 3), c) for (ts, c) in session.g.key_writes()
            if (ts - rt.t0) > stop_t + 0.001]
    if late:
        errors.append(f"{label}: {len(late)} key writes are timestamped "
                      f"after stop_requested t={stop_t} (observation-time "
                      f"rule, not run() return): {late[:3]}")
    return late

def _events(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]

def _input_log(path):
    """Raw timestamped input/stop records (C1 ordering proof)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    except FileNotFoundError:
        return []


def validate_run_receipt(receipt, run_dir, errors=None):
    """Lifecycle checks a run receipt must satisfy against its own artifacts.

    Astra round-6 gap 1: every run that CLAIMS external input in its event
    stream must have a NON-EMPTY input log on disk. The scenario runners
    verify their own scripted assertions AND this contract; a harness that
    removes the log from a receipt's directory now fails here. A run with
    legitimately zero input (planner rejection, pre-input stop) keeps its
    empty log: it is the evidence FOR zero input.
    """
    errors = [] if errors is None else errors
    label = receipt.get("run_id", run_dir)
    input_log_path = os.path.join(run_dir, "input-log.jsonl")
    claims_input = False
    try:
        with open(os.path.join(run_dir, "events.jsonl"),
                  encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if (rec.get("control_mode") == "external"
                        and rec.get("kind") != "boundary"
                        or rec.get("selected_action") is not None):
                    # boundary events only ANNOUNCE detected menu ownership
                    # (they precede the plan decision by design); input is
                    # claimed by turn/action records — those require the log
                    claims_input = True
                    break
    except FileNotFoundError:
        pass
    if not os.path.exists(input_log_path):
        errors.append(f"{label}: input-log.jsonl missing from the run "
                      f"directory (input claims are unverifiable without "
                      f"it)")
    elif os.path.getsize(input_log_path) == 0 and claims_input:
        errors.append(f"{label}: input-log.jsonl is empty but the run "
                      f"claims external input (input ordering claims are "
                      f"unverifiable without it)")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", default="all",
                            choices=["all", "takeover", "unknown", "disconnect",
                                     "restart", "defeat", "results", "submenu",
                                     "pause", "strict-press",
                                     "stop-before-start",
                                     "stop-during-drive",
                                     "stop-coincides-with-progress",
                                     "guard-failure", "identified-move",
                                     "identified-move-wrong",
                                     "identified-move-invalid",
                                     "identified-move-occupied",
                                     "identified-wait-control",
                                     "identified-wait-noecho",
                                     "boundary-panel", "boundary-dead",
                                     "resume-after-pause"])
    ap.add_argument("--out-root", default=os.path.join("outputs", "autobattle",
                                                       "transport-checks"))
    args = ap.parse_args(argv)

    names = ["takeover", "unknown", "disconnect", "restart", "defeat",
             "results", "submenu", "pause", "strict-press",
             "stop-before-start", "stop-during-drive",
             "stop-coincides-with-progress", "guard-failure",
             "identified-move", "identified-move-wrong",
             "identified-move-invalid", "identified-move-occupied",
             "identified-wait-control", "boundary-panel", "boundary-dead",
             "resume-after-pause"]
    if args.scenario != "all":
        names = [args.scenario]
    failures = []
    for name in names:
        print(f"scenario {name}")
        t0 = time.time()
        try:
            _, errors = run_scenario(name, args.out_root)
        except Exception as exc:  # a crash is a scenario failure, not a skip
            errors = [f"scenario raised: {exc!r}"]
        if errors:
            print(f"  FAIL {name} ({time.time() - t0:.1f}s)")
            for e in errors:
                print(f"    - {e}")
            failures.append(name)
        else:
            print(f"  PASS {name} ({time.time() - t0:.1f}s)")
    if failures:
        print(f"TRANSPORT VALIDATION FAILED: {failures}")
        return 1
    print("TRANSPORT VALIDATION PASSED: all recorded transport paths hold "
          "the receipts contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
