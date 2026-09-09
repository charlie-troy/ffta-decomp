"""A2.3 v28: fixed retail control + the reverse handout, one live battle.

v27 evidence, re-read statically: "player-path" BP 0x0809E398 is a COMMON
TAIL, not the player branch. The real split is at 0x0809E3AE (+0xEA bit 7,
sub_080CDADC): set -> player body 0x0809E796; clear -> AI-status housekeeping
fall-through into the same tail. v27's 149 ai/tail pairs are per-frame AI
passes; its 3 lone tail hits (t=22.1, 46.4, 49.3) are slot0's bit-7-set
frames - the Controlled seam routed the enemy through the player-turn body.
What stayed open is v27c's broken control (snowball ctx 0x020101F8 used as
the menu gate; normal-battle sequencer ctx is 0x0200F5C4; and its 150 s
window sat far short of Marche's round-2 pick, his CT resets to ~1000).

Phase A (control, pure retail): end Marche's turn (DOWN,DOWN,A,A), then watch
  - BP_PICK 0x0809E260: r0 = actor slot from the turn manager sub_0809E05C
    (executed per loop iteration; r0 TRANSITIONS are the real picks)
  - BP_NORM 0x080C03C2: sequencer ctx-init seed (once per AI turn start)
  A "Marche window" = [pick r0==6 .. next pick r0!=6]. Verdict per window:
  seeds inside it => player turns DO ctx-init; zero => they do not (and
  v27's frozen slot0 state was the real menu handout). His subsequent menus
  are driven promptly in-watch (gate: ctx phase 0x0200F5C4+0x54F4 == 8 and
  slot6 CT == 0) so the idle auto-battle path cannot answer for him.

Phase B (reverse handout, one bit): set Marche's slot6 +0xEA bit 7 before his
  next pick. His turn should route through 0x0809E796 like an AI unit:
  ctx-init seed with his pick, autonomous action on screen. After his turn
  completes (next non-Marche pick) clear bit 7 again; his following turn
  should reopen the command menu with no seed. Reversible by construction:
  the write is a single bit on a RAM record, restored in the same battle.

Boot first: python tools/boot_fixture_gdb.py   (verifies the fixture live)
Run:        python tools/exp_control_v28.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
SLOT0 = 0x020159E8
STRIDE = 0x108
SLOT6 = SLOT0 + STRIDE * 6          # 0x02016018 (Marche's record)
EA6 = SLOT6 + 0xEA                  # bit 7 = the pick branch (sub_080CDADC)
ID6 = SLOT6 + 0x104                 # Marche class/id byte (6)
CTX = 0x0200F5C4                    # normal-battle sequencer ctx (v27 seeds)
PHASE = CTX + 0x54F4                # u16 phase; 8 = command menu open
BP_NORM = 0x080C03C2                # sequencer ctx-init seed
BP_PICK = 0x0809E260                # r0 = actor slot from sub_0809E05C
OUT = "outputs/lua-nav/controlled-v28.json"
# 0x080C8280 = unit+0x18 == 0 (the validator's zero-HP predicate); the player
# body only proceeds to the menu/sequencer continuation for living units.
MENU_ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"),
              (0x01, "A-wait"), (0x01, "A-confirm")]


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def window_capture(pid, path):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)
    print(f"  capture {path}: {'ok' if r.returncode == 0 else 'FAIL'}")


def u8(g, a):
    d = g.read_mem(a, 1)
    return d[0] if d else None


def u16(g, a):
    d = g.read_mem(a, 2)
    return int.from_bytes(d, "little") if d else None


def dump_slots(g, tag):
    row = {}
    for i in range(7):
        base = SLOT0 + STRIDE * i
        row[i] = {"ct": u16(g, base + 0xD0), "ea": u8(g, base + 0xEA),
                  "ed": u8(g, base + 0xED)}
    ph = u16(g, PHASE)
    print(f"  [{tag}] phase={ph} " + " ".join(
        f"s{i}(ct={r['ct']},ea={r['ea']:02x},ed={r['ed']:02x})"
        for i, r in row.items()))
    return {"phase": ph, "slots": {str(k): v for k, v in row.items()}}


def force_enable(g):
    """Idle timer kills menu input (~16 s); re-enable while halted."""
    assert g.send("M3000005,1:01") == "OK", "enable write rejected"


class Sink:
    """Shared event list so BP hits consumed while driving a menu are kept."""

    def __init__(self):
        self.pending = []

    def drain(self):
        out, self.pending = self.pending, []
        return out


def press(g, sink, mask, frames=5, pause=1.1, tag=""):
    hits = 0
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
            print(f"  FAIL: KEY_BL BP rejected ({tag})")
            return 0
        for _ in range(frames):
            g.cont()
            stop = g._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = g.read_registers()
            if regs and regs[15] == KEY_BL:
                val = (regs[1] | mask) & 0x3FF
                g.send("P1=" + val.to_bytes(4, "little").hex())
                hits += 1
            elif regs and regs[15] in (BP_NORM, BP_PICK):
                sink.pending.append({"bp": regs[15], "r0": regs[0],
                                     "r4": regs[4], "r7": regs[7]})
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
        except Exception:
            pass
    time.sleep(pause)
    print(f"  key {mask:#04x} x{hits} {tag}")
    return hits


def drive_menu(g, sink, pid, tag):
    """The proven Wait route, with input re-enabled first."""
    try:
        g.interrupt()
        force_enable(g)
        g.cont()
    except Exception:
        pass
    time.sleep(0.4)
    for mask, name in MENU_ROUTE:
        press(g, sink, mask, 5, tag=f"{tag}:{name}")
    time.sleep(1.0)
    window_capture(pid, f"outputs/lua-nav/v28-{tag}.png")


def menu_open(g):
    return u16(g, PHASE) == 8 and u16(g, SLOT6 + 0xD0) == 0


def watch(g, pid, sink, deadline_fn, on_event, sample_every=8.0,
          idle_capture=25.0, drive_tag_prefix=None):
    """Run loop: handles seed/pick BPs, samples memory, captures the window,
    and (optionally) drives Marche's menu when the gate says it is open.

    drive_tag_prefix: when set, menu_open() is polled on quiet iterations and
    a newly opened, not-yet-driven window is driven via the proven route.
    Returns (events, samples)."""
    events, samples = [], []
    t0 = time.time()
    last_sample = last_cap = 0.0
    drive_done = set()
    g.sock.settimeout(3.0)
    while True:
        now = time.time() - t0
        reason = deadline_fn(now)
        if reason:
            print(f"  watch end: {reason} (t={now:.0f}s)")
            break
        try:
            g.cont()
            stop = g._read_packet()
        except Exception:
            stop = None
        if stop and stop[:1] in ("S", "T"):
            regs = g.read_registers()
            pc = regs[15] if regs else 0
            kind = {BP_NORM: "seed", BP_PICK: "pick"}.get(pc)
            if kind:
                ev = {"t": round(time.time() - t0, 1), "kind": kind,
                      "r0": regs[0], "r4": regs[4], "r7": regs[7]}
                events.append(ev)
                on_event(ev)
                continue
        now = time.time() - t0
        for p in sink.drain():
            kind = {BP_NORM: "seed", BP_PICK: "pick"}.get(p["bp"])
            ev = {"t": round(now, 1), "kind": kind, **p}
            events.append(ev)
            on_event(ev)
        if drive_tag_prefix and menu_open(g):
            key = len([e for e in events if e["kind"] == "pick"])
            if key not in drive_done:
                drive_done.add(key)
                print(f"  menu gate open at t={now:.0f}s -> driving")
                drive_menu(g, sink, pid, f"{drive_tag_prefix}{len(drive_done)}")
                continue
        if now - last_sample >= sample_every:
            try:
                g.interrupt()
                samples.append({"t": round(now, 1),
                                **dump_slots(g, f"t+{now:.0f}")})
                last_sample = now
                g.cont()
            except Exception as exc:
                print(f"  sample fail: {exc}")
                try:
                    g.cont()
                except Exception:
                    pass
        if now - last_cap >= idle_capture and pid:
            window_capture(pid, f"outputs/lua-nav/v28-t{now:.0f}.png")
            last_cap = now
    return events, samples


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process; run tools/boot_fixture_gdb.py first")
        return 1
    print(f"mGBA pid {pid}")
    out = {"phase_a": {}, "phase_b": {}}
    sink = Sink()
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")
        if u8(g, ID6) != 6:
            print("fixture signature missing (slot6 id != 6); "
                  "run tools/boot_fixture_gdb.py first")
            return 1
        out["baseline"] = dump_slots(g, "baseline")

        # ---------------- phase A: retail control --------------------------
        force_enable(g)
        for bp in (BP_NORM, BP_PICK):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()
        time.sleep(0.6)
        window_capture(pid, "outputs/lua-nav/v28-0-menu.png")
        for mask, name in MENU_ROUTE:
            press(g, sink, mask, 5, tag=f"r1:{name}")
        window_capture(pid, "outputs/lua-nav/v28-1-committed.png")

        state = {"marche_windows": [], "open_window": None,
                 "last_actor": None}

        def on_event_a(ev):
            if ev["kind"] == "seed":
                print(f"  SEED t={ev['t']} r4={ev['r4']:#010x}")
                if state["open_window"] is not None:
                    state["open_window"]["seeds"].append(
                        {"t": ev["t"], "r4": ev["r4"]})
                return
            slot = ev["r0"] & 0xFF
            if slot != state["last_actor"]:
                print(f"  PICK t={ev['t']} slot={slot}")
                state["last_actor"] = slot
                if slot == 6:
                    state["open_window"] = {"pick_t": ev["t"], "seeds": [],
                                            "ended_t": None}
                    state["marche_windows"].append(state["open_window"])
                    if pid:
                        time.sleep(1.0)
                        window_capture(
                            pid, f"outputs/lua-nav/v28-marche-pick"
                                 f"{len(state['marche_windows'])}.png")
                elif state["open_window"] is not None:
                    state["open_window"]["ended_t"] = ev["t"]
                    state["open_window"] = None

        def deadline_a(now):
            done = [w for w in state["marche_windows"] if w["ended_t"]]
            if len(done) >= 2:
                return "two Marche player turns completed"
            if now > 420:
                return "timeout"
            return None

        events_a, samples_a = watch(
            g, pid, sink, deadline_a, on_event_a,
            drive_tag_prefix="a-menu")
        for i, wnd in enumerate(state["marche_windows"]):
            wnd["window"] = (f"pick{wnd['pick_t']}..{wnd.get('ended_t')}")
            wnd["verdict"] = ("SEEDED during player turn"
                              if wnd["seeds"]
                              else "no ctx-init during player turn")
            print(f"  window {i}: {wnd['verdict']}")
        out["phase_a"] = {"marche_windows": state["marche_windows"],
                          "events": events_a, "samples": samples_a}

        # ---------------- phase B: reverse handout -------------------------
        g.interrupt()
        ea = u8(g, EA6)
        assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
        out["phase_b"]["ea_before"] = ea
        out["phase_b"]["ea_after"] = u8(g, EA6)
        print(f"phase B: slot6 +0xEA {ea:02x} -> {out['phase_b']['ea_after']:02x}")
        force_enable(g)
        g.cont()

        bstate = {"last_actor": None, "marche_pick_t": None,
                  "seed_after_pick": None, "restored_t": None}

        def on_event_b(ev):
            if ev["kind"] == "pick":
                slot = ev["r0"] & 0xFF
                if slot != bstate["last_actor"]:
                    print(f"  PICK t={ev['t']} slot={slot}")
                    bstate["last_actor"] = slot
                    if slot == 6 and bstate["marche_pick_t"] is None:
                        bstate["marche_pick_t"] = ev["t"]
                        if pid:
                            time.sleep(1.5)
                            window_capture(
                                pid, "outputs/lua-nav/v28-b-marche-ai-0.png")
                    elif (slot != 6 and bstate["marche_pick_t"] is not None
                          and bstate["restored_t"] is None):
                        bstate["restored_t"] = ev["t"]
            elif ev["kind"] == "seed":
                print(f"  SEED t={ev['t']} r4={ev['r4']:#010x}")
                if (bstate["marche_pick_t"] is not None
                        and bstate["seed_after_pick"] is None
                        and ev["t"] - bstate["marche_pick_t"] < 40):
                    bstate["seed_after_pick"] = {"t": ev["t"], "r4": ev["r4"]}
                    if pid:
                        time.sleep(2.0)
                        window_capture(
                            pid, "outputs/lua-nav/v28-b-marche-ai-1.png")

        def deadline_b(now):
            if bstate["restored_t"] is not None \
                    and now > bstate["restored_t"] + 45:
                return "post-turn observation window elapsed"
            if now > 300:
                return "timeout"
            return None

        events_b, samples_b = watch(g, pid, sink, deadline_b, on_event_b)
        out["phase_b"].update({
            "marche_pick_t": bstate["marche_pick_t"],
            "seed_after_pick": bstate["seed_after_pick"],
            "next_pick_t": bstate["restored_t"],
            "verdict": ("AI turn with ctx-init"
                        if bstate["seed_after_pick"]
                        else "picked but no ctx-init (no AI turn)"),
            "events": events_b, "samples": samples_b,
        })
        print(f"phase B verdict: {out['phase_b']['verdict']}")

        # ---------------- restore + verify ---------------------------------
        g.interrupt()
        ea = u8(g, EA6)
        assert g.send(f"M{EA6:x},1:{ea & 0x7F:02x}") == "OK"
        out["phase_b"]["ea_restored"] = u8(g, EA6)
        print(f"phase B: bit7 cleared -> {out['phase_b']['ea_restored']:02x}")
        force_enable(g)
        g.cont()

        rest = {"last_actor": None, "picked_t": None, "seed": None}
        state["last_actor"] = None
        state["open_window"] = None

        def on_event_r(ev):
            if ev["kind"] == "pick":
                slot = ev["r0"] & 0xFF
                if slot != rest["last_actor"]:
                    print(f"  PICK t={ev['t']} slot={slot}")
                    rest["last_actor"] = slot
                    if slot == 6 and rest["picked_t"] is None:
                        rest["picked_t"] = ev["t"]
                        if pid:
                            time.sleep(2.0)
                            window_capture(
                                pid, "outputs/lua-nav/v28-b-restored-menu.png")
                    elif slot != 6 and rest["picked_t"] is not None:
                        rest["end_t"] = ev["t"]
            elif ev["kind"] == "seed" and rest["picked_t"] is not None \
                    and rest["seed"] is None:
                rest["seed"] = {"t": ev["t"], "r4": ev["r4"]}

        def deadline_r(now):
            if rest.get("end_t") is not None:
                return "restored player turn completed"
            if now > 300:
                return "timeout"
            return None

        events_r, samples_r = watch(g, pid, sink, deadline_r, on_event_r)
        out["phase_b"]["restoration"] = {
            "marche_pick_seen": rest["picked_t"] is not None,
            "seed_in_window": rest["seed"],
            "verdict": ("menu restored (no ctx-init)"
                        if rest["picked_t"] is not None and not rest["seed"]
                        else "check captures"),
            "events": events_r, "samples": samples_r,
        }
        print(f"restoration verdict: {out['phase_b']['restoration']['verdict']}")

        g.interrupt()
        out["final"] = dump_slots(g, "final")
        g.send(f"z0,{BP_NORM:x},2")
        g.send(f"z0,{BP_PICK:x},2")
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v28-final.png")
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
