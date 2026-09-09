-- A2 fixture rebuild: walk the engage route and re-capture the chain.
-- Globals: FIX_PID unused here; this file is driven via dofile from the
-- console, one command per stage. Console commands (UIA bridge):
--   FIX_STAGE=1; dofile(".../lua_fixture_rebuild.lua")   -- load worldmap + enter
--   FIX_STAGE=2; dofile(".../lua_fixture_rebuild.lua")   -- law notice + placement
--   FIX_STAGE=3; dofile(".../lua_fixture_rebuild.lua")   -- start + confirm + settle
-- Each stage screenshots; the final stage saves the savestate + a PNG.
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"
local STAGE = tonumber(FIX_STAGE or "1")

if FIX_CB then callbacks:remove(FIX_CB); FIX_CB = nil end

local pressQueue = nil  -- list of {mask, frames}
local after = nil       -- function() called at end
local tag = "fix"

local function runQueue(q, done)
    local i, phase, t0 = 1, "settle", nil
    FIX_CB = callbacks:add("frame", function()
        local f = emu:currentFrame()
        if not t0 then t0 = f end
        local d = f - t0
        if i > #q then
            if phase == "settle" and d >= 45 then
                callbacks:remove(FIX_CB); FIX_CB = nil
                if done then done() end
                console:log("STAGE-DONE")
            end
            return
        end
        if phase == "settle" and d >= 45 then
            phase = "press"; t0 = f; emu:setKeys(q[i][1])
        elseif phase == "press" and d >= (q[i][2] or 16) then
            emu:setKeys(0); i = i + 1; phase = "settle"; t0 = f
        end
    end)
end

if STAGE == 1 then
    emu:loadStateFile(OUT .. "/worldmap.ss0")
    console:log("loaded worldmap")
    local q = {{1, 14}}  -- A: enter the battle prompt
    runQueue(q, function()
        emu:screenshot(OUT .. "/fix-stage1.png")
        emu:saveStateFile(OUT .. "/fix-engage.ss0")
    end)
elseif STAGE == 2 then
    -- A dismiss law NOTICE; A,A pick up + place Marche
    local q = {{1, 14}, {1, 30}, {1, 30}}
    runQueue(q, function()
        emu:screenshot(OUT .. "/fix-stage2.png")
        emu:saveStateFile(OUT .. "/fix-placement.ss0")
    end)
elseif STAGE == 3 then
    -- START banner, A confirm, then wait ~42 s for the intro
    local q = {{8, 16}, {1, 20}}
    local phase2 = false
    FIX_CB = callbacks:add("frame", function()
        local f = emu:currentFrame()
        if not FIX_T0 then FIX_T0 = f end
        if not phase2 and f - FIX_T0 > 120 then
            phase2 = true
            emu:screenshot(OUT .. "/fix-stage3-mid.png")
        end
        if f - FIX_T0 > 42 * 60 then
            callbacks:remove(FIX_CB); FIX_CB = nil; FIX_T0 = nil
            emu:screenshot(OUT .. "/fix-stage3.png")
            emu:saveStateFile(OUT .. "/fix-battle-start.ss0")
            console:log("STAGE-DONE")
        end
    end)
    runQueue(q, nil)
end
