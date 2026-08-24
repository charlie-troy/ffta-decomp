-- From outputs/mgba-snowball/state-facing.ss0, freeze FFTA's RNG and confirm
-- Ritz's facing. This causes the next
-- AI actor to enter sub_080C32C0 once for each of its four candidate targets.

local output = "C:/Users/charl/Projects/ffta-decomp/outputs/mgba-snowball"
local start = emu:currentFrame()
local RNG = 0x030034B0
local FIXED_SEED = 0x12345678

local function held(frame, from, key)
    if frame >= from and frame < from + 4 then
        return 1 << key
    end
    return 0
end

ai_replay_callback = callbacks:add("frame", function()
    local frame = emu:currentFrame() - start
    local keys = 0
    if frame == 30 then
        emu:write32(RNG, FIXED_SEED)
        console:log(string.format("RNG frozen at 0x%08X", FIXED_SEED))
    end
    keys = keys | held(frame, 60, C.GBA_KEY.A)   -- confirm facing
    emu:setKeys(keys)
    if frame == 120 then
        emu:screenshot(output .. "/replay-triggered.png")
        emu:setKeys(0)
        callbacks:remove(ai_replay_callback)
    end
end)
