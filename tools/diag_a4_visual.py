"""A4 visual diagnostic: real window screenshots at each route stage.

Questions answered in one boot:
  1. Is the engage prompt's first A time-gated? (first press moved to t+45 s)
  2. Is the post-pick screen REALLY white? (window capture via
     capture_window.ps1 + PIL stats — immune to stub-read theories)
  3. What does each stage actually look like (mean/variance/whiteness)?

Stdout only; PNGs land in outputs/autobattle/scratch/.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402
from a4_fixture_build import KEY_ENABLE, PRESS_FRAMES, ROUTE, press  # noqa: E402

SCRATCH = os.path.join("outputs", "autobattle", "scratch")
WARMUP_S = 45.0   # theory: engage prompt ignores input until ~ring settles


def shot(pid, tag):
    path = os.path.join(SCRATCH, f"a4vis-{tag}.png")
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=60)
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        px = img.load()
        w, h = img.size
        n = 0
        rs = gs = bs = 0
        white = 0
        vals = []
        for y in range(0, h, 3):
            for x in range(0, w, 3):
                r, g, b = px[x, y]
                rs += r; gs += g; bs += b
                n += 1
                if r > 240 and g > 240 and b > 240:
                    white += 1
                vals.append((r + g + b) // 3)
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        print(f"  shot {tag}: mean={mean:.1f} sd={var ** 0.5:.1f} "
              f"white%={100 * white / n:.1f} rgb=({rs // n},{gs // n},{bs // n})",
              flush=True)
    except Exception as exc:
        print(f"  shot {tag}: analyze failed {exc}", flush=True)


def main():
    prev = 0
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        pid = session.pid
        session.write_u8(KEY_ENABLE, 1, "key enable")
        g.cont()
        time.sleep(2.0)
        shot(pid, "engage")
        print(f"warmup {WARMUP_S}s before first press...", flush=True)
        time.sleep(WARMUP_S)
        for idx, (mask, tag, pause) in enumerate(ROUTE):
            if mask is None:
                time.sleep(pause)
                continue
            if not drain_paired(g):
                print(f"  DRAIN-FAILED before {tag}", flush=True)
            hits = press(g, mask, frames=PRESS_FRAMES)
            print(f"press #{idx} {tag} hits={hits}", flush=True)
            time.sleep(pause)
            shot(pid, f"{idx}-{tag}")
            if hits == 0:
                return 3
        for t in (10, 40, 80):
            time.sleep(t if t == 10 else t - prev)
            shot(pid, f"after+{t}s")
            prev = t
    return 0


if __name__ == "__main__":
    sys.exit(main())
