# A6.2 living ally target research

First effect-only cast: `a62-ally-cure-01` verifies the actual final cursor0
and canonical ally join, supplies the schema2 `cure-ally` candidate, rechecks
policy after screenshot and confirms once. Montblanc HP100->157; Marche
MP85->79 with HP442 unchanged; target MP221 unchanged; Action consumed.
50 raw writes, no fixture writes or changed inputs. Full captured RAM replay
rejects14 mutated receipts/fields; separate candidate and executor host checks
reject18 controls each. This run stops before Wait: continuation UNKNOWN and
zero verified turns. Final-reader proof supersedes the earlier derived cursor
host fixture for this observation only. Public party integration and the
preview-label discrepancy remain open.

2026-10-07 baseline: `deff57e` plus the source hashes in the A6.2 receipt.
The A6.1 opt-in remains self-only; no public target guard has changed.

## Pre-targeting identity prerequisite: PASS within the A4 fixture

`probe_recovery_party.py` boots an owned disposable copy of the eight-unit
`a4-two-player.json` fixture. It waits passively for two matching fresh-owner
observations, suspends tracing under an explicit halt and captures both battle
mirrors and all canonical member records. Each complete block is read again
while halted. Debugger packets are capped at0x200 bytes; large replies are
dropped by this mGBA stub. No gameplay input, RAM edit or state export occurs.

Fresh reloads `a62-party-baseline-04/-05` agree: Marche id7/job5/race1 is the
owner at(4,10), canonical02000080, HP442/442 and MP85/85. Montblanc
id5/job5/race1 is at(5,10), canonical02000188, HP177/241 and MP221/221.
The initial guarded fixture had Montblanc at241HP; the observed value is177HP
at the first Marche menu after the engine runs. Neither fresh run edits HP.
This 73-percent ally would not match the healer preset's50-percent rule.

Marche's name is RAM-backed02001F1C; Montblanc's is ROM-backed085512C7.
Read ROM names from the verified source image and RAM names under the halt.
Each mirror/canonical join agrees on identity, type/base/race/job/secondary/
level, side, resources and tile. Canonical name/id aliases and duplicate party
tiles reject. Each retained baseline passes37 rejection mutations, including
coherently altered KO, cross-side, over-max resources and same-job identity
aliasing. Menu root and main wrapper independently join the current caster.
Inspected the first successful baseline screenshot: Marche command menu,
HP442 and MP85. Both owned processes terminate after capture.

Earlier attempts remain unknown:01 rejected a borrowed roster;02 rejected a
large memory reply;03 rejected Montblanc's ROM name through an EWRAM-only read.
Each failed before input and retained its error/source hashes. Passive retries
do not weaken any accepted identity snapshot.

## Target processor index prerequisite: bounded ROM proof

Executed actual ROM helper080B50F0 on synthetic two-wrapper tables. Six cases
cover no input, next/previous selection, both wrap directions and an empty
list. With the caller's processor+0x4C argument, the table is processor+0x50,
the index byte is+0xA1 and count byte is+0xA2. The helper's mask0x100/0x200
branches cycle the target list. No inference about directional cursor movement
or engine Cure legality follows from those synthetic cases.

Executed caller fragment080B752C..080B7542 for both indices: it loads the
selected wrapper from processor+0x50+4*index and copies it to+0x0C/+0x10.
Static switch entry080B74E0 invokes the helper at080B751E. This identifies
concrete fields to capture live; it does not prove they currently name an ally
or establish the meaning of menu context+0x1C.

Four additional actual ROM fragment cases at080B76FC..080B7710 copy coordinates
from0200F3B8/+4 into processor+0x109/+0x10A. They intentionally vary the UI
cursor0200FFC9/+1 independently: this fragment reads the former structure,
not the latter. The earlier live overlay capture recorded only the UI cursor;
agreement with the acceptance-coordinate structure is UNKNOWN. The next live
capture must read both under the same halt and join them to the canonical
target tile. These fragment tests do not execute surrounding acceptance checks.

## Next live gate: UNKNOWN

