-- A1 probe: reload the world-map savestate, wait, hold one key, screenshot.
-- Globals: PROBE_KEY (bitmask), PROBE_TAG (string), PROBE_HOLD (frames, default 20)
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"
local SS  = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/worldmap.ss0"

if PROBE_CB then callbacks:remove(PROBE_CB); PROBE_CB = nil end

emu:loadStateFile(SS)

local hold = PROBE_HOLD or 20
local start = nil
local n = 0

PROBE_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not start then start = f end
    local d = f - start
    -- settle 60 frames after load, then hold the key, screenshots before/during/after
    if d == 40 then emu:screenshot(OUT .. "/" .. PROBE_TAG .. "-pre.png") end
    if d >= 60 and d < 60 + hold then emu:setKeys(PROBE_KEY) end
    if d == 60 + hold then emu:setKeys(0) end
    if d == 90 then emu:screenshot(OUT .. "/" .. PROBE_TAG .. "-mid.png") end
    if d == 180 then emu:screenshot(OUT .. "/" .. PROBE_TAG .. "-post.png") end
    if d >= 180 then
        callbacks:remove(PROBE_CB); PROBE_CB = nil
        console:log("probe " .. PROBE_TAG .. " done")
    end
end)
console:log("probe " .. PROBE_TAG .. " armed key=" .. string.format("%d", PROBE_KEY))
