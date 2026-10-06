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
| HP after confirmation/settle | 100 → **163/442** | **100/442**, unchanged |
| MP after confirmation/settle | 85 → **79/85** | **5/85**, unchanged |
| Final menu | Command list restored; Action disabled | White Magic list retained |
| Member and restored battle mirror | Agree | Agree |

The earlier positive `a6-cure-cast-02` healed 100 → **156** and also spent
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
  indices **58–66**, not global ability IDs. For race 1, table entry 58's
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
The delivered probe disarms router hooks and runs briefly before taking a
halted RAM/screenshot pair. Corrected positive/negative runs agree.

An exploratory breakpoint probe at AI/general usability `08133E18` and cost
`0812ED98` saw zero calls in the menu route. A follow-up trace failed at
breakpoint insertion. Neither is menu-consumer proof; that optional trace
path was removed from the delivered probe. Static menu gate code plus the
live enable-byte contrast establish the narrower facts above.

The battle roster at `020159E4` becomes scratch while selecting/confirming a
target. `ActorAdapter.snapshot()` correctly rejects it, then succeeds again
after the cast. Do not bypass that rejection or run a fresh-menu ownership
heuristic inside targeting. Implement a separate verified modal reader that
pins the original actor, validates the canonical unit/peer and selected
ability, distinguishes preview from final confirmation, and stops on stale,
changed or unknown states. Prove cancellation and insufficient-MP refusal
before connecting the policy chooser. Then test ally targets, KO/Life and
the wounded-party policy comparison. Item counts remain undecoded.

```powershell
python tools/validate_a6_recovery_probe.py --cast outputs/autobattle/a6-cure-cast-03/probe.json --low-mp outputs/autobattle/a6-cure-low-mp-01/probe.json --cancel outputs/autobattle/a6-cure-cancel-01/probe.json --out outputs/autobattle/a6-recovery-artifacts/checks.json
```

Retained-artifact validation passes three positive controls and rejects nine
mutations (missing input log, wrong ability/target, unspent MP, no healing,
low-MP enabled flag, extra fixture write, cancellation resource/state errors).
It validates the saved observations;
it does not run fresh gameplay or certify public-runner policy behavior.
