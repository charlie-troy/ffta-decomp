"""Visual stepping: what does ONE real A press do, visually?

Captures at attach and after each of 5 single real-A presses (1.6 s apart),
printing an ASCII rendering of each frame. No GDB input injection; GDB only
samples the key struct + CT to correlate. This settles what screen the
fixture resumes on and what each press does to it.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_visual_step.py
"""
import subprocess
import sys
import time

from PIL import Image

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402


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


def uia_send(pid, keys):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/uia_sendkey.ps1", "-ProcId", str(pid), "-Keys", keys],
        capture_output=True, text=True, timeout=45)
    return (r.stdout or "").strip()


def show(path):
    img_open = Image.open(path).convert("RGB")
    w, h = img_open.size
    # find the GBA frame: scan for the largest region that isn't uniform
    # window chrome; approximate by cropping 1/8 from each side, 1/10 top
    fx0, fy0 = w // 12, h // 9
    frame = img_open.crop((fx0, fy0, w - fx0, h - fy0))
    frame = frame.resize((76, 26))
    px = frame.load()
    ramp = " .:-=+*#%@"
    print(f"### {path}")
    for y in range(26):
        row = ""
        for x in range(76):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            row += ramp[min(lum * 10 // 256, 9)]
        print(row)


def main():
    from PIL import Image
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        ks = g.read_mem(0x03000000, 8)
        print(f"ks: {ks.hex() if ks else '?'}")
        ct6 = g.read_mem(0x020159E8 + 0x108 * 6 + 0xD0, 2)
        print(f"ct6: {int.from_bytes(ct6, 'little') if ct6 else '?'}")
        g.cont()
        time.sleep(0.5)
        capture(pid, "outputs/lua-nav/vs-0-attach.png")
        show("outputs/lua-nav/vs-0-attach.png")
        for i in range(5):
            uia_send(pid, "x")
            time.sleep(1.6)
            g.interrupt()
            ks = g.read_mem(0x03000000, 8)
            ct6 = g.read_mem(0x020159E8 + 0x108 * 6 + 0xD0, 2)
            g.cont()
            capture(pid, f"outputs/lua-nav/vs-{i + 1}-afterA.png")
            show(f"outputs/lua-nav/vs-{i + 1}-afterA.png")
            print(f"--- after A#{i + 1}: ks={ks.hex() if ks else '?'} "
                  f"ct6={int.from_bytes(ct6, 'little') if ct6 else '?'}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
