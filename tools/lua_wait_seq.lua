-- Timed end-turn sequence, entirely via key-shadow injection.
-- Waits GO_DELAY frames, then: DOWN, DOWN, A, (gap) A -> turn ends.
-- Frame-plan driven: the callback applies one planned mask per frame.
local BASE = 0x03000000
local GO_DELAY = GO_DELAY or 300

local plan = {}
local function add(start_f, mask, dur)
    for i = 0, dur - 1 do plan[start_f + i] = mask end
end
add(0,               0x80, 4)   -- DOWN: Move -> Action
add(24,              0x80, 4)   -- DOWN: Action -> Wait
add(48,              0x01, 4)   -- A: select Wait (facing compass)
add(78,              0x01, 4)   -- A: confirm facing -> turn ends

if SEQ_CB then callbacks:remove(SEQ_CB); SEQ_CB = nil end
local t0 = nil

SEQ_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not t0 then
        if f < GO_DELAY then return end
        t0 = f
        console:log("seq: GO at frame " .. f)
    end
    local step = f - t0
    local mask = plan[step]
    if mask then
        emu:write8(BASE + 5, 1)  -- key-system enable (0 = update_keys exits)
        local pressed = emu:read16(BASE + 2)
        local unconsumed = emu:read16(BASE + 4)
        emu:write16(BASE + 2, (pressed | mask) & 0xFFFF)
        emu:write16(BASE + 4, (unconsumed | mask) & 0xFFFF)
    end
    if step > 120 then
        callbacks:remove(SEQ_CB); SEQ_CB = nil
        console:log("seq: complete")
    end
end)
console:log("seq armed, GO_DELAY=" .. GO_DELAY)
