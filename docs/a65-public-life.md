# A6.5 bounded public Life integration

Accepted2026-10-14. Canonical gate: `docs/receipts/autobattle/A6.5.json`;
final lifecycle/regressions: `docs/receipts/autobattle/A6.5.3.json`.

The explicit schema2 `--bounded-ally-life` opt-in supports only the corrected
eight-unit Montblanc5/Life5/cost10/genuine KO Marche7 fixture. It shares the
A6.4 native state-driven transaction and verifies native HP/MP and the EXP99
level-up before rebinding the actor's identity. The flag is mutually exclusive
with both Cure opt-ins. Full-Life, arbitrary KO parties, items, whole-battle
recovery and ROM-native automation remain outside this acceptance.

## Current evidence

- Two historical source-stable public Life/Wait/next-actor turns retain their
  exact kernel scope; fresh final-source full Life, recovery STOP and manual
  continuation repeat the affected public paths.
- Same-PID lifecycle on PID67648: real public STOP, window-only manual Wait,
  exact adoption and one identified resumed Montblanc Wait with20 actual
  register writes. Source/handoff/input/history audits pass.
- Independent final-source repeat on PID58184: one zero-seed resumed Wait and
  independently owned next Marche7 command menu;19 input/completion mutations
  reject and both captured source closures resolve.
- Full Life38, ally-Cure38, self-Cure26, default5, unsupported zero-input,
  reserve11, navigation STOP8 and final STOP11 fresh scoped regression checks.

The false stall came from treating a new sequencer seed as the only completion
signal. A next ally can already own an accepting command menu without a new
seed. `wait_ally_continuation.py` verifies changed canonical wrapper/member,
restored roster, pinned party, own cursor and the accepting native command
list. Its original Wait row mixup is corrected: table8/9/10/11 uses Wait10;
legacy cursor index2 is not that row ID. Existing actor/STOP/input guards stay
in force. An unreadable, stale, same, foreign or blocked actor never supplies
this completion witness.

Ordinary Move/Wait now logs actual register writes. A completed Wait's select
and confirm input must occur inside that boundary and before the next-menu
witness; a preceding Life leg cannot supply missing resumed inputs. Recovery
transport retains its separate logger, without duplicate writes.

## Reproduce bounded controls

```
python tools/run_autobattle.py --state outputs/autobattle/a64-life-fixture-02/life-recovery.ss0 --scenario configs/battle-scenarios/a4-two-player.json --tactics-policy configs/tactics/healer.json --bounded-ally-life --run-id NEW --max-turns 1 --wall-timeout 180 --on-stop kill --yes
python tools/run_life_recovery_handoff.py --run-id NEW-HANDOFF --wall-timeout 300
python tools/run_life_final_regressions.py --prefix NEW-MATRIX
```

Use new IDs. One-turn budget stops truthfully as stalled after its attributed
turn; it is not whole-battle completion. The matrix uses already verified local
fixtures and owns sequential CLI cleanup; no RAM/ROM setup is inferred.

## Historical exclusions and source provenance

Wait01/02 adopted but yielded no resumed player turn; Wait03's oversized RSP
read and Wait04's serializer failure did not produce valid diagnostics. Their
later screenshots/status reads never repaired those captures. A6.5.1's current
serializer/validator/cleanup and full raw mirror diagnostic resolve that slice.
A6.5.2 records native picks and accepting menus before the completion fix.

The first final-source reserve changed a validator file during execution and
is excluded; the stable repeat supplies that criterion. Navigation STOP can
include one already-pending second press before observation: measured1.453s
latency stays inside2s, with zero writes after the latch and no accepted Life
target or final cast. The auditor checks those facts rather than assuming one
completed navigation entry.

`audit_life_public_sources.py` resolves each captured import graph against exact
local/Git bytes. Intermediate validator reconstructions under
`outputs/autobattle/a65-source-history` and `a653-source-history` are usable
only when their bytes match the original capture SHA256. JSON/JSONL evidence
preserves its original bytes in Git. See the receipts for exact versions and
failed/tainted exclusions; dated history remains in the project log.

Next packet: A6.6 inventory/count/engine availability and consumable execution.
Current schema2 supports host item predicates behind disabled-by-default
consumable scopes; public Item execution is still unproven and disabled.
