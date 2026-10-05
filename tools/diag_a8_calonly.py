"""A8: console-only boot calibration feasibility (2026-09-22).

Law discovered this round (cal-diag.json): on a stub-attached boot, the
FIRST scripting-console traffic freezes the emulator core permanently
(F1-frozen-core, nonce-proven). But A1's console-driven routes ran whole
battles Lua-only — no stub client ever attached. If console-only boots
stay alive, the emulated-fps calibration can run on a separate no-stub
boot (same launch args, rom/save/state scratch copies) while the stub
boot supplies the recharge trajectory.

This probe: launch mGBA WITHOUT -g, open the scripting console, take two
nonce-tagged atomic samples 30 s apart, and report whether frames
advanced (console alive) or the boot froze like the stub+console case.
"""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (DEFAULT_EMULATOR, DEFAULT_ROM, DEFAULT_SAVE,  # noqa: E402
                           rom_sha1, EXPECTED_ROM_SHA1)

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
TOOLS = os.path.dirname(os.path.abspath(__file__))
LUA_NONCE = os.path.join(TOOLS, "lua_a8_nonce.lua").replace("\\", "/")


def lua(pid, code, timeout=120):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "uia_lua2.ps1"),
         "-Cmd", code, "-ProcId", str(pid)],
        capture_output=True, text=True, timeout=timeout)


def console_open(pid):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "uia_invoke_item.ps1"),
         "-ProcId", str(pid), "-MenuName", "Tools",
         "-ItemName", "Scripting...", "-ItemIndex", "1"],
        capture_output=True, text=True, timeout=120)
    return (r.stdout or "").strip()


def nonce_sample(pid, n):
    r = lua(pid, f'A8N={n} dofile("{LUA_NONCE}")')
    out = r.stdout or ""
    found = None
    for raw in out.splitlines():
        line = raw[5:] if raw.startswith("LOG: ") else raw
        for chunk in line.split("A8S "):
            if chunk == "":
                continue
            p = chunk.split()
            if len(p) >= 4:
                try:
                    found = {"nonce": int(p[0]), "frame": int(p[1]),
                             "ct": int(p[2]), "wall": int(p[3])}
                except ValueError:
                    pass
    return found, out[-600:]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rep = {"schema": "a8-calonly-feasibility/1", "date": "2026-09-22"}
    if rom_sha1(DEFAULT_ROM) != EXPECTED_ROM_SHA1:
        print("ROM mismatch", flush=True)
        return 1
    work = os.path.join(OUT_DIR, "calboot")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    rom_copy = os.path.join(work, os.path.basename(DEFAULT_ROM))
    save_copy = os.path.join(work, os.path.splitext(
        os.path.basename(DEFAULT_ROM))[0] + ".sav")
    state_copy = os.path.join(work, os.path.basename(STATE))
    shutil.copyfile(DEFAULT_ROM, rom_copy)
    shutil.copyfile(DEFAULT_SAVE, save_copy)
    shutil.copyfile(STATE, state_copy)
    cmd = [DEFAULT_EMULATOR, "-t", state_copy, rom_copy]
    rep["cmd"] = cmd
    proc = subprocess.Popen(cmd, cwd=work, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    pid = proc.pid
    rep["pid"] = pid
    try:
        time.sleep(4.0)
        inv = console_open(pid)
        rep["console_open"] = inv
        time.sleep(2.0)
        s1, tail1 = nonce_sample(pid, 201)
        rep["s1"] = s1
        print(f"S1: {s1}", flush=True)
        time.sleep(30)
        s2, tail2 = nonce_sample(pid, 202)
        rep["s2"] = s2
        print(f"S2: {s2}", flush=True)
        rep["log_tail"] = tail2
        if s1 and s2 and s2["nonce"] == 202 and s2["frame"] > s1["frame"]:
            fps = (s2["frame"] - s1["frame"]) / (s2["wall"] - s1["wall"])
            rep["fps"] = round(fps, 2)
            rep["verdict"] = "ALIVE"
        else:
            rep["verdict"] = "FROZEN-OR-NOECHO"
    finally:
        try:
            proc.terminate()
            time.sleep(1.0)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
    print(f"CAL-ONLY {rep['verdict']} fps={rep.get('fps')}", flush=True)
    with open(os.path.join(OUT_DIR, "calonly-feasibility.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    return 0 if rep["verdict"] == "ALIVE" else 1


if __name__ == "__main__":
    sys.exit(main())
