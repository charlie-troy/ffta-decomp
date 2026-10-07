# A6 recovery menu and resource research

2026-10-06, retail USA ROM, base `3b8bb4f`. This closes the first research
dependency: an actual self-Cure and consumed MP are witnessed. A6 remains
partial: the public runner still offers Move/Wait, and no wounded-party
policy comparison, legal ally/KO target, revive, or item use is accepted.

## Owned fixture experiments

`tools/probe_a6_action_menu.py` starts a guarded, owned emulator from
`outputs/lua-nav/battle-start.ss0`, verifies the fresh Marche owner twice,
then edits only that disposable fixture. It changes secondary job to 7
(White Mage), HP to 100, and optionally MP in both the battle mirror and
the uniquely matching clan member. No ROM, original save, or savestate is
written. The explicit key route is research, not an adapter implementation.
Raw RAM and screenshots stay local; the retained JSON contains compact
observations, the complete fixture-write ledger and delivered input log.

```powershell
python tools/probe_a6_action_menu.py --out outputs/autobattle/a6-cure-cast-03 --secondary-job 7 --hp 100 --mp 85 --edit-members --route DOWN,A,DOWN,DOWN,A,A,A,A,A --settle-end 8
python tools/probe_a6_action_menu.py --out outputs/autobattle/a6-cure-low-mp-01 --secondary-job 7 --hp 100 --mp 5 --edit-members --route DOWN,A,DOWN,DOWN,A,A --settle-end 2
python tools/probe_a6_action_menu.py --out outputs/autobattle/a6-cure-cancel-01 --secondary-job 7 --hp 100 --mp 6 --edit-members --route DOWN,A,DOWN,DOWN,A,A,B,B --settle-end 2
```

These directories already exist; choose a new run ID to repeat. Reuse rejects.

| Observation | 85 MP positive run | 5 MP negative run |
|---|---|---|
| White Magic list, Cure first row | Enabled | Disabled |
| A on Cure | Ability 1 latched; self target `(4,10)` opens | Remains in list; ability remains 0 |
| HP after confirmation/settle | 100 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ **163/442** | **100/442**, unchanged |
| MP after confirmation/settle | 85 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ **79/85** | **5/85**, unchanged |
| Final menu | Command list restored; Action disabled | White Magic list retained |
| Member and restored battle mirror | Agree | Agree |

The earlier positive `a6-cure-cast-02` healed 100 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ **156** and also spent
6 MP. These observations prove healing and the consumed resource, not a
deterministic heal magnitude. Screenshots of the final command menus show
156/79 and 163/79 respectively. In `a6-cure-cast-01`, the route ended at
the **Do it / Cancel** confirmation and resources stayed unchanged: opening
the preview is not execution. The ninth input in the complete route confirms
that prompt. No Wait or opponent-turn inputs are sent.

At **exactly six MP**, Cure is enabled and opens the self-target preview.
Cancelling with B to the ability list, then B to the Action group leaves
HP100/MP6 unchanged (`a6-cure-cancel-01`). The battle roster is still scratch
after that cancellation, so this proves resource preservation, not safe
return to the existing identity adapter.

A second cancellation (`a6-cure-cancel-02`) adds a third B to return all the
way to command mode 4. HP100/MP6 stay unchanged, but the roster still fails
its shape guard after settling; the selected-ability field also retains 1.
A command cursor/mode or cached ability ID alone therefore cannot certify
a safe fresh state after cancellation. This is recorded as DE-033.

The HUD can retain the original 388 HP/85 MP after research fixture edits.
It refreshes in the target preview and after execution. Do not infer current
resources from the pre-preview HUD: the insufficient-MP list can still show
85 in that stale HUD while Cure is disabled and both records hold 5 MP.

## Decoded consumers

`0812ED98(unit, u16 ability)` reads property 2 through `080CCD50`, giving
the ability table's `+4` MP byte. Ability 0 costs zero. `080CD50C` reads
the unit's support index at `+0x3B`; if nonzero, it uses race `+6` and the
pointer table at `0851BA84`, eight-byte entries, effect byte `+4`.
Effect **4 doubles cost**, effect **10 halves it rounded up**, and other
effects leave it unchanged. `tools/ability_resources.py` implements this
read-only contract, rejects incomplete/out-of-range facts and is not wired
into candidate generation yet. Support names are not inferred from these
numeric effects.

