"""A8 probe v12: timestamped N phase + free-run poll T phase.

Round-9 (Astra): independent emulated-time calibration with retained
timestamped start/end samples, no hardcoded baseline, no extrapolation.

Phase N (traced, v10, rows already retained): clear ALL trace BPs, arm
ONLY the key-poll BP (one stop = one frame), timestamp cont/stop of
every iteration.  Gives the exact frame count N of the event (park 296
verified at stop 1, CT >= 998 at the last stop) and shows that the
cont->stop interval is stub-service-bound: dt p50 ~ 52 ms with a 50.4 ms
floor, invariant under videoSync (v10 rows).  fps_running = N/sum(dt) is
therefore the TRACED-CYCLE rate (the ~19.2 stops/s transport cap), not
a free-run rate; it is published as tracing overhead only.

Phase T (free-run, v12): no breakpoints, no interrupt().  Packet-level
tracing (tools/diag_t_phase4.py, 2026-10-05) established the exact
stub protocol: every command gets a '+' ack plus one reply packet, raw
0x03 gets one un-acked S02, 'c' gets only '+', and a served 'm' read
implicitly HALTS the core with a fresh value at the halt instant -
only a later 'c' resumes it (DE-029).  v9's ladder died from a reply
OFFSET: the arm/disarm burn can leave one stray reply, every later
send then consumes the PREVIOUS reply, and interrupt()'s stop-read
gets a mem reply - a self-sustaining shift (DE-028).  Bare polls
without an intervening 'c' look "frozen" because the core never
resumes, not because of traffic rate.

v12 sequence:
  1. clear_all_bps (press re-armed all of them; the core must run free).
  2. drain_paired: {send 'm'; raw-pump the socket 0.5 s} until two
     consecutive pumps come back EMPTY - an empty pump after a send that
     blocked for its own reply proves kernel+buffer are drained, i.e.
     every future send consumes its own reply.
  3. cont() at t0: the event starts from the parked 296 (traced boots
     pin CT=296 at frame 1 of this same event).
  4. poll loop: sleep -> t_send, 'm' (this READ implicitly halts the
     core - only a later 'c' resumes it, DE-029), t_recv, ct - then
     cont() immediately and timestamp t_resume.  Every poll therefore
     brackets one running window [t_resume, t_recv]; emulated time
     advances ONLY inside it, and the poll cadence (0.15 s, first at
     0.01 s) sets the detection granularity.  Samples retained.
  5. first read = start-CT confirm (envelope 100..400; frame-1 = 296
     pinned by the traced rows); the event ends on the first direct
     CT >= 998 read OR on the WRAP signature: after a late marker
     (ct >= 400: the 420/535 phase, a 2+ s run that 0.15 s polls land
     in with certainty), the next read >= 200 is the next cycle's
     start - the >=998 dwell is ~1 frame and not reliably pollable,
     but the counter cannot come back to >= 200 from 0 without passing
     998 first, so the crossing is bracketed the same way.

Duration bracket (paired replies; the detecting poll k's window):
  start    = t0 + L,  L in [0, LATENCY_BOUND_S]
  crossing in (t_resume_k, t_recv_k]  (the core is halted between
             t_recv_{k-1} and t_resume_k, so the crossing lies inside
             window k)
  D_min = t_resume_k - t0 - L
  D_max = t_recv_k   - t0

fps = N / D with N taken from this probe's traced boots of the same
mode (event is fixture-deterministic: default 1190/1190; jitter across
v9+v10 boots 0-5.7% is carried into the bracket as N_lo..N_hi).

Gates (pre-registered):
  * traced rows: park in tolerance, end CT >= 998, zero PC anomalies,
    N spread <= 6% per mode (observed event-length jitter, documented;
    the mechanism gate at 30% is far above it);
  * T rows: start confirm inside the early-cycle envelope (100..400;
    frame-1 = 296 pinned by the traced rows, a frame or two of free-run
    before the first halt reads 188), event detected within budget, no
    run of 3 consecutive failed CT reads;
  * the two T boots of a mode must have OVERLAPPING fps brackets;
  * MECHANISM VERDICT from bracket separation: worst-case ratio
    min(lo)/max(hi) >= 1.30 => videoSync=1 is a working speed control;
    best-case ratio max(hi)/min(lo) < 1.30 => no tested mechanism
    changes gameplay speed materially; otherwise indeterminate, said so.

No whole-battle wall-time extrapolation is computed from these numbers.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe, BP_KEY  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
SPEED_JSON = os.path.join(OUT_DIR, "speed.json")
CT_BASE = ROSTER + STRIDE * 6 + OFF_CT
CT_FULL = 998
TRACE_BUDGET_S = 120
T_POLL_S = 0.15            # poll cadence; every poll is followed by a
                           # cont (reads implicitly halt the core, DE-029)
T_FIRST_POLL_S = 0.01      # near-frame-1 start-CT confirm
T_PUMP_S = 0.5             # drain pump window
T_BUDGET_S = 60            # wall budget for one T boot (event ~13-25 s)
GBA_FPS = 59.7275          # definitional: GBA nominal refresh
PARK_TOLERANCE = (200, 400)
START_ENVELOPE = (100, 400)  # first T read: 296 at frame 1, 188 a frame in
N_SPREAD_GATE = 0.06         # observed event-length jitter 0..5.7% (v9+v10)
MECH_RATIO_GATE = 1.30
# Pooled traced frame counts for the same fixture event across v9+v10
# boots (the event's length jitters a few % boot-to-boot from commit
# timing; a T boot does not count frames, so its N is bracketed by the
# pooled observations rather than pinned to this probe's two rows).
N_POOL = {"default": (1126, 1190),   # v9: 1126, 1163; v10: 1190, 1190
          "vsync1": (1123, 1162)}    # v9: 1143, 1123; v10: 1162, 1123
# Per-packet stub service bound: traced dt floor is 50.4 ms (one cont ->
# stop-reply exchange incl. one frame); 60 ms bounds one-way service with
# margin.  Used only to widen the T duration bracket honestly.
LATENCY_BOUND_S = 0.06


def arm_key_bp(g, tries=6):
    """Arm ONLY the key-poll BP, retrying past stale stop packets."""
    for _ in range(tries):
        try:
            if g.send(f"Z0,{BP_KEY:x},2") == "OK":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def disarm_key_bp(g, tries=6):
    """Disarm the key-poll BP with the same retry-until-OK convergence
    (the pairing burn after arm: traced boots prove reads are healthy
    immediately after this sequence)."""
    for _ in range(tries):
        try:
            if g.send(f"z0,{BP_KEY:x},2") == "OK":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def clear_all_bps(g, tries=10):
    """Clear EVERY known breakpoint (BP_NAMES incl. BP_KEY), converging
    per address until its 'OK' ack is seen.  Any stray packet (a stale
    S/T stop or a shifted ack) is consumed as a non-OK and retried, so
    this drains the whole post-commit backlog: v9c proved one-send-per-
    address still leaves k shifted acks behind, and a read cannot drain
    them itself (interrupt() blocks on a halted core and its retries
    consume nothing).  After this returns, exchanges are paired."""
    from probe_control_handoff import BP_NAMES
    for a in BP_NAMES:
        for _ in range(tries):
            try:
                if g.send(f"z0,{a:x},2") == "OK":
                    break
            except Exception:
                pass
            time.sleep(0.2)


def phase_N_traced(g):
    """Traced phase (v10): cont -> stop -> reads, timestamped per stop.

    Returns dict with N, per-stop samples, running/wall sums, anomalies.
    Event ends at the first stop whose CT read is >= CT_FULL."""
    clear_all_bps(g)
    if not arm_key_bp(g):
        raise RuntimeError("key-poll BP rejected after retries")
    samples = []
    anomalies = 0
    n = 0
    running_sum = 0.0
    t_start = None
    t_end = None
    t_prev_stop = None
    t0 = time.time()
    try:
        while time.time() - t0 < TRACE_BUDGET_S:
            t_cont = time.time()
            g.cont()
            stop = g._read_packet()
            t_stop = time.time()
            if not stop or stop[:1] not in ("S", "T"):
                continue
            regs = g.read_registers()
            if not regs:
                continue
            if regs[15] != BP_KEY:
                anomalies += 1
                continue
            n += 1
            if t_start is None:
                t_start = t_cont
            dt = t_stop - t_cont
            gap = (t_cont - t_prev_stop) if t_prev_stop is not None else None
            running_sum += dt
            t_prev_stop = t_stop
            try:
                d = g.read_mem(CT_BASE, 2)
            except Exception:
                d = None
            ct = int.from_bytes(d, "little") if d else None
            samples.append({
                "stop": n,
                "t_cont": round(t_cont, 6),
                "t_stop": round(t_stop, 6),
                "gap": round(gap, 6) if gap is not None else None,
                "dt": round(dt, 6),
                "ct": ct,
            })
            if ct is not None and ct >= CT_FULL:
                t_end = t_stop
                return {"N": n, "samples": samples, "anomalies": anomalies,
                        "t_start_epoch": t_start, "t_end_epoch": t_end,
                        "running_s": running_sum,
                        "wall_s": t_end - t_start}
    finally:
        g.send(f"z0,{BP_KEY:x},2")
        g.cont()
    raise RuntimeError(f"trace budget exhausted (stops={n})")


def _pump(g, dur=T_PUMP_S):
    """Raw-recv whatever is pending on the socket for up to dur seconds.
    Returns the bytes seen (b'' = nothing pending)."""
    import socket as _socket
    end = time.time() + dur
    got = b""
    g.sock.settimeout(0.05)
    try:
        while time.time() < end:
            try:
                chunk = g.sock.recv(4096)
            except _socket.timeout:
                continue
            if not chunk:
                break
            got += chunk
    finally:
        g.sock.settimeout(5.0)
    return got


def drain_paired(g, tries=8):
    """Converge the stream so every future send consumes ITS OWN reply.

    The offset law (DE-028): trace_mgba's send() may consume the
    previous command's reply when one is still in flight, after which
    every exchange reports one reply late - interrupt()'s stop-read then
    gets mem data and the shift sustains itself.  The cure is a pump:
    send one 'm', then raw-drain the socket.  If the send had to block
    for its own reply AND the pump finds nothing, buffer and kernel are
    both empty = paired.  Two consecutive empty pumps = confirmed.
    Returns True on convergence, False otherwise."""
    empty_streak = 0
    for _ in range(tries):
        try:
            g.send(f"m{CT_BASE:x},2")
        except Exception:
            pass
        got = _pump(g)
        if got:
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= 2:
                return True
        time.sleep(0.1)
    return False


def phase_T_free(g):
    """Free-run phase (v12): sparse paired polls, cont after every read.

    Physics: a served 'm' read implicitly HALTS the core (only 'c'
    resumes it - DE-029), so wall time between bare reads is not
    emulated time.  Each poll therefore brackets a running window:
    cont at t_resume -> sleep -> read (halts, value = state at halt).
    The event advances only inside [t_resume + L, t_recv], and the
    duration is bracketed by the timestamps of the detecting window.

    Returns duration bracket [D_min, D_max] plus every poll sample
    (t_resume / t_send / t_recv / ct / raw), absolute epochs.  On
    failure the RuntimeError carries the partial samples."""
    samples = []
    try:
        clear_all_bps(g)
        if not drain_paired(g):
            raise RuntimeError("stream did not converge to paired replies")
        none_run = 0
        t0 = time.time()
        g.cont()
        t_resume = t0
        next_at = t0 + T_FIRST_POLL_S
        prev_ct = None
        late_marker = False
        while time.time() - t0 < T_BUDGET_S:
            wait = next_at - time.time()
            if wait > 0:
                time.sleep(wait)
            t_send = time.time()
            try:
                raw = g.send(f"m{CT_BASE:x},2")
            except Exception as exc:
                raw = f"EXC:{type(exc).__name__}"
            t_recv = time.time()
            hexok = (raw and len(raw) == 4
                     and all(c in "0123456789abcdef" for c in raw))
            ct = int.from_bytes(bytes.fromhex(raw), "little") if hexok else None
            samples.append({"i": len(samples) + 1,
                            "t_resume": round(t_resume, 6),
                            "t_send": round(t_send, 6),
                            "t_recv": round(t_recv, 6),
                            "ct": ct, "raw": raw})
            if ct is None:
                none_run += 1
                if none_run >= 3:
                    raise RuntimeError("3 consecutive CT read failures")
            else:
                none_run = 0
                # End detection, two triggers (the >=998 state dwells for
                # ~1 frame and is NOT reliably pollable at 0.15 s):
                #   1. direct read CT >= 998;
                #   2. WRAP: after a late marker (>= 400: the 420/535
                #      phase), the next read >= 200 is the next cycle's
                #      start - the crossing happened in between (the
                #      counter cannot return to >=200 from 0 without
                #      passing 998 first).
                # In both cases the crossing lies in
                # (t_resume, t_recv] because the core is halted from
                # t_recv of the previous read until t_resume.
                wrapped = (late_marker and prev_ct is not None
                           and prev_ct < 200 and ct >= 200)
                if ct >= CT_FULL or wrapped:
                    d_min = t_resume - t0 - LATENCY_BOUND_S
                    d_max = t_recv - t0
                    return {"D_min": max(0.0, d_min), "D_max": d_max,
                            "samples": samples, "t0": t0, "t_end": t_recv,
                            "first_ct": samples[0]["ct"],
                            "end_trigger": ("direct-998" if ct >= CT_FULL
                                            else "wrap"),
                            "end_ct": ct}
                if ct >= 400:
                    late_marker = True
                prev_ct = ct
            g.cont()                 # reads implicitly halt; resume
            t_resume = time.time()
            next_at = time.time() + T_POLL_S
        last_ct = samples[-1]["ct"] if samples else None
        raise RuntimeError(
            f"T budget exhausted (windows={len(samples)}, last_ct={last_ct})")
    except RuntimeError as exc:
        exc.samples = samples
        raise


def cycle_regime(samples):
    """Interpret the per-stop dt of a TRACED row (honest labels)."""
    dts = [s["dt"] for s in samples]
    if not dts:
        return None
    srt = sorted(dts)
    p50 = srt[len(srt) // 2]
    frac_lt2 = sum(1 for d in dts if d < 0.002) / len(dts)
    if frac_lt2 > 0.8:
        regime = ("deadline catch-up: dt collapses near zero; fps_running "
                  "would overstate the paced rate (not observed)")
    elif p50 > 0.025:
        regime = ("stop-reply dominated: dt p50 far exceeds the 16.7 ms "
                  "frame period with a hard ~50 ms floor and no videoSync "
                  "response, so the cont->stop interval is bounded by stub "
                  "service latency; fps_running is the traced-cycle rate "
                  "(transport cap), NOT a free-run rate")
    elif 0.008 <= p50 <= 0.025:
        regime = ("per-frame pacing: dt centers on the frame period; "
                  "fps_running reflects the paced rate")
    else:
        regime = ("compute-bound: dt dominated by frame compute; "
                  "fps_running approximates an unthrottled free-run rate")
    return {"dt_p50_ms": round(p50 * 1000, 3),
            "dt_min_ms": round(min(dts) * 1000, 4),
            "dt_max_ms": round(max(dts) * 1000, 2),
            "frac_dt_lt_2ms": round(frac_lt2, 4),
            "regime": regime}


def one_boot(extra, label, phase):
    row = {"label": label, "mgba_args": extra or [], "phase": phase}
    try:
        with FixtureSession(STATE, mgba_args=extra, quiet=True) as s:
            g = s.g
            row["pid"] = s.pid
            probe = Probe(s, verbose=False)
            plan = probe.plan_identified_wait()
            if not plan:
                row["error"] = "no identified-wait plan"
                return row
            completed, _ = probe.commit_identified_wait(plan)
            if not completed:
                row["error"] = "commit failed"
                return row
            if phase == "N":
                try:
                    res = phase_N_traced(g)
                except RuntimeError as exc:
                    row["error"] = f"phase N: {exc}"
                    row["samples"] = []
                    return row
                row.update({k: v for k, v in res.items() if k != "samples"})
                row["samples"] = res["samples"]
                row["park_ct"] = res["samples"][0]["ct"] if res["samples"] else None
                row["fps_running"] = (round(res["N"] / res["running_s"], 3)
                                      if res["running_s"] else None)
                row["fps_wall"] = (round(res["N"] / res["wall_s"], 3)
                                   if res["wall_s"] else None)
                row["cycle"] = cycle_regime(res["samples"])
                row["t_start_iso"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(res["t_start_epoch"]))
                row["t_end_iso"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(res["t_end_epoch"]))
            else:
                try:
                    res = phase_T_free(g)
                except RuntimeError as exc:
                    row["error"] = f"phase T: {exc}"
                    row["samples"] = getattr(exc, "samples", [])
                    if row["samples"]:
                        row["first_ct"] = row["samples"][0].get("ct")
                    return row
                row.update({k: v for k, v in res.items() if k != "samples"})
                row["samples"] = res["samples"]
                row["D_min_s"] = round(res["D_min"], 3)
                row["D_max_s"] = round(res["D_max"], 3)
                row["polls"] = len(res["samples"])
                row["t_start_iso"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(res["t0"]))
                row["t_end_iso"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(res["t_end"]))
    except Exception as exc:      # noqa: BLE001 - record, continue
        row["error"] = str(exc)[:200]
    return row


def summarize(report):
    """Build per-mode summary from ALL rows; return (summary, failures,
    verdict).  Traced section: N + traced-cycle rate.  Free-run section:
    duration brackets -> fps brackets (the calibration A8 needs)."""
    gate_failures = []
    summary = {}
    for label in ("default", "vsync1"):
        n_rows = [r for r in report["rows"]
                  if r.get("phase") == "N"
                  and str(r.get("label", "")).startswith(label)]
        t_rows = [r for r in report["rows"]
                  if r.get("phase") == "T"
                  and str(r.get("label", "")).startswith(label)]
        entry = {"traced": {}, "freerun": {}}
        # -- traced rows -------------------------------------------------
        n_ok = [r for r in n_rows
                if not r.get("error") and r.get("N")
                and r.get("park_ct") is not None
                and PARK_TOLERANCE[0] <= r["park_ct"] <= PARK_TOLERANCE[1]
                and r.get("anomalies") == 0
                and (r.get("samples") or [{}])[-1].get("ct", 0) >= CT_FULL]
        if len(n_ok) < 2:
            gate_failures.append(f"{label}: {len(n_ok)}/{len(n_rows)} usable N rows")
        ns = [r["N"] for r in n_ok]
        tr = entry["traced"]
        tr["rows_usable"] = len(n_ok)
        tr["N_frames"] = ns
        if ns:
            tr["mean_N"] = round(sum(ns) / len(ns), 1)
            tr["N_spread_frac"] = round(
                (max(ns) - min(ns)) / (sum(ns) / len(ns)), 4) if len(ns) > 1 else 0.0
            if tr["N_spread_frac"] > N_SPREAD_GATE:
                gate_failures.append(
                    f"{label}: N spread {tr['N_spread_frac']} > {N_SPREAD_GATE}")
            tr["traced_cycle_fps"] = [r["fps_running"] for r in n_ok if r.get("fps_running")]
            p50s = [r["cycle"]["dt_p50_ms"] for r in n_ok if r.get("cycle")]
            if p50s:
                tr["dt_p50_ms"] = round(sum(p50s) / len(p50s), 2)
        # -- free-run rows ----------------------------------------------
        t_ok = [r for r in t_rows
                if not r.get("error") and r.get("D_min_s") is not None
                and r.get("D_max_s") is not None
                and r.get("first_ct") is not None
                and START_ENVELOPE[0] <= r["first_ct"] <= START_ENVELOPE[1]]
        if t_rows and len(t_ok) < len(t_rows):
            bad = [r.get("error") or f"first_ct={r.get('first_ct')}"
                   for r in t_rows if r not in t_ok]
            gate_failures.append(f"{label}: unusable T rows: {bad}")
        if not t_rows:
            gate_failures.append(f"{label}: no T rows run")
        fr = entry["freerun"]
        fr["rows_usable"] = len(t_ok)
        fr["D_min_s"] = [r["D_min_s"] for r in t_ok]
        fr["D_max_s"] = [r["D_max_s"] for r in t_ok]
        fr["first_ct"] = [r["first_ct"] for r in t_ok]
        fr["polls"] = [r["polls"] for r in t_ok if r.get("polls") is not None]
        if ns and t_ok:
            pool_lo, pool_hi = N_POOL.get(label, (min(ns), max(ns)))
            n_lo = min(pool_lo, min(ns))
            n_hi = max(pool_hi, max(ns))
            fr["N_range_used"] = [n_lo, n_hi]
            d_lo = min(r["D_min_s"] for r in t_ok)
            d_hi = max(r["D_max_s"] for r in t_ok)
            per_boot = []
            for r in t_ok:
                # per-boot bracket uses the mode's N range too
                lo = n_lo / r["D_max_s"]
                hi = n_hi / r["D_min_s"] if r["D_min_s"] else None
                per_boot.append([round(lo, 3), round(hi, 3) if hi else None])
            fps_lo = n_lo / d_hi
            fps_hi = n_hi / d_lo if d_lo else None
            fr["fps_bracket"] = [round(fps_lo, 3),
                                 round(fps_hi, 3) if fps_hi else None]
            fr["fps_bracket_per_boot"] = per_boot
            if fps_hi:
                fr["realtime_factor_vs_nominal"] = [
                    round(fps_lo / GBA_FPS, 3), round(fps_hi / GBA_FPS, 3)]
                # reproducibility: the two T boots' brackets must overlap
                if len(per_boot) >= 2:
                    (a_lo, a_hi), (b_lo, b_hi) = per_boot[0], per_boot[1]
                    if a_hi and b_hi and (max(a_lo, b_lo) > min(a_hi, b_hi)):
                        gate_failures.append(
                            f"{label}: T boot fps brackets do not overlap "
                            f"{per_boot}")
        summary[label] = entry

    # -- mechanism verdict from bracket separation ----------------------
    verdict = None
    d_br = summary.get("default", {}).get("freerun", {}).get("fps_bracket")
    v_br = summary.get("vsync1", {}).get("freerun", {}).get("fps_bracket")
    if d_br and v_br and d_br[1] and v_br[1]:
        r_worst = min(d_br[0], v_br[0]) / max(d_br[1], v_br[1])
        r_best = max(d_br[1], v_br[1]) / min(d_br[0], v_br[0])
        summary["mode_ratio_bracket"] = [round(r_worst, 3), round(r_best, 3)]
        if r_worst >= MECH_RATIO_GATE:
            verdict = ("videoSync=1 is a working speed control "
                       f"(worst-case separation {r_worst:.2f}x >= "
                       f"{MECH_RATIO_GATE})")
        elif r_best < MECH_RATIO_GATE:
            verdict = ("no tested mechanism changes gameplay speed "
                       f"materially (best-case separation {r_best:.2f}x < "
                       f"{MECH_RATIO_GATE})")
        else:
            verdict = ("indeterminate: fps brackets allow separation "
                       f"between {r_worst:.2f}x and {r_best:.2f}x")
    else:
        gate_failures.append("mechanism verdict unavailable: a mode lacks "
                             "an fps bracket")
    return summary, gate_failures, verdict


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    phases = "N,T"
    if "--phases" in argv:
        phases = argv[argv.index("--phases") + 1]
    want = [p.strip().upper() for p in phases.split(",")
            if p.strip() in ("N", "T")]
    summarize_only = "--summarize-only" in argv
    os.makedirs(OUT_DIR, exist_ok=True)

    report = None
    if os.path.exists(SPEED_JSON):
        try:
            with open(SPEED_JSON, encoding="utf-8") as fh:
                old = json.load(fh)
            if old.get("schema") in ("a8-speed/11", "a8-speed/12"):
                report = old
                # v10 rows predate the phase field: they are all traced
                for _r in report.get("rows", []):
                    if "phase" not in _r:
                        _r["phase"] = "T" if "D_min_s" in _r else "N"
                    # v10 named its regime dict 'pacing'
                    if "cycle" not in _r and "pacing" in _r:
                        _r["cycle"] = _r["pacing"]
        except (OSError, ValueError):
            report = None
    if report is None:
        report = {"schema": "a8-speed/12",
                  "rows": []}
    report["schema"] = "a8-speed/12"
    report["method"] = (
        "v12: phase N (traced, timestamped cont/stop per frame) gives the "
        "event frame count N with park/end CT verification; phase T "
        "(free-run) brackets the event duration in wall time from sparse "
        "timestamped polls, each followed by cont because a served read "
        "implicitly halts the core (DE-029) - the window [cont, read] is "
        "the running interval. drain_paired proves reply pairing first "
        "(DE-028). fps = N / D with a per-packet latency bound widening D; "
        "start/end samples retained with absolute epochs. No CT-rate "
        "baseline, no Lua console, no hardcoded prediction, no "
        "whole-battle extrapolation.")
    report["gbp_fps_nominal"] = GBA_FPS
    report["ct_datum"] = (f"single 2-byte reads at 0x{CT_BASE:08X} (coherent "
                          "across the cycle; v9)")
    report["latency_bound_s"] = LATENCY_BOUND_S
    report["gates"] = {"n_spread_per_mode": N_SPREAD_GATE,
                       "park_tolerance": list(PARK_TOLERANCE),
                       "start_envelope": list(START_ENVELOPE),
                       "mechanism_ratio": MECH_RATIO_GATE}
    report.setdefault("phases_run", [])

    mode_args = {"default": None, "vsync1": ["-C", "videoSync=1"]}
    existing = {r.get("label") for r in report["rows"]}
    plan_list = []
    if not summarize_only:
        for m, extra in mode_args.items():
            for ph in want:
                for k in (1, 2):
                    # N rows keep the v10 label shape so an existing run merges
                    name = f"{m}-{k}" if ph == "N" else f"{m}-T{k}"
                    if name in existing:
                        continue
                    plan_list.append((name, extra, ph))
    for name, extra, ph in plan_list:
        row = one_boot(extra, name, ph)
        report["rows"].append(row)
        report["phases_run"].append(ph)
        got = row.get("N") or row.get("D_min_s")
        print(f"  {name}[{ph}]: {got}"
              f"{', err=' + row['error'] if row.get('error') else ''}",
              flush=True)
        with open(SPEED_JSON, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    summary, gate_failures, verdict = summarize(report)
    report["summary"] = summary
    report["mechanism_verdict"] = verdict
    report["gate_failures"] = gate_failures
    with open(SPEED_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(summary, indent=2))
    ok = not gate_failures
    print(f"A8-SPEED {'PASS' if ok else 'FAIL'}; verdict: {verdict}")
    if gate_failures:
        print("gate failures: " + "; ".join(gate_failures))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
