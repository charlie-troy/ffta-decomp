-- Load the A2 battle-start fixture. Globals: FIX_SS overrides the path.
local SS = FIX_SS or "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/a2-battle-start.ss0"
emu:loadStateFile(SS)
console:log("fixture loaded: " .. SS)
