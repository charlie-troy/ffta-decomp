## FFTA decompilation
##
## Run from WSL. The Windows side has no make; the toolchain is Linux-native.
##
##   make setup                       build agbcc + binutils into $HOME
##   make rom                         full ROM rebuild, verifies SHA1
##   make verify                      check a ROM's sha1 without building
##   make funcs                       list leaf-function match candidates
##   make match SRC=src/foo.c AT=0x5bb0 LEN=18
##   make progress                    how much of the ROM is C
##
## ROM is supplied by the user and never committed. Point ROM= at your dump.

ROM ?= /mnt/d/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba
PY  ?= python3

BUILD := build

.PHONY: all rom setup verify funcs match progress clean

all: rom

setup:
	bash tools/setup_toolchain.sh

rom:
	bash tools/build_rom.sh "$(ROM)"

verify:
	$(PY) tools/verify_rom.py "$(ROM)"

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
