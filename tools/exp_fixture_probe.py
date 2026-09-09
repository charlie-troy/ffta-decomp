"""Probe a fixture's live state without the boot tool's signature gate.

The boot tool's signature (slot1 name ptr at 0x02015AF0 == 0x0856xxxx) was
built for fix3; a2-battle-start fails it (name0=1aa11b31). This probe tells
us what a fixture ACTUALLY holds:
  1. launch (kill first) with -g -t <fixture>, connect ~3 s, halt.
  2. dump 7 unit records at 0x020159E8 (name ptr, mid, ct, ea) — if garbage,
     scan IWRAM 0x02000000..0x02030000 for ROM-pointer clusters (0x085xxxxx)
     to locate the real record table for this battle.
  3. key struct, both known ctx-phase addresses, screen capture.
  4. arm BP_PICK (0x0809E260) + BP_NORM (0x080C03C2), release, pump 12 s.
  5. final dump + capture; JSON report.

Usage: python tools/exp_fixture_probe.py [fixture] (default a2-battle-start.ss0)
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from PIL import Image  # noqa: E402

MGBA = r"C:\Users\charl\ffta-tools\mGBA-0.10.5-win64\mGBA.exe"
ROM = r"C:\Users\charl\Projects\ffta-decomp\baserom.gba"
FIXDIR = r"C:\Users\charl\Projects\ffta-decomp\outputs\lua-nav"
KEY_BL = 0x08000494
SLOT0 = 0x020159E8
STRIDE = 0x108
CT6 = SLOT0 + STRIDE * 6 + 0xD0
EA6 = SLOT0 + STRIDE * 6 + 0xEA
BP_PICK = 0x0809E260
BP_NORM = 0x080C03C2


def capture(pid, path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def screen_brief(path):
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return "?"
    if img.size != (480, 351):
        return f"size{img.size}"
    px = img.load()
    dark = bright = tanp = n = 0
    for y in range(40, 351, 8):
        for x in range(0, 480, 8):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            n += 1
            if lum < 60:
                dark += 1
            elif lum > 200:
                bright += 1
            if r > 200 and g > 180 and b > 140:
                tanp += 1
    return (f"dark={dark / n:.2f} bright={bright / n:.2f} tan={tanp / n:.2f}")


def dump_records(g):
    rows = []
    for slot in range(7):
        base = SLOT0 + STRIDE * slot
        name = int.from_bytes(g.read_mem(base, 4) or b"\0\0\0\0", "little")
        mid = (g.read_mem(base + 0x104, 1) or b"\0")[0]
        ct = int.from_bytes(g.read_mem(base + 0xD0, 2) or b"\0\0", "little")
        ea = (g.read_mem(base + 0xEA, 1) or b"\0")[0]
        rows.append({"slot": slot, "name": f"{name:08x}", "mid": mid,
                     "ct": ct, "ea": ea})
    return rows


def scan_name_ptrs(g):
    hits = []
    base = 0x02000000
    chunk = 0x1000
    for off in range(0, 0x30000, chunk):
        d = g.read_mem(base + off, chunk)
        if not d:
            continue
        for i in range(0, len(d) - 3, 4):
            v = int.from_bytes(d[i:i + 4], "little")
            if 0x08500000 <= v <= 0x085FFFFF:
                hits.append(base + off + i)
    # cluster: consecutive hits 0x108 apart
    clusters = []
    for a in hits:
        if clusters and a - clusters[-1][-1] <= 0x108:
            clusters[-1].append(a)
        else:
            clusters.append([a])
    return {"ptr_count": len(hits),
            "clusters": [[f"{a:08x}" for a in c] for c in clusters
                         if len(c) >= 3][:6]}


def main():
    fixture = sys.argv[1] if len(sys.argv) > 1 else "a2-battle-start.ss0"
    if "/" not in fixture and "\\" not in fixture:
        fixture = FIXDIR + "\\" + fixture
    subprocess.run(["taskkill", "/F", "/IM", "mgba.exe"],
                   capture_output=True, timeout=30)
    time.sleep(2)
    subprocess.Popen([MGBA, "-g", "-t", fixture, ROM])
    time.sleep(3)
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    out = {"fixture": fixture}
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        out["records_at_020159E8"] = dump_records(g)
        print("records:", out["records_at_020159E8"])
        if not any(r["name"].startswith("085") for r in
                   out["records_at_020159E8"]):
            out["name_ptr_scan"] = scan_name_ptrs(g)
            print("scan:", json.dumps(out["name_ptr_scan"], indent=1))
        ks = g.read_mem(0x03000000, 8)
        out["keystruct"] = ks.hex() if ks else None
        for label, ctx in (("normal", 0x0200F5C4 + 0x54F4),
                           ("alt", 0x020101F8 + 0x54F4)):
            d = g.read_mem(ctx, 1)
            out[f"ctx_phase_{label}"] = d[0] if d else None
        print(f"keystruct={out['keystruct']} "
              f"phase_normal={out.get('ctx_phase_normal')} "
              f"phase_alt={out.get('ctx_phase_alt')}")
        capture(pid, "outputs/lua-nav/probe-0.png")
        out["screen0"] = screen_brief("outputs/lua-nav/probe-0.png")
        print(f"screen: {out['screen0']}")
        assert g.send(f"Z0,{BP_PICK:x},2") == "OK"
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK"
        picks, seeds = [], []
        t0 = time.time()
        g.sock.settimeout(0.4)
        while time.time() - t0 < 14:
            try:
                g.cont()
                st = g._read_packet()
            except Exception:
                continue
            if st and st[:1] in ("S", "T"):
                regs = g.read_registers()
                if not regs:
                    continue
                t = round(time.time() - t0, 1)
                if regs[15] == BP_PICK:
                    picks.append({"t": t, "actor": regs[0]})
                    print(f"  PICK t={t} actor={regs[0]}")
                elif regs[15] == BP_NORM:
                    seeds.append({"t": t, "r4": f"{regs[4]:08x}"})
                    print(f"  SEED t={t} r4={regs[4]:08x}")
        g.send(f"z0,{BP_PICK:x},2")
        g.send(f"z0,{BP_NORM:x},2")
        out["picks"] = picks
        out["seeds"] = seeds
        g.interrupt()
        out["records_final"] = dump_records(g)
        print("final records:", out["records_final"])
        capture(pid, "outputs/lua-nav/probe-1.png")
        out["screen1"] = screen_brief("outputs/lua-nav/probe-1.png")
        print(f"screen after 14s: {out['screen1']}")
        g.cont()
        with open("outputs/lua-nav/fixture-probe.json", "w") as fh:
            json.dump(out, fh, indent=1)
        print("wrote outputs/lua-nav/fixture-probe.json")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
