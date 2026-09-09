"""A2.3 v22: the Controlled seam with NATURAL turn order (the fix for v21).

v21 wrote slot0.ct=1000, which hijacked turn order and deadlocked the round
(the loop waited on Marche ct=0 forever; nothing committed). The seam the
decode describes needs no CT edit: mark slot0 as Marche-controlled
(+0xE6 controller id, +0xED bit 3) and set flag[0x0D]=1; when the turn loop
reaches slot0 in natural CT order, ctx init 0x080C034C seeds phase 0xB
(walk + end turn) instead of phase 9 (AI plan) iff flag[0x0D]!=0 and
gate 0x080C1B2C==0.

Sequence:
  1. boot fixture (mgba -g -t fix3-battle-start.ss0), attach GDB, halt.
  2. takeover writes WITHOUT touching CT: e6=6, ed|=8, flag0D=1; read back.
  3. resume; A1 menu sequence DOWN,DOWN,A,A via r1 patches; capture each step.
  4. sample all CTs every 2 s for ~45 s, capturing at 10 s intervals.
  5. final report: did the round advance, and what did slot0's turn do?

Usage: python tools/exp_controlled_natural.py
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
OUT_JSON = "outputs/lua-nav/controlled-natural.json"


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


def cts(gdb, tag):
    row = []
    for i in range(7):
        d = gdb.read_mem(SLOT0 + STRIDE * i + 0xD0, 2)
        row.append(int.from_bytes(d, "little") if d else None)
    print(f"  [{tag}] cts={row}")
    return row


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-writes", action="store_true",
                    help="control run: menu keys only, no takeover writes")
    args = ap.parse_args()
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    out = {}
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        gdb.send("?")
        gdb.interrupt()
        print("GDB attached; halted")

        # -- takeover writes (no CT change) ---------------------------------
        if not args.no_writes:
            mid = gdb.read_mem(SLOT0 + STRIDE * 6 + 0x104, 1)[0]  # Marche id
            ed = gdb.read_mem(SLOT0 + 0xED, 1)[0]
            assert gdb.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
            assert gdb.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
            assert gdb.send(f"M{FLAG0D:x},1:01") == "OK"
            wv = {
                "e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
                "ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
                "ct0_natural": int.from_bytes(gdb.read_mem(SLOT0 + 0xD0, 2), "little"),
                "flag0D": gdb.read_mem(FLAG0D, 1)[0],
            }
            out["written"] = wv
            ok = wv["e6"] == mid and (wv["ed"] & 8) and wv["flag0D"] == 1
            print(f"  writes: {wv} ok={ok}")
            if not ok:
                print("FAIL: writes did not stick")
                with open(OUT_JSON, "w") as fh:
                    json.dump(out, fh, indent=1)
                gdb.cont()
                return 1
        else:
            print("  control run: no writes")
        gdb.cont()

        # -- menu keys, capture after each ----------------------------------
        def press(mask, frames=4, pause=1.1, tag=""):
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
                print(f"  press error: {exc}")
            finally:
                try:
                    gdb.send(f"z0,{KEY_BL:x},2")
                    gdb.cont()
                except Exception:
                    pass
            time.sleep(pause)
            print(f"  key {mask:#04x} x{hits} {tag}")
            return hits

        time.sleep(0.8)
        for i, (mask, tag) in enumerate([
                (0x80, "DOWN1"), (0x80, "DOWN2"),
                (0x01, "A-wait"), (0x01, "A-confirm")]):
            press(mask, 4, tag=tag)
            window_capture(pid, f"outputs/lua-nav/nat-{i + 1}-{tag}.png")
        out["keys"] = "DOWN DOWN A A"

        # -- sample the round -------------------------------------------------
        samples = []
        for i in range(24):
            time.sleep(2.0)
            gdb.interrupt()
            row = cts(gdb, f"t+{(i + 1) * 2.0:.0f}s")
            samples.append(row)
            gdb.cont()
            if i in (4, 9, 14, 19):
                window_capture(pid, f"outputs/lua-nav/nat-t{(i + 1) * 2}.png")
        out["samples"] = samples

        gdb.interrupt()
        out["final_state"] = {
            "flag0D": gdb.read_mem(FLAG0D, 1)[0],
            "s0.e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
            "s0.ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
        }
        gdb.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/nat-final.png")
        advanced = len({tuple(r) for r in samples}) > 1
        print(f"round advanced: {advanced}")
        out["round_advanced"] = advanced
        with open(OUT_JSON, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT_JSON}")
        return 0
    finally:
        try:
            gdb.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
