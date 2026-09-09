"""Map the fixture's post-boot sequence with ground truth at every step.

Open questions this answers:
- Does the law card / skit block input via key-struct enable (+5)==0? (v27
  wrote enable=1 before its first press; the v33/v34 dismissal loops did not.)
- What does the battle ctx phase byte (0x0200F5C4+0x54F4) read during law
  card, skit, field, and (if reached) the command menu?
- When does the first pick fire, and what is on screen then?

Protocol: fresh boot (run boot_fixture_gdb first). Attach, write enable=1,
then A presses (need=4, v27-faithful) on a ~1.4 s cadence, up to 24. After
each press: capture screen, read key struct (halted), ctx phase, ct6, ea6.
Print one line per press; save a JSON map.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_boot_map.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from PIL import Image  # noqa: E402

KEY_BL = 0x08000494
KEYSTRUCT = 0x03000000
SLOT0 = 0x020159E8
STRIDE = 0x108
CT6 = SLOT0 + STRIDE * 6 + 0xD0
EA6 = SLOT0 + STRIDE * 6 + 0xEA
CTX_PHASE = 0x0200F5C4 + 0x54F4
BP_PICK = 0x0809E260
OUT = "outputs/lua-nav/boot-map.json"


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


def classify(path):
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return "?"
    if img.size != (480, 351):
        return "?"
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
    return (f"dark={dark / n:.2f} bright={bright / n:.2f} "
            f"tan={tanp / n:.2f}")


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    out = {"steps": []}
    picks = []
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        assert g.send(f"Z0,{BP_PICK:x},2") == "OK"
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"
        t0 = time.time()

        def sample(tag):
            g.interrupt()
            ks = g.read_mem(KEYSTRUCT, 8)
            phase = g.read_mem(CTX_PHASE, 1)
            row = {
                "t": round(time.time() - t0, 1), "tag": tag,
                "ks": ks.hex() if ks else None,
                "ctx_phase": phase[0] if phase else None,
                "ct6": int.from_bytes(g.read_mem(CT6, 2) or b"\0\0", "little"),
                "ea6": (g.read_mem(EA6, 1) or b"\0")[0],
                "picks": list(picks),
            }
            return row

        for i in range(24):
            # one A press (v27-faithful)
            hits = 0
            try:
                if g.send(f"Z0,{KEY_BL:x},2") == "OK":
                    for _ in range(4):
                        g.cont()
                        st = g._read_packet()
                        if not st or st[:1] not in ("S", "T"):
                            break
                        regs = g.read_registers()
                        if not regs:
                            break
                        if regs[15] == KEY_BL:
                            val = (regs[1] | 0x01) & 0x3FF
                            g.send("P1=" + val.to_bytes(4, "little").hex())
                            hits += 1
                        elif regs[15] == BP_PICK:
                            picks.append({"t": round(time.time() - t0, 1),
                                          "actor": regs[0]})
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception as exc:
                print(f"  press error: {exc}")
            time.sleep(1.0)
            row = sample(f"A#{i}")
            p = f"outputs/lua-nav/bm-{i:02d}.png"
            capture(pid, p)
            row["screen"] = classify(p)
            out["steps"].append(row)
            print(f"A#{i:02d} t={row['t']:5.1f} hits={hits} "
                  f"ks={row['ks']} phase={row['ctx_phase']} "
                  f"ct6={row['ct6']} ea6={row['ea6']} picks={len(picks)} "
                  f"{row['screen']}")
            if len(picks) >= 3:
                print("three picks observed; battle is running")
                break
        g.send(f"z0,{BP_PICK:x},2")
        g.cont()
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
