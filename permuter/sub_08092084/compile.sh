#!/bin/bash
# Invoked by decomp-permuter as: ./compile.sh input.c -o output.o
set -e

TC="$HOME/ffta-toolchain"
IN="$1"
OUT="$3"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cpp -undef -nostdinc -P -o "$TMP/x.i" "$IN"
"$TC/agbcc/agbcc" -mthumb-interwork -Wimplicit -Wparentheses -O2 -o "$TMP/x.s" "$TMP/x.i"
"$TC/local/usr/bin/arm-none-eabi-as" -mcpu=arm7tdmi -mthumb-interwork -o "$OUT" "$TMP/x.s"
