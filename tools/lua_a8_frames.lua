-- A8 Lua watch: measure the CT recharge window entirely Lua-side.
--
-- Law (2026-09-21): ANY console interaction (focus steal for SetValue/
-- SendKeys) pauses the emulator for a few seconds, so no console traffic
-- may occur inside a measured window. This driver therefore does the
-- whole measurement from inside running frames: a per-frame callback
-- samples Marche's CT (ROSTER + 6*STRIDE + OFF_CT = 0x020160E8) and
-- snapshots (emu:currentFrame, os.time) at the first CT>=296 and
-- first CT>=998 sample. The console read afterwards only collects
-- the recorded pair; its own pause lands after the window closed.
--
-- Robustness (2026-09-22): callbacks proved NONDETERMINISTIC across
-- boots (n stayed 0 for 30+ s on one boot after arming cleanly), so the
-- body is pcall-wrapped, counts invocations FIRST, and records the first
-- Lua error into A8C.err (logged once) — a dead callback is now data,
-- not silence. A sampled trajectory (every 30 frames) survives late or
-- lost read-backs.
--
-- os.time has 1 s granularity -> windows < ~4 s are unusable; the full
-- recharge is ~12-13 s, comfortably above that.
A8C = A8C or {}
if A8C.cb then callbacks:remove(A8C.cb); A8C.cb = nil end
A8C.ct_base = 0x020160E8
A8C.start = nil
A8C.full = nil
A8C.n = 0
A8C.err = nil
A8C.traj = {}
A8C.cb = callbacks:add("frame", function()
  A8C.n = A8C.n + 1
  local ok, err = pcall(function()
    local f = emu:currentFrame()
    local ct = emu:read16(A8C.ct_base)
    if A8C.n % 30 == 0 and #A8C.traj < 3000 then
      A8C.traj[#A8C.traj + 1] = { f, ct }
    end
    if not A8C.start and ct ~= nil and ct >= 296 then
      A8C.start = { f = f, w = os.time(), ct = ct }
    end
    if A8C.start and not A8C.full and ct ~= nil and ct >= 998 then
      A8C.full = { f = f, w = os.time(), ct = ct }
      console:log(string.format("W %d %d %d %d",
        A8C.start.f, A8C.start.w, A8C.full.f, A8C.full.w))
      callbacks:remove(A8C.cb); A8C.cb = nil
    end
  end)
  if not ok and not A8C.err then
    A8C.err = tostring(err)
    console:log("A8C-ERR " .. A8C.err)
  end
end)
console:log("A8C armed")