```powershell
python tools/validate_ability_resources.py baserom.gba --out outputs/autobattle/a6-resource-cost/checks.json
```

**2,429/2,429 comparisons** execute the actual retail function under Unicorn:
all 347 ability IDs across six constructed support/race profiles plus a null
unit. The validator checks return-to-sentinel, includes odd costs for rounding,
and rejects seven invalid-input controls. This proves function semantics, not
live learned status, MP sufficiency, or targeting legality.

The menu state root is `*(0200F438)`, observed at `0202D8A0`. In these runs:

- `context+4` low byte: command mode 4, Action group 5, White Magic list 7,
  target preview/confirmation 12 (intermediate samples retain list mode 7).
  These are observations for this fixture, not a complete mode enum.
- `context+0x18/+0x1C`: unit/peer pointers, both `02000080` for self-Cure.
  `context+0x14` latches the resolved ability ID **1** after accepted selection.
- `context+0x28` points to a callback block whose function is `08028DE1`;
  its payload at `+0x18` is the list object, observed at `0202DD70`.
- Object `+0x50/+0x52`: row count/scroll; `+0x69`: cursor;
  `+0x94/+0x98`: row array/enable-byte array. White Magic rows are race-table
  indices **58ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“66**, not global ability IDs. For race 1, table entry 58's
  `+4` u16 resolves Cure **1** (`08028A70` accepted-selection branch).
- `08028970` computes the selected row via `08017B68`, writes one-based
  selection to the context, and calls `080287C4`. That gate rejects a zero
  enable byte; a nonzero selection alone therefore does **not** prove acceptance.
  The low-MP run stores selection 1 but never latches ability 1.

## Evidence limits and next implementation

The first mirror-only experiment (`a6-menu-01`) changed RAM reads but the UI
still offered Black Magic. Editing the canonical member as well
(`a6-menu-02`) exposed White Magic. The latter's initial snapshots were taken
before redraw, so its raw list bytes cannot be paired with later screenshots.
The delivered probe disarms router hooks and permits redraw before bulk
RAM, guarded-reader and screenshot observations. These are separate captures,
not one atomic pair. Corrected positive/negative runs agree.

An exploratory breakpoint probe at AI/general usability `08133E18` and cost
`0812ED98` saw zero calls in the menu route. A follow-up trace failed at
breakpoint insertion. Neither is menu-consumer proof; that optional trace
path was removed from the delivered probe. Static menu gate code plus the
live enable-byte contrast establish the narrower facts above.

The battle roster at `020159E4` becomes scratch while selecting/confirming a
target. `ActorAdapter.snapshot()` correctly rejects it, then succeeds again
after the cast. Do not bypass that rejection or run a fresh-menu ownership
heuristic inside targeting. The read-only modal reader below now pins the original actor and separates
preview from final confirmation. Next connect it to a state-driven policy
executor, proving cancellation and insufficient-MP refusal without bypassing
the existing roster rejection. Then test ally targets, KO/Life and
the wounded-party policy comparison. Item counts remain undecoded.

```powershell
python tools/validate_a6_recovery_probe.py --cast outputs/autobattle/a6-cure-cast-03/probe.json --low-mp outputs/autobattle/a6-cure-low-mp-01/probe.json --cancel outputs/autobattle/a6-cure-cancel-01/probe.json --out outputs/autobattle/a6-recovery-artifacts/checks.json
```

Retained-artifact validation passes three positive controls and rejects nine
mutations (missing input log, wrong ability/target, unspent MP, no healing,
low-MP enabled flag, extra fixture write, cancellation resource/state errors).
It validates the saved observations;
it does not run fresh gameplay or certify public-runner policy behavior.


## Pinned modal reader (2026-10-06)

`tools/recovery_menu.py` binds the independently verified player owner to the
unique canonical clan member, name bytes, identity, support, resource maxima
and tile. It pins the menu root, actor/peer and callback allocation. Every
observation checks decoded list bounds, race/global ability join and enable
bytes; pre-input revalidation rejects changed facts or observations older than
two seconds. End-of-read checks reject drift in actor, target, controller and
decoded list facts. Undecoded animation counters are excluded.

