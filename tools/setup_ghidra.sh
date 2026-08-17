#!/bin/bash
# Install a JDK and Ghidra into $HOME, no root required.
#
#   bash tools/setup_ghidra.sh
#
# Ghidra's decompiler produces C from ARM/Thumb assembly. It will never be
# byte-matching, but a structurally correct skeleton is a far better starting
# point for the compile-and-diff pipeline than reading disassembly by eye,
# which is what has limited this project to small leaf functions.
set -u

TC="$HOME/ffta-toolchain"
mkdir -p "$TC/dl"
cd "$TC/dl" || exit 1

# ---- JDK ----
if [ -x "$TC/jdk/bin/java" ]; then
  echo "JDK already present"
else
  echo "=== downloading Temurin JDK 21 (~180 MB) ==="
  curl -fL --retry 3 -o jdk.tar.gz \
    "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse" \
    || { echo "JDK download failed"; exit 1; }
  mkdir -p "$TC/jdk"
  tar -xzf jdk.tar.gz -C "$TC/jdk" --strip-components=1 || exit 1
fi
"$TC/jdk/bin/java" -version 2>&1 | head -2

# ---- Ghidra ----
if [ -d "$TC/ghidra" ] && [ -x "$TC/ghidra/support/analyzeHeadless" ]; then
  echo "Ghidra already present"
else
  echo "=== resolving latest Ghidra release ==="
  URL=$(curl -fsSL https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest \
        | grep -o 'https://[^"]*_PUBLIC_[0-9]*\.zip' | head -1)
  [ -n "$URL" ] || { echo "could not resolve Ghidra release URL"; exit 1; }
  echo "$URL"
  echo "=== downloading Ghidra (~400 MB) ==="
  curl -fL --retry 3 -o ghidra.zip "$URL" || { echo "Ghidra download failed"; exit 1; }
  python3 - <<'PY'
import zipfile, os, glob
home = os.path.expanduser("~")
dst = os.path.join(home, "ffta-toolchain")
with zipfile.ZipFile(os.path.join(dst, "dl", "ghidra.zip")) as z:
    z.extractall(dst)
d = glob.glob(os.path.join(dst, "ghidra_*_PUBLIC"))
if d:
    target = os.path.join(dst, "ghidra")
    if os.path.exists(target):
        os.remove(target) if os.path.islink(target) else None
    os.symlink(d[0], target)
    print("linked", d[0], "->", target)
PY
  # Python's zipfile.extractall does not preserve the executable bit, so the
  # launchers and the native decompiler binaries come out non-executable.
  G=$(readlink -f "$TC/ghidra")
  find "$G" -name '*.sh' -exec chmod +x {} + 2>/dev/null
  find "$G" -path '*/os/linux_x86_64/*' -type f -exec chmod +x {} + 2>/dev/null
  chmod +x "$G/support/analyzeHeadless" "$G/ghidraRun" 2>/dev/null
fi

echo "=== verifying headless analyzer ==="
JAVA_HOME="$TC/jdk" "$TC/ghidra/support/analyzeHeadless" 2>&1 | head -5
echo "GHIDRA SETUP DONE"