Final-prompt experiment `a62-ally-confirmation-01` now reaches Do-it/Cancel
through a revalidated `AllyPreviewReader` token, then stops. Twelve preview
reader controls reject changed resources, target wrappers/table and coordinates.
The live final prompt is CONFIRM/mode11/state0x102, processor state2/flags0x20.
Processor+8 retains ally wrapper0202270C/canonical02000188; +0/+4/+0x0C name
caster0202267C, +0x10 is0, and context peer still names canonical caster.
45 raw writes, no final cast and no HP/MP changes. Eight retained prompt mutants
reject. Inspected Do-it/Cancel screenshot. Callback-header captures do not
include its cursor payload; the next live final-candidate reader must verify
cursor0 and all target joins afresh, then repeat policy/identity checks after
any screenshot before one final input. This is a target-prompt prerequisite,
not two successful ally-Cure/Wait continuation reloads.

Selection experiment `a62-ally-acceptance-01` independently pins both party
records, then uses a separate read-only `AllyOverlayReader` token for the one
target-selection A. Both coordinate structures agree on(5,10). Fourteen
derived reader mutations reject before that step; this reader does not expose
a policy candidate or authorize a final cast.

The live selection reaches DESCRIPTION/mode12/state0x102. Processor+0 and+4
join caster wrapper0202267C; processor+8 joins ally wrapper0202270C and canonical
02000188/id5/HP100. The table reorders the ally first, while index0 and empty
+0x0C/+0x10 remain. Flags become0x6C with target state10. Context+0x1C still
names the caster; it is not the selected ally reference on this path. Both
units' HP/MP remain unchanged.40 raw writes, no input after selection; eight
retained preview/input mutations reject. Final Do-it confirmation, legal policy
candidate and healing remain UNKNOWN.

The inspected preview displays the Cure description and ally HP100/241, but
its right-side label reads "Blizzard" despite canonical/mirror identity joining
Montblanc. Retain that UI-label discrepancy; do not use the rendered label to
certify target identity or dismiss the independent wrapper join. The retagged
A4 fixture's preview-name interpretation needs investigation before broader
product claims.

Overlay experiment `a62-ally-overlay-01` reaches engine-enabled Cure through
the unchanged self-only reader, then performs one guarded RIGHT and stops.
Seven navigation/cursor keys produce35 raw writes; no target acceptance A or
cast follows. The cursor moves(4,10)->(5,10), and the live table contains
Marche wrapper0202267C/canonical02000080 and Montblanc wrapper0202270C/
canonical02000188 with HP442/100. Both processor captures are identical:
ability1, state10, flags0, index0, count2, selected copies+0x0C/+0x10 both0.
Inspected the final screen: Montblanc HP100/241 under the Cure range cursor.
The retained raw joins pass eight altered metadata/input controls. This proves
an overlay observation, not an accepted ally target: cursor and selected index
are distinct. Next capture must establish how target acceptance populates the
selected wrapper and menu peer before any final cast is authorized.

Scratch construction `a62-party-fixture-01` now passes: four ledgered RAM
writes set Marche's secondary job7 and Montblanc's living HP100 in both copies.
Owned export and a fresh read-only reload agree on HP100/241, caster MP85 and
secondary White Mage. The reloaded baseline rejects37 mutants and records zero
gameplay/fixture writes. The builder records zero gameplay keys. Construction
does not establish learned/available Cure or another ally's legal target.

Use the independently reloaded `a62-party-fixture-01/party-recovery.ss0`, with
secondary White Mage on the verified caster and a living ally below50 percent.
Keep the original fixture untouched. Reuse guarded command/ability navigation only
while the self-only reader accepts it. Capture the target processor, wrapper
table/index/count and cursor before and after selecting the other ally.
Join that wrapper to the pinned canonical Montblanc and tile, then inspect the
engine's accepted confirmation. Do not press final A until the new target
contract is proven and revalidated. Preserve the existing public self-only
peer rejection. Healing, MP consumption, guarded Wait, independent later
actors, STOP and policy comparison remain separate, unpassed gates.
