-- Generic mGBA Lua key driver.
-- Usage: set DRIVE_KEYS (list of {key, from, dur} in frames, key = bitmask value
-- like C.GBA_KEY.A) and DRIVE_SHOTS (list of frame offsets), DRIVE_OUT (prefix),
-- then call drive_run(). Loaded through the Scripting console QLineEdit via
--   DRIVE_KEYS={}; ... ; dofile("C:/.../lua_drive.lua")
-- The driver advances frames itself: it polls emu:currentFrame in a fast
-- callback and applies keys for the scheduled durations, then screenshots at
-- the requested offsets and removes itself when the schedule ends.

local start_frame = emu:currentFrame()

-- default schedule: nothing
DRIVE_KEYS = DRIVE_KEYS or {}
DRIVE_SHOTS = DRIVE_SHOTS or {}
DRIVE_OUT = DRIVE_OUT or "C:/Users/charl/Projects/ffta-decomp/outputs"
DRIVE_TAG = DRIVE_TAG or "drive"
DRIVE_MAX = DRIVE_MAX or 600   -- safety cap in frames

local function snapshot(driver_frame)
    local path = string.format("%s/%s-%03d.png", DRIVE_OUT, DRIVE_TAG, driver_frame)
    emu:screenshot(path)
    console:log("shot " .. driver_frame .. " -> " .. path)
end

if DRIVE_CB then
    callbacks:remove(DRIVE_CB)
    DRIVE_CB = nil
end

DRIVE_CB = callbacks:add("frame", function()
    local f = emu:currentFrame() - start_frame
    local keys = 0
    for _, k in ipairs(DRIVE_KEYS) do
        if f >= k[2] and f < k[2] + (k[3] or 20) then
            keys = keys | (1 << k[1])
        end
    end
    emu:setKeys(keys)
    for _, s in ipairs(DRIVE_SHOTS) do
        if f == s then snapshot(s) end
    end
    if f >= DRIVE_MAX then
        emu:setKeys(0)
        callbacks:remove(DRIVE_CB)
        DRIVE_CB = nil
        console:log("drive complete at " .. f)
    end
end)
console:log("driver armed")
