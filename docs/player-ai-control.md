# Player/AI control boundary (A2)

> Current acceptance authority: [C1–C3 roadmap](auto-battle-roadmap.md) and
> [worker contract](autobattle-worker-contract.md), updated 2026-09-17.
> Earlier closure claims below retain their historical limits; cancellation
> and usable handoff (C1) and identified non-Wait selection (C2) are now
> accepted per their criterion receipts
> (`docs/receipts/autobattle/C1.json`, `C2.json`).

Status: **A2.4a done (2026-09-10); A2.3's roster model is refuted in part.**
Retail player turns DO ctx-init the AI sequencer and the menu/AI split is a
merged pipeline — both stand. But the fixture's slot identities were inverted:
**slot0 is an enemy (Jon), and Marche is slot 6**, the RAM-named unit the old
rule wrote off as scratch. Every A2.3 statement phrased as "Marche = slot 0"
is wrong and is annotated below. The verified fixture is `battle-start.ss0`;
`a2-battle-start.ss0` does not pass the guard at all.
**A2.4b done (2026-09-10): neither candidate lever is a player-to-AI route.**
The bit7 router is the **Stop** skip, not a menu handout, and Controlled
(`+0xED` bit3 + `+0xE6` id) is cleared at its own consumer's turn start.
Receipt: `outputs/autobattle/A2.4b/`. A2.5 as written has no surviving lever;
the decision below replaces it.
**Dispatch authority:** the orchestrator must pick a direction from the design
comparison at the end of this file before A2.5 or A3 is commissioned.

## A2.4a result (2026-09-10) — fixture and harness repair

Receipt: `outputs/autobattle/A2.4a/` (`inventory-variants.json`,
`baseline.json`, `control.json`, `reject.json`, `summary.md`); metadata in
`docs/battle-fixtures.md` and `configs/battle-scenarios/normal-battle.json`.

* Only `battle-start.ss0`, `battle-start-r1.ss0` and `fix3-battle-start.ss0`
  hold the battle roster. `a2-battle-start.ss0` (used by the v36/v44-era
  experiments) fails the guard: empty roster array, undecodable slot0 name.
* Live roster: 7 units — enemies Jon, Velasquez, Godfrey, Schneider, Carson
  (0x8000 set), the neutral Judge (0x1000), and the player Marche (slot6,
  EWRAM name pointer `0x02001F1C`, id 6). No turn-scratch record exists inside
  the array.
* The old boot guard's `NAME0_ADDR` sampled slot1 (Velasquez) and its
  `MID6_ADDR` sampled Marche's unit id 6. `tools/fixture_guard.py` now verifies
  slot0 identity, roster bounds, count/unit agreement and the named player.
* Reload baseline (x2) is identical: PC `0x08000428`, CT
  `[45, 464, 850, 821, 515, 315, 0]`, the DOWN DOWN A A route commits the
  player turn, seeds at `0x080C03C2` name Carson/Jon/Schneider, Godfrey and
  Schneider CT reset to 0, Marche CT charges 0→257. Only write: the key-enable
  byte, restored.
* No-input control: zero seeds, CT vector unchanged over 25 s
  (`dormant_awaits_player_input`), so the baseline's progress is caused by the
  driven commit.
* Guard rejection proven for `engage.ss0` and a missing state, with zero
  writes before the decision.

## Fixture chain

`outputs/lua-nav/worldmap-nat.ss0` → `engage.ss0` → `battle-start.ss0`
(verified: solo Marche vs the five-member enemy clan Jon/Velasquez/Godfrey/
Schneider/Carson plus the Judge, player menu open, WT 1/7). The battle-start
state reloads deterministically on fresh instances. `a2-battle-start.ss0`,
which this line used to name, is **not** a battle state — see the A2.4a section.

## Input channels (the hard-won part)

