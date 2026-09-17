param([int]$ProcId = 0, [string]$Out = "outputs/window.png")
# Capture an mGBA window (client area) to PNG without touching the GDB stub.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32c {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool IntersectRect(out RECT dst, ref RECT a, ref RECT b);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
'@
# Capture rules learned live:
# - CopyFromScreen grabs whatever is visibly on top at the client rect, so
#   the window must be foreground (and not minimized) or the capture gets
#   the occluding window's pixels (seen live: a white app panel instead of
#   the game). SetForegroundWindow from a background process CAN be blocked
#   by focus-steal prevention, so we first MINIMIZE every visible top-level
#   window that overlaps the mGBA client rect (mGBA excluded). Probe input is
#   injected via GDB breakpoints, never window messages, so minimizing other
#   windows cannot affect the probe. Verified live: preview panel occluding
#   mGBA produced 6 byte-identical captures in one run until this was added.
# - PrintWindow(+PW_RENDERFULLCONTENT) returns a blank surface for mGBA's
#   GL client (verified live: white/black frame), so it is not usable here.
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DpiFix { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DpiFix]::SetProcessDPIAware() | Out-Null
$root = [System.Windows.Automation.AutomationElement]::RootElement
$hwnd = [IntPtr]::Zero
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($w in $wins) {
  if ($ProcId -eq 0 -or $w.Current.ProcessId -eq $ProcId) {
    if ($w.Current.ClassName -eq 'QGBA::Window') { $hwnd = [IntPtr]$w.Current.NativeWindowHandle }
  }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "no mGBA window"; exit 1 }
if ([Win32c]::IsIconic($hwnd)) { [Win32c]::ShowWindow($hwnd, 9) | Out-Null; Start-Sleep -Milliseconds 600 }
# Compute the mGBA client rect in screen coordinates.
$mr = New-Object Win32c+RECT
[Win32c]::GetClientRect($hwnd, [ref]$mr) | Out-Null
$mp = New-Object Win32c+POINT
$mp.X = 0; $mp.Y = 0
[Win32c]::ClientToScreen($hwnd, [ref]$mp)
$mb = New-Object Win32c+RECT
$mb.L = $mp.X; $mb.T = $mp.Y; $mb.R = $mp.X + ($mr.R - $mr.L); $mb.B = $mp.Y + ($mr.B - $mr.T)
# Minimize every visible top-level window that overlaps that rect (except mGBA
# and the shell taskbar) so CopyFromScreen cannot grab an occluder.
$minimized = 0
foreach ($w in $wins) {
  $wh = [IntPtr]$w.Current.NativeWindowHandle
  if ($wh -eq [IntPtr]::Zero -or $wh -eq $hwnd) { continue }
  if ($w.Current.ClassName -eq 'Shell_TrayWnd') { continue }
  if (-not [Win32c]::IsWindowVisible($wh)) { continue }
  if ([Win32c]::IsIconic($wh)) { continue }
  $wr = New-Object Win32c+RECT
  if (-not [Win32c]::GetWindowRect($wh, [ref]$wr)) { continue }
  if (($wr.R - $wr.L) -le 0 -or ($wr.B - $wr.T) -le 0) { continue }
  $ix = New-Object Win32c+RECT
  if ([Win32c]::IntersectRect([ref]$ix, [ref]$mb, [ref]$wr)) {
    [Win32c]::ShowWindow($wh, 6) | Out-Null
    $minimized++
  }
}
if ($minimized -gt 0) { Start-Sleep -Milliseconds 700 }
[Win32c]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 400
$r = New-Object Win32c+RECT
[Win32c]::GetClientRect($hwnd, [ref]$r) | Out-Null
$p = New-Object Win32c+POINT
$p.X = 0; $p.Y = 0
[Win32c]::ClientToScreen($hwnd, [ref]$p) | Out-Null
$w = $r.R - $r.L; $h = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($p.X, $p.Y, 0, 0, [System.Drawing.Size]::new($w, $h))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out ($w x $h)"
