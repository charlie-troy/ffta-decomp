"""Read-only EWRAM dump of engage.ss0 (screen-diff anchor). Stdout + bin."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixture_guard import FixtureSession  # noqa: E402

OUT = os.path.join("outputs", "autobattle", "scratch", "a4-engage-ewram.bin")

with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                    rom="baserom.gba", quiet=True) as s:
    time.sleep(2.0)
    blob = b""
    for off in range(0, 0x40000, 512):
        blob += s.g.read_mem(0x02000000 + off, 512) or b"\x00" * 512
    s.g.cont()
    with open(OUT, "wb") as fh:
        fh.write(blob)
print(f"wrote {OUT} ({len(blob)} bytes)")