The battle menu ignores D-pad from **every** source — `emu:setKeys`, real
keyboard (UIA SendKeys), and raw KEYINPUT patches — while A/B/START/SELECT
respond. The key system explains it:

* Per-frame poll: `0x08000482–0x08000494` composes `r1 = (KEYINPUT ^ 0x3FF)` and
  calls the update function: `bl 0x0800221C` with `r0 = 0x03000000`.
* Key-state struct at **IWRAM 0x03000000**: `+0` held (u16), `+2` newly-pressed
  (u16), `+4` unconsumed-pressed (u16), `+5` enable byte, `+7` mode byte,
  `+8` consumed mask, `+0xC..+0x10` auto-repeat state.
* `update_keys` **recomputes** `+2`/`+4` from `r1` every frame, so Lua writes to
  those fields are clobbered before the UI reads them. They do work for
  out-of-battle UI (the world-map cursor moved with `tools/lua_inject_key.lua`),
  but never inside battle screens.
* The working battle input channel is **register patching**: break at the call
  site `0x08000494` and OR the wanted bits into `r1` each frame via GDB `P`
  packets. `tools/gdb_force_key.py --mask 0x80 --frames 4` moves the battle-menu
  cursor one entry. Masks: A=1 B=2 SEL=4 ST=8 RIGHT=16 LEFT=32 UP=64 DOWN=128.

### Crash trap (cost half a session)

Single-stepping into `update_keys` and resuming mid-function leaves the game in
the BIOS illegal-instruction handler (`pc=0x00000004`, stop reply `S04`). The
screen looks alive but game logic is dead; all subsequent breakpoints/injections
silently no-op. Diagnose by connecting GDB and reading the PC. Recovery: reload
a savestate. Never `s`-step through the key system; patch registers only.

## Turn manager (live capture)

* `sub_0809E05C` runs in normal battles, called from `sub_0809E1E0` at
  `lr=0x0809E261` — exactly the turn-order.md chain. 30 hits recorded in
  `outputs/lua-nav/turn-manager.json` across a Wait→enemy-turn boundary.
* Battle struct: `r0 = 0x020159E4`; `[struct+0] = 7` (unit count, matches WT x/7).
* Unit array at `struct+4`, stride **0x108**. The function rebuilds a candidate
  list per unit, gated by `0x080CD8B4` (return byte == 1) and
  `0x0812E368` (nonzero) — the controller-decision surface to decode next.
* At entry `r1` cycles over seven 4-byte records at `0x02016750..0x02016768`
  (scanned in descending order) — the caller's CT-scan loop state.
* Static (prior session): the turn loop clears the new actor's Controlled bit at
  `0x0809E272` (`sub_080CE2F0(actor, 0)`); `sub_080970E8` searches units by
  controller id; Controlled (`0xED` bit 3, duration byte = controller unit id)
  is independent of the `0x8000` side bit and of Charm/Confuse.

## Hands-off loop (A3 prerequisite, proven)

From `a2-battle-start.ss0` (per A2.4a this savestate is rejected by the guard;
the runs behind this claim most likely booted `fix3-battle-start.ss0`, which is
what the default boot helper used): inject DOWN ×2 → Wait → A ×2. Turn ends,
enemies act autonomously (Marche 442→436→438 across rounds), and Marche's menu
re-opens automatically. A2.4a reproduced the turn-flow half on the verified
fixture: the same route commits the turn and enemy sequencer seeds follow, while
the no-input control stays dormant. This proves an input/turn-flow loop.
Re-confirming Wait each round does not prove autonomous player tactical
selection and does not satisfy A2/A3.

