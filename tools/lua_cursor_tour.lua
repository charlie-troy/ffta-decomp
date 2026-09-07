-- A1 cursor tour: from the world-map savestate, press each direction in
-- sequence with a settle, screenshotting after each hop, then report.
-- TOUR_DIRS: list of {key, frames} steps; TOUR_TAG for output prefix.
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"
local SS  = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/worldmap.ss0"

TOUR_DIRS = TOUR_DIRS or {}
TOUR_TAG = TOUR_TAG or "tour"
TOUR_SS = TOUR_SS or SS

if TOUR_CB then callbacks:remove(TOUR_CB); TOUR_CB = nil end

if TOUR_SS ~= "" then emu:loadStateFile(TOUR_SS) end

local start = nil
local step = 1          -- 1-based index into TOUR_DIRS
local phase = "settle"  -- settle -> press -> shot
local t0 = nil

TOUR_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not start then start = f; t0 = f end
    local d = f - t0
    if phase == "settle" and d >= 45 then
        phase = "press"; t0 = f; emu:setKeys(TOUR_DIRS[step][1])
    elseif phase == "press" and d >= (TOUR_DIRS[step][2] or 16) then
        emu:setKeys(0); phase = "shot"; t0 = f
    elseif phase == "shot" and d >= 30 then
        local idx = string.format("%02d", step)
        emu:screenshot(string.format("%s/%s-%s.png", OUT, TOUR_TAG, idx))
        console:log(string.format("tour %s step %d key=%d done", TOUR_TAG, step, TOUR_DIRS[step][1]))
        step = step + 1
        if step > #TOUR_DIRS then
            callbacks:remove(TOUR_CB); TOUR_CB = nil
            console:log("tour complete")
        else
            phase = "settle"; t0 = f
        end
    end
end)
console:log("tour armed steps=" .. #TOUR_DIRS)
