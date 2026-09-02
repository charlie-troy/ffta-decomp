## FFTA decompilation
##
## Run from WSL. The Windows side has no make; the toolchain is Linux-native.
##
##   make setup                       build agbcc + binutils into $HOME
##   make rom                         full ROM rebuild, verifies SHA1
##   make verify                      check a ROM's sha1 without building
##   make verify-mod MOD=out.gba      what a mod changes about the AI
##   make funcs                       list leaf-function match candidates
##   make match SRC=src/foo.c AT=0x5bb0 LEN=18
##   make progress                    how much of the ROM is C
##
## ROM is supplied by the user and never committed. Point ROM= at your dump.

ROM ?= /mnt/d/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba
PY  ?= python3

BUILD := build

.PHONY: all rom mod mod-ai-always-pass check index setup verify verify-mod validate-text funcs match progress clean

all: rom

setup:
	bash tools/setup_toolchain.sh

rom:
	bash tools/build_rom.sh "$(ROM)"

## Build with deliberate changes. Does not require a SHA1 match; reports which
## functions differ from the base ROM so unintended changes stand out.
mod:
	MOD_BUILD=1 bash tools/build_rom.sh "$(ROM)"

## Source-driven proof mod: make every AI status-effect eligibility roll pass.
## The two 0..100 thresholds become 100, preserving the evaluator's layout.
mod-ai-always-pass:
	FFTA_CPPFLAGS="-DFFTA_AI_SELF_STATUS_THRESHOLD=100 -DFFTA_AI_OTHER_STATUS_THRESHOLD=101" \
	MOD_BUILD=1 bash tools/build_rom.sh "$(ROM)"

## What CI runs: compile everything and check each function's bytes against
## data/functions.json. Needs no ROM.
check:
	bash tools/compile_src.sh build/obj
	$(PY) tools/verify_functions.py data/functions.json build/obj

## Refresh data/functions.json after adding a function to src/. Needs the ROM.
index:
	$(PY) tools/gen_function_index.py "$(ROM)" build/leaf_candidates.json

verify:
	$(PY) tools/verify_rom.py "$(ROM)"

validate-text:
	$(PY) tools/validate_text.py "$(ROM)"

## Show what a modded ROM changes about the AI's decisions, measured by
## running both ROMs' own code. MOD= is the ROM you built.
verify-mod:
	@test -n "$(MOD)" || { echo "usage: make verify-mod MOD=build/ffta-mod.gba"; exit 2; }
	$(PY) tools/verify_mod.py "$(ROM)" "$(MOD)"

funcs:
	cd tools && $(PY) find_leaf_funcs.py "$(ROM)" --max-bytes 48 --count 20 --min-callers 4

match:
	@test -n "$(SRC)" || { echo "usage: make match SRC=src/foo.c AT=0x5bb0 LEN=18"; exit 2; }
	bash tools/match.sh "$(SRC)" "$(BUILD)"
	$(PY) tools/verify_match.py "$(ROM)" "$(BUILD)/$(basename $(notdir $(SRC))).bin" "$(AT)" "$(LEN)"

progress:
	$(PY) tools/progress.py build/leaf_candidates.json

clean:
	rm -rf $(BUILD)/obj $(BUILD)/ffta.elf $(BUILD)/ffta.gba