**Claim correction (2026-09-16, external review).** A2.5's roadmap checkbox
was marked done while its first acceptance item — autonomously choosing a
non-Wait action — was never demonstrated: the manual route selects Wait and
the delegated turn's selection is the engine's retail AI. What the receipts
do prove is the reversible delegation cycle (boundary detect → external
commit → engine runs → boundary returns). Deliberate non-Wait selection is
now implemented in the runtime as the IDENTIFIED-ONLY boundary (round 6): every
player turn is selected from RAM — the decoded command cursor must read Move
and the target cursor must be readable before ANY input is issued; a rejection
prevents input entirely (chooser routes, fixed routes, and B-recovery are
deleted, since selecting by key sequence is exactly the unfalsifiable claim
the contract bans). Live verification: c2-live4/5/6/7 (verified identified
moves, twice from reload under final code).

## mGBA environment notes

* `-g` instances hang occasionally in a DMA-wait (`0x0800143C`) during boot or
  scene transitions — nondeterministic; relaunch. The title→attract-cutscene
  transition also masquerades as a hang; a START burst skips it.
* Natural boot: title → START burst ×8 (skip cutscene + open menu) → Load →
  FILE NO. 2 → world map. Savestate reloads kill setKeys D-pad on the world
  map; a full-key mash-and-release (`{1023,10}` then release) restores it.
* mGBA 0.10.5 Lua read callbacks never fire; execute callbacks and
  `emu:read16/write16/setKeys` all work.

## A2.3 verdicts (v46–v48, 2026-09-09)

**Superseded 2026-09-10 (A2.4a): this paragraph is inverted.** Read it as
recorded history only. The live roster at `0x020159E8`, stride `0x108`, holds
**seven** units: slot0 is an enemy named **Jon** (`0x085671EE` decodes to
`Jon`, CT=45), slot1 is the enemy Velasquez (`0x0856702F`), slots 2–4 are the
enemies Godfrey/Schneider/Carson, slot5 is the neutral Judge, and **slot6
(`0x02016018`) is Marche** — a real unit whose name pointer is in EWRAM
(`0x02001F1C`) because the player's name is save data. There is no turn-scratch
record in the array. Consequences: every "EA6/CT6" read in v44–v46 read
*Marche*, not a phantom; the v44 bit7 flip wrote an **enemy's** `+0xEA` (slot1);
and the wake marks in the v27 recipe (`+0xE6`/`+0xDC` = id `+0x104`) were
written to **slot0 = Jon with id 0**, not to the player. A2.4b must re-derive
the wake/commit protocol with the corrected layout (player slot6, id 6).

**Dormant-boot mystery solved.** From `fix3-battle-start` the menu never
idles into auto-battle by itself; the turn loop starts only after Marche's
turn is committed. Wake recipe (v27's, reconstructed from v43's docstring):
write the forward-handout marks on slot0 — `+0xE6`/`+0xDC` = Marche id
(`+0x104`), `+0xED |= 8`, `+0xEA |= 0x80` — then drive DOWN DOWN A A with
`enable=1` (`M3000005,1:01`). *(A2.4a: slot0 is the enemy Jon and `+0x104` there
is 0, so these marks were applied to an enemy unit; the "self-play" below is
therefore the enemy side being handed to the menu body, and the recipe must be
re-derived on slot6 = Marche before it is used again.)* With marks the battle
self-plays a full round instantly (6 seeds); without them 8/8 runs stayed frozen
despite identical drives.

**A2.3 Q1 — do retail player turns ctx-init the sequencer? YES.** v48: the
player-driven commit (A-ok at t≈7.0, Marche menu pbody at t=8.9) is followed
by a seed (`0x080C03C2`) at t=10.2. Auto-battle turns pair the same way:
scratch-record pbody burst → seed within 1.6 s (t=54.4→55.2, t=62.0→63.6),
including an enemy seed at t=55.2. Player-side and enemy turns share one
action-execution path through `sub_080C034C`.

**The pipeline model (replaces the two-body picture).** `0x0809E796` is a
**merged continuation**, not an exclusive player body. It has exactly two
in-edges (exhaustive branch scan): the bit-7 router at `0x0809E3AE→E3B8`, and
the status-housekeeping tail at `0x0809E784/788` (`+0xDB`/r6 tests — the
Haste/Slow tick per unit-flags.md). Every active turn flows through it:
bit-7 units jump in directly, all others arrive after AI housekeeping. Hence
pbody hits with `ea=0` and pb≈ai hit counts (v48) — not a contradiction.