The Action group uses a dynamic child at parent callback `+0x10`, back-pointer
at child `+0xC`, function `08028DE1`, state `0x102`; parent state is `0x106`.
The group cursor comes from that child's payload, not a fixed scratch address.
Ability list: function `08028DE1`, mode 7, state `0x102`. Target overlay:
same function/mode, state 3. Description: `08029189`, mode 12, state `0x102`.
Final Do it/Cancel: `080293DD`, mode 11, state `0x102`, cursor 0/1.
Input handler `08029350` writes selection 1/2 for A and `0xFFFF` for B.
These signatures are bounded to the documented fixture.

The description callback is reused after final confirmation. States 3/0x103 under
description/confirmation is read-only settling and cannot authorize input.
The future executor must also track lifecycle so a reused description cannot
cause a duplicate A. A cached ability ID or cursor is not freshness proof.

```powershell
python tools/validate_recovery_menu.py --out outputs/autobattle/a6-modal-reader/checks.json
```

Reader checks pass 14 retained captured states plus one explicitly derived
settling signature and reject 46 altered/stale/mid-read cases. The derived
case uses a later live guard's state with the earlier bulk bytes; it is labeled
constructed. Bulk RAM, guarded reads and screenshots are separate observations,
not one atomic capture. The first live guarded cast stopped after confirmation
on settling (`a6-modal-cure-01`); the overbroad animation-coherence check then
stopped `a6-modal-cure-03` before any key. Both failed runs remain local.
`a6-modal-cancel-01` reaches command state with HP100/MP6 unchanged while the
original ActorAdapter still rejects scratch storage. The reader supplies an
independent canonical observation; it does not relax that guard or restore it.

No public ability execution is enabled by this slice. Policy selection,
STOP during recovery, safe fallback, ally/KO targets and item counts remain
separate acceptance work.


## State-driven research executor

`tools/recovery_executor.py` navigates decoded row IDs (command Action 9,
secondary group 10 with pinned secondary job 7, global Cure 1), checking enable
bytes before selection. It verifies the self cursor, selected ability and
canonical target through the engine's final Do it/Cancel prompt. Only then
does it supply that single candidate and current resources to schema-v2 policy
evaluation. It repeats revalidation/evaluation before the final A, latches
confirmation once and permits only passive waiting afterwards.

Post-cast command opening (`08028DE1`, mode 4, state `0x101`) is a distinct
transient error: it never authorizes input, but the committed executor can
wait for the stable command controller. The first policy run stopped on this
opening transition (`a6-policy-cure-01`), preserving the failure. The next run
(`a6-policy-cure-02`) selected `heal-self`, healed HP100→162 and spent MP85→79;
the restored mirror agrees and Action is disabled. This is a constructed
self-Cure research proof, not public-runner or full-turn acceptance.

```powershell
python tools/validate_recovery_executor.py --out outputs/autobattle/a6-executor-host/checks.json
python tools/probe_a6_action_menu.py --out outputs/autobattle/a6-policy-cure-02 --secondary-job 7 --hp 100 --mp 85 --edit-members --policy configs/tactics/healer.json
python tools/validate_recovery_execution.py --cast outputs/autobattle/a6-policy-cure-02/probe.json --out outputs/autobattle/a6-policy-artifacts/checks.json
```

The real executor passes 23 host checks with a fake menu/transport: reordered
rows, reserve/healthy/unavailable declines, identity failure, enemy-only healing,
unspent MP, duplicate confirmation suppression and STOP at input/cancel
boundaries. These tests prove host control flow, not ROM behavior. Saved-receipt
checks replay the exact policy and reject fourteen altered input/target/resource/
terminal cases. `--stop-file` polls at route/cancel/wait boundaries and between
bulk evidence reads. Debugger packets time out at one second; the existing
screenshot subprocess can block up to 45 seconds and is an explicit STOP
latency limit. No gameplay input follows observed STOP.

