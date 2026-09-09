"""Does a r1-patched press actually move the battle-menu cursor?

v29's drive armed the gate (mode flicker 0x83/0x8b is NOT a menu-open
signal - it toggles with no input at all) and fired the proven
DOWN,DOWN,A,A route, but the turn never committed. This probe answers the
prerequisite directly: dump OAM (0x07000000), press DOWN via the poll
patch, dump again. A menu cursor steps a fixed pixel distance; animation
sprites churn instead. Sequence:

  1. attach, dump OAM A; wait 0.6 s, dump OAM B  -> baseline churn set
  2. press DOWN x3 frames, dump OAM C            -> press diff
  3. press DOWN x3 again, dump OAM D             -> second step?
  4. press A x3, dump OAM E                      -> submenu open?
  5. key struct +0..+0x10 after each stage; screenshots throughout

Cursor candidates: sprites whose (X,Y) changed in the press diffs but whose
change is a clean multiple of 8 px, unlike the churn set.

Run: python tools/boot_fixture_gdb.py && python tools/exp_menu_probe.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
OAM = 0x07000000
OAM_LEN = 0x400
KEYSTRUCT = 0x03000000
OUT = "outputs/lua-nav/menu-probe.json"


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def window_capture(pid, path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)


def sprites(raw):
    """Parse OAM entries 0..127 (attributes 0/1 enough for position)."""
    out = []
    for i in range(0, min(len(raw), 1024), 8):
        a0 = int.from_bytes(raw[i:i + 2], "little")
        a1 = int.from_bytes(raw[i + 2:i + 4], "little")
        y = a0 & 0xFF
        x = a1 & 0x1FF
        affine = (a0 & 0x100) != 0
        if (a0 & 0x300) == 0x300 and not affine:  # offscreen dual-purpose
            x = None
        out.append({"i": i // 8, "x": x, "y": y})
    return out


def press(g, mask, frames=3):
    hits = 0
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
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
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
            g.interrupt()
        except Exception:
            pass
    return hits


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    report = {"stages": []}
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")

        def snap(tag):
            g.interrupt()
            raw = g.read_mem(OAM, OAM_LEN)
            ks = g.read_mem(KEYSTRUCT, 0x10)
            window_capture(pid, f"outputs/lua-nav/mp-{tag}.png")
            report["stages"].append({
                "tag": tag,
                "oam": raw.hex() if raw else None,
                "keystruct": ks.hex() if ks else None,
                "spr": sprites(raw) if raw else None,
            })
            print(f"  [{tag}] OAM + keystruct {ks.hex() if ks else '?'}")

        def changed(a, b):
            sa = {s["i"]: s for s in a}
            sb = {s["i"]: s for s in b}
            out = []
            for i, s in sb.items():
                p = sa.get(i)
                if p and s["x"] is not None and p["x"] is not None \
                        and (s["x"] != p["x"] or s["y"] != p["y"]):
                    out.append({"i": i, "from": (p["x"], p["y"]),
                                "to": (s["x"], s["y"])})
            return out

        snap("0-attach")
        g.cont()
        time.sleep(0.6)
        snap("1-baseline2")
        g.cont()
        time.sleep(0.6)

        g.interrupt()
        h = press(g, 0x80)
        snap("2-down1")
        print(f"  DOWN x{h}")
        g.cont()
        time.sleep(0.4)
        h = press(g, 0x80)
        snap("3-down2")
        print(f"  DOWN x{h}")
        g.cont()
        time.sleep(0.4)
        h = press(g, 0x01)
        snap("4-A")
        print(f"  A x{h}")
        g.cont()
        time.sleep(0.8)
        snap("5-after")

        s = report["stages"]
        for name, x, y in [("baseline churn", 0, 1), ("down1", 0, 2),
                           ("down2", 2, 3), ("A", 3, 4)]:
            ch = changed(s[x]["spr"], s[y]["spr"])
            stepish = [c for c in ch
                       if (c["to"][0] - c["from"][0]) % 8 == 0
                       and (c["to"][1] - c["from"][1]) % 8 == 0]
            print(f"  {name}: {len(ch)} sprites changed; "
                f"8px-aligned: {[(c['i'], c['from'], c['to']) for c in stepish[:6]]}")
        json.dump(report, open(OUT, "w"), indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
