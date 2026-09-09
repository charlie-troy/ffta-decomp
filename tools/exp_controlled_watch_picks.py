"""A2.3 v23: watch the retail actor pick with the Controlled mark in place.

Evidence so far (v22 + screenshots): the menu sequence commits Marche's Wait,
the round bubbles cycle, but the +0xD0 CT fields never move -- they are not
the live turn-order CTs. The authoritative observable is the retail turn
loop itself: at 0x0809E272 it clears the newly picked actor's Controlled bit
(`sub_080CE2F0(actor, 0)`), so r0 there IS the picked actor's record
pointer. Breakpointing it answers directly:
  - does the loop pick slot0 (0x020159E8) after Marche's Wait?
  - does it pick anyone at all (deadlock vs seam)?

Sequence: fixture boot -> takeover writes (no CT edit) -> menu keys ->
breakpoint 0x0809E272, 8 hits over up to 90 s, recording r0 per hit ->
per-3 s captures -> dump of the 7-record turn array 0x02016750 before/after.

Usage: python tools/exp_controlled_watch_picks.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
PICK_CLEAR = 0x0809E272
SLOT0 = 0x020159E8
ARRAY = 0x02016750
FLAG0D = 0x0200203D
OUT_JSON = "outputs/lua-nav/controlled-picks.json"


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


def array_records(gdb):
    rows = []
    for i in range(7):
        d = gdb.read_mem(ARRAY + i * 4, 4)
        rows.append(f"{int.from_bytes(d, 'little'):08x}" if d else None)
    return rows


def main():
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
        out["array_before"] = array_records(gdb)

        # -- takeover writes (no CT change) ---------------------------------
        mid = gdb.read_mem(SLOT0 + 0x108 * 6 + 0x104, 1)[0]
        ed = gdb.read_mem(SLOT0 + 0xED, 1)[0]
        assert gdb.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert gdb.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert gdb.send(f"M{FLAG0D:x},1:01") == "OK"
        wv = {
            "e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
            "ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
            "flag0D": gdb.read_mem(FLAG0D, 1)[0],
        }
        print(f"  writes: {wv}")
        out["written"] = wv
        gdb.cont()

        # -- menu keys -------------------------------------------------------
        def press(mask, frames=4, pause=1.1, tag=""):
            hits = 0
            try:
                if gdb.send(f"Z0,{KEY_BL:x},2") != "OK":
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
        for mask, tag in [(0x80, "DOWN1"), (0x80, "DOWN2"),
                          (0x01, "A-wait"), (0x01, "A-confirm")]:
            press(mask, 4, tag=tag)
        window_capture(pid, "outputs/lua-nav/pick-0-committed.png")

        # -- watch the actor pick --------------------------------------------
        hits = []
        t0 = time.time()
        if gdb.send(f"Z0,{PICK_CLEAR:x},2") == "OK":
            while len(hits) < 8 and time.time() - t0 < 90:
                gdb.cont()
                try:
                    stop = gdb._read_packet()
                except Exception:
                    break
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = gdb.read_registers()
                if not regs or regs[15] != PICK_CLEAR:
                    continue
                r0 = regs[0]
                row = {
                    "t": round(time.time() - t0, 1),
                    "r0": f"{r0:08x}",
                    "r1": f"{regs[1]:08x}",
                    "lr": f"{regs[14]:08x}",
                }
                hits.append(row)
                print(f"  pick {len(hits)}: t={row['t']}s r0={row['r0']} "
                      f"r1={row['r1']} lr={row['lr']}")
                if len(hits) == 1:
                    window_capture(pid, "outputs/lua-nav/pick-1-first.png")
            gdb.send(f"z0,{PICK_CLEAR:x},2")
        out["picks"] = hits
        out["array_after"] = array_records(gdb)
        print(f"  picks observed: {len(hits)}")
        print(f"  array before: {out['array_before']}")
        print(f"  array after : {out['array_after']}")

        # -- let it play, capture ---------------------------------------------
        for i in range(6):
            time.sleep(3.0)
            window_capture(pid, f"outputs/lua-nav/pick-t{(i + 1) * 3}.png")

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
