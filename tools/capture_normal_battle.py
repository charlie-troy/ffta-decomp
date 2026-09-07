#!/usr/bin/env python3
"""A1 consolidated capture: replay the normal-battle fixture from engage.ss0.

Drives the already-running Windows mGBA (Scripting console via UIA bridge)
through the proven navigation: engage prompt -> dispatch -> place Marche ->
To Battle -> confirm -> intro -> Marche's turn (battle-start fixture).

Prerequisites:
  * mGBA running with the game at any state, Scripting window open
  * outputs/lua-nav/engage.ss0 present (fixture anchor)
  * tools/lua_cursor_tour.lua armed through the UIA bridge (tools/uia_console.ps1)

Usage:
  python tools/capture_normal_battle.py [--proc-id 28912] [--out outputs/lua-nav]
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "lua-nav")
UIA = os.path.join(ROOT, "tools", "uia_console.ps1")
TOUR = os.path.join(ROOT, "tools", "lua_cursor_tour.lua")
ENGAGE_SS = os.path.join(OUT, "engage.ss0")

# KEYINPUT bitmasks as accepted by emu:setKeys (hardware bit order).
A, B, SELECT, START = 1, 2, 4, 8


def console_cmd(proc_id: int, cmd: str, wait: float = 2.0) -> str:
    """Send one Lua line through the UIA Scripting-console bridge."""
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", UIA, "-ProcId", str(proc_id), "-Cmd", cmd],
        capture_output=True, text=True, timeout=60,
    )
    time.sleep(wait)
    return (res.stdout or "") + (res.stderr or "")


def drive(proc_id: int, tag: str, steps, wait_after: float = 3.0) -> None:
    """Run a step-wise key tour: steps = [(bitmask, frames_held), ...]."""
    body = ",".join("{%d,%d}" % (k, f) for k, f in steps)
    cmd = ('TOUR_DIRS={%s}; TOUR_TAG="%s"; TOUR_SS=""; dofile("%s")'
           % (body, tag, TOUR))
    out = console_cmd(proc_id, cmd, wait=1.0)
    if "tour armed" not in out:
        print(f"  ! tour {tag} may not have armed: {out.strip()[:120]}")
    time.sleep(wait_after)


def screenshot(proc_id: int, name: str) -> str:
    path = os.path.join(OUT, name).replace("\\", "/")
    console_cmd(proc_id,
                "local p=emu:screenshot('%s'); console:log('shot ok')" % path,
                wait=1.0)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc-id", type=int, default=28912)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tag", default="fixture")
    args = ap.parse_args()

    if not os.path.exists(ENGAGE_SS):
        print(f"missing fixture anchor: {ENGAGE_SS}", file=sys.stderr)
        return 1

    t0 = time.time()
    print(f"[{time.time()-t0:6.1f}s] loading engage.ss0")
    console_cmd(args.proc_id,
                "emu:loadStateFile('%s'); console:log('loaded engage')"
                % ENGAGE_SS.replace("\\", "/"), wait=4.0)

    print(f"[{time.time()-t0:6.1f}s] A: enter battle (law NOTICE appears)")
    drive(args.proc_id, f"{args.tag}-enter", [(A, 12)], wait_after=8.0)

    print(f"[{time.time()-t0:6.1f}s] A: dismiss law NOTICE (placement screen)")
    drive(args.proc_id, f"{args.tag}-notice", [(A, 12)], wait_after=6.0)

    print(f"[{time.time()-t0:6.1f}s] A,A: pick up + place Marche (1/6)")
    drive(args.proc_id, f"{args.tag}-place", [(A, 30), (A, 30)], wait_after=8.0)

    print(f"[{time.time()-t0:6.1f}s] START: To Battle! banner")
    drive(args.proc_id, f"{args.tag}-start", [(START, 16)], wait_after=3.0)

    print(f"[{time.time()-t0:6.1f}s] A: confirm Yes")
    drive(args.proc_id, f"{args.tag}-confirm", [(A, 20)], wait_after=45.0)

    shot = screenshot(args.proc_id, f"{args.tag}-settle.png")
    ss_path = os.path.join(OUT, f"{args.tag}-battle-start.ss0").replace("\\", "/")
    console_cmd(args.proc_id,
                "emu:saveStateFile('%s'); console:log('state saved')" % ss_path,
                wait=2.0)
    print(f"[{time.time()-t0:6.1f}s] fixture settle: {shot}")
    print(f"        savestate:       {ss_path}")
    print("Verify visually: Marche's turn, MENU open, WT 1/7.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
