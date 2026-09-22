-- A8 frame-clock driver for the mGBA Scripting console (UIA bridge).
-- Loaded via dofile with A8TK set:
--   on  : reset the pair, install a per-frame callback that overwrites
--         A8.f (emu:currentFrame) / A8.w (host wall clock, os.time)
--   read: echo the current pair as "P <frame> <wall>"
-- Design law (learned live 2026-09-21): the console LOG truncates older
-- lines, so we never accumulate samples — only the latest pair matters,
-- and the Python side takes two dumps to form intervals. os.time has 1 s
-- granularity, so windows must be long (>=12 s) for useful rates.
if not A8 then
  A8 = { f = 0, w = 0 }
end

if A8TK == "on" then
  callbacks:clear()
  A8.f = emu:currentFrame()
  A8.w = os.time()
  callbacks:add("frame", function()
    A8.f = emu:currentFrame()
    A8.w = os.time()
  end)
  console:log("A8 armed")
elseif A8TK == "read" then
  console:log("P " .. A8.f .. " " .. A8.w)
end
