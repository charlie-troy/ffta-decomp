-- A8 debug read-back: report callback liveness (n), the CT the Lua side
-- currently sees, the recorded window pair, the first Lua error, and a
-- compact trajectory dump. Tokens:
--   WD <n> <cur_ct> <start_f> <start_w> <full_f | -1> <full_w | -1>
--   TJ <k> <f1>:<ct1> <f2>:<ct2> ...   (every 8th recorded pair)
--   A8C-ERR <msg>                       (first Lua error, if any)
if A8C and A8C.start then
  local s, f2 = A8C.start, A8C.full
  local cur = emu:read16(A8C.ct_base)
  console:log(string.format("WD %d %d %d %d %d %d",
    A8C.n or -1, cur or -1, s.f, s.w,
    f2 and f2.f or -1, f2 and f2.w or -1))
  local parts = {}
  for i = 1, #A8C.traj do
    if (i - 1) % 8 == 0 then
      parts[#parts + 1] = A8C.traj[i][1] .. ":" .. A8C.traj[i][2]
    end
  end
  console:log("TJ " .. #A8C.traj .. " " .. table.concat(parts, " "))
  if A8C.err then console:log("A8C-ERR " .. A8C.err) end
else
  console:log("W- none n=" .. tostring(A8C and A8C.n or -1)
    .. " err=" .. tostring(A8C and A8C.err or "nil"))
end