Policy declines unwind known modal states and report fallback **unexecuted**.
The normal battle-roster adapter can still reject the returned command storage.
A safe Wait/facing executor and public runtime integration remain separate work.

## Wait-facing ownership and bounded continuation

`a6-wait-facing-01` reached the Wait-facing screen after canceling self-Cure.
The reader rejected the cached command callback (LIST/mode4/state3) and
preserved the unknown screenshot/RAM before cleanup. The active player driver
at `0200F4E8` supplies an independent discriminator: `+0xDC` is the switch
index, and table `080929D4[0x2F]` dispatches to `080955E0`. That arm calls
`080A82C0` -> `080A1BE8`, the facing input handler. A confirms; B cancels;
direction keys update the facing choice. The branch returns the current stored
direction on A. `validate_recovery_facing.py` executes its actual input branch
for four starting directions and all 256 low-byte key masks (1,024 cases),
stopping before rendering/audio helpers. This is input-dispatch proof only.

The fixture-bound reader requires driver state47/flags0x48, no target processor,
no active UI callback, facing object `0200F8A8` owned by the pinned wrapper,
enabled facing, and matching wrapper/object direction in 0..3. It rechecks these
facts before input and after each observation. Command input independently
requires driver state37 with no target processor. Fourteen facing mutation
controls reject stale/wrong ownership, cached callbacks, invalid/changed
direction, main-state drift, and changes during reads.

`a6-wait-facing-cancel-01` sends guarded B from facing and returns to the
command menu with Wait selected, HP100/MP6 unchanged; the battle roster remains
borrowed. `a6-wait-facing-commit-02` instead sends one guarded facing A, latches
the terminal input and then observes only. The restored roster identifies Marche
at HP100/MP6 on tile4,10. Two later captures join the active wrapper's canonical
enemy to a unique restored battle record (IDs3 then4), matching name/job/side/tile
and cursor. Screenshots corroborate enemy progression. Old modal ownership
correctly rejects the changed wrapper. CT changes alone are not the criterion.
The retained continuation validator rejects nine altered receipts, including
post-final input, empty raw input, wrong ownership, missing distinct enemies,
cursor mismatch and resource changes.

A fresh policy-Cure regression then exposed description closing state0x104
after final confirmation (`a6-facing-cure-regression-01`). Static callback
`08029188` explicitly dispatches 0x104 to `080291FA`, which closes the window
and writes state3; it does not accept gameplay input. The reader now treats
this description state as read-only settling. A fifteenth facing-suite
rejection verifies that it cannot authorize a key. Its replay is explicitly
derived from the later live rejection and earlier bulk capture, not an atomic
captured state. The original failed run remains evidence, not an accepted cast.
Fresh rerun `a6-facing-cure-regression-02` settles to command with HP100->160,
MP85->79 and Action disabled; its receipt passes twelve rejection controls.

The first confirmation run (`a6-wait-facing-commit-01`) delivered its final A
but had an incomplete following sweep, so it proves no continuation. The
research probe now disables unused router-trace re-arming after initial owner
verification; those asynchronous stops could mispair a bulk-memory reply.
No global transport or public-runner behavior was changed. Screenshots, bulk
captures and live reads remain separate observations, not atomic pairs.

```powershell
python tools/validate_recovery_facing.py --out outputs/autobattle/a6-facing-reader/checks.json
python tools/validate_recovery_facing_execution.py --out outputs/autobattle/a6-facing-continuation/checks.json
```

This is bounded fixed-route research. A state-driven policy-decline Wait
fallback, public integration, ally/KO targeting and wounded-party comparison
remain open. No input is inferred safe from a cached menu alone.

## Explicit policy Wait after a declined recovery

`WaitFacingExecutor` uses the same guarded reader and navigation code as Cure.
It requires a unique enabled command row10, supplies that legal Wait candidate
to schema-v2 policy, selects the row by identity and re-evaluates policy at
verified facing before the final A. It latches before transport and reports
only `confirmed` / continuation `unverified`. The caller observes independently;
neither a sent route nor the executor's result is upgraded to turn completion.
The research CLI enables this only with `--policy ... --wait-fallback`, after a
completed Cure decline. A successful Cure does not trigger this fallback.

