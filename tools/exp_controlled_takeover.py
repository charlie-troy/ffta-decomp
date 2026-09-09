"""A2.3 v21: Controlled takeover, one GDB session, full causal record.

Sequence (all inside the stub's single connection):
  1. baseline: dump all 6 battle records (0x108 stride from 0x020159E8).
  2. liveness: resume 5 s, re-halt, re-read CTs -- proves the turn loop ticks
     (or not) while Marche's menu is open.
  3. takeover writes to slot0 (e6=Marche id, ed|=8, ct=1000, flag[0x0D]=1),
     verified by read-back.
  4. menu keys via r1 patches at 0x08000494, window capture after each press.
  5. post-turn CT sampling for ~20 s + final capture.

Fixture: fix3-battle-start.ss0 via `mgba -g -t <fixture> baserom.gba`.
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
FLAG0D = 0x0200203D
OUT_JSON = "outputs/lua-nav/controlled-takeover.json"
CAP = "outputs/lua-nav/step-{}.png"


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


def read_records(gdb, tag, n=7):
    rows = []
    for i in range(n):
        s = SLOT0 + STRIDE * i
        name = gdb.read_mem(s, 4)
        ct = gdb.read_mem(s + 0xD0, 2)
        e6 = gdb.read_mem(s + 0xE6, 1)
        e8 = gdb.read_mem(s + 0xE8, 1)
        ed = gdb.read_mem(s + 0xED, 1)
        mid = gdb.read_mem(s + 0x104, 1)
        rows.append({
            "slot": i,
            "name": f"{int.from_bytes(name, 'little'):08x}" if name else None,
            "ct": int.from_bytes(ct, "little") if ct else None,
            "e6": e6[0] if e6 else None, "e8": e8[0] if e8 else None,
            "ed": ed[0] if ed else None, "mid": mid[0] if mid else None,
        })
    print(f"  [{tag}] " + " | ".join(
        f"s{r['slot']}:ct={r['ct']},e8={r['e8']:02x},mid={r['mid']}"
        for r in rows if r["ct"] is not None))
    return rows


def main():
    # NOTE: never leave the stub with the CPU halted -- a disconnect while
    # halted wedges mGBA's stub; disconnecting while running is safe.
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    out = {}

    window_capture(pid, CAP.format("00-boot"))
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        return run(gdb, pid, out)
    finally:
        try:
            gdb.cont()      # leave the CPU running: a halted disconnect wedges the stub
        except Exception:
            pass


def run(gdb, pid, out):
    gdb.send("?")
    gdb.interrupt()
    print("GDB attached; CPU halted")

    # -- 1. baseline --------------------------------------------------------
    out["baseline"] = read_records(gdb, "baseline")

    # -- 2. liveness: do CTs tick while Marche's menu is open? --------------
    gdb.cont()
    time.sleep(5.0)
    gdb.interrupt()
    out["after5s"] = read_records(gdb, "after 5s run")
    ticked = any(a["ct"] != b["ct"] for a, b in
                 zip(out["baseline"], out["after5s"])
                 if a["ct"] is not None and b["ct"] is not None)
    print(f"  CTs ticked while menu open: {ticked}")

    # -- 3. takeover writes on slot0 ----------------------------------------
    s0 = SLOT0
    mid = out["baseline"][6]["mid"]          # Marche's unit id (slot6)
    if not mid:
        mid = 6                              # live-verified Marche unit id
    ed = out["baseline"][0]["ed"]
    assert gdb.send(f"M{s0 + 0xE6:x},1:{mid:02x}") == "OK"
    assert gdb.send(f"M{s0 + 0xED:x},1:{ed | 8:02x}") == "OK"
    assert gdb.send(f"M{s0 + 0xD0:x},2:{(1000).to_bytes(2, 'little').hex()}") == "OK"
    assert gdb.send(f"M{FLAG0D:x},1:01") == "OK"
    wv = {
        "e6": gdb.read_mem(s0 + 0xE6, 1)[0],
        "ed": gdb.read_mem(s0 + 0xED, 1)[0],
        "ct0": int.from_bytes(gdb.read_mem(s0 + 0xD0, 2), "little"),
        "flag0D": gdb.read_mem(FLAG0D, 1)[0],
    }
    out["written"] = wv
    ok = wv["e6"] == mid and (wv["ed"] & 8) and wv["ct0"] == 1000 and wv["flag0D"] == 1
    print(f"  writes: {wv} ok={ok}")
    if not ok:
        print("FAIL: writes did not stick")
        with open(OUT_JSON, "w") as fh:
            json.dump(out, fh, indent=1)
        gdb.cont()
        return 1

    # -- 4. menu keys, capture after each -----------------------------------
    def press(mask, frames=4, pause=1.0, tag=""):
        hits = 0
        try:
            if gdb.send(f"Z0,{KEY_BL:x},2") != "OK":
                print("  bp rejected")
                return 0
            for _ in range(frames):
                gdb.cont()
                stop = gdb._read_packet()
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = gdb.read_registers()
                if regs and regs[15] == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    gdb.send("P1=" + val.to_bytes(4, "little").hex())
                    hits += 1
        except Exception as exc:
            print(f"  press error at hit {hits}: {exc}")
        finally:
            try:
                gdb.send(f"z0,{KEY_BL:x},2")
                gdb.cont()
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag}")
        return hits

    gdb.cont()
    time.sleep(0.8)
    for i, (mask, tag) in enumerate([
            (0x80, "DOWN#1"), (0x80, "DOWN#2"),
            (0x01, "A#1"), (0x01, "A#2")]):
        press(mask, 4, 1.2, tag)
        window_capture(pid, CAP.format(f"{i + 1:02d}-{tag.replace('#', '')}"))
    out["keys"] = "DOWN DOWN A A"

    # -- 5. post-turn sampling ----------------------------------------------
    samples = []
    for i in range(8):
        time.sleep(2.5)
        gdb.interrupt()
        rows = read_records(gdb, f"t+{(i + 1) * 2.5:.1f}s")
        samples.append({f"slot{r['slot']}_ct": r["ct"] for r in rows})
        gdb.cont()
    out["samples"] = samples
    window_capture(pid, CAP.format("99-final"))

    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT_JSON}")
    print("NOTE: leave the emulator running (stub spent); kill when done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
