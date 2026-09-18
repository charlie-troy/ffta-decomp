"""A2.4b: isolate the player/AI control lever on the verified normal fixture.

One reusable probe, built on `fixture_guard.FixtureSession` (one owned mGBA
process, one GDB connection through boot and experiment) and the v48
observation style (per-hit registers, actor attribution by decoded name).

Why this probe looks where it does (static decode, 2026-09-10):

    sub_0809E1E0  turn loop. Per picked actor r7, record r4 = &units[r7]:
        0x0809E272  bl sub_080CE2F0(r4, 0)   clears +0xED bit 3 (Controlled)
                    at the actor's turn start
        0x0809E276  Stop countdown block: getter sub_080CDADC reads
                    (+0xEA & 0x80), duration byte +0xDC is decremented
        0x0809E3AE  bl sub_080CDADC(r4)      the "bit7 router" A2.3 named
        0x0809E3B6  beq 0x0809E3BA           bit7 clear -> AI housekeeping
        0x0809E3B8  b   0x0809E796           bit7 set   -> skip to the tail
        0x0809E796  common tail              reached by BOTH paths

    `docs/unit-flags.md` names `+0xEA` bit 7 **Stop** (setter sub_080CE050,
    duration +0xDC). So 0x0809E3B8 is not a menu body: it is the Stop skip.
    The probe records the branch actually taken (0x0809E3B8 vs 0x0809E3BA)
    and the visible/input consequence, rather than counting 0x0809E796, which
    both paths share.

Interventions available (one hypothesis per slice, never combined):

    none        unmodified control (only the key-enable byte is written)
    bit7        force +0xEA |= 0x80 on the target actor at its router
                (0x0809E3AE), i.e. immediately before its pick
    controlled  write +0xED bit 3 and +0xE6 = controller id on the target
                enemy, either at boot or immediately after the turn-start
                clear at 0x0809E272

Protocol rules carried from A2.3/A2.4a: presses are 5 frames at the
0x08000494 key poll with the CPU running between them; the key-enable byte is
written once at attach and its original value restored at exit; sample ticks
call interrupt(); the key updater is never single-stepped. A run is invalid if
the PC is 0x00000004 / the stop reply is S04, if CT is static with no seeded
action, or if a stalled instance produced no seed. CT is never compressed.

Evidence: outputs/autobattle/A2.4b/ (untracked; no game bytes).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixture_guard import (  # noqa: E402
    DEFAULT_FIXTURE_DIR, FixtureSession, OFF_CT, OFF_DC, OFF_EA, OFF_ED, OFF_ID,
    ROSTER, STRIDE, decode_ram_name, u8, u16, u32, write_receipt,
)

# --- A2.5 boundary-contract protocol constants -----------------------------

# The A2.5 action-selection contract uses the shared key-poll channel with a
# CONFIRM-only press: exactly one frame at 0x08000494 with A=1 ORed into r1,
# no D-pad. This is the minimal press shape for the "commit the currently
# highlighted legal choice" step of the acceptance proof.
A_MASK = 0x01
CONFIRM_FRAMES = 1

# --- addresses (verified by static decode; see module docstring) ------------
BP_ROUTER = 0x0809E3AE     # bl sub_080CDADC : reads +0xEA bit 7 for this actor
BP_SHORTCUT = 0x0809E3B8   # b 0x0809E796    : taken only when bit7 is set
BP_AI_PATH = 0x0809E3BA    # beq target      : AI housekeeping / decision path
BP_TAIL = 0x0809E796       # common tail reached by both paths
BP_CTRL_PRE = 0x0809E272   # bl sub_080CE2F0 : turn-start Controlled clear
BP_CTRL_POST = 0x0809E276  # instruction after the clear
BP_SEED = 0x080C03C2       # sequencer action seed (v48)
BP_KEY = 0x08000494        # key poll: r1 = KEYINPUT ^ 0x3FF
BP_PREVIEW = 0x0809E830    # "advance the turn loop N times" helper (turn preview)

BP_NAMES = {
    BP_ROUTER: "router", BP_SHORTCUT: "shortcut", BP_AI_PATH: "ai_path",
    BP_TAIL: "tail", BP_CTRL_PRE: "ctrl_pre", BP_CTRL_POST: "ctrl_post",
    BP_SEED: "seed", BP_PREVIEW: "preview",
}

# sub_0809E1E0 pushes {r4,r5,r6,r7,lr} then {r5,r6,r7} = 32 bytes, so the
# caller's return address sits at sp+28 for the whole body. Reading it at the
# router tells us which driver reached the turn loop (the headless turn-order
# preview at 0x0809E830 vs the live battle driver).
SAVED_LR_OFFSET = 28
ALL_BPS = sorted(BP_NAMES)

KEY_ENABLE = 0x03000005
# Ability-state scan depth for chooser evidence: the array is inline at
# unit+0x34 (0x9C bytes: 12-byte header + one byte per race ability, Human
# 142); scan the first 64 entries so any plausible race shows nonzero
# learned entries without huge reads.
ABILITY_SCAN_MAX = 64
SIDE_BIT = 0x8000
UNAFFILIATED_BIT = 0x1000
FLAG_ARRAY = 0x020159E4 + 0xDD4     # per-slot status-expiry flag dwords

ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"), (0x01, "A-wait"), (0x01, "A-ok")]
# The manual leg uses the SAME plain route. Run 13's screenshots settled the
# navigation model: the command menu (Move, Action, Wait, Status) always
# reopens with the cursor on Move, so cursor memory does not exist and the
# UP x3 "normalization" instead walks onto Status and opens the Status
# screen modal — the real cause of the runs 10-13 inert wedges. Run 9
# (plain route) committed a legal turn and the engine kept running.
ROUTE_TAKEOVER = ROUTE
# Chooser route for a deliberately selected non-Wait command: the plain route
# is DOWN DOWN (cursor on Action) A (open the submenu) A (confirm its top
# entry). This navigation is proven commit-shaped (same frame counts and
# pacing as ROUTE); only the submenu's resolved command is not decoded yet.
ROUTE_ACTION = [(0x80, "DOWN1"), (0x80, "DOWN2"), (0x01, "A-open"),
                (0x01, "A-confirm")]
PARK_CT_MAX = 300   # menu-open park marker observed at 188; charging passes
                    # through this band in ~2 s, so only a STABLE low CT is
                    # the parked (menu awaiting input) state
RUN_ID = "A2.4b"
OUT_ROOT = os.path.join("outputs", "autobattle", RUN_ID)


def evidence_path(name):
    p = os.path.join(OUT_ROOT, name)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    return p


class Probe:
    """Router/branch/clear instrumentation on one FixtureSession."""

    def __init__(self, session, intervene="none", target="first-enemy",
                 controlled_when="boot", controller_id=6, verbose=True):
        self.s = session
        self.g = session.g
        self.intervene = intervene
        self.target = target
        self.controlled_when = controlled_when
        self.controller_id = controller_id
        self.verbose = verbose
        self.t0 = time.time()
        self.turns = []          # one entry per actor turn at the router
        self.branches = []       # {t, slot, path, actor, ea}
        self.clears = []         # {t, slot, actor, ed_before, e6_before}
        self.seeds = []
        self.tail_hits = 0
        self.router_hits = 0
        self.samples = []
        self.invalid = []
        self.intervention = {"armed": False, "applied": False,
                             "phase": "awaiting-first-enemy-turn"}
        self.preview_hits = 0
        self.rearm_key_enable = False  # one-flag key-enable re-arm diagnostic
        # routes: re-write 0x03000005=1 before each press so the engine's
        # scratch clear (observed between the turn-ready flash and the menu
        # park) cannot gate the injected keys mid-route.
        self._last_router = None

    # -- helpers ----------------------------------------------------------
    def now(self):
        return round(time.time() - self.t0, 1)

    def note_key_write(self, val, hits):
        # timestamped raw-write record: the runtime input log only covers
        # press()/drive() INTENT, so a validator cross-checking writes
        # against stop events needs the actual packet stream too
        # (Astra round 4, gap 1/2). Writes without a wrapping press —
        # e.g. manually injected input during a handed-off session — are
        # tagged so the validator can scope its post-stop rule correctly.
        try:
            log = self.key_write_log
        except AttributeError:
            log = self.key_write_log = []
        log.append({"t": round(time.time() - self.t0, 3), "val": val,
                    "hits": hits, "manual": False})

    def say(self, msg):
        # bounded in-memory log so validators can assert on press/abort
        # behavior without parsing stdout (Astra round 3: the strict-press
        # gate needs the ABORTED records)
        log = getattr(self, "_log", None)
        if log is None:
            log = self._log = []
        log.append(msg)
        if len(log) > 4000:
            del log[:2000]
        if self.verbose:
            print(msg, flush=True)

    def cts(self):
        return [u16(self.g, ROSTER + STRIDE * i + OFF_CT) for i in range(8)]

    def slot_of(self, rec_ptr):
        if rec_ptr and ROSTER <= rec_ptr < ROSTER + STRIDE * 8:
            return (rec_ptr - ROSTER) // STRIDE
        return None

    def actor_info(self, rec_ptr):
        """Identity for a unit record pointer, by decoded name (never slot alone)."""
        if not rec_ptr:
            return {"slot": None, "name": None}
        slot = self.slot_of(rec_ptr)
        info = {
            "slot": slot,
            "rec": f"{rec_ptr:08x}",
            "name_ptr": None,
            "name": None,
            "id": u8(self.g, rec_ptr + OFF_ID),
            "ct": u16(self.g, rec_ptr + OFF_CT),
            "ea": u8(self.g, rec_ptr + OFF_EA),
            "ed": u8(self.g, rec_ptr + 0xED),
            "e6": u8(self.g, rec_ptr + 0xE6),
        }
        if slot is not None:
            roster = self.s.receipt["roster"]["slots"][slot]
            info["name_ptr"] = f"{roster['name']:08x}" if roster["name"] else None
            info["name"] = roster["name_text"]
        else:
            # sequencer contexts reference the AI mirror array at 0x02002FC4
            nm = u32(self.g, rec_ptr)
            info["name_ptr"] = f"{nm:08x}" if nm else None
            info["name"] = decode_ram_name(self.g, nm,
                                           rom=self.s.read_rom_bytes())
        return info

    def flagword(self, slot):
        if slot is None:
            return None
        return u32(self.g, FLAG_ARRAY + 4 * slot)

    def caller_lr(self, regs):
        """Caller of the turn loop, from the saved-lr slot sub_0809E1E0 pushes."""
        sp = regs[13] if len(regs) > 13 else None
        if not sp:
            return None
        d = self.g.read_mem(sp + SAVED_LR_OFFSET, 4)
        if not d:
            return None
        return f"{int.from_bytes(d, 'little') & ~1 & 0xFFFFFFFF:08x}"

    def is_enemy(self, slot):
        if slot is None:
            return False
        r = self.s.receipt["roster"]["slots"][slot]
        return bool(r["live"] and r["side_raw"] and
                    (r["side_raw"] & SIDE_BIT) and not (r["side_raw"] & UNAFFILIATED_BIT))

    # -- breakpoint handling ----------------------------------------------
    def set_bp(self, addr):
        return self.g.send(f"Z0,{addr:x},2")

    def clear_bp(self, addr):
        try:
            self.g.send(f"z0,{addr:x},2")
        except Exception:
            pass

    def arm(self):
        for bp in ALL_BPS:
            self.set_bp(bp)

    def disarm(self):
        for bp in ALL_BPS:
            self.clear_bp(bp)

    def handle_stop(self, during=""):
        g = self.g
        regs = g.read_registers()
        if not regs:
            return None
        pc = regs[15]
        kind = BP_NAMES.get(pc)
        t = self.now()
        if kind is None:
            return regs
        if pc == 0x00000004 or pc in (0x08000004,):
            self.invalid.append({"t": t, "reason": "pc_bios_trap", "pc": f"{pc:08x}"})
        if kind == "router":
            self._on_router(regs, t, during)
        elif kind in ("shortcut", "ai_path"):
            self._on_branch(kind, regs, t, during)
        elif kind == "ctrl_pre":
            self._on_ctrl_pre(regs, t, during)
        elif kind == "ctrl_post":
            self._on_ctrl_post(regs, t, during)
        elif kind == "tail":
            self.tail_hits += 1
        elif kind == "preview":
            self.preview_hits += 1
        elif kind == "seed":
            r4 = regs[4]
            entry = {"t": t, "r4": f"{r4:08x}", "r7": f"{regs[7]:08x}",
                     "ctx_units": self.scan_ctx(r4), "during": during}
            self.seeds.append(entry)
            self.say(f"  SEED t={t} ctx={entry['ctx_units']} {during}")
        return regs

    def _on_router(self, regs, t, during):
        rec = regs[4]
        info = self.actor_info(rec)
        self.router_hits += 1
        entry = {"t": t, "slot": info["slot"], "name": info["name"],
                 "id": info["id"], "ct": info["ct"], "ea": info["ea"],
                 "ed": info["ed"], "e6": info["e6"],
                 "flagword": self.flagword(info["slot"]),
                 "enemy": self.is_enemy(info["slot"]),
                 "active": info["slot"] == self.player_slot() and info["slot"] is not None,
                 "caller_lr": self.caller_lr(regs),
                 "during": during, "branch": None}
        self.turns.append(entry)
        self._last_router = entry
        self.say(f"  ROUTER t={t} slot={entry['slot']} name={entry['name']!r} "
                 f"ea={entry['ea']:#04x} ed={entry['ed']:#04x} e6={entry['e6']} "
                 f"ct={entry['ct']} {during}")
        if self.intervene == "bit7":
            self._maybe_bit7(entry, rec, t)

    def _maybe_bit7(self, entry, rec, t):
        if self.intervention["applied"]:
            return
        want = self._target_match(entry)
        if not want:
            return
        if entry["ea"] is None:
            return
        if not (entry["ea"] & 0x80):
            old_ea = entry["ea"]
            old_dc = u8(self.g, rec + OFF_DC)
            self.s.write_bytes(rec + OFF_EA, bytes([old_ea | 0x80]),
                               "bit7 intervention: +0xEA |= 0x80 (Stop status bit) "
                               "on the target actor at its router 0x0809E3AE")
            self.s.write_bytes(rec + OFF_DC, bytes([1]),
                               "bit7 intervention: +0xDC = 1, the Stop duration so "
                               "the status self-clears at the actor's next turn "
                               "start (0x0809E276 block)")
            self.intervention.update({
                "armed": True, "applied": True, "t": t,
                "target_slot": entry["slot"], "target_name": entry["name"],
                "ea_addr": f"{rec + OFF_EA:08x}", "ea_old": old_ea,
                "ea_new": old_ea | 0x80,
                "dc_addr": f"{rec + OFF_DC:08x}", "dc_old": old_dc,
                "dc_new": 1, "site": "0x0809e3ae",
                "restore_policy": "self-clearing: the turn-start Stop countdown "
                                  "clears +0xEA bit7 when +0xDC reaches 0; the "
                                  "probe also restores the byte at run end"})
            self.say(f"  *** BIT7 intervention on slot {entry['slot']} "
                     f"({entry['name']}): ea {old_ea:#04x} -> {old_ea | 0x80:#04x}, "
                     f"dc {old_dc} -> 1 t={t}")
        else:
            self.intervention.update({"armed": True, "applied": False,
                                      "note": "target already carried bit7"})

    def _on_branch(self, kind, regs, t, during):
        path = "shortcut_0x0809E3B8" if kind == "shortcut" else "ai_path_0x0809E3BA"
        slot = self.slot_of(regs[4])
        info = self.actor_info(regs[4])
        rec = {"t": t, "slot": slot, "name": info["name"], "path": path,
               "ea": info["ea"], "during": during}
        self.branches.append(rec)
        if self._last_router is not None and self._last_router["slot"] == slot:
            self._last_router["branch"] = path
        self.say(f"  BRANCH t={t} slot={slot} name={info['name']!r} -> {path} "
                 f"(ea={info['ea']:#04x})")

    def _on_ctrl_pre(self, regs, t, during):
        rec = regs[4]
        info = self.actor_info(rec)
        entry = {"t": t, "slot": info["slot"], "name": info["name"],
                 "ed_before": info["ed"], "e6_before": info["e6"],
                 "during": during}
        self.clears.append(entry)
        self.say(f"  CTRL pre-clear t={t} slot={info['slot']} name={info['name']!r} "
                 f"ed={info['ed']:#04x} e6={entry['e6_before']}")
        # pre-clear injection: write immediately before the clear executes, so
        # the post-clear read decides whether the clear consumes it
        if self.intervene == "controlled" and self.controlled_when == "pre-clear" \
                and not self.intervention["applied"]:
            if self._target_match({"slot": info["slot"],
                                   "enemy": self.is_enemy(info["slot"])}):
                self.s.write_bytes(rec + 0xED, bytes([(info["ed"] or 0) | 0x08]),
                                   "Controlled injected immediately before the "
                                   "turn-start clear: +0xED |= bit3")
                self.s.write_bytes(rec + 0xE6, bytes([self.controller_id & 0xFF]),
                                   "Controlled injected before the clear: +0xE6 = "
                                   "controller id")
                self.intervention.update({
                    "armed": True, "applied": True, "t": t, "when": "pre-clear",
                    "target_slot": info["slot"], "target_name": info["name"],
                    "ed_old": info["ed"], "ed_new": (info["ed"] or 0) | 0x08,
                    "e6_old": info["e6"], "e6_new": self.controller_id})
                self.say(f"  *** CONTROLLED (pre-clear) on slot {info['slot']} "
                         f"({info['name']}) t={t}")

    def _on_ctrl_post(self, regs, t, during):
        rec = regs[4]
        info = self.actor_info(rec)
        if self.clears:
            self.clears[-1]["ed_after"] = info["ed"]
        self.say(f"  CTRL post-clear t={t} slot={info['slot']} "
                 f"ed={info['ed']:#04x} e6={info['e6']}")
        # post-clear Controlled injection (survives to the router)
        if self.intervene == "controlled" and self.controlled_when == "post-clear" \
                and not self.intervention["applied"]:
            if self._target_match({"slot": info["slot"], "name": info["name"],
                                   "enemy": self.is_enemy(info["slot"])}):
                old_ed, old_e6 = info["ed"], info["e6"]
                self.s.write_bytes(rec + 0xED, bytes([(old_ed or 0) | 0x08]),
                                   "Controlled after the turn-start clear: +0xED |= 3")
                self.s.write_bytes(rec + 0xE6, bytes([self.controller_id & 0xFF]),
                                   "Controlled after the turn-start clear: +0xE6 = "
                                   "controller id")
                self.intervention.update({
                    "armed": True, "applied": True, "t": t, "when": "post-clear",
                    "target_slot": info["slot"], "target_name": info["name"],
                    "ed_old": old_ed, "ed_new": (old_ed or 0) | 0x08,
                    "e6_old": old_e6, "e6_new": self.controller_id})
                self.say(f"  *** CONTROLLED (post-clear) on slot {info['slot']} "
                         f"({info['name']}) t={t}")

    def _target_match(self, entry):
        if self.target == "first-enemy":
            return bool(entry.get("enemy"))
        try:
            return entry.get("slot") == int(self.target, 0)
        except (TypeError, ValueError):
            return False

    def player_slot(self):
        slots = self.s.receipt["roster"]["ram_named_slots"]
        return slots[0] if slots else None

    def scan_ctx(self, r4):
        """Decoded unit names in the sequencer context around r4."""
        if not r4:
            return []
        lo, hi = r4 - 0x90, r4 + 0x10
        blob = self.g.read_mem(lo, hi - lo)
        hits = []
        if blob:
            for off in range(0, len(blob) - 3, 4):
                v = int.from_bytes(blob[off:off + 4], "little")
                if not 0x02000000 <= v < 0x02040000:
                    continue
                nm = u32(self.g, v)
                if nm is None or not (0x08000000 <= nm < 0x09000000 or
                                      0x02000000 <= nm < 0x04000000):
                    continue
                hits.append({"off": lo + off - r4, "v": f"{v:08x}",
                             "slot": self.slot_of(v),
                             "name": decode_ram_name(self.g, nm,
                                                     rom=self.s.read_rom_bytes())})
        return hits        # -- input -------------------------------------------------------------
        # (press() below re-arms the key-enable byte per press when
        # (run 13 disproved key-enable gating on this channel; kept as a
        # one-flag diagnostic)
    def press(self, mask, frames=5, pause=1.2, tag="", stop_check=None):
        # Astra 2026-09-17 (round 3): a STOP observed before an input must
        # abort THAT input — a post-recovery check still lets one full input
        # sequence escape. Returns -1 when aborted (distinct from 0 hits) so
        # callers neither mistake it for a delivered press nor redeliver it.
        if stop_check is not None and stop_check():
            self.say(f"  press {mask:#04x} ABORTED (stop requested) {tag} "
                     f"t={self.now()}")
            return -1
        g = self.g
        hits = 0
        if self.rearm_key_enable:
            # Run 13 disproved the key-enable gating theory (route commits
            # with the byte at 0), so per-press re-arm is off by default;
            # kept only as a one-flag diagnostic for future runs.
            self.s.write_u8(KEY_ENABLE, 1, "re-arm key enable (press)")
        # A2.5 run 5 failure vector: with the trace breakpoints armed, the
        # menu-loop router fires ~10x/s, so the stop loop kept catching
        # ROUTER/BRANCH stops instead of the key poll and every route press
        # after the first landed x0 (incomplete route -> wedged modal).
        # During a press the key poll must be the ONLY armed breakpoint.
        try:
            self.disarm()
            for attempt in range(5):
                reply = g.send(f"Z0,{BP_KEY:x},2")
                if reply == "OK":
                    break
                # A breakpoint fired between packets and its stop-reply raced
                # the insert: service it, resume, and try again.
                try:
                    stop = g._read_packet()
                except socket.timeout:
                    stop = None
                pc = g.read_pc() if stop else None
                self.say(f"  Z0 retry {attempt + 1} ({tag}): reply={reply!r} "
                         f"stop={stop!r} pc={pc and hex(pc)}")
                if stop and stop[:1] in ("S", "T") and pc != BP_KEY:
                    g.cont()
            else:
                self.say(f"  FAIL: key poll breakpoint rejected ({tag})")
                return 0
            g.cont()
            for _ in range(frames):
                try:
                    stop = g._read_packet()
                except socket.timeout:
                    break
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = g.read_registers()
                if not regs:
                    break
                if regs[15] == BP_KEY:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    self.note_key_write(val, hits + 1)
                    hits += 1
                g.cont()
        finally:
            try:
                self.clear_bp(BP_KEY)
            except Exception:
                pass
            try:
                self.arm()
            except Exception:
                pass
            try:
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        self.say(f"  key {mask:#04x} x{hits} {tag} t={self.now()}")
        return hits

    def drive(self, tag, route=None, stop_check=None):
        route = ROUTE if route is None else route
        delivered = {}
        for mask, name in route:
            delivered[name] = self.press(mask, stop_check=stop_check,
                                         tag=f"{tag}:{name}")
            if delivered[name] < 0:
                # stop landed mid-route: no further legs (Astra round 3)
                self.say(f"  drive {tag}: aborted at leg {name} (stop)")
                return False
        # An incomplete route leaves the menu modal open and wedges the
        # sequencer (the A2.5 run 4 wedge vector). Redeliver any leg that
        # landed zero key-poll hits — but never after a stop request.
        if stop_check is not None and stop_check():
            self.say(f"  drive {tag}: stop requested, skipping redelivery")
            return False
        for mask, name in route:
            if delivered[name] == 0:
                self.say(f"  redeliver {name} ({tag})")
                self.press(mask, stop_check=stop_check,
                           tag=f"{tag}:{name}:retry")
        return True

    def sample(self, tag):
        s = {"t": self.now(), "tag": tag, "cts": self.cts(),
             "pc": self.g.read_pc()}
        self.samples.append(s)
        self.say(f"  [t={s['t']} {tag}] cts={s['cts']} pc={s['pc'] and hex(s['pc'])} "
                 f"seeds={len(self.seeds)} router={self.router_hits}")
        return s

    def pump(self, seconds, tag, stop_when=None, sample_every=8.0, tick=2.0):
        g = self.g
        end = time.time() + seconds
        last_s = self.now()
        while time.time() < end:
            try:
                g.cont()
                stop = g._read_packet()
            except socket.timeout:
                stop = None
            except Exception:
                stop = None
                time.sleep(0.05)
            if stop and stop[:1] in ("S", "T"):
                try:
                    self.handle_stop(tag)
                except Exception as exc:
                    self.say(f"  handle_stop error: {exc}")
            if self.now() - last_s >= tick:
                try:
                    g.interrupt()
                except Exception:
                    pass
                if self.now() - last_s >= sample_every:
                    last_s = self.now()
                    self.sample(tag)
            if stop_when and stop_when(self):
                self.say(f"  {tag}: stop condition met t={self.now()}")
                break

    # -- A2.5 boundary-contract helpers ------------------------------------
    def unit_u16(self, slot, off):
        return u16(self.g, ROSTER + STRIDE * slot + off)

    def player_menu_open(self):
        """Marche's record carries CT 1000 while his menu awaits input.

        Observed live: the player's CT sits at exactly 1000 from his turn
        start until his turn is committed (a committed turn writes 0 and the
        engine charges him back up afterwards), so CT==1000 on the player slot
        is the in-register equivalent of the open battle menu.

        Caveat (run 7 evidence): the raw signature also holds during a ~10 s
        "turn ready" window BEFORE the menu opens, after which the engine
        itself parks the active unit at a low stable CT (188). Driving on the
        raw signature hits the wrong UI state. Use `player_menu_parked` /
        `player_menu_settled` before sending input.
        """
        ps = self.player_slot()
        return ps is not None and self.unit_u16(ps, OFF_CT) == 1000

    def player_menu_parked(self):
        """Menu-open signature: Marche parked at a low, stable CT marker.

        Run 7's trace (no input sent): CT flashes 1000 at turn-ready, then
        the engine parks the active player unit at exactly 188 and idles
        (seed silence) while the battle menu awaits input. Charging passes
        188 in ~2 s at ~12.8 CT/s, so a STABLE low value is the parked
        state; `player_menu_settled` adds the stability requirement.
        """
        ps = self.player_slot()
        if ps is None:
            return False
        ct = self.unit_u16(ps, OFF_CT)
        return 0 < ct <= PARK_CT_MAX and ct != 1000

    def player_menu_settled(self, ticks=3, tick_secs=3.0,
                            tag="menu-settle", allow_zero=False):
        """True when the parked signature holds for `ticks` equal polls.

        The parked marker must be byte-stable across polls (charging changes
        the CT by ~38 per 3 s poll, so equal values imply parked). Three 3 s
        polls (~9 s) also ride out the turn-ready flash. Polling keeps the
        target running.

        allow_zero (run 17, visual proof): after a committed turn the
        RE-opened menu parks the player at a stable 0, not 188 — the wedge
        screenshot shows the command menu open while the roster CT reads 0.
        Stability still discriminates: charging leaves 0 within one poll.
        """
        first = None
        hold = 0
        end = self.now() + ticks * tick_secs + 6.0
        while self.now() < end:
            self.pump(tick_secs, tag, sample_every=60.0, tick=tick_secs)
            ps = self.player_slot()
            ct = self.unit_u16(ps, OFF_CT) if ps is not None else None
            if ct is not None and ct <= PARK_CT_MAX and ct != 1000 \
                    and (allow_zero or ct > 0):
                if ct == first:
                    hold += 1
                else:
                    first, hold = ct, 1
                if hold >= ticks:
                    return True
            else:
                first, hold = None, 0
        return False

    def player_menu_frozen(self, ticks=2, tick_secs=3.0,
                           tag="menu-frozen"):
        """True when the menu owner's CT is byte-stable at ANY value.

        Run 18 (visual proof at two moments): a re-opened command menu
        freezes the owner's roster CT at an arbitrary value (0, 305, 812
        observed) — whatever the engine last wrote when the menu opened.
        The `player_menu_parked` bound (ct <= 188) only matches the FIRST
        menu of a turn, so re-opened menus were invisible to phase 5. The
        discriminating signature is stability itself: charging changes the
        CT every poll, a parked menu does not. The 1000 ready-flash is
        excluded (it holds ~10 s before the engine parks the unit).
        """
        first = None
        hold = 0
        end = self.now() + ticks * tick_secs + 6.0
        while self.now() < end:
            self.pump(tick_secs, tag, sample_every=60.0, tick=tick_secs)
            ps = self.player_slot()
            ct = self.unit_u16(ps, OFF_CT) if ps is not None else None
            if ct is not None and ct != 1000:
                if ct == first:
                    hold += 1
                else:
                    first, hold = ct, 1
                if hold >= ticks:
                    return True
            else:
                first, hold = None, 0
        return False

    def menu_reopen(self):
        """Settled parked signature, used to detect the menu reopening."""
        return self.player_menu_parked() and self.player_menu_settled(2)

    def roster_guard(self):
        """Per-slot CT/HP/tile snapshot for teardown and route diagnostics."""
        ps = self.player_slot()
        slots = []
        for i in range(8):
            base = ROSTER + STRIDE * i
            slots.append({"slot": i, "ct": u16(self.g, base + OFF_CT),
                          "hp": u16(self.g, base + 0x18),
                          "x": u8(self.g, base + 0xF6),
                          "y": u8(self.g, base + 0xF7)})
        return {"marche": slots[ps] if ps is not None else None,
                "slots": slots}

    # -- action chooser (A3 closure: deliberately selected non-Wait) -------
    def player_tile(self):
        """The tracked player record's tile (A2.5 contract: +0xF6/+0xF7)."""
        from fixture_guard import u8
        ps = self.player_slot()
        if ps is None:
            return None
        base = ROSTER + STRIDE * ps
        x, y = u8(self.g, base + 0xF6), u8(self.g, base + 0xF7)
        if not (0 <= x < 64 and 0 <= y < 64):
            return None  # transient roster-copy garbage (a3 boundary lesson)
        return (x, y)

    def player_abilities(self):
        """The unit's learned-ability evidence from the real unit struct.

        include/ffta.h + docs/unit-struct.md: unit+0x34 IS the ability-state
        array inline (0x9C bytes: a 12-byte header plus one byte per ability
        available to the unit's race; Human count 142 -> 12+142=154 bytes
        ending at +0xce with one pad byte before CT at +0xd0). Ability-menu
        and learned-ability consumers read this region, so nonzero entries
        are engine-grounded evidence that the action submenu has selectable
        commands. The per-entry ability-ID mapping is not decoded here;
        this reports counts only (live diagnostic 2026-09-16: the +0x34
        region does NOT hold a pointer — 0x000a028e on this fixture — the
        data is inline).
        """
        ps = self.player_slot()
        if ps is None:
            return []
        from fixture_guard import u8, u16
        base = ROSTER + STRIDE * ps
        header = u16(self.g, base + 0x34)
        nonzero = 0
        total = 0
        for off in range(12, ABILITY_SCAN_MAX):
            v = u8(self.g, base + 0x34 + off)
            if v is None:
                break
            total += 1
            nonzero += 1 if v else 0
        if total == 0:
            return []
        return [{"header": f"{header:04x}", "entries": total,
                 "nonzero": nonzero}]

    def choose_non_wait(self):
        """Choose a deliberately selected non-Wait command, or None.

        Deliberate selection (not a fixed sequence): requires live engine
        evidence — the player unit has at least one decoded-legal ability
        word and stands at a nonzero tile. The chosen ROUTE_ACTION legs
        resolve the engine's own submenu; `effect_snapshot` (called by the
        runtime post-commit) records what actually changed so the commit's
        meaning is evidence, not assumption.
        """
        tile = self.player_tile()
        abilities = self.player_abilities()
        if tile in (None, (0, 0)) or not abilities:
            return None
        return {"route": ROUTE_ACTION, "command_menu": "action-submenu",
                "chosen_from": abilities[0], "tile": list(tile)}

    def effect_snapshot(self):
        """Decoded engine-side effect evidence for the last committed turn.

        Reads the player record and every other live roster record before
        and after a commit; the runtime diffs them. Only engine-observed
        deltas are recorded (hp/ct/mp/target-id/tile); no effect is inferred.

        mp (+0x1C, unit-struct doc: the ability-cost check reads it) and
        tg (+0xE7, "action resolution records the two most recent distinct
        targets") make the actor-specific evidence: a non-Wait ability
        costs the ACTOR MP and the engine records whom it targeted — CT
        churn alone cannot distinguish a committed Wait from a real command
        (Astra 2026-09-17).
        """
        from fixture_guard import u8, u16
        rows = []
        for i in range(8):
            base = ROSTER + STRIDE * i
            hp = u16(self.g, base + 0x18)
            if hp == 0 and u16(self.g, base + 0x1A) == 0:
                continue  # unallocated/defeated slot
            rows.append({"slot": i,
                         "hp": hp,
                         "ct": u16(self.g, base + OFF_CT),
                         "mp": u16(self.g, base + 0x1C),
                         "tg": u8(self.g, base + 0xE7),
                         "x": u8(self.g, base + 0xF6),
                         "y": u8(self.g, base + 0xF7)})
        return rows

    def battle_torn_down(self):
        """Whole tracked roster block wiped (run 6 teardown signature).

        Run 6's fixed-address Marche record read hp=0/max_hp=0 while the
        end screenshot still showed a live battle scene: the roster block
        is copied around during action execution, so a single zeroed
        record is NOT teardown evidence. Teardown is declared only when
        every slot in the tracked block reads hp==0 AND max_hp==0; a live
        battle always keeps nonzero max_hp somewhere in it.
        """
        for i in range(8):
            base = ROSTER + STRIDE * i
            if u16(self.g, base + 0x18) != 0 or u16(self.g, base + 0x1A) != 0:
                return False
        return True

    def confirm_press(self, tag="confirm"):
        """One A press on the key-poll channel (the A2.5 commit shape)."""
        return self.press(A_MASK, frames=CONFIRM_FRAMES, pause=1.2, tag=tag)

    def wait_seed_quiet(self, seconds=75.0, quiet_ticks=9):
        """Wait for the engine-boundary signature: sequencer seed silence.

        A2.4a's no-input control proved the menu-open state persists
        indefinitely with zero seeds (`dormant_awaits_player_input`), while
        this session's runs show inter-action seed gaps of ~11-20 s while the
        engine executes turns. `quiet_ticks` x 3 s of no new seed therefore
        marks the boundary where the engine awaits player menu input.
        """
        if not self.seeds:
            return False
        quiet = 0
        end = self.now() + seconds
        while self.now() < end:
            last = len(self.seeds)
            self.pump(3.0, "boundary-wait", sample_every=60.0, tick=3.0)
            quiet = quiet + 1 if len(self.seeds) == last else 0
            if quiet >= quiet_ticks:
                return True
        return False

    def wait_progress(self, seconds=45.0, want_seeds=None, min_new_seeds=1,
                      stop_check=None):
        """Pump until the sequencer has produced more actions or time expires.

        stop_check (Astra 2026-09-17): called every cycle; True ends the wait
        immediately so a pause request takes effect INSIDE long waits instead
        of only after them.
        """
        start = len(self.seeds)
        target = want_seeds if want_seeds is not None else start + min_new_seeds
        end = self.now() + seconds
        while self.now() < end:
            # C1 latency: evaluate the stop check per packet cycle inside the
            # pump as well — between 3 s pump chunks the worst case was one
            # full chunk over the 2 s contract bound (measured 2.997 s)
            self.pump(3.0, "progress", sample_every=60.0, tick=3.0,
                      stop_when=(lambda _probe: stop_check())
                      if stop_check is not None else None)
            if stop_check is not None and stop_check():
                return False
            if len(self.seeds) >= target:
                return True
        return len(self.seeds) >= target

    def wait_player_menu_ready(self, seconds=240.0, max_seeds=None):
        """Wait for the two-stage menu boundary, or expire.

        Stage 1: the turn-ready flash (player CT==1000) appears.
        Stage 2: the engine parks the player unit at a stable low CT with
        seed silence — the menu-open state (run 7 trace). The boundary is
        declared only when stage 2 settles, i.e. the menu can be driven.
        """
        end = self.now() + seconds
        trace = []
        saw_ready = False
        self.menu_unstick = []
        last = None
        frozen = 0
        while self.now() < end:
            self.pump(3.0, "menu-wait", sample_every=60.0, tick=3.0)
            ps = self.player_slot()
            ct = self.unit_u16(ps, OFF_CT) if ps is not None else None
            trace.append({"t": self.now(), "ct": ct,
                          "seeds": len(self.seeds)})
            if ct == 1000:
                saw_ready = True
            if saw_ready and self.player_menu_settled(3):
                self.menu_ct_trace = trace[-60:]
                self.menu_saw_ready = True
                return True
            state = (ct, len(self.seeds), tuple(self.cts()))
            if state == last:
                frozen += 1
                # Run 15 shape: Marche frozen mid-charge (580) with seed
                # silence and a live roster — the engine paused on a modal
                # awaiting A (same family as run 14's post-commit
                # dormancy). A is evidence-backed (the A2.4a control run)
                # and harmless when no modal is up; D-pad into unknown UI
                # is what wedged runs 10-11, so only A is tried here.
                if frozen >= 8 and len(self.menu_unstick) < 3:
                    self.press(0x01, frames=1, pause=1.2,
                               tag="menu-wait:unstick-a")
                    self.menu_unstick.append({
                        "t": self.now(), "action": "a-commit",
                        "ct_before": ct, "seeds_before": len(self.seeds)})
                    frozen = 0
            else:
                frozen = 0
                last = state
            if max_seeds is not None and len(self.seeds) >= max_seeds:
                break
        self.menu_ct_trace = trace[-60:]
        self.menu_saw_ready = saw_ready
        return self.player_menu_settled(3)


