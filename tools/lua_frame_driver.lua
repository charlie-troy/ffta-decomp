-- A2.3 takeover experiment, Lua-side: staged key driving + sampling.
-- Driven from the console with FIX_TK=<stage>; all state in globals so each
-- console command is independent.
--   FIX_TK=arm   : reload fixture, verify slots, apply takeover writes,
--                  then start the key program + sampling.
--   FIX_TK=ctrl  : same without the takeover writes (control run).
--   FIX_TK=status: print CTs + program state.
local STAGE = FIX_TK or "status"
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"

local SLOT0 = 0x020159E8
local SLOT6 = 0x02016018
local FLAG0D = 0x0200203D

local function snapshot(tag)
    console:log(string.format("%s name=%08x mid=%d ct0=%d ct6=%d e8=%02x e6=%02x ed=%02x flag=%d",
        tag,
        emu:read32(SLOT0), emu:read8(SLOT6 + 0x104),
        emu:read16(SLOT0 + 0xD0), emu:read16(SLOT6 + 0xD0),
        emu:read8(SLOT0 + 0xE8), emu:read8(SLOT0 + 0xE6),
        emu:read8(SLOT0 + 0xED), emu:read8(FLAG0D)))
end

if STAGE == "status" then
    snapshot("STATUS")
    return
end

if STAGE == "arm" or STAGE == "ctrl" then
    local ss = OUT .. "/a2-battle-start.ss0"
    local ok = emu:loadStateFile(ss)
    console:log("LOAD=" .. tostring(ok))
    if not ok then return end
    snapshot("LOADED")
    if STAGE == "arm" then
        local mid = emu:read8(SLOT6 + 0x104)
        emu:write8(SLOT0 + 0xE6, mid)
        emu:write8(SLOT0 + 0xED, emu:read8(SLOT0 + 0xED) | 8)
        emu:write16(SLOT0 + 0xD0, 1000)
        emu:write8(FLAG0D, 1)
        snapshot("WRITTEN")
    end
    -- key program: DOWN DOWN A A (arm), sampled, with screenshot at the end
    FIX_KEYS = {{128, 3, 40}, {128, 3, 40}, {1, 3, 50}, {1, 3, 50}}
    FIX_PROG_T0 = nil
    FIX_PROG_I = 1
    FIX_PROG_PHASE = "settle"
    FIX_SAMPLES = {}
    FIX_LAST_SAMPLE = nil
    if FIX_CB then callbacks:remove(FIX_CB); FIX_CB = nil end
    FIX_CB = callbacks:add("frame", function()
        local f = emu:currentFrame()
        if not FIX_PROG_T0 then FIX_PROG_T0 = f end
        local d = f - FIX_PROG_T0
        -- sample every ~3 s (180 frames)
        if not FIX_LAST_SAMPLE or f - FIX_LAST_SAMPLE >= 180 then
            FIX_LAST_SAMPLE = f
            snapshot("SAMP")
            FIX_SAMPLES[#FIX_SAMPLES + 1] = f
        end
        local step = FIX_KEYS[FIX_PROG_I]
        if not step then
            if d > 20 * 60 then
                emu:screenshot(OUT .. "/takeover-outcome.png")
                console:log("PROG-DONE")
                callbacks:remove(FIX_CB); FIX_CB = nil
            end
            return
        end
        if FIX_PROG_PHASE == "settle" and d >= step[3] then
            FIX_PROG_PHASE = "press"; FIX_PROG_T0 = f; emu:setKeys(step[1])
        elseif FIX_PROG_PHASE == "press" and d >= step[2] then
            emu:setKeys(0); FIX_PROG_I = FIX_PROG_I + 1
            FIX_PROG_PHASE = "settle"; FIX_PROG_T0 = f
        end
    end)
    console:log("PROGRAM-ARMED stage=" .. STAGE)
end
