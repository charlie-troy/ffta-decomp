-- A2 fixture rebuild v2: from the VERIFIED bervenia.ss0, walk the engage
-- route with staged stops and screenshots. Console: FIX_RB=<n>; dofile(...).
--   FIX_RB=0 : load bervenia + status snapshot
--   FIX_RB=1 : A (engage prompt) + shot + save fix2-engage.ss0
--   FIX_RB=2 : A (enter) -> A (law notice) -> shot
--   FIX_RB=3 : A,A (pick+place Marche) -> shot + save fix2-placement.ss0
--   FIX_RB=4 : START, A (confirm) -> wait 42 s -> shot + save
--              fix2-battle-start.ss0 + status
-- Every stage reuses one frame-callback; FIX_RB_STAGE keeps progress.
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"
local STAGE = tonumber(FIX_RB or "0")

local SLOT0 = 0x020159E8
local SLOT6 = 0x02016018

local function snapshot(tag)
    console:log(string.format("%s name=%08x mid=%d ct0=%d ct6=%d e8=%02x",
        tag, emu:read32(SLOT0), emu:read8(SLOT6 + 0x104),
        emu:read16(SLOT0 + 0xD0), emu:read16(SLOT6 + 0xD0),
        emu:read8(SLOT0 + 0xE8)))
end

if FIX_CB then callbacks:remove(FIX_CB); FIX_CB = nil end

if STAGE == 0 then
    local ok = emu:loadStateFile(OUT .. "/bervenia.ss0")
    console:log("LOAD=" .. tostring(ok))
    snapshot("BERV")
    return
end

local steps = {
    [1] = {{1, 12}},                       -- A
    [2] = {{1, 12}, {1, 12}},              -- A, A
    [3] = {{1, 25}, {1, 25}},              -- A, A (pick+place)
    [4] = {{8, 14}, {1, 18}},              -- START, A(confirm) then intro wait
}

local q = steps[STAGE]
if not q then console:log("BAD-STAGE") return end
if STAGE == 1 then
    -- stage 1 continues from bervenia: reload to be deterministic
    local ok = emu:loadStateFile(OUT .. "/bervenia.ss0")
    console:log("LOAD=" .. tostring(ok))
end
snapshot("PRE" .. STAGE)

local i, phase, t0, mid = 1, "settle", nil, nil
FIX_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not t0 then t0 = f end
    local d = f - t0
    if STAGE == 4 and not mid and d > 45 * 60 then
        mid = true
        emu:screenshot(OUT .. "/fix2-stage4.png")
        emu:saveStateFile(OUT .. "/fix2-battle-start.ss0")
        snapshot("BATTLE")
        console:log("STAGE-DONE")
        callbacks:remove(FIX_CB); FIX_CB = nil
        return
    end
    if i > #q then
        -- settle tail then finish
        local tail = 90
        if STAGE == 4 then return end  -- stage 4 finishes via the timer above
        if d >= tail then
            emu:screenshot(OUT .. "/fix2-stage" .. STAGE .. ".png")
            if STAGE == 1 then emu:saveStateFile(OUT .. "/fix2-engage.ss0") end
            if STAGE == 3 then emu:saveStateFile(OUT .. "/fix2-placement.ss0") end
            console:log("STAGE-DONE")
            callbacks:remove(FIX_CB); FIX_CB = nil
        end
        return
    end
    if phase == "settle" and d >= 50 then
        phase = "press"; t0 = f; emu:setKeys(q[i][1])
    elseif phase == "press" and d >= q[i][2] then
        emu:setKeys(0); i = i + 1; phase = "settle"; t0 = f
    end
end)
console:log("RB-ARMED stage=" .. STAGE)
