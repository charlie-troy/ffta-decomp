"""What is on the screen? Classify without eyes:
- menu panel: the battle command menu is a large near-white parchment block
  on the right side; count near-white pixels per region.
- animation: diff two captures 1 s apart (cutscenes/dialog watermarks move;
  an open menu is static except a blinking cursor).
- dialog: law skit/dialogs render a text band at the bottom.
Also probes one DOWN and one A while sampling the key struct, reporting
whether held/pressed bits flow.

Run: python tools/boot_fixture_gdb.py && python tools/exp_screen_classify.py
"""
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

KEY_BL = 0x08000494
KEYSTRUCT = 0x03000000


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def capture(pid, path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def analyze(img, tag):
    w, h = img.size
    px = img.load()
    white = [0, 0]      # [right third, rest]
    dark = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r > 220 and g > 220 and b > 220:
                white[0 if x >= 2 * w // 3 else 1] += 1
            elif r < 40 and g < 40 and b < 40:
                dark += 1
    total = (h // 2) * (w // 2)
    print(f"  [{tag}] white right-third {100*white[0]/total:.1f}% "
          f"white elsewhere {100*white[1]/total:.1f}% dark {100*dark/total:.1f}%")
    return {"white_right": white[0] / total, "white_rest": white[1] / total,
            "dark": dark / total}


def diff(a, b, tag):
    if a is None or b is None:
        print(f"  [{tag}] capture missing")
        return None
    if a.size != b.size:
        print(f"  [{tag}] size mismatch")
        return None
    d = ImageChops.difference(a, b).convert("L")
    hist = d.histogram()
    changed = sum(hist[40:])
    total = a.size[0] * a.size[1]
    print(f"  [{tag}] animation diff {100*changed/total:.2f}% of pixels")
    return changed / total


def press(g, mask, frames=10):
    hits = 0
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
            return 0, None
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
        g.interrupt()
        ks = g.read_mem(KEYSTRUCT, 8)
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
        except Exception:
            pass
    return hits, ks.hex() if ks else None


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        t0 = time.time()

        a = capture(pid, "outputs/lua-nav/sc-0.png")
        print(f"t={time.time()-t0:.1f}")
        analyze(a, "boot")
        g.cont()
        time.sleep(1.0)
        b = capture(pid, "outputs/lua-nav/sc-1.png")
        g.interrupt()
        diff(a, b, "1s-apart")
        # DOWN probe
        hits, ks = press(g, 0x80)
        print(f"  DOWN x{hits} keystruct={ks}")
        g.cont()
        time.sleep(0.8)
        c = capture(pid, "outputs/lua-nav/sc-2.png")
        g.interrupt()
        analyze(c, "after-DOWN")
        diff(b, c, "after-DOWN")
        # A probe
        hits, ks = press(g, 0x01)
        print(f"  A x{hits} keystruct={ks}")
        g.cont()
        time.sleep(0.8)
        e = capture(pid, "outputs/lua-nav/sc-3.png")
        g.interrupt()
        analyze(e, "after-A")
        diff(c, e, "after-A")
        # classic route
        for mask, name in [(0x80, "DOWN"), (0x80, "DOWN"),
                           (0x01, "A"), (0x01, "A")]:
            hits, ks = press(g, mask)
            print(f"  route {name} x{hits} ks={ks}")
            g.cont()
            time.sleep(0.7)
        g.interrupt()
        f = capture(pid, "outputs/lua-nav/sc-4.png")
        analyze(f, "after-route")
        diff(e, f, "after-route")
        g.cont()
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
