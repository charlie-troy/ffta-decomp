# A6.6 inventory and consumable research

Status UNKNOWN. Prerequisite A6.5 bounded PASS at24efadd. Item execution stays
disabled until native inventory, count, availability and legal use are proved.
Canonical gate: `docs/receipts/autobattle/A6.6.json`.

## Bootstrap on2026-10-14

Native item-table regression8/8 passes, including7144 property loads and the
CSV/icon round trips. Pure-host schema2 policy119 checks pass, including
consumables disabled by default, missing counts and last-item conditions.
These are prior-component checks, not a live inventory acceptance gate.

Known consumable stat-table IDs362..375: Potion, Hi-Potion, X-Potion, Ether,
Elixir, Antidote, Eye Drops, Echo Screen, Maiden Kiss, Soft, Holy Water,
Bandage, Cureall and Phoenix Down. All have raw item_type30 and random-pool
category29 at+0x18. Accessor080CA7A4 property3 confirms raw type30.
Raw item_type29 instead describes accessories355..361.080CC788 draws random
items; it is not a category/count getter. Preserve those namespace exclusions.

## Next discriminating packet

Capture one actor-owned native Item list with guarded, separately ledgered
menu navigation if needed, and no final consumption input. Join its actual
rows/names to inventory records and locate the count accessor or renderer.
Item group IDs and counts must be observed; do not reuse cursor index or static
category as an inventory field. Unknown count stays UNKNOWN, never zero.

Require native count0/1/multiple, zero-count disabling, last-item reserve,
stale/aliased/foreign actor and inventory refusal, and current battle target/
law legality. Only then design the single-attempt use witness with actual
count decrement, attributable HP effect, Wait/next actor, STOP and fresh public
same-PID lifecycle. No count or use field was mapped by this bootstrap.

## Native inventory and Item reader checkpoint

A6.6.1 remains UNKNOWN overall; inventory and owned-list joins now pass.
`consumable_inventory.py` reads fourteen four-byte records at02001EE4:
u16 global item ID, u8 owned quantity, u8 reserved quantity.080CB2B4 searches
that pool and returns owned minus reserved. An absent ID means zero only after
the complete pool has passed bounds, uniqueness and coherence checks. Invalid
reservation arithmetic fails closed. Pool order is not the Item-menu order.

080CB388 maps native Item rows1..14 to global IDs362,363,364,365,366,375,
369,370,371,373,372,367,374,368. The native menu uses race0 item-effect rows;
the character's own race table would misidentify them. Row15 is ability265
Draw Weapon and has no consumable count: always excluded from this reader.

Two source-stable native captures (`a66-Item-list-02`, PID111284, and
`a66-Potion-overlay-03`) join13 consumables to Montblanc5's secondary Item1
list. Potion60 and Ether6 agree with rendered counts; Elixir is absent and0.
`OwnedItemList` pins canonical actor/name uniqueness, wrapper/peer, menu,
manager/callback, accepting mode7/state0102/driver004B, rows and inventory.
33 actual-ROM accessor controls,36 reader mutations and8 actual-ROM builder
controls pass. The builder controls isolate count0/1/2/60, reservations, Frog
(only Maiden Kiss remains enabled) and runtime availability flag13. Their
synthetic changes occur only in Unicorn, not in a live game or source asset.

The probe selected enabled Potion once and stopped in an unaccepted native
overlay: ability251, no inventory change, no target acceptance/final input.
The original battle-start fixture first had an invalid transient mirror, then
passively reached Marche7 without Item; both honest failures remain excluded.
The retained Montblanc fixture's cached HUD still reads HP100 while canonical
HP is241: count agreement does not establish healing target or effect.

Next: decode that overlay's canonical target/source and current law constraints,
then acquire a coherent wounded Item-owning fixture. Native flag13 is pinned
but its gameplay/law meaning remains open. Do not advance A6.6.2 until those
reader prerequisites pass. Receipt: `docs/receipts/autobattle/A6.6.1.json`.

## Wounded self-overlay and live count controls

The new constructed `a66-wounded-Item-fixture-01/consumable-recovery.ss0`
reloads with HP100/241 matching the HUD and Potion2. Only two actor HP records
and the Potion owned/reserved bytes were edited in the copied construction
session. No gameplay input occurs on build/reload. The original files remain
unchanged; this is a fixture, not a healing action.

