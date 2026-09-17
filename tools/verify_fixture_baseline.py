"""A2.4a receipts: fixture inventory, live reload baseline, guard rejection.

Three subcommands, all read-only until an experiment phase explicitly writes:

* `inventory` — boot each local battle-start variant once and record the live
  roster/scene the guard sees, without writing anything. This is what
  reconciles the conflicting roster claims (scenario JSON "six clan members",
  docs "solo Marche vs six monsters", A2.3 "six live units").
* `baseline` — on the chosen fixture: verify the guard, capture a live
  baseline (valid PC, slot0 actor identity, roster/scratch pointers, menu
  evidence), then commit a player turn with the A2.3 wake marks + key route
  and record whether a sequencer seed and an enemy-side action follow.
  Intervention writes are recorded and restored, and the reload is repeated.
* `reject` — prove the guard refuses a wrong or missing fixture before any
  memory write.

Run protocol facts reused from v48 (`tools/exp_control_v48.py`):
`enable=1` once at attach; presses are 5 frames at the `0x08000494` key poll
with the CPU running between presses; sample ticks call `interrupt()`; seeds
at `0x080C03C2`, player-body continuation at `0x0809E796`, AI housekeeping at
`0x0809E2DA`. Never single-step the key updater (BIOS trap, PC 0x00000004).

Evidence: outputs/autobattle/<run-id>/ (untracked; no game bytes).
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
    DEFAULT_FIXTURE_DIR, FixtureSession, OFF_CT, OFF_EA, OFF_ID, ROSTER, STRIDE,
    decode_ram_name, u8, u16, u32, write_receipt,
)

KEY_BL = 0x08000494
BP_SEED = 0x080C03C2
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NAMES = {BP_SEED: "seed", BP_PBODY: "pbody", BP_AI: "ai"}
ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"), (0x01, "A-wait"), (0x01, "A-ok")]
ROSTER_LO, ROSTER_HI = ROSTER, ROSTER + STRIDE * 8
RUN_ID = "A2.4a"
OUT_ROOT = os.path.join("outputs", "autobattle", RUN_ID)

INVENTORY_FIXTURES = [
    "battle-start.ss0",
    "a2-battle-start.ss0",
    "fix3-battle-start.ss0",
    "engage.ss0",
]


def evidence_path(name):
    p = os.path.join(OUT_ROOT, name)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    return p


def scan_ctx(g, r4, rom=None):
    """Unit pointers in the sequencer context around r4 (actor attribution).

    Accepts any pointer that looks like a unit record: the roster at
    0x020159E8, the mirrored battle copy, or any EWRAM record whose name
    pointer decodes. Attribution by name survives the copy the observed hit
    happened to reference.
    """
    if not r4:
        return []
    lo, hi = r4 - 0x90, r4 + 0x10
    blob = g.read_mem(lo, hi - lo)
    hits = []
    if blob:
        for off in range(0, len(blob) - 3, 4):
            v = int.from_bytes(blob[off:off + 4], "little")
            if not 0x02000000 <= v < 0x02040000:
                continue
            name = u32(g, v)
            if name is None or not (0x08000000 <= name < 0x09000000 or
                                    0x02000000 <= name < 0x04000000):
                continue
            entry = {"off": lo + off - r4, "v": f"{v:08x}",
                     "name": decode_ram_name(g, name, rom=rom),
                     "slot": (v - ROSTER) // STRIDE if ROSTER_LO <= v < ROSTER_HI else None}
            hits.append(entry)
    return hits


class Recorder:
    """Breakpoint observation, press, and pump helpers on one connection."""

    def __init__(self, session):
        self.s = session
        self.g = session.g
        self.t0 = time.time()
        self.seeds = []
        self.pbody = []
        self.ai = []
        self.samples = []

    def now(self):
        return round(time.time() - self.t0, 1)

    def cts(self):
        return [u16(self.g, ROSTER + STRIDE * i + OFF_CT) for i in range(8)]

    def arm(self):
        for bp in BP_NAMES:
            self.g.send(f"Z0,{bp:x},2")
        self.g.cont()

    def disarm(self):
        for bp in BP_NAMES:
            try:
                self.g.send(f"z0,{bp:x},2")
            except Exception:
                pass

    def sample(self, tag):
        s = {"t": self.now(), "tag": tag, "cts": self.cts()}
        self.samples.append(s)
        return s

    def handle_stop(self):
        g = self.g
        regs = g.read_registers()
        if not regs:
            return
        pc = regs[15]
        name = BP_NAMES.get(pc)
        t = self.now()
        if name == "seed":
            r4 = regs[4]
            self.seeds.append({"t": t, "r4": f"{r4:08x}", "r7": f"{regs[7]:08x}",
                               "ctx_units": scan_ctx(g, r4,
                                                     rom=self.s.read_rom_bytes())})
            print(f"  SEED t={t} ctx_units={self.seeds[-1]['ctx_units']}")
        elif name == "pbody":
            r4 = regs[4]
            self.pbody.append({"t": t, "r4": f"{r4:08x}", "r7": f"{regs[7]:08x}",
                               "ct": u16(g, r4 + OFF_CT) if r4 else None,
                               "ea": u8(g, r4 + OFF_EA) if r4 else None})
        elif name == "ai":
            self.ai.append({"t": t, "r4": f"{regs[4]:08x}", "r7": f"{regs[7]:08x}"})

    def press(self, mask, frames=5, pause=1.2, tag=""):
        g = self.g
        hits = 0
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                print(f"  FAIL: key poll breakpoint rejected ({tag})")
                return 0
            for _ in range(frames):
                g.cont()
                stop = g._read_packet()
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = g.read_registers()
                if not regs:
                    break
                if regs[15] == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    hits += 1
                elif BP_NAMES.get(regs[15]):
                    try:
                        self.handle_stop()
                    except Exception:
                        pass
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} t={self.now()}")
        return hits

    def drive(self, tag):
        for mask, name in ROUTE:
            self.press(mask, tag=f"{tag}:{name}")

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
                    self.handle_stop()
                except Exception as exc:
                    print(f"  handle_stop error: {exc}")
            if self.now() - last_s >= tick:
                try:
                    g.interrupt()
                except Exception:
                    pass
                if self.now() - last_s >= sample_every:
                    last_s = self.now()
                    self.sample(tag)
            if stop_when and stop_when(self):
                print(f"  {tag}: stop condition met t={self.now()}")
                break


def attributed_names(rec):
    """Names seen in sequencer contexts across all seeds."""
    return sorted({u["name"] for s in rec.seeds for u in s["ctx_units"] if u["name"]})


def classify_outcome(rec, arm_ctx, end_ctx, pc, hp_before, hp_after, player_names,
                     enemy_names):
    """Wedge vs negative control vs progress, per the A2.3 protocol rules.

    Attribution is by decoded unit name, not slot index: the sequencer context
    references the mirrored battle copy (0x02002FC4), not the roster array.

    * Wedge: no sequencer seed and no CT movement after a driven commit.
    * Negative control: no seed, but CTs moved, so the instance is live and the
      lever simply did not fire.
    * Progress: at least one sequencer seed, with the acting side named.
    """
    if pc == 0x00000004:
        return "trap_bios_illegal_instruction"
    names = set(attributed_names(rec))
    if not rec.seeds:
        cts_moved = arm_ctx is not None and end_ctx is not None and arm_ctx != end_ctx
        return "negative_control_no_seed" if cts_moved else "wedge_suspected"
    enemy_seed = bool(names & set(enemy_names))
    player_seed = bool(names & set(player_names))
    hp_moved = hp_before != hp_after
    if enemy_seed and player_seed:
        return "progress_player_and_enemy_actions"
    if enemy_seed:
        return "progress_enemy_action_only"
    if player_seed:
        return "progress_player_action_only"
    if hp_moved:
        return "progress_hp_moved_only"
    return "progress_seed_unattributed"


def live_side_map(session):
    """slot -> {name, side_bit, unaffiliated} for live records."""
    roster = session.receipt["roster"]
    return {s["slot"]: {"name": s["name_text"], "side_bit": s["side_bit"],
                        "unaffiliated": s["unaffiliated"], "id": s["id"],
                        "type": s["type"], "job": s["job"], "race": s["race"],
                        "level": s["level"], "hp": s["hp"],
                        "max_hp": s["max_hp"]}
            for s in roster["slots"] if s["live"]}


def hp_vector(g, roster):
    """Current/max HP per live slot: the visible-progress signal."""
    out = {}
    for s in roster["slots"]:
        if not s["live"]:
            continue
        base = ROSTER + STRIDE * s["slot"]
        out[s["slot"]] = {"name": s["name_text"], "hp": u16(g, base + 0x18),
                          "max_hp": u16(g, base + 0x1A),
                          "ct": u16(g, base + OFF_CT)}
    return out


def capture_baseline(session, rec, tag):
    g = session.g
    g.interrupt()
    base = {
        "tag": tag,
        "t": rec.now(),
        "pc": g.read_pc(),
        "keystruct": (g.read_mem(0x03000000, 8) or b"").hex() or None,
        "phases": session.receipt["scene"]["phases"],
        "cts": rec.cts(),
        "slot0": {
            "name": u32(g, ROSTER),
            "id": u8(g, ROSTER + OFF_ID),
            "ct": u16(g, ROSTER + OFF_CT),
            "ea": u8(g, ROSTER + OFF_EA),
        },
        "scratch_slots": [
            {
                "slot": s["slot"],
                "addr": s["addr"],
                "name": s["name"] and f"{s['name']:08x}",
                "ct": s["ct"],
                "ea": s["ea"],
                "id": s["id"],
            }
            for s in session.receipt["roster"]["slots"] if not s["live"]
        ],
        "side_map": live_side_map(session),
        "menu_evidence": {
            "note": "menu-open state is visual; see attached screenshot",
            "screenshot": session.screenshot(
                evidence_path(f"baseline-{tag}-menu.png")),
        },
    }
    rec.samples.append(base)
    g.cont()
    return base


def run_inventory(fixtures):
    results = []
    for fx in fixtures:
        state = fx if os.path.isabs(fx) or "/" in fx else os.path.join(
            DEFAULT_FIXTURE_DIR, fx)
        print(f"\n=== inventory: {fx} ===")
        entry = {"fixture": fx, "state": state}
        session = FixtureSession(
            state=state, work_dir=os.path.join(
                "outputs", "autobattle", "scratch",
                os.path.splitext(os.path.basename(state))[0]))
        try:
            session.start()
            entry["guard_ok"] = session.receipt["ok"]
            entry["checks"] = session.receipt["checks"]
            entry["roster"] = session.receipt["roster"]
            entry["scene"] = session.receipt["scene"]
            entry["pc"] = session.g.read_pc()
            entry["writes"] = list(session.writes)
            entry["screenshot"] = session.screenshot(
                evidence_path(f"inventory-{os.path.splitext(os.path.basename(state))[0]}.png"))
            r = session.receipt["roster"]
            print(f"  guard_ok={entry['guard_ok']} count={r['struct_count']} "
                  f"live={r['live_count']} names={r['live_names']} "
                  f"side8={r['side_bit_set']}/{r['side_bit_clear']} "
                  f"unaffil={r['unaffiliated']} scratch={r['scratch_slots']} "
                  f"pc={entry['pc']}")
            for c in session.receipt["checks"]:
                mark = {True: "ok", False: "FAIL", None: "info"}[c["ok"]]
                print(f"    [{mark}] {c['check']}: {c['detail']}")
        except Exception as exc:
            entry["error"] = str(exc)
            print(f"  ERROR: {exc}")
        finally:
            session.stop()
        results.append(entry)
    return results


def run_baseline(state, runs):
    results = []
    for i in range(1, runs + 1):
        tag = f"run{i}"
        print(f"\n=== baseline {tag}: {state} ===")
        entry = {"run": i, "state": state}
        session = FixtureSession(
            state=state, work_dir=os.path.join(
                "outputs", "autobattle", "scratch",
                os.path.splitext(os.path.basename(state))[0]))
        try:
            session.start()
            entry["guard_ok"] = session.receipt["ok"]
            entry["roster"] = session.receipt["roster"]
            if not session.receipt["ok"]:
                entry["outcome"] = "fixture_rejected"
                results.append(entry)
                continue
            rec = Recorder(session)
            g = session.g
            roster = session.receipt["roster"]
            player_slots = set(roster["ram_named_slots"])          # RAM-named = player
            enemy_slots = {s["slot"] for s in roster["slots"]
                           if s["live"] and s["side_bit"] and s["slot"] not in player_slots}
            entry["player_slots"] = sorted(player_slots)
            entry["enemy_slots"] = sorted(enemy_slots)
            player_names = [s["name_text"] for s in roster["slots"]
                            if s["slot"] in player_slots]
            enemy_names = [s["name_text"] for s in roster["slots"]
                           if s["slot"] in enemy_slots]
            entry["player_names"] = player_names
            entry["enemy_names"] = enemy_names

            # -- live baseline -------------------------------------------
            entry["baseline"] = capture_baseline(session, rec, tag)
            print(f"  baseline pc={entry['baseline']['pc'] and hex(entry['baseline']['pc'])} "
                  f"slot0={entry['baseline']['slot0']} cts={entry['baseline']['cts']}")
            arm_ctx = tuple(entry["baseline"]["cts"])
            hp_before = hp_vector(g, roster)

            # -- intervention: key enable, then the A1/A2.3 menu route ----
            g.interrupt()
            enable_old = u8(g, 0x03000005)
            session.write_u8(0x03000005, 1, "key enable (protocol: write once at attach)")
            g.cont()
            time.sleep(0.8)
            rec.arm()
            # From the fixture's open battle menu: DOWN, DOWN, A (Wait), A (confirm).
            rec.drive(tag)
            rec.pump(40.0, tag, stop_when=lambda r: len(r.seeds) >= 2)
            if not rec.seeds:
                rec.drive(f"{tag}-retry")
                rec.pump(25.0, f"{tag}-retry", stop_when=lambda r: len(r.seeds) >= 1)

            # -- observation ---------------------------------------------
            g.interrupt()
            end_ctx = tuple(rec.cts())
            pc_end = g.read_pc()
            hp_after = hp_vector(g, roster)
            entry["pc_end"] = pc_end
            entry["hp_before"] = hp_before
            entry["hp_after"] = hp_after
            entry["seeds"] = rec.seeds
            entry["pbody_count"] = len(rec.pbody)
            entry["ai_count"] = len(rec.ai)
            entry["pbody"] = rec.pbody[:40]
            entry["ai"] = rec.ai[:40]
            entry["samples"] = rec.samples
            entry["attributed_names"] = attributed_names(rec)
            entry["outcome"] = classify_outcome(
                rec, arm_ctx, end_ctx, pc_end, hp_before, hp_after,
                player_names, enemy_names)
            print(f"  seeds={len(rec.seeds)} pbody={len(rec.pbody)} "
                  f"ai={len(rec.ai)} actors={entry['attributed_names']} "
                  f"outcome={entry['outcome']}")
            print(f"  hp {hp_before} -> {hp_after}")
            entry["screenshot_final"] = session.screenshot(
                evidence_path(f"baseline-{tag}-final.png"))

            # -- restoration ---------------------------------------------
            g.interrupt()
            session.write_u8(0x03000005, enable_old if enable_old is not None else 1,
                             "restore key enable")
            entry["writes"] = list(session.writes)
            entry["restored"] = True
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR: {exc}")
        finally:
            session.stop()
        results.append(entry)
    return results


def run_control(state, seconds=25.0):
    """Negative control: watch the verified fixture with no input at all.

    Distinguishes a fixture that genuinely awaits player input (dormant) from
    one that self-plays, and from a wedge. Only the key-enable byte is written.
    """
    print(f"\n=== control (no drive): {state} ===")
    entry = {"state": state, "seconds": seconds}
    session = FixtureSession(
        state=state, work_dir=os.path.join(
            "outputs", "autobattle", "scratch",
            os.path.splitext(os.path.basename(state))[0]))
    try:
        session.start()
        entry["guard_ok"] = session.receipt["ok"]
        entry["roster"] = session.receipt["roster"]
        if not session.receipt["ok"]:
            entry["outcome"] = "fixture_rejected"
            return entry
        rec = Recorder(session)
        g = session.g
        g.interrupt()
        enable_old = u8(g, 0x03000005)
        session.write_u8(0x03000005, 1, "key enable (protocol: write once at attach)")
        rec.arm()
        cts0 = tuple(rec.cts())
        entry["cts_before"] = list(cts0)
        rec.pump(seconds, "control-no-drive", sample_every=8.0)
        g.interrupt()
        cts1 = tuple(rec.cts())
        entry["cts_after"] = list(cts1)
        entry["seeds"] = rec.seeds
        entry["pbody_count"] = len(rec.pbody)
        entry["ai_count"] = len(rec.ai)
        entry["samples"] = rec.samples
        entry["pc_end"] = g.read_pc()
        if not rec.seeds and cts0 == cts1:
            entry["outcome"] = "dormant_awaits_player_input"
        elif not rec.seeds:
            entry["outcome"] = "ct_progressed_without_seed"
        else:
            entry["outcome"] = "auto_played_without_input"
        session.write_u8(0x03000005, enable_old if enable_old is not None else 1,
                         "restore key enable")
        entry["writes"] = list(session.writes)
        entry["screenshot_final"] = session.screenshot(
            evidence_path("control-final.png"))
        print(f"  seeds={len(rec.seeds)} cts {cts0} -> {cts1} "
              f"outcome={entry['outcome']}")
    except Exception as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {exc}")
    finally:
        session.stop()
    return entry


def run_reject(states):
    results = []
    for st in states:
        missing = st == "__missing__"
        state = (os.path.join(DEFAULT_FIXTURE_DIR, "does-not-exist.ss0")
                 if missing else st)
        print(f"\n=== reject: {st} ===")
        session = FixtureSession(
            state=state, missing_state_ok=missing,
            work_dir=os.path.join("outputs", "autobattle", "scratch", "reject"))
        entry = {"requested": st, "state": state}
        try:
            session.start()
            entry["guard_ok"] = session.receipt["ok"]
            entry["checks"] = session.receipt["checks"]
            entry["pc"] = session.g.read_pc()
            entry["rejected"] = not session.receipt["ok"]
            entry["writes_before_decision"] = list(session.writes)
            print(f"  guard_ok={entry['guard_ok']} rejected={entry['rejected']}")
        except Exception as exc:
            entry["rejected"] = True
            entry["error"] = str(exc)
            print(f"  rejected before attach/write: {exc}")
        finally:
            session.stop()
        results.append(entry)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_inv = sub.add_parser("inventory", help="read-only roster/scene inventory")
    p_inv.add_argument("--fixtures", nargs="*", default=INVENTORY_FIXTURES)
    p_inv.add_argument("--json", default=evidence_path("inventory.json"))

    p_base = sub.add_parser("baseline", help="live reload baseline on a fixture")
    p_base.add_argument("state", nargs="?",
                        default=os.path.join(DEFAULT_FIXTURE_DIR, "battle-start.ss0"),
                        help="verified fixture (default battle-start.ss0)")
    p_base.add_argument("--runs", type=int, default=2)
    p_base.add_argument("--json", default=evidence_path("baseline.json"))

    p_ctl = sub.add_parser("control", help="no-input control on the verified fixture")
    p_ctl.add_argument("state", nargs="?",
                       default=os.path.join(DEFAULT_FIXTURE_DIR, "battle-start.ss0"))
    p_ctl.add_argument("--seconds", type=float, default=25.0)
    p_ctl.add_argument("--json", default=evidence_path("control.json"))

    p_rej = sub.add_parser("reject", help="prove wrong/missing fixtures are rejected")
    p_rej.add_argument("states", nargs="*",
                       default=[os.path.join(DEFAULT_FIXTURE_DIR, "engage.ss0"),
                                "__missing__"])
    p_rej.add_argument("--json", default=evidence_path("reject.json"))

    args = ap.parse_args()
    if args.cmd == "inventory":
        payload = {"schema": "a2.4a-inventory/1", "results": run_inventory(args.fixtures)}
    elif args.cmd == "baseline":
        payload = {"schema": "a2.4a-baseline/1", "results": run_baseline(args.state, args.runs)}
    elif args.cmd == "control":
        payload = {"schema": "a2.4a-control/1",
                   "results": [run_control(args.state, args.seconds)]}
    else:
        payload = {"schema": "a2.4a-reject/1", "results": run_reject(args.states)}
    print(f"\nwrote {write_receipt(args.json, payload)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
