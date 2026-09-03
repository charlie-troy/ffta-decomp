"""Guarded patches for verified AI target-candidate ordering.

sub_080C2940 sorts the per-actor target-candidate arena (20-byte candidate
records at record+4, s16 impact score at candidate+0x0c, AI-priority byte at
candidate+0x10, count halfword at arena+0x324) before the evaluator runs.
Its second argument selects between two comparator regimes, and each regime
owns exactly one RNG draw:

- mode=1 (caller 0x080C077C), comparator from 0x080C2F28: challenger score
  <= 0 keeps the incumbent order, incumbent <= 0 swaps, signed priority bytes
  compare, and a full tie rolls Rand() % 101 <= 49 -- about half the ties
  swap and every tie consumes one RNG draw (window 0x080C2F7E..0x080C2F94).
- mode=0 (caller 0x080C078A, argument 0x87 -- the slot walk is skipped and
  the record walk dispatches straight to its case-7 regime), comparator from
  0x080C2D5C: the same score and priority checks run, three exemption scans
  look for KO/heal/Heaver effects, and when the challenger score is negative
  with no exemption found, a Rand() % 101 <= 49 roll gates whether the swap
  is even considered (window 0x080C2E9E..0x080C2EB6; <= 49 proceeds to the
  ally-safety checks, > 49 keeps the incumbent order). The case-7 record walk
  also randomizes candidate enumeration: targets above maxHP/3 get the random
  BST key Rand() % 0x201 + 0x10000 while low-HP targets use their current HP
  (branch 0x080C2C58..0x080C2C5A), so mode=0 full ties break by a random
  enumeration order. A live battle draws 3 times here -- one roll per
  healthy-target record.

Both windows are reached only by falling through their preceding compares
(no branch, jump-table entry, or ROM pointer lands inside either), which is
what makes same-size patches safe. deterministic_ties replaces each roll with
an unconditional branch to the keep-ordering path and NOPs the enumeration
branch, so earlier candidates win, mode=0 ties break by ascending current HP
(the same key the low-HP branch already uses), and the battle RNG is left
untouched.

Execution evidence: running the retail mode=1 window on an emulated ARM7TDMI
over 500 seeds swaps exactly half the ties; the patched window keeps every
tie without drawing from the RNG. The mode=0 window likewise swaps about half
of 500 seeded runs and consumes a draw only on the swap path.
"""


# mode=1 full-tie roll: 22 bytes (0x080C2F7E..0x080C2F94).
PATCH_OFFSET = 0x0C2F7E
PATCH_END = 0x0C2F94
# mode=0 probabilistic gate roll: 24 bytes (0x080C2E9E..0x080C2EB6).
GATE_OFFSET = 0x0C2E9E
GATE_END = 0x0C2EB6
# mode=0 enumeration-order roll: 2 bytes (0x080C2C58..0x080C2C5A). The case-7
# record walk inserts each target unit into the ordering BST with key =
# current HP when current <= maxHP/3, else with the random key
# Rand() % 0x201 + 0x10000; the branch at 0x080C2C58 selects the random key.
ENUM_OFFSET = 0x0C2C58
ENUM_END = 0x0C2C5A

# The retail mode=1 tie-break: one Rand() draw, swap when Rand() % 101 <= 49.
# Each BL is followed by lsls/asrs halfwords that sign-extend the 16-bit result.
RETAIL = bytes.fromhex(
    "3ff741fc0004001465217ff0e2fc00040014312817dc"
)
# The retail mode=0 gate: same roll shape, one window later in the function.
RETAIL_GATE = bytes.fromhex(
    "3ff7b1fc0004001465217ff052fd00040014312800dd86e0"
)
# The retail mode=0 enumeration branch (bgt over the direct HP-key insert).
RETAIL_ENUM = bytes.fromhex("06dc")
# NOP: never take the random-key branch, so every target uses the same key
# the low-HP branch already uses (current HP) and the enumeration is
# deterministic HP-ascending.
ENUM_KEY_HP = bytes.fromhex("c046")

# Unconditional branch to the keep-ordering path (0x080C2FC4 for both
# windows), then ARMv4T NOP (mov r8, r8) filler over the abandoned roll code.
# mode=1: equal candidates keep the earlier one. mode=0: an unexempted
# negative-score challenger never swaps instead of coin-flipping. Either way
# the RNG is never consulted and the conservative side of the retail coin is
# always taken.
DETERMINISTIC_TIES = bytes.fromhex("21e0" + "c046" * 10)
DETERMINISTIC_GATE = bytes.fromhex("91e0" + "c046" * 11)

POLICIES = {
    "retail": RETAIL,
    "deterministic_ties": DETERMINISTIC_TIES,
}


def apply_policy(rom, policy):
    if policy not in POLICIES:
        raise ValueError(f"unknown target_ordering policy {policy!r}")
    sites = ((PATCH_OFFSET, PATCH_END, RETAIL, "tie-break"),
             (GATE_OFFSET, GATE_END, RETAIL_GATE, "order gate"),
             (ENUM_OFFSET, ENUM_END, RETAIL_ENUM, "enumeration order"))
    changed = 0
    for offset, end, retail, label in sites:
        current = bytes(rom[offset:end])
        if current != retail:
            raise ValueError(
                f"target-ordering {label} site does not match the supported retail code")
        if policy == "retail":
            replacement = retail
        elif offset == PATCH_OFFSET:
            replacement = DETERMINISTIC_TIES
        elif offset == GATE_OFFSET:
            replacement = DETERMINISTIC_GATE
        else:
            replacement = ENUM_KEY_HP
        rom[offset:end] = replacement
        changed += sum(a != b for a, b in zip(current, replacement))
    return changed