Fresh constructed-fixture runs:

- `a6-policy-wait-reserve-01`: Cure enabled at MP6, but the eight-MP reserve
  declines it. Guarded cancellation returns command, then policy chooses Wait.
  Sixteen keys are delivered; there are none after facing confirmation.
- `a6-policy-wait-low-mp-02`: Cure disabled at MP5 and never selected. Ten keys
  cancel the list and confirm policy Wait. The first low-MP run (`-01`) has a
  bulk/live controller-state mismatch in its last observation and is retained
  without a continuation acceptance claim; the strict fresh rerun passes.
- Both accepted continuation receipts join two later enemy actors to restored
  roster records, with Marche's HP100, MP6/5 and tile4,10 unchanged.
- `a6-policy-wait-stop-01`: STOP arrives at the facing screenshot before final
  confirmation. Fifteen keys /75 raw writes are delivered; zero writes occur
  after observed STOP and no final facing A is requested. Cleanup owns its PID.

The real Wait executor passes fifteen host checks with fake menu/transport,
including reordered rows, disabled/missing Wait, fallback none, changed resources,
wrong modal state, ambiguous delivery, policy recheck, STOP during revalidation
and after the final latch, and forbidden post-final input. Retained policy-Wait
receipts reject thirteen mutations each, including consistent wrong candidate
facts, missing Cure rejection, post-final/post-STOP input and false completion.
The existing Cure flow still passes23 host checks and the reader46 controls.
Fresh positive regression `a6-wait-cure-regression-01` heals HP100->165,
spends85->79 MP, disables Action and does not invoke Wait fallback. Its retained
receipt rejects twelve mutations; AI10/10 and strategy9/9 pass.

```powershell
python tools/validate_recovery_wait_executor.py --out outputs/autobattle/a6-wait-executor-host/checks.json
python tools/validate_recovery_wait_execution.py --stopped outputs/autobattle/a6-policy-wait-stop-01/probe.json --out outputs/autobattle/a6-wait-policy-artifacts/checks.json
python tools/validate_recovery_wait_execution.py --capture outputs/autobattle/a6-policy-wait-low-mp-02 --stopped outputs/autobattle/a6-policy-wait-stop-01/probe.json --out outputs/autobattle/a6-wait-low-mp-artifacts/checks.json
```

This proves bounded policy-decline fallback on the constructed self-Cure fixture.
It does not close A6: successful Cure's remaining turn, public integration,
ally/KO/item handling, wounded-party comparison and manual continuation remain
separate. The research screenshot subprocess can still delay STOP observation
up to its45-second timeout; this slice does not claim a general latency bound.

## Successful Cure through turn finish

The research-only `--finish-recovery-turn` option also invokes the guarded Wait
executor after successful Cure. Its independent command observation must join
the same actor and the newly healed HP/spent MP. The engine-disabled Action
row is preserved as Cure acceptance evidence; Wait remains separately offered
and policy-evaluated. Two executor-local final latches cover distinct engine
operations: Cure's Do it, then Wait's facing. Neither retries ambiguous input.

`a6-cure-complete-turn-01` healed but stopped during a passive settling read
when the main controller advanced between reads. That rejected observation
remains invalid. The reader now emits `RecoveryTransient` specifically for
main-state coherence failure in read-only settling; the already-committed Cure
loop may passively retry within its existing15-second deadline. Command/facing
drift still fails hard, and settling never authorizes input. The facing suite
executes its additional mid-read rejection control (sixteen total).

The host composition check runs the real Cure executor and then the real Wait
executor with fake dependencies, including one rejected settling observation.
The fake transport's effect is now one-shot and resets the command cursor as
captured live; it previously reapplied healing on each passive tick and retained
the Action cursor. These are test-model corrections, not ROM semantics proof.
The Wait suite has sixteen host checks; Cure's existing23 still pass.

Live accepted runs and receipt hashes are recorded in A6.json. They must join
Cure's exact six-MP cost, HP increase and consumed Action to the following
engine-enabled Wait and distinct enemy actors after roster restoration.
`validate_recovery_turn_execution.py` rejects ten mutations: missing healing,
wrong cost/Action consumption, mismatched finish actor/resources, missing policy
recheck, coherent duplicate terminal input, missing raw input, false completion
and enemy-only effects. No public recovery or manual handoff is claimed.

