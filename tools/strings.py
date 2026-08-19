"""Find and dump FFTA's string tables.

Text is addressed by tables of ascending ROM pointers, so scanning for long
ascending pointer runs finds every string table without needing to know where
any of them are. Each run is then decoded with both codecs and the cleaner one
wins.

    python tools/strings.py list  baserom.gba
    python tools/strings.py dump  baserom.gba 0x0855A64C 511 out.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_text import decode, decode1, score

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"


def pointer_runs(rom, minlen=32):
    n = len(rom)
    out = []
    i = 0
    while i < n - 4:
        v = int.from_bytes(rom[i:i + 4], "little")
        if not (0x08000000 <= v < 0x08000000 + n):
            i += 4
            continue
        j, prev, cnt = i, -1, 0
        while j < n - 4:
            w = int.from_bytes(rom[j:j + 4], "little")
            if not (0x08000000 <= w < 0x08000000 + n) or w < prev:
                break
            prev = w
            cnt += 1
            j += 4
        if cnt >= minlen:
            out.append((i, cnt))
            i = j
        else:
            i += 4
    return out


def best(rom, off):
    a = decode(rom, off)[0]
    b = decode1(rom, off)[0]
    return (a, "2-byte") if score(a) >= score(b) else (b, "1-byte")


def cmd_list(rom_path):
    rom = open(rom_path, "rb").read()
    runs = pointer_runs(rom)
    print(f"ascending pointer runs of 32+ entries: {len(runs)}")
    print()
    print(f"{'table':>12} {'count':>6} {'codec':>7}  samples")
    print("-" * 78)
    for off, cnt in runs:
        def p(i):
            return int.from_bytes(rom[off + i * 4:off + i * 4 + 4],
                                  "little") - 0x08000000
        texts, codecs = [], []
        for i in range(min(cnt, 6)):
            t, c = best(rom, p(i))
            texts.append(t)
            codecs.append(c)
        codec = max(set(codecs), key=codecs.count)
        clean = sum(1 for t in texts if t and "[" not in t)
        if clean == 0:
            continue
        samp = " | ".join(repr(t[:22]) for t in texts[1:4])
        print(f"  {0x08000000+off:#010x} {cnt:>6} {codec:>7}  {samp}")
    return 0


def cmd_dump(rom_path, table, count, out_path):
    rom = open(rom_path, "rb").read()
    off = int(table, 0) - 0x08000000
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "address", "text"])
        for i in range(int(count)):
            a = int.from_bytes(rom[off + i * 4:off + i * 4 + 4],
                               "little") - 0x08000000
            t, _ = best(rom, a)
            w.writerow([i, f"{0x08000000+a:#010x}", t])
    print(f"wrote {out_path}: {count} strings")
    return 0


def main(argv):
    if len(argv) == 2 and argv[0] == "list":
        return cmd_list(argv[1])
    if len(argv) == 5 and argv[0] == "dump":
        return cmd_dump(argv[1], argv[2], argv[3], argv[4])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
