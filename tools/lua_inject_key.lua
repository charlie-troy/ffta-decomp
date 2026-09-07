-- Inject key bits directly into the game's pressed-key shadow (0x03000002).
-- Globals: INJ_MASK (bitmask, active-high), INJ_FRAMES (default 20), INJ_TAG
local BASE = 0x03000000
local MASK = INJ_MASK or 0x80
local FRAMES = INJ_FRAMES or 20
local TAG = INJ_TAG or "inj"

local start = nil
local hits = 0
local f = 0

if INJ_CB then callbacks:remove(INJ_CB); INJ_CB = nil end

INJ_CB = callbacks:add("frame", function()
    local cur = emu:currentFrame()
    if not start then start = cur end
    f = cur - start
    local held = emu:read16(BASE)
    local pressed = emu:read16(BASE + 2)
    local unconsumed = emu:read16(BASE + 4)
    emu:write16(BASE + 2, (pressed | MASK) & 0xFFFF)
    emu:write16(BASE + 4, (unconsumed | MASK) & 0xFFFF)
    hits = hits + 1
    if f >= FRAMES then
        callbacks:remove(INJ_CB); INJ_CB = nil
        console:log(string.format("%s done: injected %08x for %d frames (held=%04x pressed=%04x)", TAG, MASK, hits, held, pressed))
    end
end)
console:log(string.format("%s armed mask=%04x frames=%d", TAG, MASK, FRAMES))
