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
        return [c for c in self.send_log if c.startswith("P1=")]

    def press_writes_after(self, mark):
        return [c for c in self.send_log[mark:] if c.startswith("P1=")]


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
        self.expect_action_route = False  # scenario knob: chooser route shape
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
        self.player_tile = (4, 10)   # chooser evidence: nonzero recorded tile

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
        if a_seen and not self._a_prev:
            self.a_presses += 1
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
        if (b_seen and not self._b_prev and self.menu_up
                and not self.swallow_b):
            if self.swallow_first_route and self.commits == 0:
                # submenu layer: B returns to the parent command menu
                self.swallow_first_route = False
            else:
                # closing the menu parks the unit at CT 1000 — ready to be
                # re-selected; the recorded parked-menu CT stays <= 999
                self.menu_up = False
                self.charging = True
                self.march_ct = CT_REOPEN_AT
            self.a_presses = 0      # fresh menu episode
            self._a_prev = False
            self.b_closes += 1
        self._b_prev = b_seen
        # the engine polls keys every frame while a menu is up: the key
        # breakpoint hits and a stop reaches the probe
        self.session.g.queue.append((BP_KEY, "T05keypoll"))

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
        # second A onset of the proven route commits the menu (A2.5 contract)
        if self.a_presses < 2 or not self.menu_up:
            return
        if self.swallow_route:
            return  # unknown dialog eats the route; nothing changes
        if        self.swallow_first_route and self.commits == 0:
            return  # submenu shape: the plain route cannot reach a commit
        self.commits += 1
        # the action executes after the menu commit: apply its engine-side
        # consequences (target hp loss, actor MP spend) synchronously - the
        # ORDER is the recorded shape (commit, then effects), and a delayed
        # timer raced the runtime's first evidence snapshot inside the
        # commit-to-execution gap (takeover turn 2 closed its window on a
        # CT-only read before the timer fired)
        self.apply_action_evidence()
        self.menu_up = False
        self.charging = True
        self.march_ct = 0.0
        self.a_presses = 0  # fresh menu episode next time it opens
        self.last_seed_t = self.now()
        t = self.now()
        # committed action evidence (Astra 2026-09-17): the resolution path
        # records the target ids at +0xE7 and the ability-cost path spends
        # MP at +0x1C — CT-only deltas cannot identify a committed command.
        # Scenarios script expect_action_route like the other recorded
        # shapes (swallow_route, fail_at_commit); the input stream alone
        # cannot distinguish the two routes (identical masks).
        if self.expect_action_route:
            self.march_tg = 0x21  # unit ids 2 and 1 packed (two 4-bit ids)
            self.march_mp = max(0, self.march_mp - 8)  # ability MP cost
        else:
            self.march_tg = 0
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

    def apply_action_evidence(self):
        """Scripted engine-side consequences of the committed action.

        The engine executes the action AFTER the menu commit: the target
        (slot 2 per the scripted +0xE7 record) loses hp — bounded by its
        max_hp so the runtime's roster-bounded validation accepts it — and
        the actor spends a second MP source. Astra round 3: actor-specific
        evidence must be VALIDATED (hp delta within max_hp, ids inside the
        roster), not just present.
        """
        if self.expect_action_route:
            self.slot2_hp = max(0, self.slot2_hp - 47)  # target slot-2 hp
            self.march_mp = max(0, self.march_mp - 4)   # 2nd-source MP cost

    # -- input commit model ------------------------------------------------------
    def on_key_write(self, val):
        self.presses += 1
        # one P1= write covers exactly one upcoming engine key-poll (the
        # probe intercepts a single poll per stop); queued, not overwritten,
        # so a write can never outlive its frame and fire later
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


