"""Scan the ROM for every `bl` reaching the turn-manager gate helpers.

Census for A2.3: who calls sub_080CD8B4 (+0xE8 bit1), sub_080CD92C
(+0xE8 bit6), and sub_0812E368 (CT speed term) besides the turn manager
sub_0809E05C. Answered by a full BL sweep, not by assumption.

Usage: python tools/scan_gate_callers.py
"""
import struct
import sys

ROM_PATH = "baserom.gba"
TARGETS = (0x080CD8B4, 0x080CD92C, 0x0812E368)
LO, HI = 0x08000000, 0x08370000  # dense code region


def bl_targets(rom, lo_off, hi_off):
    """Yield (site_addr, target_addr) for every Thumb BL pair in range."""
    cur_hi10 = None
    for i in range(lo_off, hi_off, 2):
        hw = rom[i] | (rom[i + 1] << 8)
        if (hw & 0xF800) == 0xF000:
            cur_hi10 = i
            continue
        if (hw & 0xF800) == 0xF800 and cur_hi10 is not None \
                and i == cur_hi10 + 2:
            hi = (rom[cur_hi10] | (rom[cur_hi10 + 1] << 8)) & 0x7FF
            lo = hw & 0x7FF
            offset = (hi << 12) | (lo << 1)
            if offset & 0x400000:
                offset -= 0x800000
            site = 0x08000000 + cur_hi10
            yield site, site + 4 + offset
        else:
            cur_hi10 = None


def main():
    rom = open(ROM_PATH, "rb").read()
    end = min(len(rom), HI - 0x08000000)
    hits = {t: [] for t in TARGETS}
    for site, target in bl_targets(rom, LO - 0x08000000, end):
        if target in hits:
            hits[target].append(site)
    for t in TARGETS:
        sites = hits[t]
        print(f"{t:#010x}: {len(sites)} call sites")
        for s in sites:
            print(f"  {s:#010x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
