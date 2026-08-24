-- Drive a blank US FFTA save from the title screen to a battle-positioned
-- snowball tutorial state. Load this once from mGBA's Scripting window.

local output = "C:/Users/charl/Projects/ffta-decomp/outputs/mgba-snowball"
local start = emu:currentFrame()
local captured = {}

local function held(frame, from, key, width)
    width = width or 4
    if frame >= from and frame < from + width then
        return 1 << key
    end
    return 0
end

local function periodic(frame, from, until_frame, period, key)
    if frame >= from and frame < until_frame and (frame - from) % period < 3 then
        return 1 << key
    end
    return 0
end

local function capture(frame)
    for at = 600, 9000, 600 do
        if frame >= at and not captured[at] then
            captured[at] = true
            local path = string.format("%s/frame-%04d.png", output, at)
            emu:screenshot(path)
            console:log("captured " .. path)
        end
    end
end

snowball_callback = callbacks:add("frame", function()
    local frame = emu:currentFrame() - start
    local keys = 0

    -- Reach the title menu and choose NEW GAME.
    keys = keys | held(frame, 30, C.GBA_KEY.START)
    keys = keys | held(frame, 150, C.GBA_KEY.START)
    keys = keys | held(frame, 270, C.GBA_KEY.A)

    -- Advance the opening scene until the name editor appears.
    keys = keys | periodic(frame, 420, 3550, 18, C.GBA_KEY.A)
    -- START opens the name confirmation. Its default is No, so select Yes.
    keys = keys | held(frame, 3600, C.GBA_KEY.START)
    keys = keys | held(frame, 3660, C.GBA_KEY.LEFT)
    keys = keys | held(frame, 3720, C.GBA_KEY.A)
    -- Advance the remaining dialogue and tutorial into battle control.
    keys = keys | periodic(frame, 3900, 9000, 18, C.GBA_KEY.A)

    emu:setKeys(keys)
    capture(frame)
    if frame >= 7800 and frame <= 9000 and frame % 300 == 0 then
        local path = string.format("%s/state-%04d.ss0", output, frame)
        emu:saveStateFile(path)
        console:log("saved " .. path)
    end
    if frame == 9010 then
        emu:setKeys(0)
        callbacks:remove(snowball_callback)
        console:log("snowball automation complete")
    end
end)