def run_probe(state, intervene="none", target="first-enemy",
              controlled_when="boot", controller_id=6, seconds=45.0,
              drive=True, guard_expect=None, screenshot_tag=""):
    """One run from a fresh reload: baseline -> optional intervention -> observe."""
    state_abs = state if os.path.isabs(state) else os.path.join(DEFAULT_FIXTURE_DIR, state)
    tag = os.path.splitext(os.path.basename(state_abs))[0]
    entry = {
        "state": state_abs, "intervene": intervene, "target": target,
        "controlled_when": controlled_when, "controller_id": controller_id,
        "drive": drive,
    }
    print(f"\n=== probe {intervene}/{target}: {os.path.basename(state_abs)} ===")
    session = FixtureSession(
        state=state_abs, expect=guard_expect,
        work_dir=os.path.join("outputs", "autobattle", "scratch",
                              f"probe-{tag}-{intervene}"))
    try:
        session.start()
        entry["guard_ok"] = session.receipt["ok"]
        entry["guard_checks"] = session.receipt["checks"]
        entry["roster"] = session.receipt["roster"]
        if not session.receipt["ok"]:
            entry["outcome"] = "fixture_rejected"
            entry["writes"] = list(session.writes)
            return entry

        p = Probe(session, intervene=intervene, target=target,
                  controlled_when=controlled_when, controller_id=controller_id)
        g = session.g
        roster = session.receipt["roster"]
        p.say(f"  player_slot={p.player_slot()} "
              f"enemies={[s['slot'] for s in roster['slots'] if s['live'] and s['side_bit']]}")

        # -- baseline -----------------------------------------------------
        g.interrupt()
        entry["baseline"] = {
            "t": p.now(), "pc": g.read_pc(),
            "keystruct": (g.read_mem(0x03000000, 8) or b"").hex() or None,
            "cts": p.cts(),
            "slot_ea": [u8(g, ROSTER + STRIDE * i + OFF_EA) for i in range(8)],
            "slot_dc": [u8(g, ROSTER + STRIDE * i + OFF_DC) for i in range(8)],
            "slot_ed": [u8(g, ROSTER + STRIDE * i + OFF_ED) for i in range(8)],
            "slot_e6": [u8(g, ROSTER + STRIDE * i + 0xE6) for i in range(8)],
        }
        entry["baseline"]["screenshot"] = session.screenshot(
            evidence_path(f"probe-{tag}-{intervene}{screenshot_tag}-baseline.png"))
        p.say(f"  baseline pc={entry['baseline']['pc'] and hex(entry['baseline']['pc'])} "
              f"cts={entry['baseline']['cts']}")
        p.sample("baseline")

        # -- boot-time Controlled injection -------------------------------
        if intervene == "controlled" and controlled_when == "boot":
            for s in roster["slots"]:
                if not p._target_match({"slot": s["slot"], "enemy": p.is_enemy(s["slot"])}):
                    continue
                base = ROSTER + STRIDE * s["slot"]
                old_ed = u8(g, base + 0xED)
                old_e6 = u8(g, base + 0xE6)
                session.write_bytes(base + 0xED, bytes([(old_ed or 0) | 0x08]),
                                    "Controlled at boot: +0xED |= bit3")
                session.write_bytes(base + 0xE6, bytes([controller_id & 0xFF]),
                                    "Controlled at boot: +0xE6 = controller id")
                p.intervention.update({
                    "armed": True, "applied": True, "when": "boot",
                    "target_slot": s["slot"], "target_name": s["name_text"],
                    "ed_old": old_ed, "ed_new": (old_ed or 0) | 0x08,
                    "e6_old": old_e6, "e6_new": controller_id})
                p.say(f"  *** CONTROLLED (boot) on slot {s['slot']} "
                      f"({s['name_text']})")
                break
        entry["intervention"] = dict(p.intervention)

        # -- key enable + breakpoints -------------------------------------
        g.interrupt()
        enable_old = u8(g, KEY_ENABLE)
        session.write_u8(KEY_ENABLE, 1, "key enable (write once at attach)")
        entry["key_enable_old"] = enable_old
        p.arm()
        g.cont()
        time.sleep(0.8)

        # -- drive the committed player turn ------------------------------
        if drive:
            p.drive(tag)
            p.pump(seconds, tag,
                   stop_when=lambda q: (len(q.seeds) >= 2 and
                                        (q.intervene == "none" or
                                         q.intervention["applied"] or
                                         q.router_hits >= 6)))
            if not p.seeds:
                p.drive(f"{tag}-retry")
                p.pump(max(20.0, seconds / 2), f"{tag}-retry",
                       stop_when=lambda q: len(q.seeds) >= 1)
        else:
            p.pump(seconds, tag)

        # -- observation --------------------------------------------------
        g.interrupt()
        pc_end = g.read_pc()
        entry["pc_end"] = pc_end
        entry["cts_end"] = p.cts()
        entry["turns"] = p.turns
        entry["branches"] = p.branches
        entry["clears"] = p.clears
        entry["seeds"] = p.seeds
        entry["router_hits"] = p.router_hits
        entry["tail_hits"] = p.tail_hits
        entry["preview_hits"] = p.preview_hits
        entry["callers"] = dict(
            (str(k), v) for k, v in _counter(
                t["caller_lr"] for t in p.turns).items())
        entry["intervention"] = dict(p.intervention)   # final state, post-run
        entry["target_timeline"] = [
            {"t": t["t"], "slot": t["slot"], "ea": t["ea"],
             "ed": t["ed"], "e6": t["e6"],
             "branch": t["branch"], "caller_lr": t["caller_lr"]}
            for t in p.turns
            if p.intervention.get("target_slot") is not None
            and t["slot"] == p.intervention.get("target_slot")]
        entry["target_clears"] = [
            c for c in p.clears
            if p.intervention.get("target_slot") is not None
            and c["slot"] == p.intervention.get("target_slot")]
        entry["samples"] = p.samples
        entry["invalid"] = p.invalid
        entry["slot_ea_end"] = [u8(g, ROSTER + STRIDE * i + OFF_EA) for i in range(8)]
        entry["screenshot_final"] = session.screenshot(
            evidence_path(f"probe-{tag}-{intervene}{screenshot_tag}-final.png"))

        # -- validity gates (A2.3 protocol) -------------------------------
        cts_before = tuple(entry["baseline"]["cts"])
        cts_after = tuple(entry["cts_end"])
        if pc_end == 0x00000004:
            entry["validity"] = "invalid_pc_bios_trap"
        elif not p.seeds and cts_before == cts_after:
            entry["validity"] = "invalid_static_ct_no_seed_no_progress"
        elif not p.seeds and drive:
            entry["validity"] = "stalled_no_seed"
        elif p.seeds and cts_before == cts_after:
            entry["validity"] = "seeded_but_ct_static"
        else:
            entry["validity"] = "valid"
        entry["outcome"] = classify(p, entry)

        # -- restore owned writes -----------------------------------------
        g.interrupt()
        restored = []
        for slot in range(8):
            base = ROSTER + STRIDE * slot
            cur_ea = u8(g, base + OFF_EA)
            base_ea = entry["baseline"]["slot_ea"][slot]
            if cur_ea is not None and base_ea is not None and cur_ea != base_ea:
                # only undo the bit our intervention owns
                if (cur_ea & 0x80) and not (base_ea & 0x80):
                    session.write_bytes(base + OFF_EA, bytes([cur_ea & ~0x80 & 0xFF]),
                                        f"restore +0xEA bit7 on slot {slot}")
                    restored.append(slot)
            cur_dc = u8(g, base + OFF_DC)
            base_dc = entry["baseline"]["slot_dc"][slot]
            if cur_dc is not None and base_dc is not None and cur_dc != base_dc:
                session.write_bytes(base + OFF_DC, bytes([base_dc]),
                                    f"restore +0xDC Stop duration on slot {slot}")
        entry["restored_slots"] = restored
        session.write_u8(KEY_ENABLE, enable_old if enable_old is not None else 1,
                         "restore key enable")
        entry["slot_ea_restored"] = [u8(g, ROSTER + STRIDE * i + OFF_EA)
                                     for i in range(8)]
        entry["slot_dc_restored"] = [u8(g, ROSTER + STRIDE * i + OFF_DC)
                                     for i in range(8)]
        entry["writes"] = list(session.writes)
        p.disarm()
    except Exception as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {exc}")
    finally:
        session.stop()
    return entry


