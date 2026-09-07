-- Dump GBA display state via the mGBA Lua console for local decoding.
-- Writes: DISPCNT + BG0-3CNT to a header line, then one binary file per
-- enabled text BG: 2-byte map entries (map_base, 32*32 max) followed by the
-- tile data actually referenced.
local outdir = "C:/Users/charl/Projects/ffta-decomp/outputs/vram"

local function r16(a)
    return emu:read16(a)
end

local disp = r16(0x04000000)
local hdr = io.open(outdir .. "/header.txt", "w")
hdr:write(string.format("disp=%04x\n", disp))
local mode = disp & 7
for i = 0, 3 do
    local cnt = r16(0x04000008 + i * 2)
    local en = (disp & (0x100 << i)) ~= 0
    hdr:write(string.format("bg%d cnt=%04x en=%d\n", i, cnt, en and 1 or 0))
    if en and mode <= 1 then
        local colors = (cnt >> 5) & 1
        local sb = (cnt >> 8) & 0x1F
        local cb = (cnt >> 2) & 3
        local size = (cnt >> 6) & 3
        local mw, mh
        if size == 0 then mw, mh = 32, 32
        elseif size == 1 then mw, mh = 64, 32
        elseif size == 2 then mw, mh = 32, 64
        else mw, mh = 64, 64 end
        local map_base = 0x06000000 + sb * 0x800
        local tile_base = 0x06000000 + cb * (colors == 1 and 0x8000 or 0x4000)
        local tb = colors == 1 and 64 or 32
        -- collect referenced tiles
        local used = {}
        local f = io.open(outdir .. string.format("/bg%d.map", i), "wb")
        local buf = {}
        for k = 0, mw * mh - 1 do
            local e = r16(map_base + k * 2)
            buf[#buf + 1] = string.char(e & 0xFF, (e >> 8) & 0xFF)
            local t = (e & 0x3FF)
            if colors == 1 then t = e & 0x1FF end
            if t ~= 0 then used[t] = true end
        end
        f:write(table.concat(buf))
        f:close()
        hdr:write(string.format("bg%d mode=%d colors=%d size=%d mw=%d mh=%d map_base=%08x tile_base=%08x tb=%d tiles=%d\n",
            i, mode, colors, size, mw, mh, map_base, tile_base, tb, #used))
        local tf = io.open(outdir .. string.format("/bg%d.tiles", i), "wb")
        local tbuf = {}
        for t = 0, 1023 do
            if used[t] then
                for j = 0, tb - 1 do
                    tbuf[#tbuf + 1] = string.char(emu:read8(tile_base + t * tb + j))
                end
            else
                for j = 0, tb - 1 do tbuf[#tbuf + 1] = string.char(0) end
            end
        end
        tf:write(table.concat(tbuf))
        tf:close()
    end
end
hdr:close()
console:log("vram dumped, mode=" .. mode)
