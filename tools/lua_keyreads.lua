-- Count reads of KEYINPUT (0x04000130/131) over N frames, and whether any
-- read happens while a key is held. Result: outputs/lua-nav/keyreads.txt

local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/keyreads.txt"
KEYREAD_FRAMES = KEYREAD_FRAMES or 120

local hits = 0
local held_reads = 0
local start_frame = emu:currentFrame()
local hold_key = KEYREAD_HOLD or 0   -- 0 = no key held

if KR_CB then callbacks:remove(KR_CB) end
if KR_FCB then callbacks:remove(KR_FCB) end

local function read_cb(address)
    if address == 0x04000130 or address == 0x04000131 then
        hits = hits + 1
        if hold_key ~= 0 then held_reads = held_reads + 1 end
    end
end

local function frame_cb()
    if hold_key ~= 0 then emu:setKeys(hold_key) end
    local f = emu:currentFrame() - start_frame
    if f >= KEYREAD_FRAMES then
        callbacks:remove(KR_CB)
        callbacks:remove(KR_FCB)
        emu:setKeys(0)
        local fh = io.open(OUT, "w")
        fh:write(string.format("keyinput_reads=%d frames=%d per_s=%.1f held_reads=%d hold=%d\n",
            hits, KEYREAD_FRAMES, hits / KEYREAD_FRAMES * 60, held_reads, hold_key))
        fh:close()
    end
end

KR_CB = callbacks:add("read", read_cb)
KR_FCB = callbacks:add("frame", frame_cb)
console:log("keyread counter armed hold=" .. string.format("%d", hold_key))
