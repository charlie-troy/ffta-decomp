-- Test whether emu:setKeys reaches the emulated KEYINPUT register.
-- Holds key bit `keybit` (0..9) for KEY_HOLD frames starting next frame,
-- samples 0x04000130 each frame, writes the distinct samples to a file.
local OUT = "C:/Users/charl/Projects/ffta-decomp/outputs/lua-nav/keytest.txt"
local KEY = TESTKEY and (function() local n=0; local v=TESTKEY; while v>1 do v=v/2; n=n+1 end; return n end)() or 3  -- bit index from TESTKEY mask, default START
local HOLD = 45
local start_frame = emu:currentFrame()
local samples = {}
local seq = 0

if KT_CB then callbacks:remove(KT_CB) end

KT_CB = callbacks:add("frame", function()
    local f = emu:currentFrame() - start_frame
    if f < HOLD then
        emu:setKeys(1 << KEY)
    else
        emu:setKeys(0)
    end
    if f % 5 == 0 then
        seq = seq + 1
        samples[#samples + 1] = string.format("%d:%04x", f, emu:read16(0x04000130))
    end
    if f >= HOLD + 10 then
        callbacks:remove(KT_CB)
        local fh = io.open(OUT, "w")
        fh:write(table.concat(samples, " ") .. "\n")
        fh:close()
    end
end)
console:log("keytest armed")
