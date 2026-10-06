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

## Same-job cross-side divergence: demonstrated (2026-10-05)

The roadmap's demonstration ("two same-job allies diverge while an enemy of
that job is unaffected") ran on the purpose-built two-ally fixture
`outputs/lua-nav/a4-multi-ally-battle-start.ss0` (sha1
`34c88fa47dc314891f93584e151484451dc94aa6`, built by
`tools/a4_fixture_build.py`, round-trip verified by its `--verify`): players
**Marche** and **Montblanc** both job 5, five enemies including same-job
**Velasquez** (job 5), Judge present. Evidence:
`outputs/autobattle/A4-demo/fixture-build.json` + `demo.json` (schema
`a4-divergence-demo/3`, `A4-DEMO PASS` in 169.7 s, all six verdicts true).

Method (player-menu boundary, zero memory writes — `writes=[]`):

1. menu 1: owner **Marche** identified from the engine's own target cursor
   (rule `target-cursor-own-tile`, cursor `(4,10)` = his own tile),
   `identified-move` committed — the engine moved him `(4,10) -> (4,11)`
   (`moved_slots=[7]`);
2. menu 2: owner **Montblanc** (cursor `(5,10)`; Marche excluded from
   attribution), `identified-wait` committed — no tile change
   (`moved_slots=[]`);
3. final pump: same-job enemy **Velasquez** attributed a retail turn by
   decoded-name seed attribution, unaffected throughout.

Attribution law established while building the demo (recorded as DE-030):
**CT cannot name the menu owner on a multi-ally fixture.** The owner parks
ABOVE `PARK_CT_MAX` (306/353 observed) while the frozen ally sits stable at
0, so the flash+park rule that worked on the solo fixture swapped both
attributions in demo run 2 — the commits were engine-correct, only the
labels were wrong, and the full-snapshot tile delta exposed the swap. The
owner is now read from the target cursor (`TARGET_X/Y` reads the owner's own
tile at a freshly opened menu, the C2 law) held across two ticks, with the
tile delta as independent cross-check.

## Precedence contract (frozen for A5+)

When several assignment scopes could apply to one actor, the adapter resolves
in this fixed order — first match wins:

1. **Explicit character assignment** — a rule set keyed by the identity
   vector (name + id; job/race fields recorded for human review, not for
   matching).
2. **Job default** — keyed by the unit's active job id.
3. **Party default** — keyed by side (the player's party vs the enemy clan);
   the player's side is identified by the RAM-named member(s), per the guard.
4. **Supported fallback** — no rule matched: use an explicitly identified legal
   Wait only where its validity is established; otherwise pause without input.
   This external companion fallback is not native retail-AI delegation.

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
  `None` (= no match; the adapter applies the documented supported fallback).
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
| Same-job divergence demo | Bounded PASS on the two-ally fixture, 2026-10-05; `docs/receipts/autobattle/A4.json` and `outputs/autobattle/A4-demo/demo.json`. Public-runner integration is A5.1. |

## Integration limit (2026-10-06 review)

The public runner now uses `autobattle_identity.py`: boot-verified name/id
with job/side agreement, two fresh cursor-own-tile observations, per-input
actor validation, and an independent full-party movement cross-check. Two
reloads of the A4 fixture produced Marche Move and Montblanc Wait through
`run_autobattle.py`; the final run is `outputs/autobattle/a51-two-player-final`.
Only the verified seven/eight-record fixtures and identified Move/Wait are
supported. Multi-player battle-end signatures are not certified.

**A5.1 is accepted** (2026-10-06). The live manual takeover now passes and is
reproducible: `run_autobattle.py --pause-at-boundary` stops on purpose at the
identified player menu (open, untouched, zero automation input), the manual
layer commits a window-SendInput Move whose destination is verified from a
whole-board tile delta, and `--resume` adopts the same pid and continues from
that tile. The manual layer identifies the owner from the roster rather than
slot 6, and `adopt_existing` retries the roster guard because the battle
struct is scratch for ~10 s after a turn closes (DE-032). See
`docs/a51-integration.md` and `docs/receipts/autobattle/A5.json`.
