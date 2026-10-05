-- A8 atomic sample (v3, 2026-09-22).
--
-- The per-frame callback design (lua_a8_frames.lua) is dead: callbacks
-- proved NONDETERMINISTIC across boots (n=0 for 30+ s after a clean
-- registration, unrecoverable by re-arming; see docs/dead-ends.md).
-- Replacement: ATOMIC CONSOLE SAMPLES. One console evaluation reads the
-- emulated frame counter and Marche's CT in the same Lua evaluation, so
-- each sample is a self-locating point on the GDB trajectory:
--   A8S <frame> <ct> <wall_epoch_s>
-- Console traffic pauses the emulator for a few seconds (the console
-- pause law), so samples are taken only OUTSIDE measured windows: the
-- wall duration of the window comes from the GDB trajectory, and the
-- frame span from the two samples (park start CT=296 -> full CT>=998).
local f = emu:currentFrame()
local ct = emu:read16(0x020160E8)
console:log(string.format("A8S %d %d %d", f, ct or -1, os.time()))
