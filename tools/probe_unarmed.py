"""Confirm +0x33 is the innate attack power used when no weapon is equipped.

sub_08130820 takes a unit pointer, reads the job index from unit+5, and
returns job_table[job].b33. Running it against synthetic units checks both the
unit+5 claim and the offset, without needing a real battle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
GETTER = 0x08130820
BASE, STRIDE, COUNT = 0x08521A14 - 0x08000000, 0x34, 116
UNIT = 0x02000400

rom = open(ROM, "rb").read()
gba = Gba(ROM)
raw = lambda i, o: rom[BASE + i * STRIDE + o]

bad = 0
for job in range(COUNT):
    gba.uc.mem_write(UNIT, bytes(0x40))
    gba.uc.mem_write(UNIT + 5, bytes([job]))
    got = gba.call(GETTER, [UNIT])
    if got != raw(job, 0x33):
        bad += 1
        if bad <= 3:
            print(f"  job {job}: getter={got} +0x33={raw(job, 0x33)}")
print(f"sub_08130820(unit) == job_table[unit+5].b33 for {COUNT - bad}/{COUNT} jobs")

# The value must move when the table moves, not merely correlate.
job = 5
for probe in (0, 7, 99, 255):
    patched = bytearray(rom)
    patched[BASE + job * STRIDE + 0x33] = probe
    g2 = Gba(ROM, rom_bytes=bytes(patched)) if "rom_bytes" in \
        Gba.__init__.__code__.co_varnames else None
    if g2 is None:
        gba.uc.mem_write(0x08000000 + BASE + job * STRIDE + 0x33, bytes([probe]))
        gba.uc.mem_write(UNIT + 5, bytes([job]))
        got = gba.call(GETTER, [UNIT])
    else:
        g2.uc.mem_write(UNIT, bytes(0x40))
        g2.uc.mem_write(UNIT + 5, bytes([job]))
        got = g2.call(GETTER, [UNIT])
    print(f"  set +0x33 of job {job} to {probe:>3} -> getter returns {got}")
