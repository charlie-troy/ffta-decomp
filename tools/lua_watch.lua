-- Dense passive watch: screenshot every WATCH_EVERY frames for WATCH_N shots.
-- Globals: WATCH_TAG, WATCH_EVERY (frames, default 90), WATCH_N (default 30)
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav"

WATCH_TAG = WATCH_TAG or "watch"
WATCH_EVERY = WATCH_EVERY or 90
WATCH_N = WATCH_N or 30

if WATCH_CB then callbacks:remove(WATCH_CB); WATCH_CB = nil end

local n = 0
local t0 = nil

WATCH_CB = callbacks:add("frame", function()
    local f = emu:currentFrame()
    if not t0 then t0 = f end
    if f - t0 >= WATCH_EVERY then
        t0 = f
        n = n + 1
        local idx = string.format("%02d", n)
        emu:screenshot(string.format("%s/%s-%s.png", OUT, WATCH_TAG, idx))
        console:log(string.format("watch %s shot %d", WATCH_TAG, n))
        if n >= WATCH_N then
            callbacks:remove(WATCH_CB); WATCH_CB = nil
            console:log("watch complete")
        end
    end
end)
console:log(string.format("watch armed tag=%s every=%d n=%d", WATCH_TAG, WATCH_EVERY, WATCH_N))
