#!/usr/bin/env bash
# Launch Windows mGBA-qt with the GDB stub and the Zophar save, loading the
# title savestate so navigation starts at the known title screen.
ROM="C:\Users\charl\Projects\ffta-decomp\baserom.gba"
STATE="C:\Users\charl\Projects\ffta-decomp\outputs\lua-title.ss0"
SAV="C:\Users\charl\Projects\ffta-decomp\baserom.sav"
MGBA="/c/Users/charl/ffta-tools/mGBA-0.10.5-win64/mGBA.exe"
cd /c/Users/charl/Projects/ffta-decomp || exit 1
# copy battery save next to rom under its name
cp -f baserom.sav "baserom.sav" 2>/dev/null
"$MGBA" -g -t "$(cygpath -w "$STATE")" "$(cygpath -w "$ROM")" > outputs/mgba-steer/mgba-win2.log 2>&1 &
echo "launched pid $!"
