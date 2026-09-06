"""Interactive steering over the mGBA GDB stub (single-client constraint).

The stub accepts one client per emulator session, so this process connects
once and stays: each loop it pauses the CPU, renders the screen, writes a
status file, then waits for a command in the steer file and executes it.

Command file protocol (outputs/mgba-steer/cmd.json), rewritten per command:
    {"action": "keys", "keys": ["A", "START"], "hold": 0.25, "rest": 0.2}
    {"action": "mash", "keys": ["A"], "on": 0.08, "off": 0.18,
     "total": 8.0}              # repeat on/off presses for `total` seconds
    {"action": "run", "seconds": 2.0}          # advance unattended
    {"action": "seq", "steps": [{...}, ...]}    # run steps in order
    {"action": "diag"}                          # write BG/OAM/text diagnostics
    {"action": "quit"}
Keys: A B Select Start Right Left Up Down (bit names from gba_drive).

Status file (outputs/mgba-steer/status.json), rewritten each step:
    {"step": N, "png": path, "disp": "...", "text": "...", "poll_hits": K,
     "note": "..."}
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_drive import Session, A, B, SEL, START, RIGHT, LEFT, UP, DOWN  # noqa: E402
from gba_render import Renderer, write_png  # noqa: E402

KEYS = {"A": A, "B": B, "SEL": SEL, "START": START, "RIGHT": RIGHT,
        "LEFT": LEFT, "UP": UP, "DOWN": DOWN}
OUT = os.path.join("outputs", "mgba-steer")
IO = 0x04000000
POLL = 0x0800048A
POLL_ORIG = "111c5940"


def u16(b):
    return int.from_bytes(b, "little")


def poll_activity(s, seconds):
    """Count how often the key-poll site runs while the CPU is free."""
    hits = 0
    s.gdb.send(f"Z0,{POLL:x},2")
    deadline = time.time() + seconds
    s.gdb.cont()
    try:
        while time.time() < deadline:
            pkt = s.gdb._read_packet()
            if not pkt or pkt[:1] not in ("S", "T"):
                break
            hits += 1
            s.gdb.cont()
    except Exception:
        pass
    s.gdb.send(f"z0,{POLL:x},2")
    return hits


def render(s, path):
    rgb = Renderer(s).render()
    write_png(path, rgb)
    return rgb


def mask_of(cmd):
    mask = 0
    for k in cmd.get("keys", ["A"]):
        mask |= KEYS.get(k.upper(), 0)
    return mask


def diag(s, path):
    import gba_screen as scr
    lines = []
    def out(*a):
        lines.append(" ".join(str(x) for x in a))
    mode, blank, bgs, disp = scr.bg_config(s.gdb)
    out(f"DISPCNT={disp:#06x} mode={mode} forced_blank={blank}")
    for i, bg in enumerate(bgs):
        if bg["enabled"]:
            out(f" BG{i}: prio={bg['priority']} colors="
                f"{'256' if bg['colors'] else '16'} size={bg['size']} "
                f"charbase={bg['char_base']} scrbase={bg['screen_base']}")
    # OAM census (OBJ layer): how many sprites, where, and tile/size.
    oam = s.read_mem(0x07000000, 0x400) or b""
    objs = []
    for k in range(128):
        at = oam[k * 8:k * 8 + 8]
        if len(at) < 8:
            break
        a0 = int.from_bytes(at[0:2], "little")
        a1 = int.from_bytes(at[2:4], "little")
        a2 = int.from_bytes(at[4:6], "little")
        if a0 == 0 and a1 == 0 and a2 == 0:
            continue
        y = a0 & 0xFF
        x = a1 & 0x1FF
        tile = a2 & 0x3FF
        objs.append(f"o{k}: y={y} x={x} tile={tile:#x} "
                    f"a0={a0:#06x} a1={a1:#06x} a2={a2:#06x}")
    out(f"OBJ count={len(objs)}")
    for o in objs[:40]:
        out("  " + o)
    # Text tilemap grid + distinct glyphs for each enabled text BG.
    for i, bg in enumerate(bgs):
        if not bg["enabled"]:
            continue
        cnt = bg["cnt"]
        colors = (cnt >> 5) & 1
        mw, mh = scr.text_map_geometry(cnt)
        map_base = 0x06000000 + bg["screen_base"] * 0x800
        cb = 0x06000000 + bg["char_base"] * (0x8000 if colors else 0x4000)
        md = s.read_mem(map_base, mw * mh * 2) or b""
        entries = [int.from_bytes(md[k * 2:k * 2 + 2], "little")
                   for k in range(len(md) // 2)]
        used = sorted({(e & 0x1FF) if colors else (e & 0x3FF)
                       for e in entries if e})
        out(f"--- BG{i} map {mw}x{mh} {colors and '256' or '16'}-color "
            f"{len(used)} distinct tiles")
        # print a compact tile grid (only first 32 rows)
        for row in range(min(mh, 32)):
            cells = []
            for col in range(mw):
                e = entries[row * mw + col]
                cells.append(" ." if not e else
                             f"{(e & 0x1FF) if colors else (e & 0x3FF):3x}")
            out("  " + " ".join(cells))
        if len(used) <= 80:
            for t in used:
                tb = 64 if colors else 32
                d = s.read_mem(cb + t * tb, tb) or b""
                rows = []
                for ty in range(8):
                    ln = []
                    for tx in range(8):
                        if colors:
                            c = d[ty * 8 + tx]
                        else:
                            nib = d[ty * 4 + tx // 2]
                            c = (nib >> ((tx & 1) * 4)) & 0xF
                        ln.append("#" if c else ".")
                    rows.append("".join(ln))
                out(f"  tile {t:#x}:")
                for r in rows:
                    out("    " + r)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"diag wrote {path} ({len(lines)} lines)", flush=True)


def do_keys(s, cmd):
    hold = float(cmd.get("hold", 0.25))
    rest = float(cmd.get("rest", 0.2))
    s.set_mask(mask_of(cmd))
    s.resume(hold)
    s.set_mask(0)
    if rest:
        s.resume(rest)
    print(f"pressed {cmd.get('keys')} for {hold}s", flush=True)


def do_mash(s, cmd):
    on = float(cmd.get("on", 0.08))
    off = float(cmd.get("off", 0.18))
    total = float(cmd.get("total", 6.0))
    mask = mask_of(cmd)
    start = time.time()
    n = 0
    while time.time() - start < total:
        s.set_mask(mask)
        s.resume(min(on, total - (time.time() - start)))
        s.set_mask(0)
        if time.time() - start >= total:
            break
        s.resume(min(off, total - (time.time() - start)))
        n += 1
    print(f"mashed {cmd.get('keys')} {n} cycles over {total}s", flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    s = Session("127.0.0.1", 2345, timeout=15)
    step = 0
    try:
        while True:
            # Pause and snapshot the screen.
            try:
                s.gdb.interrupt()
            except Exception:
                pass
            disp = u16(s.read_mem(IO, 2) or b"\0\0")
            png = os.path.join(OUT, f"step-{step:03d}.png")
            try:
                render(s, png)
            except Exception as exc:
                print(f"render failed: {exc}", flush=True)
                png = None
            # Free-run briefly to observe poll activity and let idle screens
            # settle, then pause again for the command wait.
            try:
                hits = poll_activity(s, 1.0)
            except Exception as exc:
                print(f"poll probe failed: {exc}", flush=True)
                hits = -1
            status = {"step": step, "png": png, "disp": f"{disp:#06x}",
                      "mode": disp & 7, "poll_hits_per_s": hits,
                      "time": time.time()}
            with open(os.path.join(OUT, "status.json"), "w") as fh:
                json.dump(status, fh, indent=1)
            print(f"step {step}: disp={disp:#06x} polls/s={hits} "
                  f"png={png}", flush=True)

            # Wait for a command.
            cmd_path = os.path.join(OUT, "cmd.json")
            if os.path.exists(cmd_path):
                os.remove(cmd_path)
            cmd = None
            deadline = time.time() + 600
            while time.time() < deadline:
                if os.path.exists(cmd_path):
                    try:
                        with open(cmd_path) as fh:
                            cmd = json.load(fh)
                        os.remove(cmd_path)
                        break
                    except (ValueError, OSError):
                        time.sleep(0.2)
                time.sleep(0.2)
            if cmd is None:
                print("steer timeout: no command for 600 s", flush=True)
                break
            action = cmd.get("action", "keys")
            if action == "quit":
                break
            if action == "diag":
                diag(s, os.path.join(OUT, f"diag-{step:03d}.txt"))
                step += 1
                continue
            if action == "seq":
                for sub in cmd.get("steps", []):
                    if sub.get("action") == "keys":
                        do_keys(s, sub)
                    elif sub.get("action") == "mash":
                        do_mash(s, sub)
                    elif sub.get("action") == "run":
                        s.resume(float(sub.get("seconds", 1.0)))
                print(f"seq done", flush=True)
                step += 1
                continue
            if action == "mash":
                do_mash(s, cmd)
                step += 1
                continue
            if action == "run":
                s.resume(float(cmd.get("seconds", 1.0)))
                print(f"ran {cmd.get('seconds', 1.0)} s", flush=True)
                step += 1
                continue
            # action == keys
            do_keys(s, cmd)
            step += 1
    finally:
        try:
            s.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
