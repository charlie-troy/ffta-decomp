#!/bin/bash
# Disassemble the base ROM with luvdis and emit its discovered function list.
#
#   tools/run_luvdis.sh [rom] [stop_addr]
#
# luvdis produces buildable, matching disassembly and does function discovery
# with the same call-count heuristic this project arrived at independently, so
# its output doubles as a cross-check on tools/find_leaf_funcs.py.
set -u

V="$HOME/ffta-toolchain/luvdis-venv/bin/python3"
cd "$(dirname "$0")/.." || exit 1

ROM="${1:-baserom.gba}"
STOP="${2:-0x8360000}"
OUT=build/luvdis
mkdir -p "$OUT"

[ -f "$ROM" ] || { echo "no ROM at $ROM"; exit 1; }

echo "=== luvdis info ==="
"$V" -m luvdis info "$ROM" 2>/dev/null

echo "=== luvdis disasm (stop $STOP) ==="
"$V" -m luvdis disasm "$ROM" \
  -o "$OUT/rom.s" \
  -co "$OUT/functions.cfg" \
  --stop "$STOP" 2>&1 | grep -v pkg_resources | tail -20

echo "=== output ==="
ls -la "$OUT"
echo "functions guessed: $(grep -c '^' "$OUT/functions.cfg" 2>/dev/null || echo 0)"
