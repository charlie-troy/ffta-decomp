#!/bin/bash
# Install the agbcc permuter fork and its own venv.
#
# The fork imports pycparser.plyparser, which pycparser 3.x removed, so it
# needs pycparser 2.x. Upstream decomp-permuter works fine on 3.x, so the two
# get separate environments rather than one shared, pinned one.
set -u

TC="$HOME/ffta-toolchain"
REPO_DIR="$TC/decomp-permuter-agbcc"
V="$TC/permuter-agbcc-venv"

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 https://github.com/WhenGryphonsFly/decomp-permuter-agbcc.git \
    "$REPO_DIR" 2>&1 | tail -2
fi

[ -x "$V/bin/python3" ] || python3 -m venv "$V" || exit 1
"$V/bin/python3" -m pip install --quiet --upgrade pip 2>&1 | tail -1
"$V/bin/python3" -m pip install --quiet 'setuptools<81' toml 'pycparser<3' 2>&1 | tail -3

echo "=== versions ==="
"$V/bin/python3" -c 'import pycparser, toml; print("pycparser", pycparser.__version__)'
"$V/bin/python3" -c 'from pycparser.plyparser import ParseError; print("plyparser ok")'
echo "venv: $V"
