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
