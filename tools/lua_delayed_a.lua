-- Delayed confirm: hold A via setKeys for HOLD frames after GO_DELAY frames.
-- Fires the turn-end while the GDB breakpoint experiment is already armed.
local HOLD = HOLD or 16
local GO_DELAY = GO_DELAY or 600

if A_CB then callbacks:remove(A_CB); A_CB = nil end
local t0 = nil
local held = false

A_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not t0 then
        if f < GO_DELAY then return end
        t0 = f
        console:log("delayed-A: GO at " .. f)
    end
    local step = f - t0
    if step < HOLD then
        emu:setKeys(0x01)
        held = true
    elseif held then
        emu:setKeys(0)
        held = false
        callbacks:remove(A_CB); A_CB = nil
        console:log("delayed-A: sent, released")
    end
end)
console:log("delayed-A armed, GO_DELAY=" .. GO_DELAY)
