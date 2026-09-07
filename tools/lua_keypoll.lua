-- Force FFTA input by RAM-patching the key-poll at 0x0800048A (the only input
-- channel that works on this mGBA build; emu:setKeys is unreliable here).
-- Retail bytes: adds r1,r2,#0 ; eors r1,r3  => 11 1c 59 40
-- Patch:          movs r1,#mask ; nop        => (0x2100|mask) LE, c0 46
--
-- Usage (from the Scripting console):
--   KEYPOLL_MASK=0x08; KEYPOLL_FRAMES=45; dofile(".../lua_keypoll.lua")
-- The driver holds the key for KEYPOLL_FRAMES from the next frame, then
-- restores the retail bytes.

local POLL = 0x0800048A
local RET = { 0x1c, 0x11, 0x59, 0x40 }  -- retail 11 1c 59 40

KEYPOLL_MASK = KEYPOLL_MASK or 0x08      -- START default
KEYPOLL_FRAMES = KEYPOLL_FRAMES or 45

local start_frame = emu:currentFrame()

if KEYPOLL_CB then
    callbacks:remove(KEYPOLL_CB)
    KEYPOLL_CB = nil
end

-- apply patch
local pv = (0x2100 | KEYPOLL_MASK) & 0xFFFF
emu:write16(POLL, pv)       -- movs r1,#mask
emu:write16(POLL + 2, 0x46C0)  -- nop
console:log(string.format("poll patched mask=%02x", KEYPOLL_MASK))

KEYPOLL_CB = callbacks:add("frame", function()
    local f = emu:currentFrame() - start_frame
    if f >= KEYPOLL_FRAMES then
        -- restore retail
        emu:write8(POLL, RET[1])
        emu:write8(POLL + 1, RET[2])
        emu:write8(POLL + 2, RET[3])
        emu:write8(POLL + 3, RET[4])
        callbacks:remove(KEYPOLL_CB)
        KEYPOLL_CB = nil
        console:log("poll restored")
    end
end)
console:log("keypoll driver armed")
