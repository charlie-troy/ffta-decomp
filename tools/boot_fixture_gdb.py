"""Boot mGBA with a fixture and guarantee a live battle via early GDB halt.

Unified model of this session's boot bimodality:
- `-g` pause engagement is NONDETERMINISTIC. When it engages, the emulator
  sits paused until the first connection sends `$c#63`. When it does NOT,
  the game runs from launch — the idle timer then hands Marche's menu to
  auto-battle (~16 s), the fight plays out and EXITS by ~25 s, releasing
  unit records (name ptr -> 0x00000100, mid -> 0) while CT scratch retains
  fixture values. Any attach after that sees wreckage.
- Therefore: connect at ~3 s and HALT immediately. Halted before the menu
  even opens, verify the fixture signature, then release. One connection
  for the whole procedure, closed cleanly (cont + drain) so the stub
  accepts the experiment's connection afterwards.

Usage: python tools/boot_fixture_gdb.py [fixture-name]   (default fix3)
"""
import socket
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

MGBA = r"C:\Users\charl\ffta-tools\mGBA-0.10.5-win64\mGBA.exe"
ROM = r"C:\Users\charl\Projects\ffta-decomp\baserom.gba"
FIXDIR = r"C:\Users\charl\Projects\ffta-decomp\outputs\lua-nav"

NAME0_ADDR = 0x02015AF0   # first unit-record ROM name ptr (0x0856xxxx)
MID6_ADDR = 0x0201611C    # slot6 class byte (6 = Marche)
CT0_ADDR = 0x020159E8 + 0xD0


def kill_mgba():
    subprocess.run(["taskkill", "/F", "/IM", "mgba.exe"],
                   capture_output=True, timeout=30)
    time.sleep(2)


def boot(fixture):
    subprocess.Popen([MGBA, "-g", "-t", fixture, ROM],
                     cwd=r"C:\Users\charl\Projects\ffta-decomp",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"launched mGBA with {fixture}")


def halt_now(g, tries=2):
    """Interrupt; if the stub is silent (emulator still paused), un-pause
    with $c and interrupt again."""
    for i in range(tries):
        try:
            stop = g.interrupt()
            if stop:
                return stop
        except Exception:
            pass
        print("  stub silent (paused?) - sending $c and retrying interrupt")
        g.send("c", expect_reply=False)
        time.sleep(1.5)
    return None


def signature(g):
    name0 = int.from_bytes(g.read_mem(NAME0_ADDR, 4), "little")
    mid6 = g.read_mem(MID6_ADDR, 1)
    ct0 = int.from_bytes(g.read_mem(CT0_ADDR, 2), "little")
    ok = (name0 & 0xFF000000) == 0x08000000 and mid6 == b"\x06" and ct0 == 45
    return ok, f"name0={name0:08x} mid6={mid6.hex() if mid6 else '?'} ct0={ct0}"


def main():
    fixture = sys.argv[1] if len(sys.argv) > 1 else "fix3-battle-start.ss0"
    if fixture != "title" and "/" not in fixture and "\\" not in fixture:
        fixture = FIXDIR + "\\" + fixture
    for attempt in range(1, 4):
        kill_mgba()
        boot(fixture)
        time.sleep(3)
        try:
            g = Gdb("127.0.0.1", 2345, timeout=6)
        except OSError as exc:
            print(f"attempt {attempt}: stub not up ({exc})")
            continue
        try:
            stop = halt_now(g)
            if not stop:
                print(f"attempt {attempt}: could not halt CPU")
                continue
            ok, why = signature(g)
            print(f"attempt {attempt}: halted {stop}, signature {why}")
            if ok:
                g.cont()
                time.sleep(0.5)
                g.close()
                print("READY (battle live, stub released cleanly)")
                return 0
            g.cont()
            time.sleep(0.3)
            g.close()
        except Exception as exc:
            print(f"attempt {attempt}: error {exc}")
            try:
                g.cont()
                g.close()
            except Exception:
                pass
    print("FAILED after 3 attempts")
    return 1


if __name__ == "__main__":
    sys.exit(main())
