# Working on this repo

Reverse engineering Final Fantasy Tactics Advance (GBA, USA). Read
[README.md](README.md) first for what the project is; this file is about how to
work on it without repeating mistakes already made.

Then read [docs/project-log.md](docs/project-log.md). It is the operational
source of truth for the active work package, backlog order, risks, decisions,
and dated evidence. Update it in the same change as any material discovery or
priority change; do not leave project state only in chat.

## The goal shapes what is worth doing

The point is **making the game moddable, especially the battle AI**, not
reaching a complete matching decompilation. A full decomp was tracking under 1%
and would take years. The AI's tuning turned out to be table data, so the
highest-value work widens the no-compiler modding surface rather than raising
the matched-function count.

Prefer: a new table mapped and made editable, a claim moved from inferred to
verified, a tool that makes an existing lever usable. Over: matching more
functions.

## You need a ROM, and it is never committed

Supply your own USA dump. Everything reads it at a path you pass in; the tools
default to `D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba`.

SHA1 `4ac05441f4de70a4ec3dd932116346c61b8783d9`. `.gitignore` excludes `*.gba`,
`*.bin`, `*.gbc` and `baserom*`. **Keep it that way.** No ROM bytes belong in
this repository; `data/functions.json` stores SHA-256 hashes rather than bytes
for exactly this reason.

The full ROM rebuild needs WSL and agbcc (`bash tools/setup_toolchain.sh`). The
Python analysis and all the modding tools run on Windows without it.

## The method that works

**Decode statically to form a hypothesis, then run the ROM's own code to check
it.** `tools/emulate.py` maps the ROM into a Unicorn ARM7TDMI and calls
functions with chosen arguments, in milliseconds, with no game state needed.

This is not a nicety. Running the job table's accessor over every entry cut its
"45 solved offsets" to 16 that are actually plain loads. A static decoder is
not wrong about the instructions it reads; it is wrong about what they mean,
and only execution catches that.

`tools/validate_ai.py` is the regression suite — 10 checks, all passing. Add a
check when you establish something new, so it cannot silently rot.

## Traps that have already cost time

- **Resolving a value as an id proves nothing by itself.** Reading mission
  fields as job ids gave hit rates like 368/368, because every byte below 116
  resolves to some job name. A coverage test only discriminates when the
  field's range can *exceed* the candidate space.
- **One data point enshrines a wrong answer.** `+0x34` looked exactly like
  AP/10 until a second mission with known rewards refuted it. Always find a
  second case.
- **Published documentation is wrong in specific, checkable ways.** Data
  Crystal has been wrong three times here: job resistances are eight packed
  3-bit slots not four bytes, the item table base is one entry earlier than
  documented, and there are 162 maps not 163. Look it up, then verify it.
- **A self-check written against the same assumptions as the tool confirms the
  assumptions, not the result.** The former instruction-pattern version of
  `tools/dump_unit_fields.py` passed its own cross-check while being
  substantially wrong; it has been replaced by the 5,568-read formula gate.
- **Name ids do not all point at the same string table.** Abilities index the
  UI table, items and jobs the main one. The wrong table yields plausible but
  incorrect text rather than an error.
- **Heredocs corrupt Python.** Writing files through `bash <<'EOF'` mangles
  backslash escapes. Write to a file, then run it.

## Finding a new table

Two scans cover how code reaches table data, and between them they are
exhaustive:

```bash
python tools/find_accessors.py       # tables reached through a property accessor
python tools/job_getters.py          # tables reached by direct indexing
python tools/accessor_callers.py --target 0xADDR --reg r1
python tools/map_table.py --base ... --stride ... --accessor ... --props ... --count ...
```

Thumb cannot materialise a 32-bit address inline, so **any** reader must load a
table's base from a literal pool. Enumerating the pool words whose value falls
inside a table bounds the entire search — that is how four job fields were
shown to be dead data rather than merely unexplained.

## Where things stand

Mapped and editable with no compiler: abilities, jobs, items, map terrain,
arrangement and clipping tilemaps,
missions. All 2,757 primary-table strings decode, so every CSV carries real
names.

Genuinely open, with the reason:

- **Whole-battle behaviour is closed for the traced snowball turn.** The
  frozen-RNG replay enters `sub_080C32C0` once per four distinct targets and
  reproduces exactly; see `docs/whole-battle-trace.md`. Do not generalize that
  one turn to every mission-, law-, or effect-specific path.
- **The target-candidate score model is not decoded.** `sub_080C2940` builds
  and sorts 20-byte candidate records before the evaluator runs; the sort's
  tie-break roll is a verified profile control (`deterministic_ties`), but the
  score fields themselves and their producers remain STRAT9.2 work. The
  function has two comparator regimes selected by its second argument
  (`mode=1` score path vs `mode=0` list path); the control only patches the
  `mode=1` tie roll — the `mode=0` roll at `0x080C2E9E` stays retail.
- **Mission fields.** The corrected constant-caller report is exhausted;
  rewards, progression, dispatch rules, fees, type, deadlines, clear
  conditions, clan-skill requirements, cancellation, and hidden reward previews
  are named. Seven variable-id calls remain, but do not block map work.
- **Map phase.** Complete: terrain, arrangement, clipping, custom-LZSS
  graphics, animations, render modes, redirects, and exports are covered. The
  graphics wrapper is not Huffman; do not reopen that old assumption.
- **Formations do not exist** — battle setups are scripted, one Place Character
  opcode per unit. Do not go looking for a formation table.

## Before you commit

Refuted approaches live in `docs/dead-ends.md`; check it before re-deriving a
hypothesis, and add to it when one is refuted.

```bash
python tools/validate_ai.py "<rom>"      # must stay 10/10
python tools/validate_missions.py "<rom>" # must stay 13/13 when missions change
python tools/validate_maps.py "<rom>"     # must stay 17/17 when maps change
python tools/validate_all.py "<rom>"      # complete local release gate
```

Every table tool must round-trip: dumping and re-applying an unedited CSV has
to reproduce the ROM byte for byte. Check it after touching one.
