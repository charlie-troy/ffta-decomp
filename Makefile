## FFTA decompilation - working Makefile
##
## Run from WSL. The Windows side has no make; the toolchain is Linux-native.
##
##   make setup                       build agbcc + binutils into $HOME
##   make verify                      check ROM sha1 and stage baserom.gba
##   make funcs                       list leaf-function match candidates
##   make match SRC=src/foo.c AT=0x5bb0 LEN=18
##
## ROM is supplied by the user and never committed. Point ROM= at your dump.

ROM ?= /mnt/d/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba
PY  ?= python3

TC      := $(HOME)/ffta-toolchain
BUILD   := build

.PHONY: setup verify funcs match clean

setup:
	bash tools/setup_toolchain.sh

verify:
	$(PY) tools/verify_rom.py "$(ROM)"

funcs:
	cd tools && $(PY) find_leaf_funcs.py "$(ROM)" --max-bytes 48 --count 20 --min-callers 4

match:
	@test -n "$(SRC)" || { echo "usage: make match SRC=src/foo.c AT=0x5bb0 LEN=18"; exit 2; }
	bash tools/match.sh "$(SRC)" "$(BUILD)"
	$(PY) tools/verify_match.py "$(ROM)" "$(BUILD)/$(basename $(notdir $(SRC))).bin" "$(AT)" "$(LEN)"

clean:
	rm -rf $(BUILD)
