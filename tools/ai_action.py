"""Guarded patches for verified AI action selection.

Before sub_080C2940 walks target candidates it picks which behaviour slot the
actor acts on. The walk (0x080C29A2..0x080C2A8C) holds the actor's behaviour
array ([sp,#0x28] base: count at +0x527e, kind bytes at +0x5276+i) and steps
slot index i from 0: every non-last slot survives only on a Rand() % 101 > 50
roll (window 0x080C29BE..0x080C29D4; <= 50 skips to the next slot, the last
slot never rolls), and the selected slot's kind dispatches through a jump
table at 0x080C29EC. Two of the eight kinds flip their own coin:

- kind 1 (0x080C2A22): Rand() % 101 <= 50 sets flag 0x80, otherwise 0x81.
- kind 2 (0x080C2A42): Rand() % 101 <= 50 sets flag 0x80, otherwise 0x82.

A live snowball battle with a frozen RNG consumes exactly one draw on this
path; a breakpoint on Rand() pins the caller at lr=0x080C2A27 (the kind-2
coin), and NOPing exactly that call -- everything else retail -- drops the
consumption to zero. That run and a separate NOP of the walk roll (which
never fires for one-slot actors) both leave the resulting candidate arenas
byte-identical, so the draws are pure randomness with no arena effect here.

action_selection="first" removes all three draws. The walk's conditional
branch becomes unconditional (slot 0 is always processed; the dead roll code
is never reached), and each coin's Rand() call becomes `movs r0, #0` + NOP,
so the mod-101 result is 0 and the <= 50 arm runs. Every forced value -- slot
0, flag 0x80 twice -- is an outcome retail itself can produce, so the patch
cannot construct a state the retail AI could not reach. The battle RNG is
never consulted.
"""


# The non-last-slot survival roll: `bge` over the roll for the last slot
# (0x080C29BE..0x080C29C0). The roll code behind it is unreachable once the
# branch is unconditional.
WALK_OFFSET = 0x0C29BE
WALK_END = 0x0C29C0
RETAIL_WALK = bytes.fromhex("0ada")
# Unconditional branch to the process-slot path (0x080C29D6): target =
# (addr + 4) + offset * 2, offset 0x0a; halfword 0xe00a, little-endian bytes.
FIRST_WALK = bytes.fromhex("0ae0")

# kind-1 behaviour coin (0x080C2A22..0x080C2A26) and kind-2 coin
# (0x080C2A42..0x080C2A46). Each BL is followed by sign-extending halfwords
# that the movs/nop replacement leaves intact and harmless.
KIND1_OFFSET = 0x0C2A22
KIND1_END = 0x0C2A26
KIND2_OFFSET = 0x0C2A42
KIND2_END = 0x0C2A46
RETAIL_KIND1 = bytes.fromhex("3ff7effe")
RETAIL_KIND2 = bytes.fromhex("3ff7dffe")
# movs r0, #0 ; nop -- mod 101 of 0 is 0, so the <= 50 arm (flag 0x80) runs.
FIRST_COIN = bytes.fromhex("2000bf00")

SITES = (
    (WALK_OFFSET, WALK_END, RETAIL_WALK, FIRST_WALK, "action walk"),
    (KIND1_OFFSET, KIND1_END, RETAIL_KIND1, FIRST_COIN, "kind-1 behaviour coin"),
    (KIND2_OFFSET, KIND2_END, RETAIL_KIND2, FIRST_COIN, "kind-2 behaviour coin"),
)

POLICIES = {
    "retail": None,
    "first": (FIRST_WALK, FIRST_COIN, FIRST_COIN),
}


def apply_policy(rom, policy):
    if policy not in POLICIES:
        raise ValueError(f"unknown action_selection policy {policy!r}")
    changed = 0
    for offset, end, retail, replacement, label in SITES:
        if policy == "retail":
            replacement = retail
        current = bytes(rom[offset:end])
        if current != retail:
            raise ValueError(
                f"action-selection {label} site does not match the supported retail code")
        rom[offset:end] = replacement
        changed += sum(a != b for a, b in zip(current, replacement))
    return changed
