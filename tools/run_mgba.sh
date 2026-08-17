#!/bin/bash
# Launch mGBA with its GDB stub open, ready for tools/trace_mgba.py.
#
#   tools/run_mgba.sh [rom] [savestate]
#
# The savestate is what makes this useful: tracing from a cold boot only ever
# shows the title screen. Load a state sitting in the situation you care about
# (an enemy or autobattle turn) and the profile is of that.
set -u

TC="$HOME/ffta-toolchain"
L="$TC/mgba/local"
export LD_LIBRARY_PATH="$L/usr/lib:$L/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

cd "$(dirname "$0")/.." || exit 1
ROM="${1:-baserom.gba}"
STATE="${2:-}"

[ -f "$ROM" ] || { echo "no ROM at $ROM"; exit 1; }

ARGS=(-g)
if [ -n "$STATE" ]; then
  [ -f "$STATE" ] || { echo "no savestate at $STATE"; exit 1; }
  ARGS+=(-t "$STATE")
fi

echo "starting mGBA with gdb stub on port 2345"
echo "  rom:   $ROM"
echo "  state: ${STATE:-<none, cold boot>}"
exec "$L/usr/bin/mgba" "${ARGS[@]}" "$ROM"
