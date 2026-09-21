# Strategy runtime scope (A4)

What per-character strategy assignment can key on at runtime, proven on the
verified `battle-start.ss0` fixture. Companion evidence:
`outputs/autobattle/A4-scope/probe.json` (live, 2026-09-21, tool
`tools/probe_strategy_scope.py`).

## Identity: the proven per-character key

A per-character policy must name the same unit at every turn boundary,
across reloads, and across the engine's two unit arrays (DE-016: slot
indexes do not even name the same units across the roster at `0x020159E8`
and the AI mirror at `0x02002FC4`). The probe measured one immutable
identity vector — **(decoded name, unit type, base job, active job, race,
level, unit id, side bit)** — at every phase of two fresh boots, driving two
player turns per boot:

* **Stable within a battle**: all 7 live slots byte-identical across
  menu-open, post-turn-1, and post-turn-2 (7 slots × 3 phases × 2 boots).
* **Stable across reloads**: all 7 slots identical between two fresh boots
  of the same fixture. The same vector is also what the boot guard already
  checks (`slot0_name`, `slot0_id`), so a policy's character map can be
  validated at boot with no new machinery.
* **Mutable state, not identity**: ct, hp, mp, tile changed between phases
  as the engine charged and acted; they are excluded from the key.
* **Known limitation (DE-016 boundary)**: this fixture holds one player unit
  and five distinct-job enemies, so the vector is proven unique *within this
  roster*. Job-change mid-battle and two units sharing every field are not
  produced here; a future fixture that breaks the vector's uniqueness would
  need `id`-level disambiguation, which the probe records anyway.

## Sequencer attribution: actor identity by decoded name

After each driven player Wait commit, the engine served sequencer seeds with
context records decoding to **all five enemy names** (Carson, Godfrey, Jon,
Schneider, Velasquez) in both boots — the actors that acted between the
player's turns are named by decode, never by slot index. Marche never
appeared in a seed context in this fixture (his turns are the scripted menu
state, not sequencer-driven), which matches the A2.3→A2.4a correction that
the sequencer references the AI mirror copy the player unit is absent from.

## The AI mirror maps 1:1 by identity

The mirror at `0x02002FC4` (twelve 0x108-byte records; ai-findings.md) held
exactly six active records, decoding to the five enemies plus the Judge with
**job and unit id agreeing with the roster record of the same decoded name
6/6**. Marche was absent **by construction, and verified rather than
assumed**: the probe reports `mirror_absent == ["Marche"]` and fails if any
other roster unit is missing from the mirror or if a mirror name gains no
roster match.

Consequence for the adapter: a policy written against roster identity
applies unchanged to sequencer-attributed actors — map by decoded name
(+ job/id agreement), never by array position in either array.

## Interception point: the player-menu boundary (Option B)

Per `docs/player-ai-control.md` (design comparison), the interception point
for per-character policy is **external action selection at the proven
player-menu boundary**: the engine owns the turn; the companion observes the
picked actor (the parked player menu is the player unit's turn — no side-flag
write is involved) and supplies one engine-legal action through the
`0x08000494` key-poll channel, with the C2 identified-candidate discipline
(command and destination read from RAM before the confirming input; echo
gate before any commit). This is player-only by construction: enemy turns
never open the player menu, and no persistent field is written.

The A2.4b result stands as the negative control for the *other* candidate:
`+0xEA` bit 7 is Stop, not an AI switch — there is no proven one-flag
delegation lever, which is why the runner-side chooser is the architecture.

## Same-job cross-side divergence: blocked on a fixture, not on a mechanism

The roadmap's demonstration ("two same-job allies diverge while an enemy of
that job is unaffected") cannot be executed on any verified fixture today:
the battle roster holds five enemies with **five distinct jobs** (41/5/40/36/
22) and one player unit. The placement screen showed 0/6 dispatchable clan
members, so a two-ally dispatch fixture is *constructible* through the A1
capture route, but that is a new fixture capture plus new guard expectations
and is its own task — this packet does not claim the demo.

What A4 contributes now: the identity vector above is exactly the key a
policy map would use, and the divergence demo's *measurement* is already
implemented (`probe.seeds` attribution + `effect_snapshot` diffs). The
remaining work is fixture construction, not mechanism research.

## Precedence contract (frozen for A5+)

When several assignment scopes could apply to one actor, the adapter resolves
in this fixed order — first match wins:

1. **Explicit character assignment** — a rule set keyed by the identity
   vector (name + id; job/race fields recorded for human review, not for
   matching).
2. **Job default** — keyed by the unit's active job id.
3. **Party default** — keyed by side (the player's party vs the enemy clan);
   the player's side is identified by the RAM-named member(s), per the guard.
4. **Retail behavior** — no rule matched: the runner sends nothing beyond
   the proven Wait fallback, exactly as today.

Rules: engine legality always wins over policy preference (A5's rejected-
candidate law); assignment is read-only against game state (no save fields,
no ROM patches at this stage); and a policy that names a unit not present in
the boot guard's roster fails closed at boot instead of silently applying to
nobody.

## Runtime adapter contract (A5's seam)

The chooser the runtime already drives (`plan_identified_move` /
`plan_identified_wait` / `commit_*`) becomes the only seam A5 plugs into:

* **Input**: the probe's identity vector for the menu owner + the C2
  identified candidate data (command id, target cursor, tile) + the
  candidate evidence the runtime already reads (abilities, hp/mp, tile).
* **Output**: a plan the existing identified-commit drivers execute, or
  `None` (= retail fallback: the identified-Wait path).
* **Isolation**: the policy layer never writes memory and never presses keys
  itself; it only chooses among plans the driver can prove from RAM.
* **Restoration**: nothing to restore — the adapter writes nothing (Option B
  is reversible by construction); the A2.4b Stop-bit path stays dead.

## Evidence map

| Claim | Evidence |
|---|---|
| Identity vector stable within battle | `probe.json` boots[].phases, verdict `identity_stable_within_battle` (7 slots × 3 phases × 2 boots) |
| Identity stable across reloads | verdict `identity_stable_across_reload` (boot 2 vs boot 1, all 7 slots) |
| Mirror maps 1:1 by name+job+id | verdict `mirror_maps_1to1_by_name` (6/6 active records), `mirror_absent == ["Marche"]` |
| Enemy actors named by decode | boots[].seeds_actors: all five enemy names after every player commit (8 seeds/boot) |
| Interception is player-only | player-ai-control.md Option B + A2.4b Stop-bit refutation (DE-015 lineage) |
| Same-job divergence demo | **not claimed** — blocked on a two-ally fixture (construction path documented above) |
