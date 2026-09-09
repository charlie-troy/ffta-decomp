-- A2 fixture rebuild v3: one keypress per console command, screenshot after.
-- Console: PRESSK=<mask>; PRESSF=<frames>; dofile(".../lua_press_shot.lua")
-- Also wakes input after savestate loads (full-key mash, the documented fix)
-- and auto-increments the screenshot index.
--   WAKE=1; dofile(...)               -- just the mash + a shot
--   PRESSK=1; PRESSF=12; dofile(...)  -- press A, settle, shot
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"
local MASK = tonumber(PRESSK or "0")
local FRAMES = tonumber(PRESSF or "12")

if FIX_CB then callbacks:remove(FIX_CB); FIX_CB = nil end

local function shot(tag)
    emu:screenshot(string.format("%s/ps-%s.png", OUT, tag))
    console:log("SHOT " .. tag)
end

if WAKE or MASK == 0 then
    -- documented wake: every key down ~10 frames, then release
    local t0 = nil
    FIX_CB = callbacks:add("frame", function()
        local f = emu:currentFrame()
        if not t0 then
            t0 = f
            emu:setKeys(1023)
        elseif f - t0 >= 10 then
            emu:setKeys(0)
            callbacks:remove(FIX_CB); FIX_CB = nil
            shot("wake-" .. tostring(f % 100000))
            console:log("WAKE-DONE")
        end
    end)
    console:log("wake armed")
    return
end

local phase, t0, idx = "settle", nil, 0
FIX_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not t0 then t0 = f end
    local d = f - t0
    if phase == "settle" and d >= 40 then
        phase = "press"; t0 = f; emu:setKeys(MASK)
    elseif phase == "press" and d >= FRAMES then
        emu:setKeys(0); phase = "tail"; t0 = f
    elseif phase == "tail" and d >= 55 then
        callbacks:remove(FIX_CB); FIX_CB = nil
        idx = idx + 1
        shot("step-" .. tostring(f % 100000))
        console:log("PRESS-DONE mask=" .. MASK)
    end
end)
console:log("press armed mask=" .. MASK .. " frames=" .. FRAMES)