**`+0xEA` bit 7 = menu-body router (forward handout only).**
`sub_080CDADC` = `(rec+0xEA) & 0x80`; nonzero routes the turn into the menu
body at the pick. It is **consumed at turn start on turn records** (v48 pbody
hits always show `ea=0` at hit time even when the roster byte was set), and
the auto-battler sets it transiently on turn-copy records while navigating
menus for player-side units (allies hit pbody with roster ea=0). *(A2.4a: the
"scratch record" this paragraph names at `0x02016018` is Marche's unit record,
so the transient-copy claim needs re-checking in A2.4b rather than being
quoted as settled.)* Therefore
"Marche bit7 → AI" is a category error: bit7=1 routes TO the menu body — that
is the forward handout. A true reverse handout must target a different lever.

*(A2.4b, 2026-09-10: **refuted.** `sub_080CDADC` is the `+0xEA` bit 7 getter for
**Stop** (`docs/unit-flags.md`, setter `sub_080CE050`, duration `+0xDC`); there
is no menu at the other end of the branch. Live, all seven units — enemies, the
Judge **and the player Marche** — reach the router with `+0xEA = 0` and take
`0x0809E3BA`; forcing bit7 on one enemy moved exactly that one turn to
`0x0809E3B8` and changed nothing else. `0x0809E796` is reached from both paths
(`tail hits == router hits`), so it is a common continuation, not a menu body.
The router is side-agnostic and cannot be a player/AI discriminator.)*

**Wedge signature and protocol rules.** A compressed turn (CT=10) opens the
actor's menu; with no commit and `enable=0` the battle freezes forever (CTs
static, no new seeds) — v47/v48's control/reverse phases wedged this way.
Rules: write `enable=1` once at attach; never leave a turn's menu undriven;
sample ticks must call `interrupt()` (a quiet free-pump never samples); keep
presses v27-faithful (5 frames at the `0x08000494` poll, CPU running between
presses); attribute pbody hits by `r7` (actor slot) — `r4` is the record.

## A2.4b result (2026-09-10) — no safe player-to-AI lever among the candidates

Probe: `tools/probe_control_handoff.py` (one reusable tool, `FixtureSession`,
name-based actor attribution). Receipt: `outputs/autobattle/A2.4b/`
(`slice1-bit7.json`, `slice2-controlled-pc.json`, `summary.md`).

### Slice 1 — the bit7 router is the Stop skip, not a menu handout

Three fresh reloads of `battle-start.ss0`, one variable each.

* Natural: 42/42 router hits take `ai_path_0x0809E3BA` with `+0xEA = 0`. All
  seven units appear, six cycles, **including Marche and the Judge**. Every turn
  reaches the shared tail (`tail hits == router hits`).
* Intervention: forcing `+0xEA |= 0x80` (with `+0xDC = 1`) on the first enemy at
  its router moved exactly that one turn to `shortcut_0x0809E3B8` — 1 shortcut
  in 43 turns. No menu opened, no extra input was consumed, and the actor's
  acting turn was skipped (its CT ended at 959 where the natural run has 0).
* Restoration: the game's own turn-start countdown consumed the bit; all `+0xEA`
  bytes read `0` at run end with no restore write, and the third reload
  reproduces the natural run exactly.

So `+0xEA` bit 7 is the **Stop** status and `0x0809E3B8` skips the AI
housekeeping block; it is not the player/menu seam.

### Slice 2 — Controlled is cleared by its own consumer

`+0xED` bit 3 plus `+0xE6 = 6` on the first enemy, at three placements:

* boot: wiped before the turn loop reads it (`ed_before = 0`);
* immediately before `0x0809E272`: the clear consumes bit 3 in the same
  instruction (`ed_after = 0`);
* immediately after `0x0809E272`: the bit survives to the router (`ed = 8`,
  `e6 = 6`) but the branch is still `ai_path`, the enemy still acts, and the end
  CT vector is byte-identical to the natural baseline.

Controlled is a same-turn marker, cleared at its consumer's turn start. It is
neither a persistent delegation nor a way to hand an enemy turn to the player.

### Attribution and honesty notes

* Router hits were driven by `0x0809F7B4` and `0x0809F870`, two battle-side
  helpers; the turn-order preview at `0x0809E830` never ran (`preview_hits = 0`).
  The router code is shared by all callers, so the bit7 direction is
general, but this receipt does not claim the interactive pick uses that path.
* Sequencer contexts reference the AI mirror array at `0x02002FC4`; actor
  identity is decoded from the record's name pointer, never from slot index.
* No CT was written or compressed, and key enable was restored every run.

## Design comparison — sequencer delegation vs external action selection

The two candidate levers are gone, so the choice is architectural. Both options
are stated with what the existing evidence already buys and what it still costs.

**Option A — sequencer delegation (engine-internal AI).** Make the engine treat
a player unit as AI-driven for one turn: a persistent, reversible bit or a
runtime flag the turn dispatcher reads after it picks the actor.
*Evidence status:* the two bits A2.3/A2.4 tested are wrong (`+0xEA` bit7 =
Stop, `+0xED` bit3 = Controlled, both statuses with their own consumers). The
player/AI decision does **not** live in the turn-loop router (`0x0809E1E0` is
side-agnostic), so it lives in whichever caller checks the `+0x28` bit `0x8000`
side flag. That caller is not yet identified, and the `0x8000` semantics are
still "supported, not proven by an executed branch" (A2.4a limitation).
*Cost:* more reverse engineering of the battle dispatcher, plus a new runtime
hook whose lifetime must be proven safe across turns and reloads. The engine's
AI would then choose player actions with no per-character policy surface, so
M2's per-character tactics would need a second mechanism anyway.
*Strength:* no input macros, and the actor's action is engine-legal by
construction.

**Option B — external engine-legal action selection (recommended).** Let the
engine own the turn; the companion observes the picked actor and supplies one
legal action through the already-proven input channel at `0x08000494`.
*Evidence status:* `1334849` already proved register-level battle input and a
reversible turn loop; A2.4a/A2.4b prove the fixture reloads deterministically
and that a committed player turn is followed by engine-driven enemy actions.
The candidate-action and legality data come from the engine's own candidate
list (A5's `choose_action(snapshot, policy) -> candidate | None` interface is
designed for exactly this), and the policy layer stays pure and testable.
*Cost:* the runner must recognise the boundary for each player actor and must
  fall back to retail/manual on an unknown modal; action execution quality is
  only as good as the observed candidate data.
*Strength:* it matches the roadmap's stated architecture ("keep strategy
evaluation separate from emulator transport"), it needs no unverified ROM
semantics, it is reversible by construction (nothing persistent is written),
and it makes per-character tactics (M2) directly expressible.

**Recommendation.** Take Option B as the product path and treat Option A as a
diagnostic only. Concretely, A2.5 should be re-scoped from "prove retail-AI
delegation" to "freeze the boundary contract for externally selected,
engine-legal player actions", reusing the A2.4b probe as the transport layer.
If the orchestrator wants Option A, the smallest next evidence step is to find
the caller that branches on the `+0x8000` side flag and prove that branch with an
executed breakpoint before writing any runtime hook.

The roadmap defines the current ordering and acceptance criteria; per the packet
this comparison replaces the previous "Next" list.

## A2.5 result (2026-09-15) — the reversible control cycle is proven, twice