`a66-wounded-Potion-overlay-01` pins source=target02000188, wrapper/table,
cursor and processor ability251/item362. Count remains2 and no accepted-target
copy exists.25 mutations reject wrong source/target, consumed inventory,
aliases, changed controller and already-confirmed states. Exact44-module
source closure resolves, including the retained pre-alias-hardening source.

`a66-live-count-matrix-01` passes both live constructed count controls. Potion0
is absent from the native Item list; Potion1 appears enabled. Both agree with
actual080CB2B4 and reject stale count/reservation. No item is selected in these
count controls. Default disabled/last-item host policy119 remains separate.

Reproduction (fresh output directories required):

```powershell
python tools/build_consumable_fixture.py --out outputs/autobattle/a66-wounded-NEW
python tools/probe_consumable_inventory.py --state outputs/autobattle/a66-wounded-NEW/consumable-recovery.ss0 --inspect-potion-target --out outputs/autobattle/a66-overlay-NEW
python tools/validate_consumable_overlay.py --capture outputs/autobattle/a66-overlay-NEW --out outputs/autobattle/a66-overlay-NEW-checks.json
python tools/run_consumable_reader_matrix.py --out outputs/autobattle/a66-count-NEW
```

The matrix uses Python psutil (verified installed7.2.2) to clean up only its
owned child process tree if a subprocess fails or times out. It retains partial
evidence. Run one emulator-owning probe at a time (port2345).

Current open prerequisite: current law identity/compliance and final prompt
legality. START from the command menu is inert. One guarded B yields field
mode0/driver54, then START opens native System mode1/driver67 with observed
rows1..6 (Turn Order, Mission, Law Cards, Options, Flee, Save Now). Law Cards
row3 may be opened for inspection; no card application is authorized by this
reader. A6.6.2 consumption and public A6.6.3 stay gated.

## Current law display, not yet Potion compliance

`a66-Law-Cards-open-01`, PID40048, opens the native law panel with the guarded
B/START/System row3 route.25 raw key writes match those five presses; source
closure and asset/capture hashes pass. No card is selected or applied. The panel
shows forbidden Skills, Dmg2: Animal and Broadswords, recommending Techniques,
Status and Spears. Native02003C32 capacity4 and02003C34 u16 IDs1,82,42,0 are
unchanged by inspection; actual0802D764 counts3 nonzero entries. Isolated count
controls0/1/3 pass. MAIN_STRINGS[625+ID] matches the three forbidden labels;
this is a bounded inference, not a general decoded law-name accessor. The
recommended-ID mapping remains unknown.

Next executable step: trace the native law violation/classification predicates
for active Skills1, Animal82 and Broadswords42 against source Montblanc5,
self-target and Potion ability251/item362. Enabled Item rows and a legal cursor
do not settle that question. Final-prompt legality and A6.6.2 remain gated.

## 2026-10-15: isolated law matcher and final prompt reached

Native law records are16 bytes at08528F34.081343C8 is the matcher called by
08134B88 with source,target,ability,action flag in r0..r3 and phase,amount,
effect-bit pointer,law-record pointer on the stack (see0813504E..08135072).
Native08133D78 resolves ability251 to action set1 (Item). On pinned Montblanc
self-Potion, actual matcher runs return0 for active Skills1/Animal82/
Broadswords42 and1 for the separate Items20 control. Amounts-30/0/30 all agree:
12 executions, normal returns, zero EWRAM writes. These are isolated native
predicate results, not observed live calls or a proved action-result queue.

New typed preview/description gates permit only target acceptance and final
prompt inspection. Six host preview controls and nine native-description
mutations plus STOP/retry controls pass. `a66-Potion-final-prompt-01` reaches
Do it/Cancel with callback080293DD/state0102/mode11, selected251, cursor0,
processor state2/flags20.40 raw writes match eight guarded navigation/inspection
presses. HP100 and Potion2 remain unchanged; Do it is never selected. Source
closure46 resolves. Earlier preview-only capture closure45 also resolves via
the exact archived probe source.

Unresolved observation: the description header says Heal HP and selected
ability251 is Potion, while the lower panel displays Blizzard/26dmg. Keep that
visual/effect-queue mismatch UNKNOWN. Do not use it to claim healing or law
compliance of the live queue. Next bind a final-prompt token and verify the
matcher's RAM dependencies, then identify the actual preview/effect queue.
A6.6.2 and public item execution stay gated.

## 2026-10-15: bounded final reader and preview controls pass

