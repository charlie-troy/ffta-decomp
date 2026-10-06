"""C3 phase B manual layer: commit a real identified move as the player.

Runs AFTER leg 1 paused and left the emulator alive (run.json's
manual_handoff records the pid). The A5.1 entry point that produces that
pause deliberately is `run_autobattle.py --pause-at-boundary`, which stops
at the identified player menu with the fresh menu left OPEN and no
automation input issued. This script:
  1. verifies the handed-off pid is alive and matches the receipt,
  2. attaches ONE held monitor connection and samples it with the
     take-22 law: interrupt -> exactly ONE read -> cont per observation
     (a second read per interrupt times out; the connection is held and
     closed cleanly so `--resume` leg 2 can adopt the emulator),
  3. waits for the player-command window: Marche's roster CT AND the
     command cursor byte both stable across consecutive samples. The CT
     value itself is NOT a discriminator — live observation (c3-live-b1,
     2026-09-19) shows menus park wherever the engine froze them (188 at
     turn-1 boundaries, 580 after a committed move) — frozen-while-
     charging is the signature; the echo probe below then proves the
     menu is actually answering before any commit input fires,
  4. navigates the cursor to Move(0) with echo-verified window keys
     (one DOWN/UP must visibly move the byte before the next press; no
     press is ever confirmed while the cursor reads Status(3)),
  5. commits a real move through the WINDOW channel (SendInput, no stub
     writes): A (open target at Marche's tile) -> step one legal
     direction (echo-verified on the target-cursor byte) -> A (confirm
     at the reached target). The walk animates and the command menu
     re-opens with the turn still open — the roster tile only updates
     at turn close — so the layer then
  6. closes the turn with a manual Wait (cursor to Wait, echo-verified,
     A), verifies the roster tile settled on the walked tile, writes a
     receipt and LEAVES THE EMULATOR ALIVE for `--resume` leg 2.

Exit codes: 0 = the manual move committed (leg 2 may resume the battle),
1 = the manual layer failed (leg 2 must not run).
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from probe_control_handoff import (CMD_CURSOR, TARGET_X,  # noqa: E402
                                   ROSTER, STRIDE, OFF_CT)

OFF_TILE_X, OFF_TILE_Y = 0xF6, 0xF7   # A2.5 contract: roster tile bytes
OFF_HP = 0x18                         # u16 current hp
OFF_SIDE = 0x28                       # u16 side word (bit 15 = 0x8000 group)
OFF_ID = 0x104                        # u8 unit id (0xFF = sentinel/scratch)
SIDE_BIT = 0x8000
REC_LEN = 0x108                       # roster stride (fixture_guard.STRIDE)
UNITS = 8                             # records the verified fixtures cover
KEYINPUT = 0x03007F98                 # active-low key register (diagnostic)


class Desync(Exception):
    """The stub answered with shifted/stale bytes: reconnect."""

OUT_DEFAULT = os.path.join("outputs", "autobattle")

MOVE_CURSOR, WAIT_CURSOR, STATUS_CURSOR = 0, 2, 3


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def capture(pid, path):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "tools/capture_window.ps1",
                        "-ProcId", str(pid), "-Out", path],
                       capture_output=True, text=True, timeout=60)
    if "saved" not in (r.stdout or ""):
        raise RuntimeError(f"capture failed: {r.stdout!r} {r.stderr!r}")
    return path


def sendkey(pid, keys):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "tools/sendkey_window.ps1",
                        "-ProcId", str(pid), "-Keys", keys],
                       capture_output=True, text=True, timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    if "sent" not in out:
        raise RuntimeError(f"sendkey failed: {out!r}")
    return out.strip()


def u16le(b):
    return int.from_bytes(b, "little") if b is not None and len(b) >= 2 else None


class Monitor:
    """Held-connection sampler (take-22 law, hardened 2026-09-20).

    mGBA 0.10.5's stub serves ONE client per session; after interrupt()
    exactly ONE read_mem answers (a second times out), and a client that
    dies mid-reply wedges the stub for the session. The live-read law is
    therefore: hold one connection and cycle interrupt -> ONE read ->
    cont. A dirty cycle drops the connection once and retries on a fresh
    one; close() must run before handoff so leg 2 can adopt.

    Hardening after the 2026-09-20 desync: the stub can answer a read
    with a LATE stale packet, leaving the packet buffer misaligned —
    every later read then returns shifted garbage (4bpp-tile-like bytes)
    with no exception. `sample()` takes the window's fields as three
    SEPARATE interrupt→read→cont cycles (the take-22 law: one read per
    interrupt) and cross-validates them (cursor <= 3, CT <= 1000, tile
    < 64 and nonzero). A sample where every field is implausible marks
    the stream desynced: reconnect and take the whole sample again
    instead of trusting partial data.
    """

    def __init__(self, port, timeout=4.0):
        self.port = port
        self.timeout = timeout
        self.g = None
        self.reads = 0
        self.faults = 0
        self.reconnects = 0
        self.desyncs = 0

    def _ensure(self):
        if self.g is None:
            from trace_mgba import Gdb
            self.g = Gdb("127.0.0.1", self.port, timeout=self.timeout)
        return self.g

    def sample(self):
        """The window fields from three one-read cycles, cross-validated.
        A single implausible field reads as None; a fully implausible
        sample raises Desync so the caller reconnects."""
        for _attempt in (0, 1):
            try:
                cur_b = self.read(CMD_CURSOR, 1)
                tgt_b = self.read(TARGET_X, 2)
                sl6 = self.read(ROSTER + STRIDE * 6, 16)
                cur = cur_b[0] if cur_b and cur_b[0] <= 3 else None
                tgt = None
                if tgt_b and 0 < tgt_b[0] < 64 and 0 < tgt_b[1] < 64:
                    tgt = (tgt_b[0], tgt_b[1])
                ct = u16le(sl6[OFF_CT:OFF_CT + 2]) if sl6 else None
                if ct is not None and ct > 1000:
                    ct = None
                tile = None
                if sl6:
                    x, y = sl6[OFF_TILE_X], sl6[OFF_TILE_Y]
                    if 0 < x < 64 and 0 < y < 64:
                        tile = (x, y)
                if cur is None and ct is None and tile is None:
                    # every field implausible: the stream is shifted —
                    # reconnect and take the whole sample again
                    self.desyncs += 1
                    raise Desync("all fields implausible: desynced stream")
                return {"cursor": cur, "target": tgt, "ct": ct,
                        "tile": tile}
            except Desync:
                self._drop()
                time.sleep(1.0)
        return None

    def read(self, addr, length=1):
        """One raw observation: interrupt, ONE read, cont. bytes | None.

        Unvalidated — only sample() carries the cross-validation law.
        Prefer sample() at the window; read() is for diagnostics.
        """
        for _attempt in (0, 1):
            try:
                g = self._ensure()
                g.interrupt()
                try:
                    last = g.read_mem(addr, length)
                finally:
                    try:
                        g.cont()
                    except Exception:
                        pass
                self.reads += 1
                self.faults = 0
                return bytes(last) if last is not None else None
            except Exception:
                self._drop()
                self.faults += 1
                self.reconnects += 1
                time.sleep(1.0)
        return None

    def _drop(self):
        try:
            if self.g is not None:
                self.g.close()
        except Exception:
            pass
        self.g = None

    def detach(self):
        """Leave the core RUNNING for the next client, then close.

        DE-029: a served read halts the core and only `c` resumes it, so a
        client that disconnects right after a read can hand the next client
        a halted target — and a client that dies mid-reply wedges the stub
        for the session (take-22). The handoff therefore resumes explicitly
        before it lets go.
        """
        try:
            if self.g is not None:
                self.g.cont()
                time.sleep(0.3)
        except Exception:
            pass
        self._drop()

    def close(self):
        self._drop()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--receipt", required=True,
                    help="leg 1's run.json (must contain manual_handoff)")
    ap.add_argument("--out-dir", default=None,
                    help="receipt directory (default: receipt's own dir)")
    ap.add_argument("--window-timeout", type=float, default=300.0,
                    help="seconds to wait for the player-command window")
    args = ap.parse_args(argv)

    leg1 = json.load(open(args.receipt, encoding="utf-8"))
    handoff = leg1.get("manual_handoff") or {}
    pid = handoff.get("pid")
    if not pid:
        print("FAIL: the leg-1 receipt records no manual_handoff pid")
        return 2
    if leg1.get("final_state") != "paused":
        print(f"FAIL: leg 1 ended {leg1.get('final_state')!r}, not "
              f"paused — nothing was handed off")
        return 2
    if not pid_alive(pid):
        print(f"FAIL: handed-off emulator pid {pid} is gone")
        return 2

    out_dir = args.out_dir or os.path.dirname(
        os.path.abspath(args.receipt))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    log_lines = []
    trace = []

    def say(msg):
        line = f"[{time.time() - t0:6.1f}s] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    def finish(code, **extra):
        mon.detach()
        try:
            capture(pid, os.path.join(out_dir, "manual-after.png"))
        except Exception as exc:                        # noqa: BLE001
            say(f"capture failed: {exc}")
        receipt = {
            "schema": "c3-manual-layer/2",
            "pid": pid,
            "port": port,
            "leg1_final_state": leg1.get("final_state"),
            "menu_open_at_s": opened_at,
            "owner_slot": owner_slot,
            "owner_rule": ("target cursor == the unique live unit's own tile, "
                           "unchanged across three samples with a stable CT "
                           "and a known command byte"),
            "tile_before": list(tile0) if tile0 else None,
            "tile_after": list(tile_now) if tile_now else None,
            "manual_move_committed": moved,
            "keys_sent": keys_sent,
            "input_channel": "window SendInput (no stub writes)",
            "monitor_reads": mon.reads,
            "monitor_faults": mon.faults,
            "monitor_reconnects": mon.reconnects,
            "trace": trace,
            **extra,
        }
        with open(os.path.join(out_dir, "manual-layer.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2)
        with open(os.path.join(out_dir, "manual-layer.log"), "w",
                  encoding="utf-8") as fh:
            fh.write("\n".join(log_lines) + "\n")
        return code

    port = int(handoff.get("port") or 2345)
    mon = Monitor(port)
    keys_sent = []
    opened_at = None
    tile0 = tile_now = None
    moved = False
    owner_slot = None                 # identified from the roster, never fixed
    owner_ct0 = None

    def cursor():
        b = mon.read(CMD_CURSOR)
        return b[0] if b is not None and b[0] <= 3 else None

    def target():
        """Move-target cursor (x, y); only meaningful inside target mode."""
        xy = mon.read(TARGET_X, 2)
        if xy is None or len(xy) < 2:
            return None
        x, y = xy[0], xy[1]
        if not (0 <= x < 64 and 0 <= y < 64) or (x, y) == (0, 0):
            return None
        return (x, y)

    def slot_tile(slot):
        xy = mon.read(ROSTER + STRIDE * slot + OFF_TILE_X, 2)
        if xy is None or len(xy) < 2:
            return None
        x, y = xy[0], xy[1]
        if not (0 <= x < 64 and 0 <= y < 64) or (x, y) == (0, 0):
            return None
        return (x, y)

    def slot_ct(slot):
        return u16le(mon.read(ROSTER + STRIDE * slot + OFF_CT, 2))

    def roster_scan():
        """Every record's OWN tile/CT (one read per record, 0x108 < 512).

        The ownership law needs ALL of them: a fixed slot is the same guess
        as a fixed name, and A4/DE-030 showed CT cannot name an actor on a
        multi-ally fixture.
        """
        rows = []
        for slot in range(UNITS):
            raw = mon.read(ROSTER + STRIDE * slot, REC_LEN)
            if raw is None or len(raw) < REC_LEN:
                rows.append({"slot": slot, "readable": False})
                continue
            x, y = raw[OFF_TILE_X], raw[OFF_TILE_Y]
            rows.append({
                "slot": slot, "readable": True, "x": x, "y": y,
                "tile": (x, y) if 0 < x < 64 and 0 < y < 64 else None,
                "hp": u16le(raw[OFF_HP:OFF_HP + 2]),
                "max_hp": u16le(raw[OFF_HP + 2:OFF_HP + 4]),
                "ct": u16le(raw[OFF_CT:OFF_CT + 2]),
                "side": u16le(raw[OFF_SIDE:OFF_SIDE + 2]),
                "id": raw[OFF_ID],
            })
        return rows

    def fresh_menu_owner(rows, tgt):
        """The unique unit whose OWN tile the target cursor sits on.

        C2/A4 law: a freshly opened player menu parks the move cursor on the
        owner's own tile. Uniqueness plus the two-sample stability gate is
        what makes the owner IDENTIFIED here; the destination check after
        the commit is the independent falsifier.
        """
        if tgt is None:
            return None
        matches = [r for r in rows
                   if r.get("readable") and r.get("tile") == tgt
                   and (r.get("hp") or 0) > 0 and (r.get("max_hp") or 0) > 0
                   and r.get("id") not in (None, 0xFF)]
        if len(matches) != 1:
            return None
        return matches[0]

    def keyinput():
        v = u16le(mon.read(KEYINPUT, 2))
        # active-low: 0x3FF = nothing pressed
        return v

    def ct():
        return slot_ct(owner_slot) if owner_slot is not None else None

    def tile():
        return slot_tile(owner_slot) if owner_slot is not None else None

    say(f"adopted handed-off emulator pid={pid} port={port} (read-only "
        f"monitor; stub writes=0)")

    # -- 3. wait for the player-command window --------------------------
    # The handoff precondition is a PARKED PLAYER MENU: exactly one live
    # unit holds the target cursor on its own tile, the command byte is a
    # known menu value, and that unit's tile and CT are unchanged across
    # three samples ~3 s apart. A running battle can serve a stale copy of
    # all three at once, so the gate is evidence, not proof — the
    # destination check after the commit is the proof.
    deadline = time.time() + args.window_timeout
    prev = None
    stable_polls = 0
    while time.time() < deadline:
        # A pair 350 ms apart can catch an enemy animation with a frozen
        # player copy. Ride out that transient before probing a live menu.
        time.sleep(3.0)
        rows = roster_scan()
        sample = {"t": round(time.time() - t0, 1),
                  "cursor": cursor(), "target": target(),
                  "keyinput": keyinput(),
                  "slots": [{k: r.get(k) for k in
                             ("slot", "readable", "x", "y", "hp", "ct",
                              "side", "id")} for r in rows]}
        owner = fresh_menu_owner(rows, sample["target"])
        sample["owner_slot"] = owner["slot"] if owner else None
        sample["owner_tile"] = [owner["x"], owner["y"]] if owner else None
        sample["owner_ct"] = owner["ct"] if owner else None
        stable = bool(
            owner is not None and prev is not None
            and prev.get("owner_slot") == owner["slot"]
            and prev.get("owner_ct") == owner["ct"]
            and prev.get("owner_tile") == [owner["x"], owner["y"]]
            and prev.get("cursor") == sample["cursor"]
            and sample["cursor"] in (0, 1, 2)
            and sample["target"] == (owner["x"], owner["y"]))
        sample["stable"] = stable
        stable_polls = stable_polls + 1 if stable else 0
        trace.append(sample)
        if stable_polls >= 2:
            opened_at = sample["t"]
            owner_slot = owner["slot"]
            owner_ct0 = owner["ct"]
            tile0 = (owner["x"], owner["y"])
            break
        prev = sample
    if opened_at is None:
        say("FAIL: no parked player menu within "
            f"{args.window_timeout:.0f}s (last sample: "
            f"{trace[-1] if trace else None})")
        return finish(1, menu_open=False)
    say(f"parked player menu at +{opened_at}s: owner slot {owner_slot}, "
        f"own tile {tile0}, ct={owner_ct0}, cmd byte "
        f"{trace[-1].get('cursor')}")
    # Board snapshot BEFORE any window input: the destination claim is
    # compared against this, so a pre-existing position cannot be mistaken
    # for evidence that our input moved the unit.
    pre_scan = roster_scan()
    try:
        capture(pid, os.path.join(out_dir, "manual-window.png"))
    except Exception as exc:                        # noqa: BLE001
        say(f"capture failed: {exc}")

    def echo_key(key, expect_change=True, settle=2.0):
        """Send one window key; require the COMMAND cursor byte to move."""
        pre = cursor()
        sendkey(pid, f"{key}:200")
        keys_sent.append(key)
        end = time.time() + settle
        post = pre
        while time.time() < end:
            time.sleep(0.35)
            post = cursor()
            if post is not None and post != pre:
                break
        trace.append({"t": round(time.time() - t0, 1), "key": key,
                      "stage": "command-echo", "pre": pre, "post": post})
        if expect_change and (post is None or post == pre):
            say(f"echo FAIL: {key} did not move the command cursor "
                f"({pre} -> {post}); UI not answering")
            return None
        return post

    # -- 4/5. commit the move through the window -------------------------
    # Turn-START law (c3-live-b2, 2026-09-20): FFTA opens a unit's turn in
    # MOVE-TARGET MODE (ring under the unit, no command menu; cmd byte
    # sticky 0), and the command menu only exists after a move confirm
    # (the re-open law). But a FRESH COMMAND MENU also parks the target
    # copy on the owner's tile (A4/A5.1), so "target == own tile" cannot
    # name the mode — and a blocked direction (map edge, occupant) answers
    # NEITHER byte, which the old single-DOWN probe misread as a dead UI
    # and aborted on. Probe until some direction moves some cursor and let
    # the byte that answered name the mode; the first target-mode answer
    # IS the step, so no press is wasted.
    mode = None
    stepped = None
    for direction in ("DOWN", "RIGHT", "UP", "LEFT"):
        pre_cmd, pre_tgt = cursor(), target()
        sendkey(pid, f"{direction}:200")
        keys_sent.append(direction)
        time.sleep(2.0)
        post_cmd, post_tgt = cursor(), target()
        trace.append({"t": round(time.time() - t0, 1), "stage": "probe",
                      "dir": direction, "cmd": [pre_cmd, post_cmd],
                      "target": [list(pre_tgt) if pre_tgt else None,
                                 list(post_tgt) if post_tgt else None]})
        if post_cmd is not None and pre_cmd is not None and post_cmd != pre_cmd:
            mode = "command"
            break
        if post_tgt is not None and pre_tgt is not None and post_tgt != pre_tgt:
            mode = "target"
            stepped = post_tgt
            break
    if mode is None:
        say("FAIL: no direction moved either cursor — the UI is not "
            "answering; no confirmation attempted")
        return finish(1, menu_open=True,
                      abort="no cursor answered the mode probe")
    say(f"{mode} mode verified: the {direction} probe moved "
        + ("the command cursor" if mode == "command" else "the target cursor")
        + (f" to {stepped}" if stepped else ""))

    if mode == "command":
        cur = cursor()
        nav = 0
        while cur != MOVE_CURSOR and nav < 4:
            nav += 1
            nxt = echo_key("UP" if cur == 1 else "DOWN")
            if nxt is None:
                return finish(1, menu_open=True,
                              abort="cursor echo failed during navigation")
            cur = nxt
        if cur != MOVE_CURSOR:
            return finish(1, menu_open=True, abort="navigation exhausted")
        sendkey(pid, "A:200")                   # open target mode
        keys_sent.append("A")
        time.sleep(2.5)
        say(f"command menu at Move; opened target at {target()}")
        try:
            capture(pid, os.path.join(out_dir, "manual-target-open.png"))
        except Exception as exc:                # noqa: BLE001
            say(f"capture failed: {exc}")
        # step one tile: try each direction, echo-verified on the target-
        # cursor byte (a blind press into an unreachable tile leaves the
        # byte frozen — the live map decides which directions are legal)
        for direction in ("DOWN", "RIGHT", "UP", "LEFT"):
            pre = target()
            sendkey(pid, f"{direction}:200")
            keys_sent.append(direction)
            time.sleep(2.0)
            post = target()
            trace.append({"t": round(time.time() - t0, 1), "stage": "step",
                          "dir": direction, "pre": pre, "post": post})
            if post is not None and pre is not None and post != pre:
                stepped = post
                say(f"stepped {direction}: target {pre} -> {post}")
                break
            say(f"{direction} did not move the target cursor "
                f"({pre} -> {post}); trying next direction")
    else:
        try:
            capture(pid, os.path.join(out_dir, "manual-target-open.png"))
        except Exception as exc:                # noqa: BLE001
            say(f"capture failed: {exc}")

    try:
        capture(pid, os.path.join(out_dir, "manual-step.png"))
    except Exception as exc:                        # noqa: BLE001
        say(f"capture failed: {exc}")

    if stepped is None or stepped == tile0:
        say("FAIL: the step did not move the target cursor off the owner's "
            "tile — backing out (B) and leaving the battle intact")
        sendkey(pid, "B:200")                   # cancel target mode
        keys_sent.append("B")
        return finish(1, menu_open=True, abort="step unreachable")

    sendkey(pid, "A:200")                       # confirm at reached target
    keys_sent.append("A")

    # the walk animates, then the command menu re-opens (probe6 law) with
    # the turn STILL open — the roster tile only updates at turn close,
    # so verification waits for the re-opened menu, closes the turn with
    # a manual Wait, and only then checks the roster tile.
    deadline = time.time() + 45.0
    reopened = None
    prev = None
    while time.time() < deadline:
        time.sleep(0.5)
        c, t = cursor(), ct()
        if (prev is not None and c is not None and t is not None
                and c == prev[0] and t == prev[1]):
            reopened = prev
            break
        prev = (c, t)
    if reopened is None:
        say("FAIL: the command menu never re-opened after the walk")
        return finish(1, menu_open=True, abort="no menu re-open after walk")
    say(f"command menu re-opened (cursor={reopened[0]}, ct={reopened[1]}) "
        f"— closing the turn with a manual Wait")

    c = cursor()
    nav = 0
    while c != WAIT_CURSOR and nav < 4:
        nav += 1
        nxt = echo_key("DOWN" if (c is not None and c < WAIT_CURSOR) else "UP")
        if nxt is None:
            return finish(1, menu_open=True, abort="wait-nav echo failed")
        c = nxt
    if c != WAIT_CURSOR:
        return finish(1, menu_open=True, abort="cursor never reached Wait")
    # Wait = A (facing picker) + A (confirm): the picker sub-menu holds the
    # turn open — the orphaned-emulator probe proved a lone A leaves the CT
    # frozen (facing unconfirmed), and A#2 commits with CT -> 0 + charging.
    sendkey(pid, "A:200")                       # open Wait's facing picker
    keys_sent.append("A")
    time.sleep(2.0)
    sendkey(pid, "A:200")                       # confirm facing: turn closes
    keys_sent.append("A")

    # The roster tile mirrors the walked tile only at the NEXT turn close,
    # so the committed proof is the engine's own turn-close signature: the
    # CT charging again (a parked menu holds a frozen value indefinitely).
    # The tile check (== stepped target) remains as the moved-direction
    # evidence once the next boundary settles it.
    deadline = time.time() + 45.0
    committed = False
    prev = ct()
    while time.time() < deadline:
        time.sleep(2.0)
        now = ct()
        if now != prev:
            committed = True
            break
        prev = now
    if not committed:
        say("FAIL: CT never left the parked value after the Wait commit "
            "(turn did not close)")
        return finish(1, menu_open=True, abort="wait commit did not close "
                                                "the turn")
    say(f"manual turn CLOSED via window input (CT {prev} -> {now}, "
        f"charging)")

    # settle window: give the engine until the next turn close to mirror the
    # walked tile into the roster (observed lag), then record what holds
    deadline = time.time() + 60.0
    tile_now = tile()
    while time.time() < deadline:
        tile_now = tile()
        if tile_now == stepped:
            break
        time.sleep(2.0)
    say(f"owner slot {owner_slot} tile {tile0} -> {tile_now} "
        f"({'mirrored' if tile_now == stepped else 'not yet mirrored at turn close'})")

    # Independent, whole-board destination check. CT progress alone is NOT
    # evidence: the refuted pre-A5.1 helper called it a PASS while the tile
    # never moved. The claim is precise — the identified owner walked to the
    # tile our window input stepped to, and no OTHER unit on the owner's
    # side changed tile (the enemy phase may legitimately move enemies, so
    # only the owner's side is claimed).
    post_scan = roster_scan()
    before_tiles = {r["slot"]: (r["x"], r["y"])
                    for r in pre_scan if r.get("readable")}
    after_tiles = {r["slot"]: (r["x"], r["y"])
                   for r in post_scan if r.get("readable")}
    sides = {r["slot"]: r.get("side") for r in pre_scan if r.get("readable")}
    moved_slots = sorted(s for s in before_tiles
                         if before_tiles[s] != after_tiles.get(s))
    owner_side = sides.get(owner_slot)
    same_side_moved = sorted(s for s in before_tiles
                             if s != owner_slot and sides.get(s) == owner_side
                             and before_tiles[s] != after_tiles.get(s))
    reached = after_tiles.get(owner_slot)
    board_ok = (reached == tuple(stepped) and stepped != tile0
                and not same_side_moved)
    moved = board_ok                    # the receipt's only move claim
    say(f"board check: owner slot {owner_slot} at {reached} "
        f"(stepped {tuple(stepped)}); moved slots {moved_slots}; "
        f"other same-side slots moved {same_side_moved}")
    extra = {"owner_tile_before": list(tile0) if tile0 else None,
             "owner_tile_after": list(reached) if reached else None,
             "stepped_target": list(stepped),
             "moved_slots": moved_slots,
             "other_same_side_moved": same_side_moved,
             "destination_verified_by":
                 "roster tile delta across the manual turn (owner walked to "
                 "the stepped target; no other same-side slot moved)"}

    if not board_ok:
        say("FAIL: window input produced CT progress but the selected move "
            "did not reach its destination; manual action remains unverified")
        return finish(1, menu_open=True, observed_ct_progress=True,
                      manual_turn_committed=None,
                      abort="selected manual destination not verified",
                      **extra)
    say("PASS: manual move destination verified after window Move/Wait; "
        "emulator left alive for --resume leg 2")
    return finish(0, menu_open=True, manual_turn_committed=True, **extra)


if __name__ == "__main__":
    sys.exit(main())
