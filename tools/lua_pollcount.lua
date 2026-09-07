-- Count how often FFTA's key-poll code at 0x08000460..0x080004B0 executes.
-- mGBA "execute" callbacks fire on instruction fetch; filter by address.
-- Result goes to outputs/lua-nav/pollcount.txt so it can be read reliably.

local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/pollcount.txt"
local POLL_LO = 0x08000460
local POLL_HI = 0x080004B0
POLL_FRAMES = POLL_FRAMES or 120

local hits = 0
local start_frame = emu:currentFrame()

if POLL_CB then callbacks:remove(POLL_CB) end
if POLL_FRAME_CB then callbacks:remove(POLL_FRAME_CB) end

local function frame_cb()
    local f = emu:currentFrame() - start_frame
    if f >= POLL_FRAMES then
        callbacks:remove(POLL_CB)
        callbacks:remove(POLL_FRAME_CB)
        local fh = io.open(OUT, "w")
        fh:write(string.format("hits=%d frames=%d per_s=%.1f\n", hits, POLL_FRAMES, hits / POLL_FRAMES * 60))
        fh:close()
    end
end

local function exec_cb(address)
    if address >= POLL_LO and address <= POLL_HI then
        hits = hits + 1
    end
end

POLL_CB = callbacks:add("execute", exec_cb)
POLL_FRAME_CB = callbacks:add("frame", frame_cb)
console:log("poll counter armed")