Two runs from fixture reload completed the full chain — engine-delegated
player turn with movement, engine-driven enemy progression, manual takeover at
the boundary, a visible manual choice, and re-enabled delegation — and both
classified `valid_engine_legal_player_action`:

- `outputs/autobattle/A2.5/a25-acceptance-repeat1.json` (run 19; battle alive
  at end, CTs mid-charge, Marche tile (4,10), 10 seeds, 298 router hits)
- `outputs/autobattle/A2.5/a25-acceptance.json` (run 20; 17 seeds, 522 router
  hits; the battle concluded naturally shortly after re-delegation)

### Frozen runtime contract (what an A3 runtime must rely on)

**Input channel.** Inject keys by writing REG_KEYINPUT (0x04000130) at the
key-poll breakpoint 0x08000494, `frames=5` (five polls; `x5` hit counts).
`frames=1` injections do not register with an open menu. Never leave a turn's
menu undriven: a bare A on the command menu opens the move-target modal and
stops the turn driver (run 4). The only proven commit shape is the full route
DOWN, DOWN, A, A — on the first menu of a turn it selects Wait and closes.

**Boundary shapes (all RAM-verified, with screenshot proof where noted).**

1. *Turn-ready flash*: player CT == 1000, holds ~10 s BEFORE the menu opens.
   Not drivable — input here lands on no menu (run 7).
2. *First menu of a turn*: the engine parks the active player unit at a
   stable low CT (188 observed; stability across polls discriminates from
   charging). `player_menu_settled`.
3. *Re-opened menu after a commit*: the owner's roster CT freezes at an
   ARBITRARY value — 0, 305, 600, 812 all observed (runs 17–19 screenshots:
   command menu visibly open while the roster reads those values). Detection
   must be value-agnostic stability: `player_menu_frozen` (byte-equal CT
   across ≥2 polls, excluding only the 1000 flash). The old `ct <= 188` bound
   is wrong for re-opened menus.
4. *Dormant await-input*: seed silence, static CT vector, live roster, router
   still scanning — the menu-wait state under another name.

**Battle end (not teardown).** At natural battle end all eight CTs read 0,
the final frame gains a magenta cast, and the router keeps scanning — but the
fixed-address roster keeps nonzero max_hp, so `battle_torn_down()` (whole-block
hp/max_hp wipe) correctly stays False. Teardown and battle-end are different
states; neither is a menu wedge. Run 6's old "teardown" was a misread roster
copy during action execution.

**Menu cursors (C2 decode, 2026-09-17 — the open menu is readable, not
blind).** Differential RAM sweeps over repeated menu cycles pinned the player
menu's live state; the A3 runtime's identified-candidate branch
(`plan_identified_move`/`commit_identified_move` in
`tools/probe_control_handoff.py`) selects from these reads instead of
inferring an action from the key sequence it sends:

- Command cursor `0x0202ddd9` (u8): 0=Move, 1=Action, 2=Wait. Trajectory
  0,1,2,1,0 reproduced across two independent down/up cycles; neighbor
  `0x0202ddd8` reads 7 (adjacent menu field, undecoded).
- Move-target cursor x/y `0x0200ffc9`/`0x0200ffca` (adjacent-byte struct
  pair; mirror `0x02010058`/`0x02010059`). Values track every step
  ((4,10) at menu open → (4,11) after one DOWN); 4-byte-apart shadow pairs
  found in the same sweeps dropped out at the end-to-end commit.
- Commit semantics (probe5/6, engine-verified): confirming a destination
  MOVES the unit and RE-OPENS the command menu (cursor re-initializes at
  Action); the roster tile updates only at turn commit; a Wait turn closes
  with select A + confirm A. Confirming the unit's own tile re-opens the
  menu without moving (the zero-move pitfall).
- Legality: a destination outside the unit's movement range leaves target
  mode open (probe4) — the engine rejects the walk; the decoder must not
  plan past an illegal state.

