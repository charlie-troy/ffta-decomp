#!/usr/bin/env bash
# asmlift pilot setup: build asmlift in WSL and emit pilot inputs for the two
# parked functions. See README.md in this directory for the plan.
#
#   bash tools/asmlift-pilot/setup.sh [path/to/baserom.gba]
#
# Nothing here touches src/ or the build; outputs land in tools/asmlift-pilot/.
set -euo pipefail

TC="${FFTA_TOOLCHAIN:-$HOME/ffta-toolchain}"
OUT="$(cd "$(dirname "$0")" && pwd)"
ROM="${1:-/mnt/c/Users/charl/Projects/ffta-decomp/baserom.gba}"
TARGET_SHA1=4ac05441f4de70a4ec3dd932116346c61b8783d9

command -v cargo >/dev/null || {
  echo "cargo not found. Install Rust first:"
  echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
  echo "  source \$HOME/.cargo/env"
  exit 1
}

if [ ! -f "$ROM" ]; then
  echo "baserom not found at: $ROM"
  exit 1
fi
have="$(sha1sum "$ROM" | cut -d' ' -f1)"
[ "$have" = "$TARGET_SHA1" ] || { echo "unexpected ROM revision: $have"; exit 1; }

# 1. build asmlift (the Klonoa project's programmatic matching decompiler)
if [ ! -x "$TC/asmlift/target/release/asmlift" ]; then
  mkdir -p "$TC"
  cd "$TC"
  [ -d asmlift ] || git clone https://github.com/Macabeus/asmlift.git
  cd asmlift
  cargo build --release
fi
ASM="$TC/asmlift/target/release/asmlift"
echo "asmlift binary: $ASM"

# 2. emit pilot inputs from the same evidence the permuters used
python3 - "$ROM" "$OUT" <<'PY'
import json, struct, sys

rom_path, out = sys.argv[1], sys.argv[2]
rom = open(rom_path, 'rb').read()
index = json.load(open('data/functions.json'))['functions']
by_name = {f['name']: f for f in index}

for name, off in (('sub_080DD580', 0xDD580), ('sub_080BDC20', 0xBDC20)):
    f = by_name[name]
    size = f['size']
    rom_off = f['offset']
    with open(f'{out}/{name}.bin', 'wb') as fh:
        fh.write(rom[rom_off:rom_off + size])
    with open(f'{out}/{name}.meta.json', 'w') as fh:
        json.dump({'name': name, 'rom_address': f'0x{0x08000000 + rom_off:08X}',
                   'size': size, 'offset_in_rom': rom_off}, fh, indent=2)
    print(f'{name}: {size} bytes at 0x{0x08000000 + rom_off:08X}')
PY

# 3. run asmlift on each pilot (adjust flags to the version's CLI)
for name in sub_080DD580 sub_080BDC20; do
  echo "=== asmlift: $name ==="
  if "$ASM" --help 2>&1 | head -20; then
    echo "NOTE: wire the exact asmlift invocation for this version here;"
    echo "      the goal is a candidate .c that the standard pipeline compiles."
  fi
done

echo
echo "Done. Next: compare candidates against the parked baselines"
echo "(permuter/ in the repo root has the historical best efforts)."
