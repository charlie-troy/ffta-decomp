"""Headless FFTA driver over the mGBA GDB stub.

Input channel: FFTA reads the keypad at exactly one ROM site (0x0800048A in
the poll at 0x08000460). Writing the KEYINPUT register (0x04000130) is ignored
by mGBA, so this driver instead patches the two instructions at 0x0800048A to
load a forced key mask, exactly like the earlier probe tools.

Keys are GBA button bits in "pressed = 1" form (the mask the poll produces
after the EOR with 0x3FF):
    A=0x01 B=0x02 Select=0x04 Start=0x08 Right=0x10 Left=0x20 Up=0x40 Down=0x80

mGBA throttles to ~60 fps while running, so a key is held by patching the mask,
continuing the CPU for a real-time duration, then restoring the mask to 0.
"""
import hashlib
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

POLL = 0x0800048A
ORIG = "111c5940"  # adds r1,r2,#0 ; eors r1,r3 (retail ROM bytes)
NOP = "c046"       # nop
A, B, SEL, START = 0x01, 0x02, 0x04, 0x08
RIGHT, LEFT, UP, DOWN = 0x10, 0x20, 0x40, 0x80
VRAM = 0x06000000
IO = 0x04000000


def patch_bytes(mask):
    """Return the 4-byte patch: movs r1,#mask ; nop."""
    return f"{mask | 0x2100:04x}{NOP}"


class Session:
    def __init__(self, host="127.0.0.1", port=2345, timeout=10.0):
        self.gdb = Gdb(host, port, timeout=timeout)
        self.gdb.send("?")
        self.gdb.interrupt()
        # Verify the retail bytes are in place before we ever patch.
        cur = self.gdb.read_mem(POLL, 4)
        if cur is None or cur.hex() != ORIG:
            print(f"note: poll bytes are {cur.hex() if cur else None}, "
                  f"retail is {ORIG}")

    def close(self):
        self.set_mask(0)
        self.restore_poll()
        try:
            self.gdb.close()
        except OSError:
            pass

    def restore_poll(self):
        self.gdb.send(f"M{POLL:x},4:{ORIG}")

    def set_mask(self, mask):
        """Patch the poll to report `mask` as held; game must be paused."""
        self.gdb.send(f"M{POLL:x},4:{patch_bytes(mask)}")

    def resume(self, seconds):
        """Run the CPU for `seconds` of real time (no breakpoints set)."""
        self.gdb.cont()
        time.sleep(seconds)
        self.gdb.interrupt()

    def hold(self, mask, seconds):
        """Hold `mask` for `seconds`, then release (both while paused)."""
        self.set_mask(mask)
        self.resume(seconds)
        self.set_mask(0)
        self.gdb.interrupt()

    def tap(self, mask, hold_s=0.08, rest_s=0.08):
        self.set_mask(mask)
        self.resume(hold_s)
        self.set_mask(0)
        self.resume(rest_s)
        self.gdb.interrupt()

    def tap_many(self, mask, presses, period=0.28):
        for _ in range(presses):
            self.tap(mask, 0.08, max(0.05, period - 0.16))

    # ---- reading -------------------------------------------------------
    def read_mem(self, addr, n, chunk=0x200):
        out = bytearray()
        for off in range(0, n, chunk):
            part = self.gdb.read_mem(addr + off, min(chunk, n - off))
            if part is None or len(part) != min(chunk, n - off):
                raise RuntimeError(f"read failed at {addr + off:#x}")
            out += part
        return bytes(out)

    def read_u16(self, addr):
        d = self.gdb.read_mem(addr, 2)
        return int.from_bytes(d, "little") if d else None

    def fingerprint(self):
        """(disp, mode, vram_chunk_hash) — cheap stable screen signature."""
        disp = self.read_u16(IO)
        v0 = self.gdb.read_mem(VRAM, 0x200)
        v1 = self.gdb.read_mem(VRAM + 0xE000, 0x200)
        h = hashlib.md5((v0 or b"") + (v1 or b"")).hexdigest()[:12]
        nz = sum(1 for b in (v0 or b""))
        return (disp, disp & 7, h, nz)

    def fingerprint_loop(self, seconds, every=0.6):
        """Sample fingerprints while the game runs; return list."""
        out = []
        end = time.time() + seconds
        self.gdb.cont()
        while time.time() < end:
            time.sleep(every)
            self.gdb.interrupt()
            out.append((round(time.time(), 1),) + self.fingerprint())
            self.gdb.cont()
        self.gdb.interrupt()
        return out
