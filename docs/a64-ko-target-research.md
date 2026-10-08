# Bounded KO/Life target research packet (A6.4)

Entry gate: A6.3 public ally-Cure acceptance, including current-source self and
ordinary regressions. This packet is research; it cannot clear public revive
or item support. Existing living-only pins and Cure readers must continue to
reject HP0 and unsupported ability IDs.

## Starting facts and unknowns

Read-only retail table inspection on 2026-10-07 finds Life ID5, base MP cost10,
horizontal range4, vertical field0 and targeting field1. Full-Life is ID6,
base cost20. `outputs/autobattle/a64-ability-metadata.json` records the ROM hash
and table values. These fields alone establish neither learned/menu status,
effective cost, range legality, KO classification nor the accepted target.
Life is not Cure with a substituted display label. The present `RecoveryMenu`
processor guards hard-code ability1 and cannot certify a Life prompt.

## Ordered work and gates

1. Identify a genuine engine KO and its canonical/battle-mirror lifecycle.
   Prefer a retained natural battle KO or a bounded engine damage/result path.
   Distinguish KO from borrowed roster storage, Petrify, Zombie and Auto-Life.
   HP0 is a predicate, not sufficient proof of a valid reusable fixture. Record
   classifier/accessor addresses, pre/post state, actor/target identities and
   field coherence. Unresolved KO lifecycle blocks fixture acceptance.
2. Construct only a disposable local fixture after those semantics are known.
   Ledger every scratch change and independently reload it. Preserve original
   ROM/save/state bytes and hashes. Pin one living caster and one independently
   classified KO ally, plus all other party identities and resources. Existing
   `pin_party` deliberately rejects KO; a separate research pin must not weaken
   that living contract. Save/state/RAM binaries remain untracked.
3. Observe an enabled Life row and verify its effective MP cost through the
   retail cost accessor for this caster. Stop before final execution. Decode
   overlay, accepted target, preview and final Do-it independently; do not
   assume the Cure peer/table/controller fields retain their meanings. Join
   canonical name/id, side, KO state and tile twice across each transition.
   Cached UI name pixels never substitute for identity. Require engine
   acceptance before constructing a `relation: ally`, target HP0 candidate.
4. Only after that reader contract passes, add one bounded research final
   confirmation with a fresh policy/target/resource recheck, STOP checkpoints
   and a single final-input latch. Require target HP0 to become positive,
   caster MP to fall by the decoded cost, and other party HP/MP to retain their
   own values. Prove consumed Action, separate guarded Wait and an independent
   next actor. Repeat on two fresh compatible reloads. No final-input retry.
5. Reject living targets, same-job name/id aliases, enemy/unaffiliated targets,
   stale KO/tile/wrapper/controller, disabled row, insufficient or changed MP,
   misleading enemy effects, missing final policy, STOP and duplicate final
   input. Show default revive-before-attack versus an MP reserve refusal using
   actually offered candidates. Retained/host tests clear decoder guards only.

## Ownership and completion

Use separate Life research readers/probes/validators and
`docs/receipts/autobattle/A6.4.json` with PASS/FAIL/UNKNOWN criteria. Preserve
source hashes and full raw input ledgers; compact metadata is reviewable while
binary captures stay local. The narrow research contract passes only with two
attributed revivals, Wait/continuation and negative controls. Public revive
integration needs a later packet with its own adapter, policy comparison,
STOP/manual/same-PID and self/ally/ordinary regression gates. Inventory and
consumable legality remain separate work.

## Initial bounded ROM evidence

`validate_recovery_ko_classifier.py` executes080A2218..080A225E for eight
synthetic inputs: HP0 returns class1, HP1/25 of100 class2, HP26 class3.
Petrify snapshots change living classification but HP0 still returns1.
This fragment distinguishes zero HP from living critical HP; it does not
execute the surrounding KO lifecycle, scheduler, target eligibility or revival.
All required A6.4 criteria remain UNKNOWN. Capture: `a64-ko-classifier.json`.

## 2026-10-08 execution checkpoint

