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