The isolated law matcher now maps only the pinned unit. Read hooks reject any foreign EWRAM or non-stack IWRAM dependency and EWRAM writes. Current laws1/82/42 return0; Items20 returns1. Unknown law IDs, moving data, aliases and Cancel are refused. Twenty-two final-context mutations pass. This is actual ROM execution with captured unit data, not proof of a live matcher call.

Fresh `a66-reaction-free-final-01` PID22428 reaches the final owned Do it prompt with selected251, unchanged HP100/Potion2,47-module source closure and40 attributed raw writes. `a66-reaction-free-01` changes only the two HP records, reaction bytes and Potion count/reserve in a copied session; independent reload confirms native reaction getter080CD4D4 returns0. Original slot75 resolved Blizzard29; removing it removes that displayed reaction. No final use input was sent.

The remaining generic dmg label is also present in retained accepted Cure screenshot `a6-cure-cast-03/07-A.png`; its probe records actual HP100 to163 and MP85 to79. Thus the label alone does not establish damage. This resolves the preview discrepancy at the reader boundary; it does not prove the actual Potion effect queue. A6.6.1 passes only for this bounded reaction-free self-Potion fixture. A6.6.2 must measure real consumption, healing and turn completion. Clear EXP99 explicitly in a new clone before use to avoid an unrelated native level-up prompt. Public item execution remains disabled.

## A6.6.2 first native single-use witness

EXP0/reaction-free cloned fixture independently reloads with seven construction writes and zero gameplay input. The single-use gate has11 host controls (STOP, late STOP, stale/late stale, foreign token, last item, zero, reserve, partial and ambiguous input); all attempts latch against retries. Final input uses pause0 so native tracing can resume before consumption.

`a662-single-use-02`, PID98260, records45 attributed raw writes, source-stable and no RAM edits. Actual080CAA68/6A decrements global item362 quantity1 at02001EE4 from2 to1; then080A2298/9A stores canonical Montblanc5 HP100 to125. MP stays221. Eleven capture mutations reject. Count routine has no actor argument: association uses the pinned final self-Potion context, retained source wrapper0202270C and following canonical HP store. Processor+EC has already cleared to0; the first failed assertion on that field is retained as excluded evidence. No fixed30HP claim is made.

Turn completion remains UNKNOWN. First command-restoration attempt timed out after the effect. A focused follow-up records rejection reasons and permits rebinding only when the sole post-store unit change is the explicit EXP0 to10 reward. It does not retry final Potion input. Guarded Wait uses the existing validated structural Wait boundary (its historical Life diagnostic tag is retained). Two complete reloads and live STOP/refusal controls are still required; public Item execution remains disabled.

## Strict cleanup correction and two clean complete reloads

The explicit-halt-only fix was insufficient: turn06 again received a queued S02 while expecting a breakpoint-removal acknowledgement. The terminal research probe now uses `ConsumableResearchTransport`: it strictly disarms while halted and never restores hooks/resumes just before the owned process is closed. Default public `RecoveryTransport` is unchanged. Four terminal host cases and13 default-transport regressions pass.

Current-source clean-turn07/PID51040 and08/PID87840 each complete the native Potion decrement/HP-store pair, Action-consumed command, guarded Wait and independently joined next actor. Each records65 raw writes, terminal strict disarm and owned process close;13 audit mutations reject, including absent cleanup/process still alive. The final screenshot shows next actor Carson. Prior failures remain excluded. A6.6.2 still awaits the live STOP/reserve/zero matrix; public integration is separate.

## A6.6.2 bounded PASS

The actual research CLI matrix `a662-live-refusals-01` passes STOP-final-use, STOP-post-effect, STOP-Wait-final, last-item and zero. STOP observation occurs within2s of the actual STOP file and write counts remain40/45/60 after the latch. Last item1 refuses before any final use at40 writes, with unchanged HP100 and inventory; native zero omits Potion and refuses before selection at25 writes. All source closures and raw capture hashes pass; each refusal rejects3 corruptions and closes only the owned process after terminal strict disarm. This joins the two clean full use/Wait/next-actor reloads to close A6.6.2 for reaction-free EXP0 Montblanc self-Potion only.

A6.6.3 remains UNKNOWN. The public runtime must use schema2 policy evaluation and default-disabled consumables, then prove real CLI STOP, manual window handoff, same-PID resume/player result and affected Cure/Life/default regressions. Research STOP/process termination is not public manual/resume acceptance.
