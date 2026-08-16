#!/bin/bash
# Run decomp-permuter against a scratch dir in this repo.
#
#   tools/run_permuter.sh permuter/sub_080CD92C [--seconds N] [extra args...]
#
# arm-none-eabi-objdump must be on PATH for the ARM32 scorer, and the permuter's
# python deps live in a venv since the distro is externally managed.
set -u

TC="$HOME/ffta-toolchain"
PERM="$TC/decomp-permuter"
PY="$TC/permuter-venv/bin/python3"
export PATH="$TC/local/usr/bin:$PATH"

DIR="${1:?usage: run_permuter.sh <scratchdir> [--seconds N] [args...]}"
shift

SECONDS_LIMIT=600
if [ "${1:-}" = "--seconds" ]; then
  SECONDS_LIMIT="$2"
  shift 2
fi

ABS="$(cd "$DIR" && pwd)"
chmod +x "$ABS/compile.sh"

command -v arm-none-eabi-objdump >/dev/null || { echo "objdump not on PATH"; exit 1; }

cd "$PERM" || exit 1
echo "permuting $ABS for up to ${SECONDS_LIMIT}s"

# A plain `timeout` does not reliably stop this: with -j the permuter spawns
# worker processes, and SIGTERM to the parent alone left the whole tree running
# for an hour. Run it in its own process group and kill the group, escalating
# to SIGKILL if it does not go quietly.
setsid "$PY" permuter.py "$ABS" --stop-on-zero -j 4 "$@" &
pid=$!
pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')

( sleep "$SECONDS_LIMIT"
  if kill -0 "$pid" 2>/dev/null; then
    echo "TIMED OUT after ${SECONDS_LIMIT}s with no match"
    kill -INT -"$pgid" 2>/dev/null
    sleep 10
    kill -KILL -"$pgid" 2>/dev/null
  fi ) &
watchdog=$!

wait "$pid"
rc=$?
kill "$watchdog" 2>/dev/null
exit $rc
