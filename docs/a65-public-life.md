# A6.5 public Life integration

Status: implementation and public bounded turns pass; lifecycle acceptance is
still UNKNOWN. Canonical gate: `docs/receipts/autobattle/A6.5.json`.
A6.4 research PASS is a prerequisite, not public acceptance by itself.

The explicit `--bounded-ally-life` opt-in uses the same native state-driven
transaction as research. It is mutually exclusive with both Cure fixture
flags and requires schema2 tactics before launching the emulator. It supports
only the corrected eight-unit Montblanc5/Life5/cost10/genuine KO Marche7 fixture.
Its EXP99 level-up is observed natively before post-action identity is rebound.
Full-Life, arbitrary KO parties and items remain outside this contract.

```
python tools/run_autobattle.py --state outputs/autobattle/a64-life-fixture-02/life-recovery.ss0 --scenario configs/battle-scenarios/a4-two-player.json --tactics-policy configs/tactics/healer.json --bounded-ally-life --run-id NEW --max-turns 1 --wall-timeout 180 --on-stop kill --yes
python tools/validate_autobattle_runtime.py outputs/autobattle/NEW
python tools/validate_life_recovery_runtime.py --run outputs/autobattle/NEW --out outputs/autobattle/NEW-checks.json
```

A one-turn budget intentionally stops as stalled after the attributed turn;
this is not whole-battle completion. Public02/public03 independently revive,
Wait and join next Carson4 with unchanged sources. Public receipt mutation
checks reject38 changes. Partial STOP/refusal journals also retain adapter,
policy, attempt-latch, transport and any completed native effect checks.

## Lifecycle gates

| Gate | Required evidence | Current result |
|---|---|---|
| Native public transaction | Two independent owned reloads, accepted target, actual HP/MP/growth, Wait/next actor | Bounded PASS public02/public03 |
| CLI interface | Schema2 required, exclusive flags, wrong owner/job/race/tile/party before input | PASS10 host controls,31 exact pre-navigation fixture mutants, plus live unsupported seven-unit refusal before input |
| STOP navigation/final | Actual STOP latch and no later automation writes | PASS navigation01/final01 |
| STOP post-Life Wait | Attributed effect preserved, Wait final unattempted, real owned handoff | PASS Wait01 pause |
| Manual/resume | Window-only manual Wait, same PID adoption and a later identified public player turn | UNKNOWN; Wait01/Wait02 adopted but no resumed player turn at150/300 seconds |
| Reserve/default refusal | Actual remaining211 versus reserve212; no opt-in never casts Life | PASS reserve01/default01,11/5 mutants |
| Regressions | Existing Cure and runner receipt gates; fresh public Cure controls | PASS fresh ally-Cure38/self-Cure26 plus default Wait |

The first manual Wait on PID79496 passed with zero stub gameplay writes and
an independent next enemy. Same-PID adoption also passed, but the150-second
shared-clock budget ended before any resumed player turn. Keep the gate UNKNOWN.
A second fresh pause on PID76672 with a300-second resume budget also ended
without an identified player turn. The terminal screenshot suggests Sleep on
both allies; this is a hypothesis until native RAM is captured. The next
control adds read-only terminal canonical/mirror status evidence, including
the known Sleep getter0x080CDB24, +EB mask04 and +DF duration. Do not relax
identity checks or lengthen the same timeout without new evidence.

The reusable lifecycle driver is `tools/run_life_recovery_handoff.py`.
It uses the public CLI, `run_life_cli_stop.py`, the verified owned-window helper,
and the public `--resume` path. A failed child preserves its logs and owned
process state for inspection. GDB is a read-only monitor during manual input.

The bounded-resume audit rejects five changes, including false PID adoption,
missing first-leg source proofs and automated input in the manual gap. This
audit passes for the failed attempt; the lifecycle gate remains UNKNOWN.

The third capture (PID16628) records the diagnostic failure explicitly: mGBA
truncated the whole-array RSP reply. The corrected reader fetches one264-byte
unit per request; host tests enforce the512-byte bound and exercise Sleep
present/absent with no input API. A fresh diagnostic capture is still required.

`audit_life_public_sources.py` resolves the captured Python import graph from
exact local/Git bytes. Public Life03 and the full manual closure on Wait03 pass.
Reserve01 used an intermediate validator version; its archived reconstruction
matches the capture SHA256 exactly and is accepted only by that exact hash.
Use `--source-dir outputs/autobattle/a65-source-history` with Git refs790f333
and4ccb7f0 to reproduce that provenance audit. This is retained-source evidence.

Wait04 PID85332 exposed a second event whitelist: the diagnostic was decoded
but rejected by the runtime serializer before terminal finalization. That
capture is invalid and is excluded from acceptance. The schema omission is
fixed and the actual serializer/validator whitelist host control passes.
A later read-only observation on that same verified PID decoded both canonical
and mirror party records: neither ally had Sleep (+EB04 clear, +DF zero),
HP241/221 and MP211/85 were preserved. This later observation does not repair
the failed run or explain every earlier missing menu. The owned PID was ended.
Next packet: fresh same-PID resume with the corrected diagnostic serializer,
then trace the fresh-menu ownership rejection against native actor/cursor and
status history. Do not repeat longer timeouts without a discriminating witness.