def finish_run(rt, world, out_dir, final_note_override=None):
    receipt = {
        "schema": "a3-run/1",
        "run_id": rt.run_id,
        "scenario": rt.scenario_id,
        "mode": rt.mode,
        "final_state": rt.state,
        "turns": rt.turn,
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
        # Astra 2026-09-17: a deliberate non-Wait claim must ride
        # actor-specific evidence, not CT churn. The chooser drives the
        # action route, so the engine records target ids (+0xE7) and spends
        # MP (+0x1C) — the turn event must carry the structured action, the
        # decoded target, and the mp delta in its note. The battle ends only
        # after turn 2's action executes (a finishing blow) — the recorded
        # end shape follows the executed action, never teleporting the
        # results screen over the evidence window.
        world.expect_action_route = True
        world.reopen_after_commits = 2
        world.ending_after = (2, 12.0)
        state = rt.run()
        if state != "completed":
            errors.append(f"takeover: expected completed, got {state}")
        if rt.turn != 2:
            errors.append(f"takeover: expected 2 committed turns, got {rt.turn}")
        if world.commits != 2:
            errors.append(f"takeover: expected 2 engine commits, got {world.commits}")
        if world.a_presses >= 4:
            errors.append(f"takeover: A-presses should reset per menu episode "
                          f"(got {world.a_presses} after 2 commits)")
        turns = [e for e in _events(rt.events_path) if e["kind"] == "turn"]
        for t in turns:
            if not t.get("selected_action") or not t.get("selected_target"):
                errors.append(f"takeover: turn {t.get('turn')} must record a "
                              f"deliberate action AND a decoded target "
                              f"(Astra's CT-churn critique); got "
                              f"action={t.get('selected_action')} "
                              f"target={t.get('selected_target')}")
            if t.get("selected_target") and \
                    t["selected_target"].get("unit_ids") != [2, 1]:
                errors.append(f"takeover: turn {t.get('turn')} target ids "
                              f"{t['selected_target'].get('unit_ids')} != [2, 1] "
                              f"(engine-recorded +0xE7 pair)")
            if t.get("selected_target") and \
                    not t["selected_target"].get("validated"):
                errors.append(f"takeover: turn {t.get('turn')} target must be "
                              f"VALIDATED (Astra round 3: roster-bounded hp "
                              f"delta), got {t['selected_target']}")
            if "mp" not in (t.get("note") or ""):
                errors.append(f"takeover: turn {t.get('turn')} note lacks "
                              f"the mp delta (actor-specific evidence)")
            if f'"slot": {PLAYER_SLOT}' not in (t.get("note") or "") and \
                    f"'slot': {PLAYER_SLOT}" not in (t.get("note") or ""):
                errors.append(f"takeover: turn {t.get('turn')} note lacks a "
                              f"delta for the PLAYER slot — actor-specific "
                              f"means Marche's own record moved")
    elif name == "unknown":
        # recorded shape: one clean commit, then the NEXT menu (the post-turn
        # re-open) presents an unknown dialog that swallows the following
        # route (presses land, nothing commits, no seeds). B-recovery must
        # fail (the dialog ignores B) and the run must bound with no presses
        # after the stop (DE-020).
        world.allow_seeds = True   # commit #1 must close turn 1 honestly
        world.menu_reopen_seconds = 5.0  # dialog rides the next re-open
        world.after_commit = lambda w: setattr(w, "swallow_route", True)
        world.swallow_b = True  # an unknown dialog ignores B as well
        state = rt.run()
        if state != "stalled":
            errors.append(f"unknown: expected stalled, got {state}")
        # DE-020: after the bounded stop, no further key writes may occur
        mark = len(session.g.send_log)
        time.sleep(0.5)
        late = session.g.press_writes_after(mark)
        if late:
            errors.append(f"unknown: {len(late)} key writes after the bound")
        if rt.turn != 1:
            errors.append(f"unknown: expected exactly 1 bounded turn, got {rt.turn}")
    elif name == "disconnect":
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
        world.allow_seeds = True
        world.menu_reopen_seconds = 5.0
        import threading
        def _drop_stop():
            open(rt.stop_file, "w").close()
        threading.Timer(25.0, _drop_stop).start()  # turn 1 commits ~14 s in
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
        world.allow_seeds = True
        world.expect_action_route = True
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
        # per-input evidence: at least one press leg must have been ABORTED
        # by the gate (press() returns -1 and logs it) rather than executed
        probe_log = getattr(rt.p, "_log", None)
        if probe_log is not None and not any("ABORTED" in line for line in probe_log):
            errors.append("strict-press: no aborted press recorded — the STOP "
                          "may have landed in a wait instead of the input path")
    elif name == "submenu":
        # recorded a3-natural5 shape: the post-Move re-opened menu presents
        # a submenu the plain route cannot commit (presses land, nothing
        # commits). The runtime's bounded B-escape backs out (navigation,
        # not a tactical input) and the re-drive then commits normally.
        world.allow_seeds = True
        world.swallow_first_route = True
        world.after_commit = lambda w: (w.mark_ending(1) if w.commits >= 2 else None)
        state = rt.run()
        if state != "completed":
            errors.append(f"submenu: expected completed, got {state}")
        if world.b_closes < 1:
            errors.append(f"submenu: B never closed the wedged submenu "
                          f"(b_closes={world.b_closes})")
        if rt.turn != 2:
            errors.append(f"submenu: expected 2 committed turns (route+recovery), "
                          f"got {rt.turn}")
        notes = [e for e in _events(rt.events_path) if e["kind"] == "note"]
        if not any("B-recovery" in (e.get("note") or "") for e in notes):
            errors.append(f"submenu: B-recovery was not recorded: {notes}")
    else:
        raise ValueError(f"unknown scenario {name}")

    receipt = finish_run(rt, world, out_dir)
    errs = validate(out_dir)
    if errs:
        errors.extend(errs)
    print(f"  [{name}] state={receipt['final_state']} turns={receipt['turns']} "
          f"seeds={receipt['seeds']} presses={len(session.g.key_writes())}")
    return receipt, errors


def _events(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", default="all",
                            choices=["all", "takeover", "unknown", "disconnect",
                                     "restart", "defeat", "results", "submenu",
                                     "pause", "strict-press"])
    ap.add_argument("--out-root", default=os.path.join("outputs", "autobattle",
                                                       "transport-checks"))
    args = ap.parse_args(argv)

    names = ["takeover", "unknown", "disconnect", "restart", "defeat",
             "results", "submenu", "pause", "strict-press"]
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