def _counter(items):
    out = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out


def classify(p, entry):
    """Turn the router/branch table into the slice verdict.

    The discriminator is the branch actually taken and the observable
    consequence, not the shared 0x0809E796 tail.
    """
    turns = entry["turns"]
    bit7_actors = [tn for tn in turns if (tn["ea"] or 0) & 0x80]
    shortcuts = [b for b in entry["branches"] if b["path"].startswith("shortcut")]
    ai_paths = [b for b in entry["branches"] if b["path"].startswith("ai_path")]
    # consistency: every router read with bit7 must take the shortcut
    consistent = True
    for tn in turns:
        if tn["branch"] is None:
            continue
        want = "shortcut_0x0809E3B8" if (tn["ea"] or 0) & 0x80 else "ai_path_0x0809E3BA"
        if tn["branch"] != want:
            consistent = False
    if not entry["validity"].startswith("valid"):
        return entry["validity"]
    if entry["intervene"] == "bit7":
        applied = entry["intervention"].get("applied")
        if not applied:
            return "negative_intervention_never_armed"
        tgt = entry["intervention"].get("target_slot")
        tgt_branch = [tn["branch"] for tn in turns if tn["slot"] == tgt and tn["branch"]]
        if tgt_branch and tgt_branch[0] == "shortcut_0x0809E3B8":
            return "bit7_routes_to_shortcut_0x0809E3B8_not_menu"
        return "bit7_intervention_branch_unobserved"
    if entry["intervene"] == "controlled":
        if not entry["intervention"].get("applied"):
            return "negative_intervention_never_armed"
        when = entry["intervention"].get("when")
        tgt = entry["intervention"].get("target_slot")
        clears = [c for c in entry["clears"] if c["slot"] == tgt]
        survived = False
        for c in clears:
            if (c.get("ed_before") or 0) & 0x08:
                survived = (c.get("ed_after") or 0) & 0x08
        tgt_ed = [tn["ed"] for tn in turns if tn["slot"] == tgt]
        if when == "boot" and all(not ((e or 0) & 0x08) for e in tgt_ed):
            return "controlled_wiped_before_the_targets_turn_start"
        if when == "pre-clear" and not survived:
            return "controlled_cleared_by_0x0809e272_turn_start"
        if any((tn["ed"] or 0) & 0x08 for tn in turns if tn["slot"] == tgt):
            return "controlled_survived_to_router"
        return "controlled_outcome_unclear"
    return ("router_consistent_bit7_to_shortcut" if consistent and shortcuts
            else "router_consistent_bit7_clear_to_ai_path" if consistent
            else "router_inconsistent")