The dated initial UNKNOWN verdict above is superseded for the first two
criteria only. `a64-engine-ko-04` sets living Marche to HP1 in both copied
records, then issues ordinary identified Wait commands. Native instructions
`080A2298/080A229A` change canonical `02000080` from HP1 to0 at t180.4.
His KO-suffered counter increases1 to2; MP85 is preserved. Montblanc remains
HP100/MP221. Both canonical/mirror identities, resources and status fields
are rejoined; Petrify, battle/persistent Zombie and Auto-Life are clear.

The interactive caller `0809F870` reaches zero-HP skip `0809E246` at t209.5.
`08093018` then returns living battle actors. Prediction-helper skips from
`0809F7B4` are recorded separately. Fresh `a64-ko-reload-04` independently
opens living Montblanc's command menu with Marche still KO and no inputs or
unit writes. This is bounded engine-KO lifecycle evidence, not Life legality.

`a64-life-fixture-01` starts only after that audit. It changes living
Montblanc's secondary job to7 and HP to241 in both copies, with four verified
ledger entries. The genuine KO target is unchanged byte-for-byte before
export; a separate fresh reload verifies the prepared resources. Original
ROM/save/state files remain untouched, and all binary captures/states stay
local. Exact source and metadata hashes are in `A6.4.json`.

Current fixture: living Montblanc ID5, canonical02000188, HP241/241,
MP221/221, raw race1/job5/secondary7; genuine KO Marche ID7,
canonical02000080, HP0/442, MP85/85. This changes caster identity from the
accepted Cure fixtures. The separate research list reader handles ROM names;
production living-only/Cure readers are unchanged.

Thirty-seven KO join mutations and eleven actual-ROM status/pending-tail
controls pass. Existing living-party37, public-interface7 and public-Cure38
guards still pass; AI10/10 and strategy9/9 pass on the unchanged original ROM.
The initial broad helper hypothesis and failed export are retained local
research, not acceptance evidence; see DE-038. Earlier observational runs
01/02 mislabelled +D2 Speed as CT; accepted run04 reads CT at+D0 explicitly.

Next gate: identify this caster's White Magic group and an enabled Life row,
then independently decode its KO overlay, preview and final prompt. Group10
opened native Steal (mode6); group12 entered a target processor rather than
the desired ability list. Neither executed a spell. Do not transfer the
earlier caster's group-row assumption or promote an unexecuted Life probe.

The native Action-group capture (`a64-life-groups-01`) shows Fight, Black
Magic, Item and Combo. Its rendered HP100 also differs from canonical HP241.
The action-set mapping or cached-menu reconstruction is unresolved; raw
secondary7 alone cannot certify White Magic. `a64-Life-frontier.json` records
the mismatch. Stop guessing group IDs: identify the native action-set source
and menu reconstruction before another availability claim.

### Native secondary action-set dependency

`python tools/validate_recovery_action_set.py --out outputs/autobattle/a64-action-set-dependency.json`
passes three isolated actual-ROM helper executions on the retained Montblanc
capture. Native `080CCE60` selector2 reads both secondary job `+8` and secondary
ability-set byte `+0x36` (at080CCEAC/080CCECC). Captured `+0x36=1` triggers the
fallback at080CCEF8, returning pointer0851BAE4/bounds1,15 even with job7.
A synthetic change of only secondary job to0 preserves that fallback. Native
job property `080C8570(7,7,0x0C)` returns9; an isolated `+0x36=9` mutation with
job7 returns0851BB64/bounds58,68, containing global Life5 at row62.
The ordinary menu builder also reads `+0x36` directly at080272F0..08027300.

This narrows the next fixture experiment to reconstructing both canonical and
mirror secondary ability-state from the native job property, then exporting
and independently reloading before observing the enabled list. These are
synthetic helper executions, not a live corrected fixture. The prior Steal
list/visual Black Magic discrepancy and rendered HP mismatch remain unresolved.
No Life availability, targeting or revival criterion is promoted.

The same retained caster has primary ability-set `+0x35=10`, while native
`080C8570(base5,active5,0x0C)` returns24. The replay now asserts and records
that disagreement too. Reconstruct both ability-state fields from native
properties in the next disposable fixture experiment; changing secondary
state alone cannot resolve the primary-list/visual mismatch.
