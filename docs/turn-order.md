# The turn-order (CT) system

Found statically by following the slow/haste-adjusted speed getter
`sub_0812E368` back to its callers. This closes the "identify the turn-order
code" item from the Phase 1 plan in `docs/roadmap.md`.

## The call chain

```
battle loop
  -> sub_0809E1E0  (1,614 bytes)   # turn loop / battle driver
      -> sub_0809E05C  (388 bytes) # turn manager: pick the next actor
          -> sub_0809DF7C  (222 bytes) # CT tick: charge, advance, reduce
```

Both inner functions are small enough to read end to end, and they are the
first two functions in the whole ROM to call the speed getter outside the AI
evaluator. The evaluator's own two calls (`case id 1` and `case id 2`) are the
only other readers, which is what makes this chain recognisable as the turn
system rather than as more AI logic.

## The battle struct

`sub_0809DF7C(battle)` and `sub_0809E05C(battle)` share one struct.

| offset | width | meaning |
|---|---|---|
| `+0x00` | u32 | unit count |
| `+0x04 + i*0x108` | ptr | unit struct for slot `i` (stride `0x108` = 264) |
| `+0xd0` (per slot) | u16 | **CT** — charge-time accumulator |
| `+0xd4` (per slot) | u16 | **CT carry** — leftover charge carried into the next tick |
| `+0xe08` | bytes | active-unit index list (built each turn) |
| `+0xe15` | u8 | length of that list / current-turn marker |
| `+0xd6c` | ptr | secondary list written during the advance (see below) |

The stride is proven twice: `sub_0809E05C` computes `index * 33 * 8` to reach
a slot, and `sub_0809DF7C` advances both its pointers by `0x84 << 1`.

These fields are also exposed by the generic unit-stat accessor: stat `0x23`
is CT at unit `+0xd0`, stat `0x24` is base Speed at `+0xd2`, and stat `0x25`
is CT carry at `+0xd4`. AI validation executes a one-unit tick and observes
`900 + 100 + 25` normalize to CT 1000 with carry 25.

## The CT tick (`sub_0809DF7C`)

For every slot, in order:

1. If `sub_080CD92C(unit)` is set (`+0xe8` bit 6), the unit is skipped: CT and
   carry are both zeroed.
2. Otherwise `speed = sub_0812E368(unit)` — the signed item speed, halved by
   Speed Down, Slow, or one still-unidentified status and doubled by Haste.
   Slow and Haste both apply, so their shifts cancel. If speed is 0 the unit
   is also skipped.
3. If `sub_080CDCEC(unit)` is set (`+0xed` bit 6), skip again.
4. Otherwise **`CT += speed + carry`**, then `carry = 0`.

So a unit must pass two status checks and have nonzero speed before its CT
moves. This is the whole "who is eligible to act" predicate.

After the loop, if the maximum CT across all units does not exceed the
threshold nothing else happens. The threshold is the constant `0xFA << 2 =
1000`.

When some unit's CT *does* exceed 1000, the advance is:

```
delta = min(max_CT - 1000, 500)
for each unit:
    if CT >= delta:  CT -= delta; carry = delta
    else:            carry = CT; CT = 0
```

`delta` is capped at 500 so no single tick can remove more than half the gauge;
the leader's CT lands exactly on 1000 (unless the cap bites). Every unit stores
the amount removed in carry: `delta` when it had enough CT, or its whole CT
when it did not. The next charging pass adds that value back before performing
another common normalization. The earlier documentation incorrectly said the
non-underflow branch left carry at zero; execution of the complete tick exposed
the missing `strh delta, [carry]` at `0x0809E03E`.

The two literals involved are `0xFFFFE0C0 = -8000` (the initial max-CT
sentinel) and `0xFFFFFC18 = -1000` (the threshold subtraction).

## The turn manager (`sub_0809E05C`)

1. **Build the active list.** For each slot where `sub_080CD8B4(unit)` is set
   (`+0xe8` bit 1) *and* speed is nonzero, append the slot index to the list
   at `+0xe08` and increment the count at `+0xe15`.
2. **Preload the just-acted unit.** If the current-turn marker at `+0xe15`
   (read as a signed byte) is nonzero, write `0x1000` to that slot's carry
   (`+0xd4`). This gives the actor its head start for the next cycle.
3. **Find the next actor.** Scan the slots for one whose `sub_080CD92C` is
   clear, speed is nonzero, `sub_080CDCEC` is clear, and CT > 999. If none
   qualifies, call `sub_0809DF7C` to charge one tick and rescan.
4. **Advance the rest.** For every slot that fails the eligibility checks,
   read the pointer at `+0xd6c` and store `-100` into `[that + 0x24]`.

The last step is the one piece whose game meaning is not pinned: it writes a
negative offset to a secondary structure once per ineligible unit. The exact
role of `+0xd6c` and the `-100` is left open rather than guessed.

## What this contributes

- **Turn-order code identified**, the last static piece of Phase 1.
- **Six status/capability bits now have behavioural handles**, which is the exact
  technique Phase 5 (`docs/roadmap.md`) wants extended:

| getter | bit | role in the turn loop |
|---|---|---|
| `sub_080CD8B4` | `+0xe8` bit 1 | must be **set** to be in the active list — the "present/alive" eligibility flag |
| `sub_080CD92C` | `+0xe8` bit 6 | when **set**, the unit never charges (CT zeroed, never selected) — a turn-suppressing status |
| `sub_080CDCEC` | `+0xed` bit 6 | when **set**, the unit is skipped by both the tick and the actor scan — a second turn-suppressing status |
| `sub_080CDA34` | `+0xec` bit 2 | **Speed Down**; halves effective speed |
| `sub_080CDA64` | `+0xea` bit 1 | unidentified; halves effective speed and makes the target easier to hit, but the effect-descriptor chain proves it is not Sleep |
| `sub_080CDAC4` | `+0xea` bit 6 | **Slow**; halves effective speed |
| `sub_080CDAAC` | `+0xea` bit 5 | **Haste**; doubles effective speed |

The first three and `sub_080CDA64` remain behavior descriptions rather than
status names. Speed Down, Slow, and Haste have independent naming anchors and
are protected by `tools/validate_statuses.py`. This preserves the project
rule: do not enshrine a semantic name without more than a plausible bit
position.

## Open questions

1. The `0x1000` carry preload and the `-100` secondary-list write — exact
   game meaning (this is what the live mGBA trace in Phase 1 is for).
2. Which states sit on `+0xe8` bits 1/6 and `+0xed` bit 6 — resolvable by
   freezing each status in the game and watching whether the unit still takes
   turns.
