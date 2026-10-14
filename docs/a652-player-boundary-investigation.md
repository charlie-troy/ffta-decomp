# A6.5.2 player-boundary investigation

Preregistered2026-10-14 after A6.5.1 bounded PASS atb5e40db. A6.5 remains
UNKNOWN. The terminal mirror can be reused during enemy work; canonical
living/no-Sleep records do not establish a player menu or a playable turn.

Hypothesis1: the resumed monitor has not independently observed an eligible
player menu within its bound. The current generic cursor-rejection reason
cannot distinguish this from a lost or stale player opportunity.

Use an explicit read-only observer on the native battle-driver pick return
0x08093018 (wrapperr0, driverr6), plus each actual adapter observation attempt.
Record canonical5/7 and mirror5/7 raw units, driver/wrapper/member, current
menu root/callback, cursor and exact snapshot/observe rejection on one clock.
Do not change input, CT, status, jobs, ownership predicates or party identity.
All extra hooks must be disarmed before inherited key delivery and cleanup.

Falsifier: an independently joined native player pick and sustained actor-owned
command menu occurs, with restored mirror, correct identity/level and native
own cursor, but the adapter refuses or misses it. That refutes simple absence
of opportunity and directs investigation to the exact failing predicate.
Positive support requires a demonstrated engine reason or complete bounded
history showing no eligible opportunity, not an unexplained terminal timeout.

Test1: fresh public Life STOP, window-only manual Wait and same-PID resume,
with the observer and the existing300-second shared-clock bound.
Matched control: same observer, ROM, scenario and original Life fixture, but
no Life opt-in; default policy Wait and a two-turn bound. Compare native picks
and menu observations, not elapsed wall time or CT values alone. The control
retains the KO target and caster level40, so it can distinguish Life/growth/
manual-resume effects from an ordinary post-Wait monitor issue.

Stop after two materially different tests if neither discriminates a gate.
Select a different registered hypothesis rather than lengthening the timeout.
Any new guard change needs a pre-fix regression and final-source fresh evidence.

## Test1 and matched control receipts

The observed resume on PID73308 picks native player5 at t217.8 and player7
at t247.9. At t228.9/234.9, native command mode4/callback LIST/state0x102,
canonical wrapper, restored party mirror and own cursor identify Montblanc.
The adapter first records the pairing and then accepts the owner (level41).
It sends echo DOWN, navigation DOWN, Wait select A and Wait confirm A with
five key-poll hits each. The next native pick is revived Marche7. The terminal
frame shows Marche's Move/Action/Wait/Status menu with HP221/442 and MP85/85.
The receipt still claims zero turns because `_record_identified_turn` waits
for another sequencer seed; an open next ally menu cannot produce that enemy
progress until somebody acts. This falsifies absence of a player opportunity
and does not justify changing actor identity, level or cursor predicates.

The same-observer no-Life default control commits one identified Montblanc
Wait with unchanged resources and then bounds before its second player turn.
Its first joined menu is accepted at level40. Both histories validate, reject
seven mutations, and record zero observer errors. The original two-test
hypothesis packet stops here; A6.5 remains UNKNOWN.

Hypothesis2, preregistered before input/completion changes: the seed-only
post-Wait completion check incorrectly rejects an immediate next ally turn.
Falsifier: after a selected/confirmed Wait, no different canonical player
wrapper with a restored roster and accepting actor-owned command menu appears,
or that purported continuation also accepts stale/same/enemy/foreign actor,
CT-only progression, aliasing or incomplete/raw-invalid state. The proposed
minimal control adds read-only next-ally command evidence to identified Wait
completion; existing seeded enemy progress and all input identity/STOP guards
retain their behavior. Validate a pre-fix regression, then fresh same-PID resume
and an immediate-ally control, followed by affected existing regressions.

The first witness integration run01 (PID111648) remains bounded with zero attributed turns despite native picks5/7 and Wait input. The host regression passes and fails onf3dac65, but native acceptance is UNKNOWN. The reused command reader may be too narrowly tied to its research phase; record the exact origin/continuation refusal before changing a predicate. No further timeout extension is justified.

The second live attempt (PID33444) records the exact cause: `Wait origin command unavailable`. Native driver state37/0x25 and LIST accepting state0x102 are correct. The new witness used the cursor index2 as a command row; the actual captured command table is8/9/10/11, with Wait10. Native-table-backed host regression reproduces the refusal. Earlier toy-table host03/04 are excluded from command-semantic acceptance. Correct only that identifier, then repeat the registered native test. Observer driver state/control now use the proven +DC/+D0 fields instead of unrelated prefix values.
