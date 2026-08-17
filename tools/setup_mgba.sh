#!/bin/bash
# Install mGBA into $HOME (no root) for dynamic analysis.
#
# The Ubuntu noble tarball matches the WSL distro, so no Qt/SDL version
# juggling. The SDL binary carries mGBA's CLI debugger, which is what makes
# tracing scriptable; the Qt binary is there if a GUI is wanted.
set -u

TC="$HOME/ffta-toolchain"
V=0.10.5
URL="https://github.com/mgba-emu/mgba/releases/download/$V/mGBA-$V-ubuntu64-noble.tar.xz"

mkdir -p "$TC/dl"
cd "$TC/dl" || exit 1

if [ ! -d "$TC/mgba" ]; then
  echo "=== downloading mGBA $V (ubuntu noble) ==="
  curl -fL --retry 3 -o mgba.tar.xz "$URL" || { echo "download failed"; exit 1; }
  mkdir -p "$TC/mgba"
  tar -xJf mgba.tar.xz -C "$TC/mgba" --strip-components=1 || exit 1
fi

# The tarball ships .deb packages rather than binaries. dpkg -x unpacks them
# into a prefix without needing root.
if [ ! -x "$TC/mgba/local/usr/bin/mgba" ]; then
  mkdir -p "$TC/mgba/local"
  for d in "$TC/mgba"/*.deb; do
    [ -f "$d" ] && dpkg -x "$d" "$TC/mgba/local"
  done
fi

# mGBA links against libzip and lua, which are not in the tarball. Pull them
# from apt without root the same way. Noble renamed libzip4 to libzip4t64 in
# the time_t transition, so try both names.
if [ ! -f "$TC/mgba/local/usr/lib/x86_64-linux-gnu/libzip.so.4" ]; then
  mkdir -p "$TC/mgba/deps"
  (cd "$TC/mgba/deps" && \
    apt-get download libzip4t64 2>/dev/null || apt-get download libzip4 2>/dev/null
   apt-get download liblua5.4-0 2>/dev/null) >/dev/null 2>&1
  for d in "$TC/mgba/deps"/*.deb; do
    [ -f "$d" ] && dpkg -x "$d" "$TC/mgba/local"
  done
fi

echo "=== binaries ==="
find "$TC/mgba/local" -type f -name 'mgba*' -perm -u+x 2>/dev/null | head

echo "=== version ==="
M="$TC/mgba/local/usr/bin/mgba"
MGBA_LIBS="$TC/mgba/local/usr/lib:$TC/mgba/local/usr/lib/x86_64-linux-gnu"
if [ -x "$M" ]; then
  LD_LIBRARY_PATH="$MGBA_LIBS:${LD_LIBRARY_PATH:-}" "$M" --version 2>&1 | head -3
  echo "--- unresolved deps (should be empty) ---"
  LD_LIBRARY_PATH="$MGBA_LIBS" ldd "$M" 2>/dev/null | grep -i 'not found'
else
  echo "mgba SDL binary not found"
fi
echo
echo "run with: LD_LIBRARY_PATH=$MGBA_LIBS $M"
