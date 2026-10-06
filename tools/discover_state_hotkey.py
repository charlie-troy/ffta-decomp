"""Discover mGBA's save-state hotkey empirically (no Lua console).

Launches the mGBA GUI (no GDB stub, no scripting) on a scratch ROM copy,
sends candidate key combos at the emulator window via
tools/sendhotkey_window.ps1, and reports which combo created a new state
file and where it landed. Read-only with respect to the repository ROM and
the user's baserom.sav: the target ROM is an existing scratch copy whose
battery file lives in the same scratch dir.

Evidence: outputs/autobattle/scratch/state-hotkey.txt
"""
import glob
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

MGBA = r"C:\Users\charl\ffta-tools\mGBA-0.10.5-win64\mGBA.exe"
ROM = r"outputs\autobattle\scratch\placement\baserom.gba"
SENDER = r"tools\sendhotkey_window.ps1"
EVID = r"outputs\autobattle\scratch\state-hotkey.txt"

WATCH_DIRS = [
    os.path.dirname(ROM),
    r"C:\Users\charl\ffta-tools\mGBA-0.10.5-win64",
    r"C:\Users\charl\AppData\Roaming\mGBA",
    r"C:\Users\charl\Projects\ffta-decomp\outputs\lua-nav",
    r"C:\Users\charl\Projects\ffta-decomp",
]
COMBOS = ["F1", "Shift+F1", "F2", "Shift+F2", "F3", "Shift+F3",
          "F5", "Shift+F5", "Ctrl+F5", "Ctrl+S", "F9", "Shift+F9",
          "Ctrl+Shift+S", "Ctrl+1"]


def snapshot():
    seen = {}
    for d in WATCH_DIRS:
        if not os.path.isdir(d):
            continue
        for pat in ("*.ss*", "*.state*", "*.sav.*"):
            for p in glob.glob(os.path.join(d, pat)):
                try:
                    st = os.stat(p)
                    seen[os.path.abspath(p)] = (st.st_size, int(st.st_mtime))
                except OSError:
                    pass
    return seen


def main():
    lines = []
    before = snapshot()
    proc = subprocess.Popen([MGBA, os.path.abspath(ROM)],
                            cwd=os.path.dirname(MGBA))
    lines.append(f"launched mGBA pid={proc.pid}")
    print(lines[-1], flush=True)
    time.sleep(9)
    try:
        for combo in COMBOS:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy",
                 "Bypass", "-File", SENDER, "-Combo", combo],
                capture_output=True, text=True, timeout=40)
            msg = (r.stdout + r.stderr).strip().replace("\n", " | ")
            time.sleep(2.0)
            after = snapshot()
            new = {p: v for p, v in after.items() if p not in before}
            changed = {p: v for p, v in after.items()
                       if p in before and after[p] != before[p]}
            line = f"{combo}: {msg[:80]} new={ [os.path.basename(p) for p in new] } changed={ [os.path.basename(p) for p in changed] }"
            print(line, flush=True)
            lines.append(line)
            if new:
                for p in new:
                    lines.append(f"  -> {p}")
                before = after  # keep watching from here
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        lines.append("mGBA terminated")
        print("mGBA terminated", flush=True)
    os.makedirs(os.path.dirname(EVID), exist_ok=True)
    with open(EVID, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"evidence: {EVID}")


if __name__ == "__main__":
    main()
