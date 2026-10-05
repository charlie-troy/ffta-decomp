-- A8 Lua watch: read back the recorded window ("W sf sw ff fw").
-- The window may still be open (full == nil) — that is a legal outcome;
-- the caller reports it rather than waiting inside console traffic.
if A8C and A8C.start then
  local s, f2 = A8C.start, A8C.full
  if f2 then
    console:log(string.format("W %d %d %d %d", s.f, s.w, f2.f, f2.w))
  else
    console:log(string.format("WO %d %d %d", s.f, s.w, A8C.n))
  end
else
  console:log("W- none")
end
