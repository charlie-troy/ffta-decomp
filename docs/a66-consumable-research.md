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
