"""One-boot diagnostic: attach immediately after un-pause and watch the
battle-signature fields evolve for 75 s.

Distinguishes:
  - settle-late:  fixture bytes appear after N s (boot needs more settle time)
  - attract hijack: fixture bytes never appear / garbage from the start
  - instant-live:  fixture bytes present at first read (previous good case)

Keeps ONE socket for the whole run (stub wedges on extra connections while
a half-closed peer lingers).
"""
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402


def main():
    g = Gdb("127.0.0.1", 2345, timeout=15)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        t0 = time.time()
        seen = []
        while time.time() - t0 < 75:
            try:
                name0 = int.from_bytes(g.read_mem(0x02015AE8, 4), "little")
                mid6 = g.read_mem(0x02016718, 1)
                mid6 = mid6[0] if mid6 else -1
                cts = [int.from_bytes(g.read_mem(0x020159E8 + 0x108 * i + 0xD0, 2),
                                      "little") for i in range(7)]
                t = time.time() - t0
                state = (f"t={t:5.1f} name0={name0:08x} mid6={mid6} "
                         f"cts={cts}")
                sig = name0 == 0x085671EE and mid6 == 6 and cts[0] == 45
                print(state + ("  <== BATTLE LIVE" if sig else ""))
                if sig:
                    print("battle signature appeared at "
                          f"t={t:.1f}s")
                    break
                seen.append(state)
                g.cont()
                time.sleep(5)
                g.interrupt()
            except Exception as exc:
                print(f"probe error: {exc}; resync")
                time.sleep(2)
                try:
                    g.interrupt()
                except Exception:
                    pass
        g.cont()
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