Receipts: `outputs/autobattle/c2-menu-probe*/`, live identified executions
`outputs/autobattle/c2-live4/`, `c2-live5/`, negative control
`identified-move-wrong` in the transport suite,
`docs/receipts/autobattle/C2.json`.

**Transport rules.** With the battle sequencer running, breakpoints fire
continuously; stale T05 stop-replies can race Z0 inserts and presses abort
mid-route (run 5). `press()` must retry inserts, service stale stops, and
suppress the trace breakpoints (menu-loop ROUTER/BRANCH fire ~10×/s and starve
the key poll) for the press window. With that, every route press lands `x5`.

**Visual channel.** mGBA's GL surface does not composite into CopyFromScreen
on this workstation's secondary portrait monitor — every screenshot taken
there is desktop pixels and void as evidence (runs 14–16 lost their visual
record to this). `FixtureSession` now moves the emulator window to the primary
monitor at boot (`_move_window_to_primary`); probe input is injected via GDB
breakpoints, never window messages, so the move cannot affect a run. Validate
captures by distinct-row hashing: an occluded or void frame collapses to a
near-constant row set.

**What re-delegation means here.** Per the A2.4b Option B re-scope, the
"driver" is the probe supplying engine-legal choices over the input channel.
The second player turn is therefore delegated when the probe drives the
re-opened menu without human input — runs 19/20 both did this (run 18 showed
the committed route re-charges the cycle; the engine then runs turns on its
own until the next player boundary).

**Honest limitations.** (1) The manual choice in both runs selects Wait — the
route is proven, non-Wait choices are not yet wired to a chooser. (2) The
takeover boundary currently watches Marche only. (3) Battle-end vs. teardown
discrimination rests on max_hp persistence at fixed addresses; a RAM-shifted
roster during teardown could still fool the check (never observed). (4) Run
20's post-redelegate end state (all CTs 0, magenta frame) is classified
"battle concluded" from frame + seed evidence, not from an engine-end flag.
(5, 2026-09-16) In the A3 runtime, "takeover" names the automation-driven
boundary state, not a manual handoff: a STOP request now pauses the run
(`paused`), disarms breakpoints, and — with the CLI's default
`--on-stop leave-running` — leaves the emulator alive for the player.
(2026-09-17) The handoff is proven through the real cleanup path, not a mock:
`tools/handoff_cli_probe.py` boots a live battle, drops a STOP mid-battle,
and lets `FixtureSession.__exit__` run with `keep_process` already flipped —
the emulator survived the exact path Astra's review showed was broken
(receipt `outputs/autobattle/a3-handoff-probe/`). The stop file is also
polled inside long progress waits and between every identified-drive leg
(the settles poll the gate every 100 ms — round 6 restored the 2 s
observation bound), so input stops mid-wait.
(2026-09-20) The full handoff loop is closed live (`c3-live-b2`, receipt
`docs/receipts/autobattle/C3.json`): leg 1 paused via STOP and left the
emulator running; the manual layer (`tools/c3_manual_layer.py`) adopted the
handed-off pid and committed one identified move + Wait **through the window
channel only** — SendInput key events, zero stub writes — using one held
monitor connection under the stub's one-client law (interrupt → one read →
cont per observation, cross-validated fields, clean close before resume).
The layer's laws, learned live: a turn STARTS in move-target mode (ring
under the unit, command-menu byte sticky 0 — do not wait for a menu that
isn't there); an echo-verified key is the only proof the UI is answering
(stable CT alone is not: menus park at any frozen CT value); an illegal
step leaves the target cursor frozen (probe the next direction, bounded);
confirming onto an occupied tile opens the occupant's panel (B dismisses
one layer: panel → target mode → menu); the roster tile mirrors the walked
tile only at turn close, so the commit proof is the CT leaving its parked
value (charging again). Leg 2 `--resume` adopted the same pid without a
reboot, continued from the manually walked tile, and drove the same battle
to completion.

