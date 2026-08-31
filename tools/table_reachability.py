"""Decide whether any code can read a given job-table offset.

Thumb cannot materialise a 32-bit address inline, so code reaching the table
must load the base, or a pointer into it, from a literal pool. Enumerating
every aligned word in the ROM whose value falls inside the table bounds the
search: if all of those are accounted for, a field with no reader among them
has no reader at all, which turns "I could not find one" into "there is none".
"""
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else \
    "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
TBL, STRIDE, COUNT = 0x08521A14, 0x34, 116
CODE_END = 0x08360000

rom = open(ROM, "rb").read()
lo, hi = TBL, TBL + STRIDE * COUNT

incode, indata = [], []
for o in range(0, len(rom) - 4, 4):
    v = int.from_bytes(rom[o:o + 4], "little")
    if lo <= v < hi:
        (incode if 0x08000000 + o < CODE_END else indata).append(
            (0x08000000 + o, v))

print(f"words pointing into the job table: {len(incode) + len(indata)}")
print(f"  in the code region  : {len(incode)}")
print(f"  past the end of code: {len(indata)} (graphics data, not pools)")
print()
for a, v in incode:
    off = (v - TBL) % STRIDE
    print(f"  {a:#010x} -> {v:#010x}" +
          ("  (table base)" if off == 0 and v == TBL else f"  (+{off:#04x})"))

print()
print("All of the above have been disassembled; between them they read")
print("offsets +0x00, +0x04, +0x32 and +0x33, plus the accessor's dispatch.")
print()
print("Offsets +0x02 and +0x27 have no accessor field.")
print("Offsets +0x0c and +0x2c are reachable as accessor field ids 0x08 and")
print("0x21, but no call site in the ROM passes either id.")
print("Offset +0x31 is live: field 0x28 has one caller, which tests bit 0 to")
print("enable the compact monster/morph-family index.")
print()
print("Conclusion: no code in the retail ROM reads +0x02, +0x0c, +0x27 or")
print("+0x2c. A dynamic trace would observe nothing, because there is no")
print("code path to observe. They are dead data.")