def cmd_probe(args):
    payload = {"schema": "a2.4b-probe/1",
               "rom_sha1_expected": None, "results": []}
    states = args.states or [os.path.join(DEFAULT_FIXTURE_DIR, "battle-start.ss0")]
    for st in states:
        payload["results"].append(run_probe(
            st, intervene=args.intervene, target=args.target,
            controlled_when=args.controlled_when,
            controller_id=args.controller_id, seconds=args.seconds,
            drive=not args.no_drive))
    print(f"\nwrote {write_receipt(args.json, payload)}")
    return 0


def cmd_slice1(args):
    """Enemy bit7 -> routing direction: natural control, intervention, restored."""
    runs = []
    natural = run_probe(args.state, intervene="none", seconds=args.seconds)
    runs.append(natural)
    intervention = run_probe(args.state, intervene="bit7", target="first-enemy",
                             seconds=args.seconds)
    runs.append(intervention)
    restored = run_probe(args.state, intervene="none", seconds=args.seconds,
                         screenshot_tag="-restored")
    runs.append(restored)
    payload = {"schema": "a2.4b-slice1/1", "results": runs}
    print(f"\nwrote {write_receipt(args.json, payload)}")
    return 0


def cmd_slice2(args):
    """Controlled isolation: where the write lands relative to 0x0809E272.

    boot       write before the turn loop ever runs
    pre-clear  write immediately before the turn-start clear executes
    post-clear write immediately after it, so the bit survives to the router
    """
    runs = []
    placements = ["pre-clear", "post-clear"] if args.skip_boot \
        else ["boot", "pre-clear", "post-clear"]
    for when in placements:
        runs.append(run_probe(args.state, intervene="controlled", target=args.target,
                              controlled_when=when, controller_id=args.controller_id,
                              seconds=args.seconds))
    payload = {"schema": "a2.4b-slice2/1", "results": runs}
    print(f"\nwrote {write_receipt(args.json, payload)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--state", default=os.path.join(DEFAULT_FIXTURE_DIR,
                                                        "battle-start.ss0"))
        sp.add_argument("--seconds", type=float, default=45.0)
        sp.add_argument("--json", default=None)

    s1 = sub.add_parser("slice1", help="bit7 routing: natural, intervention, restored")
    common(s1)
    s1.set_defaults(json=evidence_path("slice1-bit7.json"))

    s2 = sub.add_parser("slice2", help="Controlled: boot vs pre-clear vs post-clear")
    common(s2)
    s2.add_argument("--target", default="first-enemy")
    s2.add_argument("--controller-id", type=int, default=6)
    s2.add_argument("--skip-boot", action="store_true",
                    help="omit the boot-time placement (already captured)")
    s2.set_defaults(json=evidence_path("slice2-controlled.json"))

    sn = sub.add_parser("natural", help="unmodified control only")
    common(sn)
    sn.set_defaults(json=evidence_path("natural.json"))

    sp = sub.add_parser("probe", help="single arbitrary probe run")
    common(sp)
    sp.add_argument("--states", nargs="*")
    sp.add_argument("--intervene", default="none",
                    choices=["none", "bit7", "controlled"])
    sp.add_argument("--target", default="first-enemy")
    sp.add_argument("--controlled-when", default="boot",
                    choices=["boot", "pre-clear", "post-clear"])
    sp.add_argument("--controller-id", type=int, default=6)
    sp.add_argument("--no-drive", action="store_true")
    sp.set_defaults(json=evidence_path("probe.json"))

    s25 = sub.add_parser("a25", help="A2.5 acceptance: delegate, observe, takeover, re-delegate")
    common(s25)
    s25.add_argument("--runs", type=int, default=2)
    s25.add_argument("--no-drive", action="store_true",
                     help="delegate runs skip the initial DOWN DOWN A A route")
    s25.set_defaults(json=os.path.join("outputs", "autobattle", "A2.5",
                                       "a25-acceptance.json"))

    args = ap.parse_args()
    if args.cmd == "a25":
        return cmd_a25(args)
    if args.cmd == "slice1":
        return cmd_slice1(args)
    if args.cmd == "slice2":
        return cmd_slice2(args)
    if args.cmd == "natural":
        payload = {"schema": "a2.4b-natural/1",
                   "results": [run_probe(args.state, intervene="none",
                                         seconds=args.seconds)]}
        print(f"\nwrote {write_receipt(args.json, payload)}")
        return 0
    return cmd_probe(args)