The first repeat (`-03`) mismatched bulk/live main-state observations. Explicit
debugger halts in `-04/-05` removed that race but exposed a separate fact: a
later enemy's targeting can borrow the same roster again. Their fixed-delay
last captures are therefore unaccepted. The final research observer halts and
polls passively, within20 seconds, for a readable roster and two distinct later
enemy wrappers, then captures without resuming between the check and sweep.
Unknown polls remain labeled unknown, with rejection reasons. Final acceptance
still independently joins each canonical actor to the restored battle record;
neither a halt reply nor a readable player alone proves enemy attribution.
This changes capture timing, not the action policy, and sends no more keys.
Polling runs06/07 additionally showed the next wrapper before its cursor update;
their independent validator rejects actor4 tile7,4 versus stale cursor9,2. The
final observer requires wrapper-pair agreement, a living enemy and its own
in-bounds cursor/tile before capture. It retains rejected polling states rather
than upgrading a changed wrapper to current input ownership. See DE-036.

Current-source reloads `a6-cure-complete-turn-08/-09` pass the final halted,
cursor-coherent observer: HP100->165 and100->156, MP85->79, Action consumed,
then guarded Wait and two distinct enemy actors. Each has13 delivered keys
and none after facing confirmation. Enemy canonical and battle records now
cross-check type/job/race/level/HP/MP as well as name/id/side/tile; all must fit
the verified fixture bounds. Each turn receipt rejects thirteen mutations,
including missing halt evidence and coherent invalid enemy coordinates/stats.

`probe_recovery_stop.py` replaces the ad-hoc screenshot watcher with a bounded,
reusable CLI. Fresh `a6-complete-stop-regression-01` confirms STOP at Wait facing
still suppresses the final A:15 keys/75 raw writes, none after STOP. All current
screenshots named in the receipt were inspected. The broader A6 public-runtime,
wounded-party and manual-continuation gates remain open.

```powershell
python tools/validate_recovery_turn_execution.py --capture outputs/autobattle/a6-cure-complete-turn-08 --out outputs/autobattle/a6-complete-turn-current-artifacts/checks.json
python tools/validate_recovery_turn_execution.py --capture outputs/autobattle/a6-cure-complete-turn-09 --out outputs/autobattle/a6-complete-turn-current-repeat-artifacts/checks.json
python tools/probe_recovery_stop.py --out outputs/autobattle/NEW-UNUSED-RUN --phase 15-A --mp 6
```


### Target processor and cancellation ownership

The MP6 decline exposed a second callback-lifetime trap (DE-034). B/B from
the final prompt returns to the range overlay, but mode 12 and the finished
description callback remain cached. Passive waiting cannot change this idle
input state. `a6-policy-reserve-01/-02` failed closed without spending resources.

The reader now separately pins the player driver's actor wrapper and reads its
active target processor (`0200F4E8+0x60`). Static caller `08095406` drives
`080B7E08` → `080B5A08`. The processor reuses `020159E4`, with `+0` actor wrapper,
`+0xEC` ability, `+0x1112` flags and `+0x1118` state. State 10 / flags 0 is the
range-input switch entry at `080B74E0`; its wrapper must resolve to the pinned
canonical member, ability must be Cure, and the UI scheduler must have no active
callback. The reader joins those facts before recognizing a returned overlay.
It checks them again at the end of each observation and before input. Changed
processor allocation, actor, ability, flags/state, wrapper and UI ownership
prevent input. This extends the fixture-bound modal contract, not roster bounds.


Final strengthened-reader casts `a6-policy-cure-03/-04` both healed HP100 to166
and consumed MP85 to79; final screenshots were inspected. MP6 reserve decline
(`a6-policy-reserve-03`) and MP5 unavailable Cure (`a6-policy-low-mp-01`) return
to command with resources unchanged and fallback explicitly unexecuted. Live
STOP at the final prompt (`a6-policy-stop-01`) leaves eight delivered keys /40
raw writes, no ninth confirmation and zero writes after observed STOP. All
owned emulator processes were cleaned up. Saved receipt validation passes four
controls and rejects fourteen mutations, including coherent extra terminal
input, internally consistent wrong chooser cost/target and post-STOP writes.
The repeat-cast receipt independently passes twelve applicable mutations.

