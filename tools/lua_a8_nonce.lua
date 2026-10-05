-- A8 atomic sample with nonce (v3 production + diagnostic).
--
-- The untagged version (lua_a8_sample.lua) is ambiguous under the bridge's
-- whole-log echo: when the newest A8S line is missing or evicted from the
-- echoed widget value, the parser re-finds an OLD line and a stale frame
-- reads as "no new frames". The nonce tags each evaluation, so a parsed
-- line proves THIS evaluation ran, and its frame proves the core advanced.
--   Cmd sent:  A8N=<n> dofile(".../lua_a8_nonce.lua")
--   Log line:  A8S <nonce> <frame> <ct> <wall_epoch_s>
local f = emu:currentFrame()
local ct = emu:read16(0x020160E8)
console:log(string.format("A8S %d %d %d %d", A8N or 0, f, ct or -1,
    os.time()))