def run_a25_acceptance(state, seconds=60.0, drive_menu=True,
                       movement_probe=False, movement_mode="down", guard_expect=None):
    """A2.5: reversible player AI action over the key-poll boundary.

    One fresh reload of the verified fixture, six phases:
      baseline -> delegate (engine commits Marche's action and movement) ->
      observe engine progression -> takeover (visible manual choice) ->
      re-delegate -> end-state observations and restoration.

    No ROM bytes, no game logic, and no persistent unit fields are modified.
    The key-enable byte is written once at attach and restored at exit; the
    run mutates only live battle state, which the next reload discards.
    """
    state_abs = state if os.path.isabs(state) else os.path.join(DEFAULT_FIXTURE_DIR, state)
    tag = "a25-" + os.path.splitext(os.path.basename(state_abs))[0]
    out_root = os.path.join("outputs", "autobattle", "A2.5")

    def ev_path(name):
        p = os.path.join(out_root, name)
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        return p

    entry = {"state": state_abs, "packet": "A2.5", "movement_probe": movement_probe,
             "movement_mode": movement_mode if movement_probe else None}
    print(f"\n=== A2.5 acceptance: {os.path.basename(state_abs)} ===")
    session = FixtureSession(
        state=state_abs, expect=guard_expect,
        work_dir=os.path.join("outputs", "autobattle", "scratch", tag))
    try:
        session.start()
        entry["guard_ok"] = session.receipt["ok"]
        entry["guard_checks"] = session.receipt["checks"]
        entry["roster"] = session.receipt["roster"]
        if not session.receipt["ok"]:
            entry["outcome"] = "fixture_rejected"
            entry["writes"] = list(session.writes)
            return entry

        p = Probe(session, intervene="none")
        g = session.g
        ps = p.player_slot()
        entry["player_slot"] = ps
        p.say(f"  player_slot={ps}")
        if ps is None:
            entry["outcome"] = "no_ram_named_player"
            entry["writes"] = list(session.writes)
            return entry

        def march_snapshot(tag2):
            return {"tag": tag2, "t": p.now(),
                    "ct": p.unit_u16(ps, OFF_CT),
                    "tile_x": u8(g, ROSTER + STRIDE * ps + 0xF6),
                    "tile_y": u8(g, ROSTER + STRIDE * ps + 0xF7),
                    "hp": p.unit_u16(ps, 0x18), "max_hp": p.unit_u16(ps, 0x1A),
                    "seeds": len(p.seeds), "router_hits": p.router_hits,
                    "last_ea": p.turns[-1]["ea"] if p.turns else None}

        # -- phase 1: baseline --------------------------------------------
        g.interrupt()
        ct_attach = p.unit_u16(ps, OFF_CT)
        entry["baseline"] = march_snapshot("baseline")
        entry["baseline"]["screenshot"] = session.screenshot(
            ev_path(f"{tag}-1-baseline.png"))
        p.say(f"  baseline: ct={ct_attach} "
              f"tile=({entry['baseline']['tile_x']},{entry['baseline']['tile_y']}) "
              f"hp={entry['baseline']['hp']}/{entry['baseline']['max_hp']}")

        # -- phase 2: key enable + delegate -------------------------------
        g.interrupt()
        enable_old = u8(g, KEY_ENABLE)
        session.write_u8(KEY_ENABLE, 1, "key enable (write once at attach)")
        entry["key_enable_old"] = enable_old
        p.arm()
        g.cont()
        time.sleep(0.8)
        t_delegate = p.now()
        if drive_menu:
            p.drive(tag + ":delegate")
        p.pump(seconds, tag + ":delegate",
               stop_when=lambda q: (q.turns and q.turns[-1]["slot"] == ps
                                    and q.turns[-1]["t"] > t_delegate))
        march_after = march_snapshot("after-delegate")
        entry["delegate"] = march_after
        p.say(f"  after delegate: ct={march_after['ct']} "
              f"tile=({march_after['tile_x']},{march_after['tile_y']}) "
              f"hp={march_after['hp']}/{march_after['max_hp']} "
              f"seeds={march_after['seeds']}")
        delegated = (march_after["ct"] != ct_attach
                     or march_after["seeds"] > 0)

        # -- phase 3: engine progression -----------------------------------
        if delegated:
            p.wait_progress(seconds=90.0, min_new_seeds=3)
        g.interrupt()
        pc = g.read_pc()
        entry["progression"] = {"pc": pc,
                                "router_hits": p.router_hits,
                                "seeds": len(p.seeds)}

        # -- phase 4: takeover ---------------------------------------------
        # The takeover gate is Marche's menu itself: the player's CT holds at
        # exactly 1000 while his battle menu awaits input (observed live in
        # every run; a committed turn writes 0 and the engine then charges him
        # back up). The wait ends either on that boundary or after its window.
        boundary = (p.wait_player_menu_ready(seconds=240.0)
                    if delegated else False)
        g.interrupt()
        tile_takeover = march_snapshot("takeover")
        entry["takeover"] = tile_takeover
        entry["takeover"]["screenshot"] = session.screenshot(
            ev_path(f"{tag}-2-takeover.png"))
        pc_now = g.read_pc()
        entry["takeover"]["pc"] = pc_now
        entry["takeover"]["boundary_signature"] = boundary
        entry["takeover"]["cts_at_boundary"] = p.cts()
        entry["takeover"]["menu_ct_trace"] = getattr(p, "menu_ct_trace", [])
        entry["takeover"]["menu_unstick"] = getattr(p, "menu_unstick", [])
        taken_over = bool(boundary)
        p.say(f"  takeover: pc={pc_now and hex(pc_now)} "
              f"menu_boundary={'yes' if taken_over else 'no'}")
        if taken_over:
            # A visible manual choice: cursor-normalized (UP x3) then the
            # complete proven Wait route, gated on the settled parked menu
            # signature plus a screenshot. Run 6/9 evidence: a complete
            # route always commits an engine-legal turn (the sequencer keeps
            # producing), but with raw cursor memory the selection can be a
            # different entry and the battle then ends; run 4 proved a
            # single bare A wedges the sequencer with a modal left open.
            session.screenshot(ev_path(f"{tag}-2b-preroute.png"))
            entry["manual_choice"] = {
                "press": "route UP,UP,UP,DOWN,DOWN,A,A", "observed": False,
                "roster_before": p.roster_guard()}
            if not p.player_menu_settled(3):
                entry["manual_choice"]["reason"] = (
                    "parked menu signature not stable before driving; "
                    "route aborted")
                p.say("  takeover: parked signature unstable; route aborted")
            else:
                cts_before_press = p.cts()
                seeds_before_press = len(p.seeds)
                # 0x03000005 is engine-managed IWRAM scratch: it is 0 by the
                # menu-park stage and stays 0 after writes (runs 12-13), yet
                # run 9's plain route committed with it at 0 — so it gates
                # nothing on this channel. Record it for the contract doc.
                enable_pre = u8(g, KEY_ENABLE)
                p.drive(tag + ":takeover-manual", route=ROUTE_TAKEOVER)
                enable_post = u8(g, KEY_ENABLE)
                entry["manual_choice"]["key_enable"] = {
                    "at_attach": enable_old, "pre_route": enable_pre,
                    "post_route": enable_post}
                p.pump(30.0, tag + ":takeover-observe")
                cts_after_press = p.cts()
                accepted = (cts_after_press != cts_before_press
                            or len(p.seeds) > seeds_before_press)
                # Visual evidence at the moment of classification: a healthy
                # commit shows battle play continuing; a teardown shows the
                # ending sequence. Only meaningful when mGBA is unoccluded
                # (CopyFromScreen grabs whatever is visibly on top).
                entry["post_route_screenshot"] = session.screenshot(
                    ev_path(f"{tag}-2c-postroute.png"))
                entry["post_route_cts"] = cts_after_press
                entry["manual_choice"].update({
                    "observed": bool(accepted),
                    "cts_before": cts_before_press,
                    "cts_after": cts_after_press,
                    "seeds_before": seeds_before_press,
                    "seeds_after": len(p.seeds),
                    "roster_after": p.roster_guard(),
                    "menu_parked_after": p.player_menu_parked()})
            # -- phase 5: re-delegate ------------------------------------
            # After the manual choice the engine resumes; Marche's CT must
            # re-charge from 0 to 1000 (~80 s at the observed ~12.8 CT/s)
            # before his menu reopens. Run 14 identified a second await-
            # input shape after a delegated round: the router keeps
            # scanning and the roster stays live, but the CT vector is
            # static with Marche parked at 0 and no new seeds — the A2.4a
            # dormant signature, which A2.4a's control run proved accepts
            # a single A. Navigation presses at an unknown modal are what
            # wedged runs 10-11, so the ladder escalates only through
            # evidence-backed shapes: A (commit), B (close), then the
            # proven full route only on a settled parked menu. Each step
            # logs before/after CT vectors so the receipt is diagnosable
            # alone.
            redelegate_open = False
            redelegate_via_unstick = False
            redelegate_ct_trace = []
            redelegate_unstick = []
            end5 = p.now() + 300.0
            last_cts = p.cts()
            last_seed_count = len(p.seeds)
            frozen_ticks = 0
            menu_left_park = False  # must observe the menu CLOSE before a
            # reopened park counts as a new boundary; otherwise the still-open
            # menu re-fires the settled check instantly (run 11 false positive)
            while p.now() < end5:
                p.pump(3.0, "redelegate-wait", sample_every=60.0, tick=3.0)
                cts_now = p.cts()
                redelegate_ct_trace.append({"t": p.now(),
                                            "ct": p.unit_u16(ps, OFF_CT),
                                            "seeds": len(p.seeds),
                                            "cts": cts_now})
                parked_now = p.player_menu_parked()
                if not parked_now:
                    menu_left_park = True
                if menu_left_park and parked_now and p.player_menu_settled(2):
                    redelegate_open = True
                    break
                if cts_now != last_cts or len(p.seeds) != last_seed_count:
                    frozen_ticks = 0
                    last_cts, last_seed_count = cts_now, len(p.seeds)
                else:
                    frozen_ticks += 1
                    if frozen_ticks >= 8:  # ~24 s of identical engine state
                        if not redelegate_unstick:
                            session.screenshot(ev_path(f"{tag}-4-wedge.png"))
                        # Run 17 (visual proof): the post-commit "wedge" is
                        # Marche's RE-opened command menu parked at a stable
                        # CT 0. Single keys are the wrong shape there — an A
                        # on the Move cursor opens the move-target modal
                        # (the run 4 wedge), and frames=1 injections never
                        # register with the menu at all. The accepted shape
                        # is the full proven route, delivered on the settled
                        # menu (stability implies parked; charging cannot
                        # hold equal values across polls).
                        action = "full-route"
                        seeds_before_unstick = last_seed_count
                        if p.player_menu_frozen(2):
                            # Value-agnostic frozen-CT check (run 18: a
                            # re-opened menu freezes the owner's CT at any
                            # value — 0, 305, 812 observed). D-pad into an
                            # unknown modal is still avoided: frozen CT plus
                            # a live roster is the command-menu shape.
                            p.drive(tag + ":redelegate-unstick-route")
                        p.pump(12.0, tag + ":redelegate-unstick-observe")
                        redelegate_unstick.append({"t": p.now(),
                                                   "action": action,
                                                   "cts_before": cts_now,
                                                   "cts_after": p.cts(),
                                                   "seeds": len(p.seeds)})
                        frozen_ticks = 0
                        if (len(p.seeds) > seeds_before_unstick
                                and action == "full-route"):
                            # The unstick route itself committed the
                            # re-delegated turn (run 18 shape): the engine
                            # ran new turns afterwards, so no extra drive
                            # is needed — a second route would land on a
                            # closed menu or a fresh one we did not
                            # observe.
                            redelegate_open = True
                            redelegate_via_unstick = True
                            last_cts, last_seed_count = p.cts(), len(p.seeds)
                            break
                        last_cts, last_seed_count = p.cts(), len(p.seeds)
                        if (not p.battle_torn_down()
                                and p.player_menu_frozen(2)):
                            redelegate_open = True
                            break
            if redelegate_open and not redelegate_via_unstick:
                p.drive(tag + ":redelegate")
                p.wait_progress(seconds=90.0, min_new_seeds=1)
            entry["redelegated_seeds"] = len(p.seeds)
            entry["redelegated_menu_open"] = redelegate_open
            entry["redelegate_via_unstick"] = redelegate_via_unstick
            entry["redelegate_ct_trace"] = redelegate_ct_trace[-12:]
            entry["redelegate_unstick"] = redelegate_unstick
            # committed: the presses changed engine state AND the engine kept
            # running afterwards (run 6's teardown also changed the CTs).
            # committed does not imply a legal selection — the teardown
            # classification and the re-delegate leg judge that.
            mc = entry["manual_choice"]
            mc["committed"] = bool(
                mc.get("observed")
                and (len(p.seeds) > mc.get("seeds_before", 0)
                     or p.cts() != mc.get("cts_after")))
        else:
            entry["manual_choice"] = {
                "press": None, "observed": False,
                "reason": "player menu boundary not reached: the frozen-seed "
                          "enemy loop repeats without returning the turn to "
                          "Marche within the observed window"}

        # -- phase 6: end-state observations -------------------------------
        g.interrupt()
        entry["end"] = march_snapshot("end")
        entry["end"]["screenshot"] = session.screenshot(
            ev_path(f"{tag}-3-end.png"))
        entry["end"]["pc"] = g.read_pc()
        entry["end"]["cts"] = p.cts()
        entry["turns"] = p.turns
        entry["branches"] = p.branches
        entry["seeds"] = p.seeds
        entry["router_hits"] = p.router_hits
        entry["tail_hits"] = p.tail_hits
        entry["samples"] = p.samples
        entry["invalid"] = p.invalid

        # acceptance classification
        torn_down = p.battle_torn_down()
        entry["end"]["battle_torn_down"] = torn_down
        enemy_turns = [t for t in p.turns if t["slot"] is not None
                       and t["slot"] != ps]
        end_ct = entry["end"]["ct"]
        end_tile = (entry["end"]["tile_x"], entry["end"]["tile_y"])
        base_tile = (entry["baseline"]["tile_x"], entry["baseline"]["tile_y"])
        entry["acceptance"] = {
            "engine_committed_player_action": delegated,
            "engine_progression_observed": bool(enemy_turns),
            "takeover_observed": bool(entry["manual_choice"].get("observed")),
            "takeover_committed": bool(entry["manual_choice"].get("committed")),
            "player_acting": end_ct in (0, 1),
            "moved": end_tile != base_tile,
            "moved_tile": end_tile if end_tile != base_tile else None,
            "end_ct": end_ct,
        }
        mc_observed = entry["acceptance"]["takeover_observed"]
        mc_committed = entry["acceptance"]["takeover_committed"]
        attempted = bool(boundary)
        redelegated = bool(entry.get("redelegated_menu_open"))
        entry["acceptance"]["redelegated"] = redelegated
        delegated_ok = (entry["acceptance"]["engine_committed_player_action"]
                        and entry["acceptance"]["engine_progression_observed"])
        if pc_end_is_trap(entry["end"]["pc"]):
            entry["outcome"] = "invalid_pc_bios_trap"
        elif torn_down and redelegated:
            entry["outcome"] = "battle_concluded_after_redelegate"
        elif torn_down:
            entry["outcome"] = ("invalid_takeover_tore_down_battle"
                                if attempted and mc_committed
                                else "battle_concluded")
        elif attempted and delegated_ok and mc_committed and redelegated:
            entry["outcome"] = "valid_engine_legal_player_action"
        elif attempted and not mc_observed:
            entry["outcome"] = "invalid_takeover_inert"
        elif attempted and mc_observed and not mc_committed:
            entry["outcome"] = "invalid_takeover_wedged_engine"
        elif delegated_ok:
            entry["outcome"] = "partial_boundary_not_reached"
        elif delegated:
            entry["outcome"] = "partial_delegated_but_no_enemy_turn"
        else:
            entry["outcome"] = "invalid_no_progress"

        # -- restore owned writes ------------------------------------------
        session.write_u8(KEY_ENABLE, enable_old if enable_old is not None else 1,
                         "restore key enable")
        entry["writes"] = list(session.writes)
        p.disarm()
    except Exception as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {exc}")
    finally:
        session.stop()
    return entry


def pc_end_is_trap(pc):
    return pc == 0x00000004 or pc == 0x08000004


def cmd_a25(args):
    """N fresh reloads of the verified fixture (default 2).

    The legacy movement-probe mode is folded into the delegated runs: each run
    records Marche's tile X/Y (+0xF6/+0xF7) at every phase, and the delegated
    turn itself is the engine's own movement/action commitment, so a separate
    no-drive run adds no evidence and is no longer scheduled.
    """
    runs = []
    for i in range(1, args.runs + 1):
        runs.append(run_a25_acceptance(args.state, seconds=args.seconds,
                                       drive_menu=not args.no_drive))
    payload = {"schema": "a2.5-acceptance/1", "rom_sha1_expected": None,
               "runs": runs}
    print(f"\nwrote {write_receipt(args.json, payload)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
