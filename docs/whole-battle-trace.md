# Whole-battle AI trace

Status: execution-verified on 2026-08-24 with mGBA 0.10.5 and the US ROM.

## Result

A real enemy turn in the opening snowball engagement enters
`sub_080C32C0` four times. The function's reconstructed signature is
`AiEvaluateAbility(user, target, action, checkCost)`. Across the four entries:

- `r0` (user) stays at `0x02002FC4`;
- `r1` (target) visits four distinct units, in order:
  `0x020031D4`, `0x020032DC`, `0x020030CC`, `0x020034EC`;
- `r3` (`checkCost`) stays zero;
- the stack snapshot is identical at every entry;
- execution continues into the enemy's snowball action and its tutorial text.

This confirms that the candidate-list/evaluator model is on the live battle
path: the actor is held constant while every candidate target is passed through
the 5,352-byte evaluator. No upstream rule bypassed the evaluator or collapsed
the four targets in this turn. This one tutorial turn cannot prove that no
mission-, law-, or effect-specific rule dominates in every later battle; that
broader claim remains deliberately out of scope.

## Reproducibility

The repository's `baserom.sav` was blank (`0xFF` throughout), so the battle was
reached from New Game rather than from imported campaign data.

1. Run `baserom.gba` in mGBA and load `tools/mgba_reach_snowball.lua` from
   **Tools -> Scripting**. It advances the opening and leaves periodic
   screenshots plus savestates under `outputs/mgba-snowball/`.
2. Load `state-8400.ss0`, cancel the move grid if it is open, choose **Wait**,
   and save `state-facing.ss0` before confirming Ritz's facing.
3. Start mGBA's GDB stub from that state:

   ```powershell
   mGBA.exe -g -t outputs\mgba-snowball\state-facing.ss0 baserom.gba
   ```

4. Arm the exact trace:

   ```powershell
   python tools\trace_mgba.py data\functions.json --rom baserom.gba `
     --break-at 0x080C32C0 --break-hits 4 --break-timeout 60 `
     --out outputs\mgba-snowball\trace.json
   ```

5. Load `tools/mgba_replay_ai_turn.lua`. It writes `0x12345678` to the RNG
   state at `0x030034B0` and confirms facing. The breakpoint trace checkpoints
   after every hit, so a later emulator disconnect does not erase partial data.

Two fresh runs from `state-facing.ss0` reproduced all registers, RNG values,
and stack bytes exactly. The four RNG states seen at evaluator entry were
`0x7E9CA507`, `0xB9CFFC5D`, `0x54D48AA3`, and `0xBB950159`.

Validate any repeat pair with:

```powershell
python tools\validate_ai_trace.py trace-a.json trace-b.json
```

The validator checks exact breakpoint mode/address, four target evaluations,
the stable user/distinct-target invariant, and byte-for-byte replay equality.
