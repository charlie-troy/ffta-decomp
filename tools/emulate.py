"""Run functions out of the ROM on an emulated ARM7TDMI.

Static analysis can only say what code appears to do. This actually executes
it, which is the difference between "the derivation says higher priority means
more likely" and measuring it.

Nothing here needs the game to be playable: the ROM is mapped, RAM is blank,
and individual functions are called with chosen arguments.

    from emulate import Gba
    gba = Gba(rom_path)
    gba.write32(0x030034B0, 12345)          # seed the RNG
    r = gba.call(0x0812F1DC, [60])          # returns r0

Game-generic: knows the GBA memory map, nothing about FFTA's data; reusable
in any GBA project as-is.
"""
import struct

from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_PROT_ALL,
                     UcError)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
                               UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
                               UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                               UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR,
                               UC_ARM_REG_PC, UC_ARM_REG_CPSR)

REGS = {"r0": UC_ARM_REG_R0, "r1": UC_ARM_REG_R1, "r2": UC_ARM_REG_R2,
        "r3": UC_ARM_REG_R3, "r4": UC_ARM_REG_R4, "r5": UC_ARM_REG_R5,
        "r6": UC_ARM_REG_R6, "r7": UC_ARM_REG_R7, "r8": UC_ARM_REG_R8,
        "sb": UC_ARM_REG_R9, "sl": UC_ARM_REG_R10, "fp": UC_ARM_REG_R11,
        "ip": UC_ARM_REG_R12}

ROM = 0x08000000
EWRAM = 0x02000000
IWRAM = 0x03000000
IO = 0x04000000
# Where a called function "returns" to. Mapped but never executed; emulation
# stops when the pc reaches it.
STOP = 0x01000000

ARGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]


class Gba:
    def __init__(self, rom_path):
        self.rom = open(rom_path, "rb").read()
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.uc.mem_map(ROM, 0x1000000, UC_PROT_ALL)
        self.uc.mem_map(EWRAM, 0x40000, UC_PROT_ALL)
        self.uc.mem_map(IWRAM, 0x8000, UC_PROT_ALL)
        self.uc.mem_map(IO, 0x1000, UC_PROT_ALL)
        self.uc.mem_map(STOP, 0x1000, UC_PROT_ALL)
        self.uc.mem_write(ROM, self.rom)
        self.reset_ram()

    def reset_ram(self):
        self.uc.mem_write(EWRAM, b"\x00" * 0x40000)
        self.uc.mem_write(IWRAM, b"\x00" * 0x8000)

    def write32(self, addr, val):
        self.uc.mem_write(addr, struct.pack("<I", val & 0xFFFFFFFF))

    def read32(self, addr):
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def write8(self, addr, val):
        self.uc.mem_write(addr, bytes([val & 0xFF]))

    def call(self, addr, args=(), timeout_insns=200000):
        """Call a Thumb function and return r0."""
        for i, reg in enumerate(ARGS):
            self.uc.reg_write(reg, args[i] if i < len(args) else 0)
        self.uc.reg_write(UC_ARM_REG_SP, IWRAM + 0x7F00)
        # Odd address keeps the Thumb bit set when the epilogue does `bx lr`.
        self.uc.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.uc.reg_write(UC_ARM_REG_CPSR, 0x33)      # Thumb, system mode
        self.uc.emu_start(addr | 1, STOP, count=timeout_insns)
        return self.uc.reg_read(UC_ARM_REG_R0)

    def run_range(self, start, stop, regs=None, timeout_insns=200000):
        """Execute a stretch of code with chosen registers, return r0.

        Used to exercise a fragment such as one arm of a switch, where calling
        the whole function would need game state that does not exist here.
        """
        self.uc.reg_write(UC_ARM_REG_SP, IWRAM + 0x7F00)
        self.uc.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.uc.reg_write(UC_ARM_REG_CPSR, 0x33)
        for name, val in (regs or {}).items():
            self.uc.reg_write(REGS[name], val)
        self.uc.emu_start(start | 1, stop, count=timeout_insns)
        return self.uc.reg_read(UC_ARM_REG_R0)


if __name__ == "__main__":
    import sys
    gba = Gba(sys.argv[1])
    print("ROM mapped; header title:",
          bytes(gba.uc.mem_read(ROM + 0xA0, 12)).decode("ascii", "replace"))
