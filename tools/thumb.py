"""Minimal ARMv4T Thumb decoder.

Capstone's Thumb mode happily decodes ARMv6T2+ encodings (cbz, it, movw...)
that the GBA's ARM7TDMI cannot execute. Decoding data as code and getting
plausible-looking output is the main failure mode when mapping a ROM, so
function discovery uses this strict classifier instead and leaves capstone
for display only.

Game-generic: no FFTA constants or table addresses; reusable in any GBA
ARMv4T project as-is.
"""

# instruction classes
INVALID = "invalid"
PUSH_LR = "push_lr"
POP_PC = "pop_pc"
BX = "bx"
BL = "bl"
SWI = "swi"
B_COND = "b_cond"
B_UNCOND = "b_uncond"
PC_LOAD = "pc_load"
OTHER = "other"


def classify(hw):
    """Return (class, payload) for a 16-bit halfword under ARMv4T rules."""
    top8 = hw >> 8

    # 1011 x0x1 -> CBZ/CBNZ, and 1011 1111 -> IT. Neither exists on ARMv4T.
    if top8 in (0xB1, 0xB3, 0xB9, 0xBB, 0xBF):
        return INVALID, None
    # BLX suffix / 32-bit Thumb-2 first halfwords: not on ARMv4T.
    if 0xE8 <= top8 <= 0xEF:
        return INVALID, None
    # undefined space
    if top8 in (0xB6, 0xB7, 0xBA, 0xBE):
        return INVALID, None

    if top8 == 0xB5:
        return PUSH_LR, hw & 0xFF
    if top8 == 0xBD:
        return POP_PC, hw & 0xFF
    if (hw & 0xFF80) == 0x4700:
        return BX, (hw >> 3) & 0xF
    if (hw & 0xF800) == 0xF000:
        return BL, hw & 0x7FF          # high half of a BL pair
    if (hw & 0xF800) == 0xF800:
        return BL, hw & 0x7FF          # low half (only valid after a high half)
    if top8 == 0xDF:
        return SWI, hw & 0xFF
    if top8 == 0xDE:
        return INVALID, None
    if 0xD0 <= top8 <= 0xDD:
        off = hw & 0xFF
        if off & 0x80:
            off -= 0x100
        return B_COND, off * 2 + 4
    if (hw & 0xF800) == 0xE000:
        off = hw & 0x7FF
        if off & 0x400:
            off -= 0x800
        return B_UNCOND, off * 2 + 4
    if (hw & 0xF800) == 0x4800:
        return PC_LOAD, (hw & 0xFF) * 4
    if (hw & 0xF800) == 0xA000:
        return PC_LOAD, (hw & 0xFF) * 4

    return OTHER, None


def bl_target(addr, hw1, hw2):
    """Resolve a Thumb BL pair at `addr` to its target address."""
    hi = hw1 & 0x7FF
    if hi & 0x400:
        hi -= 0x800
    lo = hw2 & 0x7FF
    return addr + 4 + (hi << 12) + (lo << 1)


def find_extent(rom, start, max_bytes=512):
    """Walk a function from `start`, returning (end_offset, is_leaf) or None.

    Returns None if the bytes decode to anything impossible on ARMv4T, which
    is the signal that `start` was not really a function.
    """
    def hw(o):
        return rom[o] | (rom[o + 1] << 8)

    pool = set()
    max_reach = start
    last_return = None
    is_leaf = True
    pc = start
    limit = start + max_bytes
    popped = None      # register just restored by a lone `pop {rN}`

    while pc < limit and pc + 1 < len(rom):
        if pc in pool:
            pc += 4
            continue

        cls, payload = classify(hw(pc))

        if cls is INVALID:
            return None

        if cls is BL:
            if pc + 3 >= len(rom):
                return None
            cls2, _ = classify(hw(pc + 2))
            if cls2 is not BL:
                return None
            is_leaf = False
            pc += 4
            continue

        if cls is SWI:
            is_leaf = False

        elif cls is PC_LOAD:
            addr = ((pc + 4) & ~3) + payload
            pool.add(addr)
            max_reach = max(max_reach, addr + 4)

        elif cls in (B_COND, B_UNCOND):
            target = pc + payload
            if target < start:
                return None            # branches out the top: not a lone function
            max_reach = max(max_reach, target)

        elif cls is POP_PC or (cls is BX and payload == 14):
            last_return = pc + 2

        # `pop {rN}` + `bx rN` is how gcc returns under -mthumb-interwork on
        # ARMv4T, where `pop {pc}` cannot change instruction set.
        if cls is BX and payload is not None and payload == popped:
            last_return = pc + 2

        hw_now = hw(pc)
        if (hw_now & 0xFF00) == 0xBC00 and bin(hw_now & 0xFF).count("1") == 1:
            popped = (hw_now & 0xFF).bit_length() - 1
        else:
            popped = None

        pc += 2

        if last_return is not None and pc >= max_reach and pc >= last_return:
            end = max(last_return, max_reach)
            return end, is_leaf

    return None