### A6.1 scoped transport prerequisite (2026-10-07)

`RecoveryTransport` now owns a bounded modal debugger interval. It explicitly
halts before reads, keeps router hooks suspended during recovery input, exports
every raw write including partial/disconnected delivery, and restores verified
trace hooks while halted before resuming. `Probe.press(rearm_trace=False)` uses
the original key-poll transport; its default behavior remains unchanged. Strict
breakpoint acknowledgments are opt-in for the modal interval. No global method
is replaced and cleanup never injects another gameplay key.

The research CLI's `--scoped-transport` exercises this interval with the real
executors. Reloads `a61-scoped-cure-05/-07` heal HP100->156, spend MP85->79,
consume Action, confirm guarded Wait and independently join enemy IDs3/4. Each
delivers13 keys/65 raw writes and no post-facing input. Tracing is then restored
and observes a real enemy sequencer seed without further keys. Each retained
receipt rejects22 mutations, including missing/modal ledger, bad halt, duplicate
restoration and absent post-restoration seed evidence. Post-heal screenshots
show HP156/MP79 and unavailable Action; the later frames show Carson's turn.

Run04 remains failed: after healing, explicit halted reads caught command-list
initialization state0x100. The ROM dispatch at08028DE0 sends0x100 to initialization
at08028E5E,0x101 to opening at08028ECC, and0x102 to input at08028F02. Three executed
dispatch cases verify that split. Both opening states now reject observations
with `RecoveryTransient`, permitting only bounded passive retry. Six derived
controls prove neither opening state authorizes a snapshot or an old command
token, and invalid identity remains a hard rejection. No input guard was relaxed.
Run06 attempted launch while05 still owned the GDB listener; the fixture guard
refused it without reusing or killing that emulator. Keep both failed artifacts.

Fresh STOP at Cure confirmation (`a61-scoped-stop-cure-01`) suppresses the final
A, retains8 keys/40 writes, and restores tracing with zero post-STOP input.
The screenshot watcher now persists the already-read modal evidence before
propagating STOP after screenshot capture, avoiding an artifact-only race.
Its screenshot subprocess still has the documented45-second timeout.

The facing STOP control (`a61-scoped-stop-facing-01`) retains12 keys/60 writes,
suppresses its final A and restores tracing. Both STOP receipts reject seven
mutations, including a coherent additional transport write after STOP.

Final source-pinned reloads10/11 heal HP100->154/157, spend MP85->79 and retain
the same thirteen-key guarded turn proof; both reject23 receipt mutations.
Run10 restores21 decoded router events with matching enemy identity/branch;
run11 observes one enemy action seed. These establish hook activity separately
from the two independent raw continuation joins. Router preview traffic is
explicitly not another executed action. The earlier run08's three-second trace
sample saw neither event and remains unknown for restoration, although its
action/continuation captures are valid. The observation budget is now bounded
at twelve seconds; seed or attributed router evidence can prove restoration,
while no observed trace traffic still fails that criterion. This corrects an
over-specific seed-only restoration check; it does not change the independent
action acceptance or continuation gate. Source hashes are recorded at launch.

Host transport13, Cure23, Wait16, modal-reader46 rejection controls and
facing1024 ROM cases/16 rejections pass. Existing tactics-adapter12 and runtime
resume host paths also pass; AI10/10 and strategy9/9 remain regression gates.
Raw receipt auditing exposed and fixed a separate validator gap in8fe1dbe;
see `C1-raw-input.json` for20 artifact cases and its pre-fix reproduction.

This is a transport prerequisite, not public-runner recovery acceptance.
`A6.1.json` retains all public integration/decline/STOP/manual-resume criteria
as unknown. Next: connect the bounded executors to `BattleRuntime` and deliberate
`TacticsAdapter` capability selection, extend event/source hashes and require
complete recovery raw logs, then execute the public CLI acceptance suite.
