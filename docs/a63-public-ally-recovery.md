# Public bounded ally recovery (A6.3)

Status: accepted within the exact bounded fixture. Public casts, policy
comparison, both STOP/manual/same-process handoffs and current-source self
and ordinary Move/Wait regressions pass.
See [receipt](receipts/autobattle/A6.3.json) and
[roadmap](auto-battle-roadmap.md). The accepted A6.2 research contract is a
prerequisite, not public acceptance.

## Public interface

`tools/run_autobattle.py --bounded-ally-cure` requires a schema-2 tactics
policy and is mutually exclusive with `--bounded-self-cure`. The exact
supported family has eight live units, caster Marche ID 7/job 5/race 1 at
(4,10), and living ally Montblanc ID 5/job 5/race 1 at (5,10). No general
party, KO, item, attack, range-search or complete-battle support is claimed.

The final target reader pins canonical identities and the engine's accepted
Cure target before the public tactics adapter evaluates the candidate. It
rechecks both after the confirmation screenshot, then permits one final A.
Cure effect, guarded Wait and a separately joined next enemy close the turn.
The ordinary runner and seven-unit self-Cure path retain their own contracts.

## Observed public behavior

Two independent CLI reloads, `a63-public-cure-01` and `-02`, healed Montblanc
from 100 to 157/153 HP. Marche stayed at 442 HP and spent 85 to 79 MP;
Montblanc retained 221 MP. Both used 70 raw transport writes, completed Wait,
and independently joined Schneider ID 3 as the next enemy. Input hashes
remained unchanged and owned emulator cleanup freed port 2345. The run ends
truthfully as `stalled` at the one-turn budget; this is not battle completion.

`a63-public-damage-01` used a schema-2 adaptation of the shipped damage-focused
preset with identical rules and Wait fallback. On the same fixture, the
public adapter declined the accepted ally Cure candidate, cancellation
preserved both players' resources, and guarded Wait reached Schneider. Its
85 writes include modal cancellation. This proves policy refusal/fallback,
not an attack or a damage-focused battle outcome.

`validate_party_recovery_runtime.py` rejects 38 alterations of each accepted
public receipt, including target substitution, missing adapter observations,
wrong resource attribution, duplicate final input, missing continuation and
invalid debugger halt. Seven interface controls reject schema/mutex and
unsupported caster/count/tile before input. The shared raw-ledger suite
passes 20 controls. Full run validation remains required for every live case.

## Handoff work

The first `a63-public-stop-cure-01` attempt paused before final Cure input.
Its manual cancellation then stopped safely at owned description-opening
signature `08029189/12/0101`. The helper now waits passively for that exact
signature, under its existing deadline, without authorizing a key. The trial
was manually completed using a separately retained retry and resumed for one
ordinary Move/Wait turn on the same PID. It is not final lifecycle acceptance.
Final cases `a63-public-stop-cure-02` and `a63-public-stop-facing-01` pass
`validate_party_recovery_handoff.py`:45/65 writes, owned-window manual Wait,
one verified ordinary turn after same-PID resume, eight handoff mutations and
seven partial-STOP mutations each. Cure-02 passively rejected the exact opening
signature once before continuing. The accepted seven-unit self-Cure matrix
passes all six current-source cases (`a63-final-self-matrix.json`). The ordinary
two-player run `a63-ordinary-live-01` proves Marche Move(4,10)->(4,11), then
Montblanc Wait. No complete-battle claim follows from these turn-budget runs.

## Reproduce

```powershell
python tools/run_autobattle.py --state outputs/autobattle/a62-party-fixture-01/party-recovery.ss0 --scenario configs/battle-scenarios/a4-two-player.json --tactics-policy configs/tactics/healer.json --bounded-ally-cure --run-id NEW_RUN --max-turns 1 --wall-timeout 120 --on-stop kill --yes
python tools/validate_party_recovery_runtime.py --run outputs/autobattle/NEW_RUN --out outputs/autobattle/NEW_RUN/mutation-checks.json
python tools/run_party_recovery_handoff.py --state outputs/autobattle/a62-party-fixture-01/party-recovery.ss0 --run-id NEW_HANDOFF --phase confirmation
```

Use new run IDs. Binary fixtures and screenshots stay local; compact metadata
and exact-byte hashes are retained. The UI's cached preview label is not a
canonical identity source; A6.2 documents the bounded ROM cache-branch proof.
