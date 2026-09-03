"""Guarded patches for verified AI target-candidate ordering.

sub_080C2940 sorts the per-actor target-candidate arena (20-byte records,
count halfword at arena+0x324) before the evaluator runs. Its comparator
spans 0x080C2F40..0x080C2F94 and selects with

  1. signed halfword +0x10: challenger <= 0 keeps the incumbent order,
     incumbent <= 0 swaps immediately;
  2. signed bytes +0x14 (incumbent) and +0x1C (challenger), lower wins;
  3. full tie: Rand() % 101 <= 49, so about half the ties swap and every tie
     consumes one RNG draw (window 0x080C2F7E..0x080C2F94).

The retail window is reachable only by falling through the equality compare
(no branch, jump-table entry, or ROM pointer lands inside it), which is what
makes a same-size patch safe. deterministic_ties replaces the roll with an
unconditional branch to the keep-ordering path, so equal candidates keep the
earlier one and the battle RNG is left untouched.

Execution evidence: running the retail window on an emulated ARM7TDMI over
500 seeds swaps exactly half the ties, and the patched window keeps every tie
without drawing from the RNG.
"""


PATCH_OFFSET = 0x0C2F7E
PATCH_END = 0x0C2F94

# The retail random tie-break: one Rand() draw, swap when Rand() % 101 <= 49.
# Each BL is followed by lsls/asrs halfwords that sign-extend the 16-bit result.
RETAIL = bytes.fromhex(
    "3ff741fc0004001465217ff0e2fc00040014312817dc"
)

# Unconditional branch to the keep-ordering path at 0x080C2FC4, then ARMv4T
# NOP (mov r8, r8) filler over the abandoned roll code. Equal candidates keep
# the earlier one and the RNG is never consulted.
DETERMINISTIC_TIES = bytes.fromhex("21e0" + "c046" * 10)

POLICIES = {
    "retail": RETAIL,
    "deterministic_ties": DETERMINISTIC_TIES,
}


def apply_policy(rom, policy):
    if policy not in POLICIES:
        raise ValueError(f"unknown target_ordering policy {policy!r}")
    current = bytes(rom[PATCH_OFFSET:PATCH_END])
    if current != RETAIL:
        raise ValueError("target-ordering patch site does not match the supported retail code")
    replacement = POLICIES[policy]
    rom[PATCH_OFFSET:PATCH_END] = replacement
    return sum(a != b for a, b in zip(current, replacement))
